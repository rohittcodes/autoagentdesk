import asyncio
from storage.chroma_client import ChromaLogStore
from datetime import datetime, timedelta, UTC
import random
import uuid
import json

async def populate_logs():
    # Initialize ChromaLogStore
    from config import CHROMA_DB_PATH, GOOGLE_API_KEY, GROQ_API_KEY, LOG_RETENTION_DAYS
    
    # Choose which AI provider to use (Google or Groq)
    # For now, we can only use Google API for ChromaLogStore as it's hardcoded to use Google embeddings
    # The provider selection logic is left for informational purposes
    use_groq = GROQ_API_KEY and len(GROQ_API_KEY.strip()) > 0
    # Always use Google API key for ChromaLogStore regardless of the provider choice
    api_key = GOOGLE_API_KEY
    provider = "groq" if use_groq else "google"
    
    log_store = ChromaLogStore(
        CHROMA_DB_PATH, 
        google_api_key=api_key,  # Fixed: using google_api_key parameter instead of api_key
        retention_days=LOG_RETENTION_DAYS
        # Removed provider parameter as it's not accepted by ChromaLogStore
    )

    # Generate sample logs
    log_levels = ["INFO", "WARN", "ERROR", "DEBUG"]
    services = ["api", "auth", "database", "worker", "cache"]
    ai_platforms = ["google", "groq", "anthropic", "openai", "mistral"]
    logs = []

    markdown_samples = [
        {
            "level": "ERROR",
            "templates": [
                "## Database Connection Error\nFailed to connect to database:\n```\n{error}\n```\nAttempted connection to: `{host}`",
                "### Authentication Failed\n- User: `{user}`\n- Source IP: `{ip}`\n- Reason: Invalid credentials",
                "# Critical System Error\n> Memory usage exceeded threshold\n\n```json\n{{\n  \"usage\": \"{memory}GB\",\n  \"limit\": \"4GB\"\n}}\n```"
            ]
        },
        {
            "level": "WARN",
            "templates": [
                "### High CPU Usage\n- Current: **{cpu}%**\n- Threshold: 80%\n- Service: `{service}`",
                "## Rate Limit Warning\nAPI requests approaching limit:\n- Current: {current}\n- Limit: {limit}\n- Endpoint: `{endpoint}`",
                "### Cache Performance\n| Metric | Value |\n|--------|-------|\n| Hit Rate | {hit_rate}% |\n| Miss Rate | {miss_rate}% |"
            ]
        },
        {
            "level": "INFO",
            "templates": [
                "### New User Registration\n- Username: `{username}`\n- Email: {email}\n- Status: ✅ Verified",
                "## Deployment Success\nDeployed version `{version}` to production\n- 🚀 Services updated: {services}\n- ⏱️ Duration: {duration}s",
                "### API Performance Report\n```markdown\n- Response Time: {response_time}ms\n- Success Rate: {success_rate}%\n- Total Requests: {requests}\n```"
            ]
        },
        {
            "level": "DEBUG",
            "templates": [
                "### Request Details\n```json\n{{\n  \"method\": \"{method}\",\n  \"path\": \"{path}\",\n  \"duration\": \"{duration}ms\"\n}}\n```",
                "## Function Trace\n1. Entry: `{entry_point}`\n2. Args: `{args}`\n3. Return: `{result}`",
                "### Cache Operation\n- Type: `{op_type}`\n- Key: `{key}`\n- TTL: {ttl}s"
            ]
        }
    ]

    # Add AI agent specific templates
    ai_agent_templates = [
        "## {ai_platform} Model Call\n- Model: `{model_name}`\n- Response time: {response_time}ms\n- Tokens: {tokens}\n- Status: {status}",
        "### AI Integration Error\nFailed to generate response with {ai_platform}:\n```\n{error_message}\n```\n- Model: `{model_name}`",
        "# {ai_platform} Performance Report\n| Metric | Value |\n|--------|-------|\n| Avg Response Time | {avg_time}ms |\n| Success Rate | {success_rate}% |\n| Cost | ${cost} |"
    ]

    for _ in range(100):  # Generate 100 logs
        level = random.choice(log_levels)
        service = random.choice(services)
        timestamp = (datetime.now(UTC) - timedelta(minutes=random.randint(0, 1440))).isoformat()

        # Find markdown templates for the selected level
        templates = next(x["templates"] for x in markdown_samples if x["level"] == level)
        
        # Randomly use AI-specific templates for some logs
        if random.random() < 0.3:  # 30% chance to create AI-related logs
            template = random.choice(ai_agent_templates)
            ai_platform = random.choice(ai_platforms)
            service = "ai-agent"  # Override service for AI logs
            
            # AI-specific values
            ai_values = {
                "ai_platform": ai_platform,
                "model_name": random.choice([
                    f"{ai_platform}-7b",
                    f"{ai_platform}-large", 
                    f"{ai_platform}-14b", 
                    f"{ai_platform}-70b",
                    "llama3-70b-instruct",
                    "mixtral-8x7b",
                    "gemini-pro",
                    "gpt-4o",
                    "claude-3-opus"
                ]),
                "response_time": random.randint(200, 5000),
                "tokens": random.randint(50, 2000),
                "status": random.choice(["success", "rate_limited", "context_overflow", "timeout"]),
                "error_message": random.choice([
                    "Rate limit exceeded",
                    "Context length exceeded",
                    "API key invalid",
                    "Model unavailable",
                    "Request timeout"
                ]),
                "avg_time": random.randint(300, 3000),
                "success_rate": random.randint(70, 99),
                "cost": round(random.uniform(0.01, 5.00), 2)
            }
            values = ai_values
        else:
            template = random.choice(templates)
            # Standard values for normal logs
            values = {
                "error": random.choice(["Connection refused", "Timeout", "Authentication failed"]),
                "host": f"db-{random.randint(1,5)}.example.com",
                "user": f"user_{random.randint(1000,9999)}",
                "ip": f"192.168.1.{random.randint(2,254)}",
                "memory": random.randint(4,8),
                "cpu": random.randint(81,99),
                "service": service,
                "current": random.randint(800,950),
                "limit": 1000,
                "endpoint": f"/api/v1/{random.choice(['users','orders','products'])}",
                "hit_rate": random.randint(60,95),
                "miss_rate": random.randint(5,40),
                "username": f"user_{uuid.uuid4().hex[:8]}",
                "email": f"user_{random.randint(1000,9999)}@example.com",
                "version": f"{random.randint(1,5)}.{random.randint(0,9)}.{random.randint(0,9)}",
                "services": ", ".join(random.sample(services, random.randint(1,3))),
                "duration": random.randint(10,300),
                "response_time": random.randint(50,500),
                "success_rate": random.randint(90,100),
                "requests": random.randint(1000,10000),
                "method": random.choice(["GET", "POST", "PUT", "DELETE"]),
                "path": f"/api/{random.choice(['users','orders','products'])}/{uuid.uuid4().hex[:8]}",
                "entry_point": f"process_{random.choice(['user','order','payment'])}",
                "args": f"id={uuid.uuid4().hex[:8]}",
                "result": random.choice(["success", "partial", "cached"]),
                "op_type": random.choice(["set", "get", "delete"]),
                "key": f"cache:{random.choice(['user','session','data'])}:{uuid.uuid4().hex[:8]}",
                "ttl": random.randint(300,3600)
            }

        # Format the template with random values
        message = template.format(**values)

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

    output_path = "logs_output.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(logs, f, indent=2)

    print(f"📝 Logs also saved to '{output_path}'.")

if __name__ == "__main__":
    asyncio.run(populate_logs())