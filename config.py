# config.py
import os
from dotenv import load_dotenv

load_dotenv()

# Configuration settings
FLUVIO_TOPIC = os.getenv("FLUVIO_TOPIC", "logs")
CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "./chroma_db")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")  # Changed from OPENAI_API_KEY to GOOGLE_API_KEY
LOG_RETENTION_DAYS = int(os.getenv("LOG_RETENTION_DAYS", "30"))
MAX_BATCH_SIZE = int(os.getenv("MAX_BATCH_SIZE", "100"))
PROCESSING_INTERVAL = int(os.getenv("PROCESSING_INTERVAL", "5"))  # seconds
