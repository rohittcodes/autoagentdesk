# config.py
import os
from dotenv import load_dotenv

load_dotenv()

# Configuration settings
FLUVIO_TOPIC = os.getenv("FLUVIO_TOPIC", "logs")
CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "./chroma_db")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
LOG_RETENTION_DAYS = int(os.getenv("LOG_RETENTION_DAYS", "30"))
MAX_BATCH_SIZE = int(os.getenv("MAX_BATCH_SIZE", "100"))
PROCESSING_INTERVAL = int(os.getenv("PROCESSING_INTERVAL", "5"))  # seconds

# Default model configuration
DEFAULT_PROVIDER = os.getenv("DEFAULT_PROVIDER", "google")  # google, openai, groq, anthropic
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gemini-1.5-pro")  # Model ID depends on provider
