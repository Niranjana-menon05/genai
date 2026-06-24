import os
from pathlib import Path
from dotenv import load_dotenv

# Base Directory of the backend
BASE_DIR = Path(__file__).resolve().parent

# Load environment variables from .env file
load_dotenv(dotenv_path=BASE_DIR / ".env")

# API Keys
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# Server Settings
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))
DEBUG = os.getenv("DEBUG", "True").lower() in ("true", "1", "yes")

# Storage Paths
DB_DIR = Path(os.getenv("DB_DIR", BASE_DIR / "chroma_db"))
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", BASE_DIR / "uploads"))

# Ensure storage paths exist
DB_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Mock Mode triggers if GROQ_API_KEY is not set or equals placeholder
IS_MOCK_MODE = not GROQ_API_KEY or GROQ_API_KEY.startswith("your_groq_api_key")

print(f"--- AI Lecture Companion Configuration ---")
print(f"Groq API Key: {'FOUND' if GROQ_API_KEY and not IS_MOCK_MODE else 'NOT FOUND / USING MOCK MODE'}")
print(f"Mock Mode: {IS_MOCK_MODE}")
print(f"Database Directory: {DB_DIR}")
print(f"Upload Directory: {UPLOAD_DIR}")
print(f"------------------------------------------")
