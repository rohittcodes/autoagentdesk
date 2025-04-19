# llm/agent.py
from typing import Dict, Any, List
import json
import google.generativeai as genai
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate

class LogAnalysisAgent:
    def __init__(self, google_api_key: str, log_store):
        self.log_store = log_store
        
        # Configure the Google Generative AI SDK
        genai.configure(api_key=google_api_key)
        
        # Initialize Gemini model
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-pro",
            google_api_key=google_api_key,
            temperature=0.1  # Lower temperature for more deterministic responses
        )
        
        # Initialize embeddings
        self.embeddings = GoogleGenerativeAIEmbeddings(
            google_api_key=google_api_key,
            model="models/embedding-001"  # Gemini's embedding model
        )
        
        # Define the prompt template for log analysis
        self.analysis_prompt = PromptTemplate(
            input_variables=["query", "logs"],
            template="""
            You are an expert log analysis system. Your task is to analyze the following logs and answer the user's query.
            
            USER QUERY: {query}
            
            LOGS:
            {logs}
            
            Analyze these logs and provide a clear, concise answer to the user's query. Include relevant information from the logs
            to support your analysis. If you identify any issues or patterns, highlight them. If you need more information or 
            different logs to fully answer the query, indicate what additional information would be helpful.
            """
        )
        
        # Chain for log analysis
        self.analysis_chain = LLMChain(llm=self.llm, prompt=self.analysis_prompt)
        
        # Define the prompt template for query translation
        self.query_translation_prompt = PromptTemplate(
            input_variables=["query"],
            template="""
            You are an expert in translating natural language queries into structured search parameters for a log analysis system.
            
            USER QUERY: {query}
            
            Translate this query into a JSON object with the following possible fields:
            - semantic_query: The core query for semantic search
            - time_range: Time range specifications (start and end timestamps if mentioned)
            - filters: Any filters like log level, service name, etc.
            - limit: How many results to return (default to 100 if not specified)
            
            Return ONLY the JSON object without any explanation or additional text.
            """
        )
        
        # Chain for query translation
        self.query_translation_chain = LLMChain(llm=self.llm, prompt=self.query_translation_prompt)
    
    async def process_natural_language_query(self, query: str) -> Dict[str, Any]:
        """Process a natural language query and return analysis results"""
        # Step 1: Translate the query to structured parameters
        translation_result = await self._translate_query(query)
        
        # Step 2: Query the log store based on the structured parameters
        logs = await self.log_store.query_logs(
            query=translation_result.get("semantic_query"),
            filters=translation_result.get("filters"),
            time_range=translation_result.get("time_range"),
            limit=translation_result.get("limit", 100)
        )
        
        # Step 3: Analyze the logs based on the original query
        analysis = await self._analyze_logs(query, logs)
        
        return {
            "query": query,
            "parameters": translation_result,
            "logs": logs,
            "analysis": analysis
        }
    
    async def _translate_query(self, query: str) -> Dict[str, Any]:
        """Translate natural language query to structured parameters"""
        result = await self.query_translation_chain.arun(query=query)
        try:
            # Parse the JSON result from the LLM
            return json.loads(result)
        except json.JSONDecodeError:
            # Fallback if parsing fails
            return {
                "semantic_query": query,
                "limit": 100
            }
    
    async def _analyze_logs(self, query: str, logs: List[Dict[str, Any]]) -> str:
        """Analyze logs based on the original query"""
        # Format logs as string for the LLM input
        logs_str = json.dumps(logs, indent=2)
        
        # Run the analysis chain
        analysis = await self.analysis_chain.arun(query=query, logs=logs_str)
        return analysis
    
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
        
        summarization_chain = LLMChain(llm=self.llm, prompt=summarization_prompt)
        
        # Format logs as string for the LLM input
        logs_str = json.dumps(logs, indent=2)
        
        # Run the summarization chain
        summary = await summarization_chain.arun(logs=logs_str, focus=focus or "General summary")
        return summary