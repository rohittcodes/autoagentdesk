from fastapi import FastAPI, Depends, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import asyncio
import json
from datetime import datetime, timedelta
import random
from typing import List, Dict, Any

from api.routes import logs, queries, credentials, ingest, database

app = FastAPI(
    title="Log Analysis AI API",
    description="API for real-time log analysis with AI",
    version="0.1.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if (websocket in self.active_connections):
            self.active_connections.remove(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                # Connection might be closed
                pass

manager = ConnectionManager()

# Include routers
app.include_router(logs.router)
app.include_router(queries.router)
app.include_router(credentials.router)
app.include_router(ingest.router)
app.include_router(database.router)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the web UI"""
    with open("static/index.html") as f:
        return f.read()

@app.get("/health")
async def health_check():
    # add more sophisticated health checks here
    return {"status": "healthy"}

@app.websocket("/logs/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print(f"WebSocket client connected from {websocket.client}")
    
    try:
        # Get absolute path to logs file
        import os
        logs_path = os.path.abspath("logs_output.json")
        print(f"Looking for logs at: {logs_path}")
        
        if not os.path.exists(logs_path):
            print(f"ERROR: Log file not found at {logs_path}")
            error_log = {
                "timestamp": datetime.now().isoformat(),
                "level": "ERROR",
                "service": "system",
                "message": f"Log file not found at {logs_path}",
                "producer_id": "system"
            }
            await websocket.send_json(error_log)
        else:
            print(f"SUCCESS: Found log file at {logs_path} with size {os.path.getsize(logs_path)} bytes")
            
            # Read the logs directly from file
            try:
                with open(logs_path, "r") as f:
                    logs_content = f.read()
                    logs = json.loads(logs_content)
                    
                print(f"Successfully loaded {len(logs)} logs from file")
                
                # Start with a test message to make sure connection is working
                test_log = {
                    "timestamp": datetime.now().isoformat(),
                    "level": "INFO",
                    "service": "system",
                    "message": "WebSocket connection successful - logs will appear shortly",
                    "producer_id": "system-test"
                }
                await websocket.send_json(test_log)
                print("Sent test log successfully")
                
                # Send logs one by one with a small delay
                for i, log in enumerate(logs):
                    await websocket.send_json(log)
                    if i % 10 == 0:
                        print(f"Sent {i+1}/{len(logs)} logs")
                    await asyncio.sleep(0.05)
                
                print(f"✅ Successfully sent all {len(logs)} logs to client")
                
            except Exception as e:
                print(f"ERROR loading/sending logs: {str(e)}")
                import traceback
                traceback.print_exc()
                
                error_log = {
                    "timestamp": datetime.now().isoformat(),
                    "level": "ERROR",
                    "service": "system",
                    "message": f"Error processing logs: {str(e)}",
                    "producer_id": "system"
                }
                await websocket.send_json(error_log)
        
        # After sending all logs, keep connection alive with heartbeats
        counter = 0
        while True:
            counter += 1
            heartbeat_log = {
                "timestamp": datetime.now().isoformat(),
                "level": random.choice(["INFO", "WARN", "ERROR", "DEBUG"]),
                "service": random.choice(["api", "auth", "database", "worker", "cache"]),
                "message": f"Live update #{counter} at {datetime.now().strftime('%H:%M:%S')}",
                "producer_id": "live-heartbeat"
            }
            await websocket.send_json(heartbeat_log)
            await asyncio.sleep(3)
            
    except WebSocketDisconnect:
        print(f"WebSocket client disconnected: {websocket.client}")
    except Exception as e:
        print(f"WebSocket error: {str(e)}")
        import traceback
        traceback.print_exc()