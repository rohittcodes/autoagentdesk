from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import Dict, Any, Optional, List
from datetime import datetime
import json
import asyncio

from log_sources.databases import DatabaseLogSource
from storage.chroma_client import ChromaLogStore

router = APIRouter(prefix="/ingest/database", tags=["database"])

# Cache of database connections
connection_cache = {}

async def get_log_store():
    from config import CHROMA_DB_PATH, LOG_RETENTION_DAYS, GOOGLE_API_KEY
    return ChromaLogStore(CHROMA_DB_PATH, google_api_key=GOOGLE_API_KEY, retention_days=LOG_RETENTION_DAYS)

@router.post("/test-connection")
async def test_database_connection(config: Dict[str, Any]):
    """Test a database connection without actually streaming logs"""
    try:
        db_source = DatabaseLogSource(config)
        await db_source.connect()
        await db_source.disconnect()
        
        return {"status": "success", "message": "Connection successful"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Connection failed: {str(e)}")

@router.post("/fetch-logs")
async def fetch_database_logs(
    config: Dict[str, Any],
    log_store: ChromaLogStore = Depends(get_log_store)
):
    """Fetch logs from a database and store them"""
    try:
        db_source = DatabaseLogSource(config)
        logs = await db_source.get_logs()
        
        # If we got logs, store them in ChromaDB
        if logs:
            # Add a producer_id field to each log if it doesn't exist
            for log in logs:
                if "producer_id" not in log:
                    log["producer_id"] = "database"
                    
                # Ensure all metadata is properly formatted for ChromaDB
                if "metadata" in log and log["metadata"] is not None:
                    # Make sure metadata is a dict
                    if not isinstance(log["metadata"], dict):
                        log["metadata"] = {"value": str(log["metadata"])}
                        
                    # Check for non-serializable objects in metadata
                    for key, value in list(log["metadata"].items()):
                        try:
                            # Test if value is JSON serializable
                            json.dumps({key: value})
                        except (TypeError, OverflowError):
                            # If not serializable, convert to string
                            log["metadata"][key] = str(value)
                else:
                    log["metadata"] = {}
                    
            try:
                await log_store.store_logs(logs)
            except Exception as e:
                print(f"Error storing logs in ChromaDB: {str(e)}")
                import traceback
                traceback.print_exc()
                # Continue with the request even if ChromaDB storage fails
            
        return {
            "message": f"Successfully fetched {len(logs)} logs",
            "logs": logs
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error fetching logs: {str(e)}")

@router.post("/stream")
async def start_database_streaming(
    config: Dict[str, Any],
    background_tasks: BackgroundTasks
):
    """Start a background task to stream logs from a database"""
    try:
        # Generate a unique ID for this connection
        import uuid
        connection_id = str(uuid.uuid4())
        
        # Store the config in the cache
        connection_cache[connection_id] = {
            "config": config,
            "status": "starting",
            "last_run": datetime.now().isoformat(),
            "logs_processed": 0
        }
        
        # Start the background task
        background_tasks.add_task(stream_logs_background, connection_id)
        
        return {
            "connection_id": connection_id,
            "status": "starting",
            "message": "Database streaming started"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error starting stream: {str(e)}")

@router.get("/status/{connection_id}")
async def get_streaming_status(connection_id: str):
    """Get the status of a database streaming task"""
    if connection_id not in connection_cache:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    return connection_cache[connection_id]

@router.post("/stop/{connection_id}")
async def stop_database_streaming(connection_id: str):
    """Stop a database streaming task"""
    if connection_id not in connection_cache:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    connection_cache[connection_id]["status"] = "stopping"
    
    # Wait for the task to stop
    for _ in range(10):  # Wait up to 10 seconds
        await asyncio.sleep(1)
        if connection_id not in connection_cache or connection_cache[connection_id]["status"] == "stopped":
            break
    
    if connection_id in connection_cache:
        connection_cache[connection_id]["status"] = "stopped"
    
    return {"status": "stopped", "message": "Database streaming stopped"}

@router.post("/list-tables")
async def list_database_tables(config: Dict[str, Any]):
    """List available tables in the database that could contain logs"""
    try:
        db_source = DatabaseLogSource(config)
        await db_source.connect()
        
        tables = await db_source.discover_tables()
        await db_source.disconnect()
        
        return {
            "tables": tables,
            "message": f"Found {len(tables)} tables in the database"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing tables: {str(e)}")

async def stream_logs_background(connection_id: str):
    """
    Background task to periodically stream logs from a database.
    This runs until manually stopped or an error occurs.
    """
    if connection_id not in connection_cache:
        return
    
    config = connection_cache[connection_id]["config"]
    connection_cache[connection_id]["status"] = "running"
    
    try:
        # Initialize log store
        log_store = await get_log_store()
        
        # Get refresh interval from config or default to 60 seconds
        refresh_interval = int(config.get("refresh_interval", 60))
        
        # Keep track of the last timestamp we processed
        last_timestamp = None
        
        # Run until stopped
        while connection_id in connection_cache and connection_cache[connection_id]["status"] == "running":
            try:
                # Update config with last timestamp
                if last_timestamp:
                    config["last_timestamp"] = last_timestamp
                
                # Create a new database source for each iteration
                db_source = DatabaseLogSource(config)
                logs = await db_source.get_logs()
                
                # If we got logs, process them
                if logs:
                    # Store logs in ChromaDB
                    await log_store.store_logs(logs)
                    
                    # Update status
                    connection_cache[connection_id]["logs_processed"] += len(logs)
                    connection_cache[connection_id]["last_run"] = datetime.now().isoformat()
                    
                    # Update last timestamp for next iteration
                    if logs:
                        last_timestamp = max(log["timestamp"] for log in logs)
                
                # Wait for the next interval
                for _ in range(refresh_interval):
                    # Check if we should stop
                    if connection_id not in connection_cache or connection_cache[connection_id]["status"] != "running":
                        break
                    await asyncio.sleep(1)
            
            except Exception as e:
                # Log the error but continue
                print(f"Error in database streaming task: {str(e)}")
                connection_cache[connection_id]["last_error"] = str(e)
                await asyncio.sleep(refresh_interval)
    
    except Exception as e:
        # Fatal error
        if connection_id in connection_cache:
            connection_cache[connection_id]["status"] = "error"
            connection_cache[connection_id]["last_error"] = str(e)
    
    finally:
        # Clean up
        if connection_id in connection_cache and connection_cache[connection_id]["status"] != "error":
            connection_cache[connection_id]["status"] = "stopped"