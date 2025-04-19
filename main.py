import asyncio
import signal
import sys
from config import FLUVIO_TOPIC, CHROMA_DB_PATH, MAX_BATCH_SIZE, PROCESSING_INTERVAL, LOG_RETENTION_DAYS

async def main():
    print("Starting Log Analysis AI System with Google Gemini...")
    
    # Initialize components
    from storage.chroma_client import ChromaLogStore
    from config import CHROMA_DB_PATH, LOG_RETENTION_DAYS, GOOGLE_API_KEY
    
    log_store = ChromaLogStore(
        CHROMA_DB_PATH, 
        google_api_key=GOOGLE_API_KEY,
        retention_days=LOG_RETENTION_DAYS
    )
    
    from log_ingestion.fluvio_consumer import LogConsumer
    
    # Define the batch processor function
    async def process_log_batch(logs):
        await log_store.store_logs(logs)
        print(f"✅ Processed {len(logs)} logs")
    
    # Create and start the consumer
    consumer = LogConsumer(
        FLUVIO_TOPIC, 
        process_log_batch, 
        max_batch_size=MAX_BATCH_SIZE,
        processing_interval=PROCESSING_INTERVAL
    )
    
    # Start the FastAPI server
    import uvicorn
    from api.main import app
    
    # Run FastAPI in a separate thread
    server_config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(server_config)
    
    # Handle shutdown gracefully
    async def shutdown(signal, loop):
        print(f"Received exit signal {signal.name}...")
        await consumer.stop()
        # Additional cleanup if needed
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        for task in tasks:
            task.cancel()
        print("Shutdown complete.")
        sys.exit(0)
    
    # Register signal handlers
    for s in (signal.SIGINT, signal.SIGTERM):
        loop = asyncio.get_event_loop()
        loop.add_signal_handler(s, lambda s=s: asyncio.create_task(shutdown(s, loop)))
    
    # Start components
    consumer_task = asyncio.create_task(consumer.start_consuming())
    cleanup_task = asyncio.create_task(log_store.cleanup_old_logs())
    
    # Schedule periodic cleanup
    async def periodic_cleanup():
        while True:
            await asyncio.sleep(24 * 60 * 60)  # Run once a day
            await log_store.cleanup_old_logs()
    
    cleanup_scheduler = asyncio.create_task(periodic_cleanup())
    
    # Start FastAPI server
    print("Starting FastAPI server on http://0.0.0.0:8000")
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main())