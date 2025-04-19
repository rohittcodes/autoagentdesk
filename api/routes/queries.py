from fastapi import APIRouter, Depends, HTTPException, Request
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field

# Import our agent
from llm.agent import LogAnalysisAgent
from storage.chroma_client import ChromaLogStore

# Create router
router = APIRouter(prefix="/queries", tags=["queries"])

# Models for request/response
class NaturalLanguageQuery(BaseModel):
    query: str = Field(..., description="The natural language query to analyze logs")
    max_logs: Optional[int] = Field(100, description="Maximum number of logs to return")

class QueryResponse(BaseModel):
    analysis: str
    logs: List[Dict[str, Any]]
    parameters: Dict[str, Any]

# Define get_log_store
async def get_log_store():
    # This is a simplified example - in production, use proper DI
    from config import CHROMA_DB_PATH, LOG_RETENTION_DAYS, GOOGLE_API_KEY
    return ChromaLogStore(CHROMA_DB_PATH, google_api_key=GOOGLE_API_KEY, retention_days=LOG_RETENTION_DAYS)

# This would typically be in a dependency injection setup
async def get_agent():
    # This is a simplified example - in production, use proper DI
    from config import GOOGLE_API_KEY
    from storage.chroma_client import ChromaLogStore
    from config import CHROMA_DB_PATH, LOG_RETENTION_DAYS
    
    log_store = ChromaLogStore(CHROMA_DB_PATH, google_api_key=GOOGLE_API_KEY, retention_days=LOG_RETENTION_DAYS)
    return LogAnalysisAgent(GOOGLE_API_KEY, log_store)

@router.post("/", response_model=Dict[str, Any])
async def query_logs(request: Request, agent: LogAnalysisAgent = Depends(get_agent), log_store: ChromaLogStore = Depends(get_log_store)):
    """Query logs using natural language"""
    try:
        # Parse the JSON body manually
        json_data = await request.json()
        query = json_data.get("query")
        max_logs = json_data.get("max_logs", 100)
        
        if not query:
            raise HTTPException(status_code=400, detail="Query parameter is required")
            
        # First translate the natural language query into structured parameters
        translation_result = await agent._translate_query(query)
        
        # Query logs from the database using the translated parameters
        logs = await log_store.query_logs(
            query=translation_result.get("semantic_query"),
            filters=translation_result.get("filters", {}),
            time_range=translation_result.get("time_range", {}),
            limit=max_logs
        )
        
        if not logs:
            raise HTTPException(status_code=404, detail="No logs found for the query")

        # Debug: Log the retrieved logs
        print(f"Retrieved {len(logs)} logs for query: {query}")
        print(f"Translation parameters: {translation_result}")

        # Pass logs to the AI agent for analysis
        analysis = await agent._analyze_logs(query, logs)
        if not analysis:
            raise HTTPException(status_code=500, detail="AI agent failed to generate a response")

        return {
            "query": query, 
            "parameters": translation_result,
            "logs": logs,
            "analysis": analysis
        }
    except Exception as e:
        import traceback
        print(f"Error in query_logs: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")
