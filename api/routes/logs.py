from fastapi import APIRouter, Depends, Query, HTTPException, WebSocket, WebSocketDisconnect
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import asyncio
import json

# Import our components
from storage.chroma_client import ChromaLogStore
from llm.agent import LogAnalysisAgent

# Create router
router = APIRouter(prefix="/logs", tags=["logs"])

# Store active WebSocket connections
active_connections: List[WebSocket] = []

# WebSocket manager
async def notify_clients(log_entry: Dict[str, Any]):
    """Send log entry to all connected clients"""
    for connection in active_connections:
        try:
            await connection.send_json(log_entry)
        except Exception:
            active_connections.remove(connection)

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time log streaming"""
    await websocket.accept()
    active_connections.append(websocket)
    
    try:
        # Keep the connection alive until the client disconnects
        try:
            while True:
                # Wait for client messages (can be used for filtering)
                data = await websocket.receive_text()
                # could implement filtering here based on client messages
        except WebSocketDisconnect:
            active_connections.remove(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        if websocket in active_connections:
            active_connections.remove(websocket)

# This would typically be in a dependency injection setup
async def get_log_store():
    # This is a simplified example - in production, use proper DI
    from config import CHROMA_DB_PATH, LOG_RETENTION_DAYS, GOOGLE_API_KEY
    return ChromaLogStore(CHROMA_DB_PATH, google_api_key=GOOGLE_API_KEY, retention_days=LOG_RETENTION_DAYS)

async def get_agent():
    # This is a simplified example - in production, use proper DI
    from config import GOOGLE_API_KEY
    log_store = await get_log_store()
    return LogAnalysisAgent(GOOGLE_API_KEY, log_store)

@router.get("/", response_model=List[Dict[str, Any]])
async def get_logs(
    service: Optional[str] = Query(None, description="Filter by service name"),
    level: Optional[str] = Query(None, description="Filter by log level"),
    start_time: Optional[str] = Query(None, description="Start timestamp (ISO format)"), 
    end_time: Optional[str] = Query(None, description="End timestamp (ISO format)"),
    limit: int = Query(100, description="Maximum number of logs to return"),
    log_store: ChromaLogStore = Depends(get_log_store)
):
    """Get logs with optional filtering"""
    try:
        # Validate log level
        valid_levels = ["INFO", "WARN", "ERROR", "DEBUG"]
        if level and level not in valid_levels:
            raise HTTPException(status_code=400, detail=f"Invalid log level: {level}. Valid levels are {valid_levels}")

        # Build filters
        filters = {}
        if service:
            filters["service"] = service
        if level:
            filters["level"] = level
        
        # Build time range
        time_range = {}
        if start_time:
            time_range["start"] = start_time
        if end_time:
            time_range["end"] = end_time
        
        # Query logs
        logs = await log_store.query_logs(
            filters=filters, 
            time_range=time_range,
            limit=limit
        )
        
        return logs
    except Exception as e:
        import traceback
        print(f"ERROR in get_logs: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error querying logs: {str(e)}")

@router.get("/summary", response_model=Dict[str, Any])
async def get_log_summary(
    service: Optional[str] = Query(None, description="Focus on specific service"),
    hours: int = Query(24, description="Hours to include in summary"),
    agent: LogAnalysisAgent = Depends(get_agent),
    log_store: ChromaLogStore = Depends(get_log_store)
):
    """Get a summary of recent logs"""
    # Calculate time range
    end_time = datetime.utcnow().isoformat()
    start_time = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
    
    # Build filters
    filters = {}
    if service:
        filters["service"] = service
    
    # Query logs
    logs = await log_store.query_logs(
        filters=filters, 
        time_range={"start": start_time, "end": end_time},
        limit=1000  # Get a substantial number for summary
    )

    # Generate summary
    focus = f"Service: {service}" if service else None
    summary = await agent.summarize_logs(logs, focus)
    
    return {
        "summary": summary,
        "time_range": {
            "start": start_time,
            "end": end_time
        },
        "log_count": len(logs)
    }