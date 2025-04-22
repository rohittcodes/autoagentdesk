# llm/agent.py
from typing import Dict, Any, List
import json
import google.generativeai as genai
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_groq import ChatGroq
from langchain_anthropic import ChatAnthropic
from langchain.prompts import PromptTemplate
from langchain.schema.runnable import RunnableSequence, RunnablePassthrough
from datetime import datetime
from groq import AuthenticationError
import asyncio
import time
import re
from collections import deque

class LogAnalysisAgent:
    def __init__(self, api_key: str, log_store, provider: str = "google", model: str = "gemini-1.5-pro"):
        self.log_store = log_store
        self.analysis_state = {}
        self.conversation_history = []
        self.provider = provider
        self.model_name = model
        
        # Initialize API keys dictionary with all available keys
        self.api_keys = {
            provider: api_key  # Store the initial API key for the current provider
        }
        
        # Initialize token usage tracking for rate limiting
        self.token_usage = deque(maxlen=20)  # Track the last 20 requests
        self.last_rate_limit_error = 0       # Timestamp of last rate limit error
        self.rate_limit_backoff = 1          # Initial backoff time (seconds)
        
        # Configure LLM based on provider
        self._configure_llm(provider, model, api_key)
        
        # Define the prompt template for log analysis with context
        self.analysis_prompt = PromptTemplate(
            input_variables=["query", "logs", "context", "previous_findings"],
            template="""
            You are an expert log analysis system specializing in identifying critical performance issues, especially regarding database services. Analyze these logs considering the following context:

            USER QUERY: {query}
            
            PREVIOUS FINDINGS: {previous_findings}
            
            SYSTEM CONTEXT: {context}
            
            LOGS:
            {logs}
            
            Analyze these logs and provide:
            1. Direct answer to the user's query - if there are database performance issues, highlight them clearly
            2. Key patterns or anomalies identified - pay special attention to memory usage, CPU spikes, and connection errors
            3. Correlation with previous findings
            4. Potential root causes for any issues - especially focus on database resource problems
            5. Recommended actions if applicable - provide specific steps to address database performance issues
            
            Important: ALWAYS prioritize critical errors related to database services, memory issues, and connectivity problems. These are the most important issues to highlight in your response even if they seem like isolated incidents.
            
            Include specific evidence from the logs to support your analysis.
            """
        )
        
        # Enhanced query translation prompt
        self.query_translation_prompt = PromptTemplate(
            input_variables=["query", "context"],
            template="""
            You are an expert in translating natural language queries for log analysis.
            
            CONTEXT: {context}
            USER QUERY: {query}
            
            Translate this query into a JSON object with:
            - semantic_query: Core search terms
            - time_range: Time specifications
            - filters: Log level, service name, etc.
            - correlations: Related metrics to analyze
            - analysis_type: Type of analysis (pattern, anomaly, root_cause, etc.)
            - limit: Results to return (default 100)
            
            If the query mentions database, performance, memory usage, CPU usage, or other system metrics, make sure to include those terms in the semantic_query and add appropriate filters for service names like "database" and error levels.
            
            Return ONLY the JSON object.
            """
        )
        
        # Create modern RunnableSequence chains instead of deprecated LLMChain
        self.query_translation_chain = self.query_translation_prompt | self.llm
        self.analysis_chain = self.analysis_prompt | self.llm

    async def process_natural_language_query(self, query: str) -> Dict[str, Any]:
        """Process a natural language query with state management and context"""
        # Update conversation history
        self.conversation_history.append({"query": query, "timestamp": datetime.now().isoformat()})
        
        # Get context from previous analyses
        context = self._get_analysis_context()
        
        try:
            # Translate query with context
            translation_result = await self._translate_query(query, context)
            
            # Get logs with enhanced parameters
            logs = await self.log_store.query_logs(
                query=translation_result.get("semantic_query"),
                filters=translation_result.get("filters"),
                time_range=translation_result.get("time_range"),
                limit=translation_result.get("limit", 100)
            )
            
            # Apply log compression for Groq to reduce token usage
            if self.provider == "groq" and isinstance(logs, list):
                original_count = len(logs)
                logs = self._compress_logs(logs)
                print(f"Compressed logs from {original_count} to {len(logs)} entries for Groq model")
            
            # Analyze with context and previous findings
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    analysis = await self._analyze_logs(
                        query=query,
                        logs=logs,
                        context=context,
                        previous_findings=self._get_previous_findings()
                    )
                    break  # Success, exit retry loop
                except Exception as e:
                    # Handle rate limiting with wait
                    if await self._handle_rate_limit(e):
                        if attempt < max_retries - 1:
                            print(f"Retrying analysis after rate limit (attempt {attempt+1}/{max_retries})")
                            continue  # Try again after waiting
                    
                    # If not a rate limit error or last retry, re-raise
                    if attempt == max_retries - 1:
                        raise
            else:
                # This executes if the for loop completes without a break (all retries failed)
                raise ValueError(f"Failed to analyze logs after {max_retries} attempts due to rate limits")
            
            # Update analysis state
            self._update_analysis_state(query, analysis, translation_result)
            
            return {
                "query": query,
                "parameters": translation_result,
                "logs": logs,
                "analysis": analysis,
                "context": context
            }
        except Exception as e:
            # Check if it's a rate limit error that we can handle with patience
            if await self._handle_rate_limit(e):
                # Try once more after waiting
                return await self.process_natural_language_query(query)
                
            # Check if it's an authentication error with a non-Google provider
            if isinstance(e, (ValueError, AuthenticationError)) and "API key" in str(e) and self.provider != "google":
                # Fallback to Google if available
                if "google" in self.api_keys and self.api_keys["google"]:
                    print(f"Authentication error with {self.provider}. Falling back to Google provider.")
                    await self.set_model("google", "gemini-1.5-pro", self.api_keys["google"])
                    # Try again with the new model
                    return await self.process_natural_language_query(query)
                
            # Re-raise the exception if we can't handle it
            raise

    def _get_analysis_context(self) -> str:
        """Get relevant context from previous analyses"""
        recent_queries = self.conversation_history[-5:] if self.conversation_history else []
        context = {
            "recent_queries": recent_queries,
            "system_state": self.analysis_state.get("system_state", {}),
            "known_issues": self.analysis_state.get("known_issues", []),
            "patterns": self.analysis_state.get("patterns", {})
        }
        return json.dumps(context)

    def _get_previous_findings(self) -> str:
        """Get relevant findings from previous analyses"""
        return json.dumps(self.analysis_state.get("findings", []))

    def _update_analysis_state(self, query: str, analysis: str, parameters: Dict[str, Any]) -> None:
        """Update agent's analysis state"""
        if "findings" not in self.analysis_state:
            self.analysis_state["findings"] = []
        
        # Extract and store findings
        self.analysis_state["findings"].append({
            "query": query,
            "analysis": analysis,
            "timestamp": datetime.now().isoformat()
        })
        
        # Update system state based on analysis
        if "system_state" not in self.analysis_state:
            self.analysis_state["system_state"] = {}
        
        # Keep only recent findings
        self.analysis_state["findings"] = self.analysis_state["findings"][-10:]

    async def _translate_query(self, query: str, context: str) -> Dict[str, Any]:
        """Translate query with context consideration"""
        result = await self.query_translation_chain.ainvoke({"query": query, "context": context})
        try:
            return json.loads(result.content)
        except (json.JSONDecodeError, AttributeError):
            return {"semantic_query": query, "limit": 100}

    async def _analyze_logs(self, query: str, logs: List[Dict[str, Any]], 
                          context: str, previous_findings: str) -> str:
        """Analyze logs with context and previous findings"""
        # Format logs as string for the LLM input - ensure it's a string
        if isinstance(logs, list):
            if logs and isinstance(logs[0], str):
                # If logs is a list of strings, join them
                logs_str = "\n".join(logs)
            else:
                # Otherwise, convert to JSON
                logs_str = json.dumps(logs, indent=2)
        elif isinstance(logs, str):
            logs_str = logs
        else:
            # Fallback for any other type
            logs_str = str(logs)
            
        print(f"Analyzing logs (type: {type(logs)}, converted to string of length: {len(logs_str)})")
        
        # Apply token limit handling for Groq
        logs_str = self._truncate_for_model(logs_str)
        
        try:
            result = await self.analysis_chain.ainvoke({
                "query": query,
                "logs": logs_str,
                "context": context,
                "previous_findings": previous_findings
            })
            return result.content
        except Exception as e:
            # If we get a token limit error, try with even more aggressive truncation
            if "tokens" in str(e).lower() and "limit" in str(e).lower():
                print(f"Token limit error: {str(e)}. Attempting with more aggressive truncation...")
                # Truncate even more aggressively - only keep 1/3 of the original token limit
                logs_str = self._truncate_for_model(logs_str, max_tokens=2000)
                result = await self.analysis_chain.ainvoke({
                    "query": query, 
                    "logs": logs_str,
                    "context": self._truncate_for_model(context, max_tokens=500),
                    "previous_findings": self._truncate_for_model(previous_findings, max_tokens=500)
                })
                return result.content
            else:
                # Re-raise other errors
                raise

    # Method to initialize agent state with seed data from logs
    async def initialize_agent_state(self) -> None:
        """Initialize the agent state with seed data from existing logs"""
        if self.analysis_state and self.conversation_history and self.analysis_state.get("findings"):
            # Already initialized with findings
            print("Agent already initialized, skipping initialization")
            return
            
        print("Initializing agent state with seed data...")
            
        # Fetch recent logs to seed initial state
        try:
            # Get a sample of recent logs
            print("Fetching logs for agent initialization...")
            recent_logs = await self.log_store.query_logs(limit=100)
            
            if (recent_logs):
                print(f"Found {len(recent_logs)} logs for initialization")
                
                # Create a seed summary to initialize the agent's knowledge
                print("Generating initial log summary...")
                summary = await self.summarize_logs(recent_logs, "System overview")
                
                # Initialize analysis state
                if not self.analysis_state:
                    self.analysis_state = {}
                
                if "findings" not in self.analysis_state:
                    self.analysis_state["findings"] = []
                
                # Add seed data
                print("Adding initial findings...")
                self.analysis_state["findings"].append({
                    "query": "Initial system analysis",
                    "analysis": summary,
                    "timestamp": datetime.now().isoformat()
                })
                
                # Initialize system state with service information
                services = set()
                error_count = 0
                warn_count = 0
                
                for log in recent_logs:
                    if log.get("service"):
                        services.add(log.get("service"))
                    if log.get("level") == "ERROR":
                        error_count += 1
                    elif log.get("level") == "WARN":
                        warn_count += 1
                
                # Add system state info
                print("Adding system state information...")
                self.analysis_state["system_state"] = {
                    "services": list(services),
                    "error_count": error_count,
                    "warn_count": warn_count,
                    "last_updated": datetime.now().isoformat()
                }
                
                # Add conversation starter
                if not self.conversation_history:
                    self.conversation_history = [{
                        "query": "Initialize system monitoring",
                        "timestamp": datetime.now().isoformat()
                    }]
                
                # Add known issues if errors found
                if "known_issues" not in self.analysis_state:
                    self.analysis_state["known_issues"] = []
                
                if error_count > 0:
                    self.analysis_state["known_issues"].append({
                        "issue": f"Found {error_count} ERROR level logs during initial scan",
                        "detected_at": datetime.now().isoformat(),
                        "status": "active"
                    })
                
                # Add patterns if found
                if "patterns" not in self.analysis_state:
                    self.analysis_state["patterns"] = {}
                
                if services:
                    service_counts = {}
                    for service in services:
                        service_counts[service] = len([log for log in recent_logs if log.get("service") == service])
                    
                    self.analysis_state["patterns"]["service_distribution"] = service_counts
                
                print(f"Agent state initialized with data from {len(recent_logs)} logs")
            else:
                print("No logs found for initialization, creating empty state")
                # Create empty state with placeholders
                if not self.analysis_state:
                    self.analysis_state = {
                        "findings": [{
                            "query": "Initial system check",
                            "analysis": "No logs available yet. Please ingest some logs to enable analysis.",
                            "timestamp": datetime.now().isoformat()
                        }],
                        "system_state": {
                            "services": [],
                            "error_count": 0,
                            "warn_count": 0,
                            "last_updated": datetime.now().isoformat()
                        },
                        "known_issues": [],
                        "patterns": {}
                    }
                
                if not self.conversation_history:
                    self.conversation_history = [{
                        "query": "Initialize system monitoring",
                        "timestamp": datetime.now().isoformat()
                    }]
        except Exception as e:
            print(f"Error initializing agent state: {str(e)}")
            import traceback
            traceback.print_exc()

    async def get_system_insights(self) -> Dict[str, Any]:
        """Get accumulated system insights"""
        # Initialize state if needed
        await self.initialize_agent_state()
        
        return {
            "system_state": self.analysis_state.get("system_state", {}),
            "known_issues": self.analysis_state.get("known_issues", []),
            "patterns": self.analysis_state.get("patterns", {}),
            "conversation_history": self.conversation_history,
            "findings": self.analysis_state.get("findings", [])
        }

    async def summarize_logs(self, logs: List[Dict[str, Any]], focus: str = None) -> str:
        """Generate a summary of the logs, optionally with a specific focus"""
        # Create a prompt for log summarization
        summarization_prompt = PromptTemplate(
            input_variables=["logs", "focus"],
            template="""
            You are an expert log analysis system. Your task is to summarize the following logs.
            
            LOGS:
            {logs}
            
            FOCUS: {focus}
            
            Provide a concise summary of these logs. Identify key patterns, anomalies, errors, or important events.
            If a specific focus is provided, emphasize information related to that focus.
            Your summary should help the user understand the overall system state and any issues that require attention.
            """
        )
        
        # Create a modern RunnableSequence chain
        summarization_chain = summarization_prompt | self.llm
        
        # Format logs as string for the LLM input - ensure it's a string
        # Fix: Handle the case where logs might be a list of strings or other format
        if isinstance(logs, list):
            if logs and isinstance(logs[0], str):
                # If logs is a list of strings, join them
                logs_str = "\n".join(logs)
            else:
                # Otherwise, convert to JSON
                logs_str = json.dumps(logs, indent=2)
        elif isinstance(logs, str):
            logs_str = logs
        else:
            # Fallback for any other type
            logs_str = str(logs)
        
        print(f"Summarizing logs (type: {type(logs)}, converted to string of length: {len(logs_str)})")
        
        # Apply token limit handling for Groq
        logs_str = self._truncate_for_model(logs_str)
        
        try:
            # Run the summarization chain
            result = await summarization_chain.ainvoke({
                "logs": logs_str, 
                "focus": focus or "General summary"
            })
            return result.content
        except Exception as e:
            # If we get a token limit error, try with even more aggressive truncation
            if "tokens" in str(e).lower() and "limit" in str(e).lower():
                print(f"Token limit error: {str(e)}. Attempting with more aggressive truncation...")
                # Truncate even more aggressively
                logs_str = self._truncate_for_model(logs_str, max_tokens=2000)
                result = await summarization_chain.ainvoke({
                    "logs": logs_str, 
                    "focus": focus or "General summary"
                })
                return result.content
            else:
                # Re-raise other errors
                raise

    def _configure_llm(self, provider: str, model: str, api_key: str) -> None:
        """Configure the LLM and embeddings based on the provider and model"""
        self.provider = provider
        self.model_name = model

        print(f"Configuring LLM with provider: {provider}, model: {model}, API key: {api_key}")
        
        # Validate API key first - it shouldn't be empty or placeholder text
        if not api_key or api_key == "your_new_groq_api_key_here" or "actual_key_should_be_here" in api_key:
            raise ValueError(f"Invalid API key for {provider}. Please provide a valid API key.")
        
        # Set up the appropriate LLM and embeddings
        if provider == "google":
            genai.configure(api_key=api_key)
            self.llm = ChatGoogleGenerativeAI(
                model=model,
                google_api_key=api_key,
                temperature=0.1
            )
            self.embeddings = GoogleGenerativeAIEmbeddings(
                google_api_key=api_key,
                model="models/embedding-001"
            )
        
        elif provider == "openai":
            self.llm = ChatOpenAI(
                model=model,
                api_key=api_key,
                temperature=0.1
            )
            self.embeddings = OpenAIEmbeddings(
                api_key=api_key
            )
            
        elif provider == "groq":
            try:
                # Validate Groq API key format
                if not api_key.startswith("gsk_"):
                    raise ValueError("Groq API key should start with 'gsk_'")
                    
                self.llm = ChatGroq(
                    model=model,
                    api_key=api_key,
                    temperature=0.1
                )
                # Fall back to OpenAI embeddings as Groq doesn't have its own embedding model
                if "openai" in self.api_keys and self.api_keys.get("openai"):
                    self.embeddings = OpenAIEmbeddings(
                        api_key=self.api_keys.get("openai", "")
                    )
                else:
                    print("Warning: OpenAI API key not found for embeddings with Groq. Some functionality may be limited.")
                    self.embeddings = None
            except Exception as e:
                # Provide more detailed error information
                raise ValueError(f"Error configuring Groq LLM: {str(e)}")
            
        elif provider == "anthropic":
            self.llm = ChatAnthropic(
                model=model,
                api_key=api_key,
                temperature=0.1
            )
            # Fall back to OpenAI embeddings as Anthropic doesn't have its own embedding model
            self.embeddings = OpenAIEmbeddings(
                api_key=self.api_keys.get("openai", "")
            ) if "openai" in self.api_keys else None
            
        else:
            raise ValueError(f"Unsupported provider: {provider}")
        
        # Update the chains
        if hasattr(self, 'query_translation_prompt') and hasattr(self, 'analysis_prompt'):
            self.query_translation_chain = self.query_translation_prompt | self.llm
            self.analysis_chain = self.analysis_prompt | self.llm
    
    async def set_model(self, provider: str, model: str, api_key: str = None) -> Dict[str, Any]:
        """Set the LLM model and provider"""
        if not api_key:
            # Use stored API key if available
            api_key = self.api_keys.get(provider)
            
        if not api_key:
            raise ValueError(f"API key for {provider} is required")
            
        # Store the API key for future use
        self.api_keys[provider] = api_key
        
        # Configure the new LLM
        self._configure_llm(provider, model, api_key)
        print(f"Model switched to {model} using {provider} provider")
        
        # Return a dictionary with model info that will be sent as JSON response
        return {
            "success": True,
            "provider": provider,
            "model": model
        }
    
    async def get_model_info(self) -> Dict[str, str]:
        """Get information about the current model"""
        return {
            "provider": self.provider,
            "model": self.model_name
        }

    def _estimate_token_count(self, text: str) -> int:
        """Roughly estimate token count - 1 token is approximately 4 characters for English text"""
        return len(text) // 4  # Simple approximation
    
    def _truncate_for_model(self, text: str, max_tokens: int = 4000) -> str:
        """Truncate text to fit within token limits for different models while preserving critical information"""
        # Use a smaller limit for inputs to leave room for the output
        input_token_limit = max_tokens
        
        # If using Groq, apply stricter limits (on_demand tier = 6000 tokens)
        if self.provider == "groq":
            # Leave ~2000 tokens for response
            input_token_limit = 4000  
            
        estimated_tokens = self._estimate_token_count(text)
        
        if estimated_tokens <= input_token_limit:
            return text
            
        # If larger than the limit, we need to truncate smartly
        print(f"Text size ({estimated_tokens} est. tokens) exceeds limit ({input_token_limit}). Truncating smartly...")
        
        # If this is JSON data, try to parse and prioritize error logs
        try:
            if text.strip().startswith('[') and text.strip().endswith(']'):
                logs = json.loads(text)
                if isinstance(logs, list) and logs and isinstance(logs[0], dict):
                    # Prioritize database error logs
                    high_priority_logs = []
                    normal_logs = []
                    
                    for log in logs:
                        level = log.get('level', '').upper() if isinstance(log.get('level'), str) else ''
                        service = log.get('service', '').lower() if isinstance(log.get('service'), str) else ''
                        msg = log.get('message', '').lower() if isinstance(log.get('message'), str) else ''
                        
                        # High priority: Database errors and memory issues
                        if (level == 'ERROR' and 
                            (service == 'database' or 
                             'memory' in msg or 
                             'cpu' in msg or 
                             'database' in msg or
                             'connection' in msg)):
                            high_priority_logs.append(log)
                        else:
                            normal_logs.append(log)
                    
                    # Calculate how many normal logs we can include
                    high_priority_json = json.dumps(high_priority_logs, indent=2)
                    high_priority_tokens = self._estimate_token_count(high_priority_json)
                    remaining_tokens = input_token_limit - high_priority_tokens - 100  # 100 tokens buffer
                    
                    # If we can include some normal logs
                    if remaining_tokens > 0:
                        # Take a sample from the beginning, middle and end
                        sample_size = min(len(normal_logs), max(3, remaining_tokens // 200))
                        if sample_size >= 3 and len(normal_logs) >= 3:
                            sample_logs = []
                            # Beginning
                            sample_logs.extend(normal_logs[:sample_size//3])
                            # Middle
                            mid_start = len(normal_logs)//2 - sample_size//6
                            sample_logs.extend(normal_logs[mid_start:mid_start + sample_size//3])
                            # End
                            sample_logs.extend(normal_logs[-sample_size//3:])
                            
                            # Combine high priority and sample logs
                            combined_logs = high_priority_logs + sample_logs
                            result = json.dumps(combined_logs, indent=2)
                            
                            # Check if we're still within limits
                            if self._estimate_token_count(result) <= input_token_limit:
                                return result
                    
                    # If we couldn't include normal logs or the combined result was too large
                    # Just return the high priority logs
                    if high_priority_logs and high_priority_tokens <= input_token_limit:
                        return json.dumps(high_priority_logs, indent=2)
        except:
            # If JSON parsing fails, continue with the regular truncation
            pass
        
        # Calculate character limit (converting tokens back to characters)
        char_limit = input_token_limit * 4
        
        # Regular truncation: preserve beginning and end, remove middle
        beginning = text[:char_limit // 2]
        ending = text[-char_limit // 2:]
        
        truncated = f"{beginning}\n...[CONTENT TRUNCATED DUE TO TOKEN LIMITS]...\n{ending}"
        print(f"Truncated to approximately {self._estimate_token_count(truncated)} tokens")
        
        return truncated

    def _compress_logs(self, logs_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Apply compression techniques to reduce token usage by removing redundant information"""
        if not logs_data:
            return logs_data
            
        compressed_logs = []
        seen_patterns = {}
        
        # Group similar logs and extract shared patterns
        for log in logs_data:
            # Create a simplified signature for the log
            if isinstance(log, dict) and 'message' in log:
                # Extract key elements from the message
                msg = log['message']
                level = log.get('level', 'INFO')
                service = log.get('service', 'unknown')
                
                # Always include ERROR logs related to database or memory
                if (level == "ERROR" and 
                    (service.lower() == "database" or 
                     "memory" in msg.lower() or 
                     "cpu" in msg.lower() or 
                     "database" in msg.lower() or
                     "connection" in msg.lower())):
                    compressed_logs.append(log)
                    continue
                
                # Create a signature based on content structure
                # Remove timestamps, IDs, and specific values
                signature = re.sub(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}', 'TIMESTAMP', msg)
                signature = re.sub(r'\b[0-9a-f]{8,}\b', 'ID', signature)
                signature = re.sub(r'\b\d+\.\d+\.\d+\.\d+\b', 'IP', signature)
                
                # Count similar patterns
                sig_key = f"{level}:{service}:{signature[:100]}"  # Use first 100 chars of pattern
                if sig_key in seen_patterns:
                    seen_patterns[sig_key]['count'] += 1
                    # Only keep a few examples of each pattern
                    if seen_patterns[sig_key]['count'] <= 3:
                        compressed_logs.append(log)
                else:
                    seen_patterns[sig_key] = {'count': 1, 'example': log}
                    compressed_logs.append(log)
            else:
                # Keep non-standard logs as is
                compressed_logs.append(log)
        
        # Add summary of compression
        if len(compressed_logs) < len(logs_data):
            # Add a synthetic log that summarizes the compression
            compressed_logs.append({
                "level": "INFO",
                "service": "log-system",
                "message": f"[LOG COMPRESSION SUMMARY] Reduced {len(logs_data)} logs to {len(compressed_logs)} logs by removing repetitive patterns. Pattern groups found: {len(seen_patterns)}.",
                "timestamp": datetime.now().isoformat(),
                "producer_id": "log-system",
                "metadata": {
                    "compression_ratio": f"{len(compressed_logs)/len(logs_data):.2f}",
                    "patterns_found": len(seen_patterns)
                }
            })
            
        return compressed_logs

    async def _handle_rate_limit(self, e: Exception) -> bool:
        """Handle rate limit exceptions by implementing backoff and waiting"""
        error_message = str(e).lower()
        
        # Check if this is a rate limit error
        if "rate limit" in error_message or "429" in error_message:
            # Extract wait time if available
            wait_time = None
            match = re.search(r'try again in (\d+)m(\d+\.\d+)s', error_message)
            if match:
                minutes = int(match.group(1))
                seconds = float(match.group(2))
                wait_time = minutes * 60 + seconds
            else:
                # Default wait time with exponential backoff
                current_time = time.time()
                time_since_last_error = current_time - self.last_rate_limit_error
                
                # Reset backoff if it's been a while since last error
                if time_since_last_error > 120:  # 2 minutes
                    self.rate_limit_backoff = 1
                else:
                    # Otherwise, increase backoff (capped at 60 seconds)
                    self.rate_limit_backoff = min(self.rate_limit_backoff * 2, 60)
                    
                wait_time = self.rate_limit_backoff
                
            self.last_rate_limit_error = time.time()
            
            print(f"⚠️ Rate limit hit. Waiting for {wait_time:.1f} seconds before retrying...")
            await asyncio.sleep(wait_time)
            print("Resuming after rate limit wait period")
            return True
            
        return False