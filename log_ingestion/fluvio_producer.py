import json
import time
import uuid
import random
from datetime import datetime
from fluvio import Fluvio

class LogProducer:
    def __init__(self, topic_name, producer_id=None):
        self.fluvio = Fluvio.connect()
        self.topic_name = topic_name
        self.producer = self.fluvio.topic_producer(topic_name)
        self.producer_id = producer_id or str(uuid.uuid4())[:8]
    
    async def send_log(self, log_level, service, message, metadata=None):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "producer_id": self.producer_id,
            "level": log_level,
            "service": service,
            "message": message,
            "metadata": metadata or {}
        }
        await self.producer.send_string(json.dumps(log_entry))
        return log_entry
    
    async def generate_sample_logs(self, count=10, interval=1):
        """Generate sample logs for testing purposes"""
        log_levels = ["INFO", "WARN", "ERROR", "DEBUG"]
        services = ["api", "auth", "database", "worker", "cache"]
        
        for _ in range(count):
            level = random.choice(log_levels)
            service = random.choice(services)
            
            if level == "ERROR":
                message = random.choice([
                    "Connection refused",
                    "Timeout waiting for response",
                    "Invalid authentication token",
                    "Database query failed",
                    "Out of memory error"
                ])
            elif level == "WARN":
                message = random.choice([
                    "Slow response time detected",
                    "Retry attempt #3",
                    "Cache miss",
                    "Deprecated API call",
                    "High CPU usage"
                ])
            else:
                message = random.choice([
                    "Request processed successfully",
                    "User logged in",
                    "Cache updated",
                    "Task completed",
                    "Service healthy"
                ])
                
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
            
            await self.send_log(level, service, message, metadata)
            time.sleep(interval)