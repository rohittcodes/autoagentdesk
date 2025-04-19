import asyncio
from storage.chroma_client import ChromaLogStore
from datetime import datetime, timedelta
import random
import uuid

async def populate_logs():
    # Initialize ChromaLogStore
    from config import CHROMA_DB_PATH, GOOGLE_API_KEY, LOG_RETENTION_DAYS
    log_store = ChromaLogStore(CHROMA_DB_PATH, google_api_key=GOOGLE_API_KEY, retention_days=LOG_RETENTION_DAYS)

    # Generate sample logs
    log_levels = ["INFO", "WARN", "ERROR", "DEBUG"]
    services = ["api", "auth", "database", "worker", "cache"]
    logs = []

    for _ in range(100):  # Generate 100 logs
        level = random.choice(log_levels)
        service = random.choice(services)
        timestamp = (datetime.utcnow() - timedelta(minutes=random.randint(0, 1440))).isoformat()  # Random timestamp within the last 24 hours
        message = f"Sample log message for {service} with level {level}"
        metadata = {
            "request_id": str(uuid.uuid4()),
            "duration_ms": random.randint(1, 1000),
            "user_agent": random.choice([
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
                "PostmanRuntime/7.29.0",
                "curl/7.68.0"
            ])
        }

        logs.append({
            "timestamp": timestamp,
            "producer_id": str(uuid.uuid4())[:8],
            "level": level,
            "service": service,
            "message": message,
            "metadata": metadata
        })

    # Store logs in the database
    await log_store.store_logs(logs)
    print(f"✅ Successfully populated the database with {len(logs)} logs.")

if __name__ == "__main__":
    asyncio.run(populate_logs())