from fastapi import APIRouter, Depends, HTTPException, Request
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from datetime import datetime
import json  # Add missing import here

# Import our agent
from llm.agent import LogAnalysisAgent
from storage.chroma_client import ChromaLogStore

# Create router
router = APIRouter(prefix="/queries", tags=["queries"])

# Enhanced models for request/response
class NaturalLanguageQuery(BaseModel):
    query: str = Field(..., description="The natural language query to analyze logs")
    max_logs: Optional[int] = Field(100, description="Maximum number of logs to return")
    analysis_focus: Optional[str] = Field(None, description="Specific aspect to focus analysis on")
    include_context: Optional[bool] = Field(True, description="Include historical context and previous findings")

class SystemInsight(BaseModel):
    system_state: Dict[str, Any] = Field(default_factory=dict)
    known_issues: List[Dict[str, Any]] = Field(default_factory=list)
    patterns: Dict[str, Any] = Field(default_factory=dict)
    conversation_history: List[Dict[str, Any]] = Field(default_factory=list)
    findings: List[Dict[str, Any]] = Field(default_factory=list)

class QueryResponse(BaseModel):
    query: str
    analysis: str
    logs: List[Dict[str, Any]]
    parameters: Dict[str, Any]
    context: Optional[Dict[str, Any]]

class ModelConfig(BaseModel):
    model_id: str = Field(..., description="The model ID to use (e.g. 'gemini-1.5-pro', 'gpt-4', 'llama3-70b-instruct', 'claude-3-opus-20240229')")
    provider: str = Field("google", description="The AI provider to use: 'google', 'openai', 'groq', or 'anthropic'")
    api_key: Optional[str] = Field(None, description="Optional API key to use (if not provided, will use the one from config)")

# Global agent instance for state persistence
global_agent = None

# Define get_log_store
async def get_log_store():
    from config import CHROMA_DB_PATH, LOG_RETENTION_DAYS, GOOGLE_API_KEY
    return ChromaLogStore(CHROMA_DB_PATH, google_api_key=GOOGLE_API_KEY, retention_days=LOG_RETENTION_DAYS)

# Get or create the agent
# todo: handle api key here
async def get_agent():
    global global_agent
    
    if global_agent is None:
        from config import (
            GOOGLE_API_KEY, OPENAI_API_KEY, GROQ_API_KEY, ANTHROPIC_API_KEY,
            CHROMA_DB_PATH, LOG_RETENTION_DAYS, DEFAULT_PROVIDER, DEFAULT_MODEL
        )
        
        from storage.chroma_client import ChromaLogStore
        
        # Get the API key for the default provider
        api_keys = {
            "google": GOOGLE_API_KEY,
            "openai": OPENAI_API_KEY,
            "groq": GROQ_API_KEY,
            "anthropic": ANTHROPIC_API_KEY
        }

        print("Loaded GROQ API key:", repr(GROQ_API_KEY))
        
        # Get the API key for the default provider
        api_key = api_keys.get(DEFAULT_PROVIDER)
        if not api_key:
            print(f"Warning: No API key found for default provider {DEFAULT_PROVIDER}, falling back to Google")
            DEFAULT_PROVIDER = "google"
            api_key = GOOGLE_API_KEY
            
        if not api_key:
            raise ValueError(f"No valid API key found for any provider")
        
        # Create the log store and agent
        log_store = ChromaLogStore(CHROMA_DB_PATH, google_api_key=GOOGLE_API_KEY, retention_days=LOG_RETENTION_DAYS)
        global_agent = LogAnalysisAgent(api_key, log_store, provider=DEFAULT_PROVIDER, model=DEFAULT_MODEL)
        
        # Store all available API keys in the agent
        for provider, key in api_keys.items():
            if key and provider != DEFAULT_PROVIDER:
                try:
                    global_agent.api_keys[provider] = key
                    print(f"Stored API key for {provider}")
                except Exception as e:
                    print(f"Error storing API key for {provider}: {str(e)}")
        
        # Initialize agent state
        await global_agent.initialize_agent_state()
        print(f"Agent initialized with {DEFAULT_PROVIDER} {DEFAULT_MODEL}")
    
    return global_agent

# Manual reinitialize function
async def reinitialize_agent():
    global global_agent
    global_agent = None
    return await get_agent()

@router.post("/", response_model=QueryResponse)
async def query_logs(
    request: NaturalLanguageQuery,
    agent: LogAnalysisAgent = Depends(get_agent)
):
    """Query logs using natural language with context awareness"""
    try:
        # Process the query with enhanced context
        result = await agent.process_natural_language_query(request.query)
        
        # Instead of raising an HTTP exception when there are no logs,
        # return a valid response with empty logs and appropriate analysis
        if not result["logs"]:
            print(f"No logs found for query: '{request.query}'")
            return QueryResponse(
                query=request.query,
                analysis="No logs were found matching your query criteria. This could mean that the logs don't exist in the database, or your search terms need to be adjusted. Try broadening your search or using different keywords.",
                logs=[],  # Empty logs list
                parameters=result["parameters"],
                context=json.loads(result["context"]) if request.include_context else None
            )

        return QueryResponse(
            query=result["query"],
            analysis=result["analysis"],
            logs=result["logs"][:request.max_logs],
            parameters=result["parameters"],
            context=json.loads(result["context"]) if request.include_context else None
        )
    except HTTPException as e:
        # Re-raise HTTP exceptions without modification
        # This ensures 404s and other HTTP errors are preserved
        raise
    except Exception as e:
        import traceback
        print(f"Error processing query: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")

@router.get("/insights", response_model=SystemInsight)
async def get_system_insights(agent: LogAnalysisAgent = Depends(get_agent)):
    """Get accumulated system insights and patterns"""
    try:
        return await agent.get_system_insights()
    except Exception as e:
        import traceback
        print(f"Error retrieving insights: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error retrieving insights: {str(e)}")

@router.post("/reinitialize")
async def reset_and_initialize():
    """Force the agent to reinitialize with fresh data"""
    try:
        agent = await reinitialize_agent()
        return {"message": "Agent successfully reinitialized"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reinitializing agent: {str(e)}")

@router.post("/summarize")
async def summarize_logs(
    logs: List[Dict[str, Any]],
    focus: Optional[str] = None,
    agent: LogAnalysisAgent = Depends(get_agent)
):
    """Generate a focused summary of provided logs"""
    try:
        summary = await agent.summarize_logs(logs, focus)
        return {"summary": summary}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating summary: {str(e)}")

@router.post("/set-model", response_model=dict)
async def set_model(
    config: ModelConfig,
    agent: LogAnalysisAgent = Depends(get_agent)
):
    """Set the LLM model for the agent"""
    try:
        provider = config.provider
        model_name = config.model_id
        api_key = config.api_key
        
        # If no API key is provided in the request, get it from config
        if not api_key and provider == "groq":
            from config import GROQ_API_KEY
            api_key = GROQ_API_KEY
            print(f"Using Groq API key from config: {api_key[:5]}...")
        
        # Debug log to see which key is being used
        key_preview = api_key[:5] + "..." if api_key else "None"
        print(f"Switching to {provider} model {model_name} with API key: {key_preview}")
        
        result = await agent.set_model(provider=provider, model=model_name, api_key=api_key)
        
        return {
            "success": True, 
            "message": f"Model switched to {config.model_id}",
            "model": config.model_id,
            "provider": provider
        }
    except Exception as e:
        import traceback
        print(f"Error setting model: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error setting model: {str(e)}")

@router.get("/current-model")
async def get_current_model(agent: LogAnalysisAgent = Depends(get_agent)):
    """Get the current LLM model configuration"""
    try:
        model_info = await agent.get_model_info()
        return model_info
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving model info: {str(e)}")
