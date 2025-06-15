import asyncio
import signal
import sys
import platform
from config import CHROMA_DB_PATH, LOG_RETENTION_DAYS

async def main():
    print("Starting Log Analysis AI System...")
    
    # Initialize components
    from storage.chroma_client import ChromaLogStore
    from config import CHROMA_DB_PATH, LOG_RETENTION_DAYS, GOOGLE_API_KEY
    
    log_store = ChromaLogStore(
        CHROMA_DB_PATH, 
        google_api_key=GOOGLE_API_KEY,
        retention_days=LOG_RETENTION_DAYS
    )
    
    # Start the FastAPI server
    import uvicorn
    from api.main import app
    
    # Run FastAPI in a separate thread
    server_config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(server_config)
    
    # Handle shutdown gracefully
    async def shutdown(signal_received=None):
        if signal_received:
            print(f"Received exit signal {signal_received}...")
        else:
            print("Shutting down...")
        # Additional cleanup if needed
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        for task in tasks:
            task.cancel()
        print("Shutdown complete.")
        sys.exit(0)
    
    # Register signal handlers only on Unix-like systems
    if platform.system() != 'Windows':
        for s in (signal.SIGINT, signal.SIGTERM):
            loop = asyncio.get_event_loop()
            loop.add_signal_handler(s, lambda s=s: asyncio.create_task(shutdown(s)))
    
    # Start components
    cleanup_task = asyncio.create_task(log_store.cleanup_old_logs())
    
    # Schedule periodic cleanup
    async def periodic_cleanup():
        while True:
            await asyncio.sleep(24 * 60 * 60)  # Run once a day
            await log_store.cleanup_old_logs()
    
    cleanup_scheduler = asyncio.create_task(periodic_cleanup())
    
    try:
        # Start FastAPI server
        print("Starting FastAPI server on http://0.0.0.0:8000")
        await server.serve()
    except KeyboardInterrupt:
        print("Received KeyboardInterrupt, shutting down...")
        await shutdown("KeyboardInterrupt")

if __name__ == "__main__":
    asyncio.run(main())