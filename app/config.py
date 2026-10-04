import os
from dotenv import load_dotenv
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

ENV_PATH = PROJECT_ROOT / ".env"

PROJECT_DATA = PROJECT_ROOT / "DATA"

load_dotenv(dotenv_path=ENV_PATH, override=True)

class Settings:
    # --- GOOGLE DRIVE CONFIG ---
    GOOGLE_DRIVE_ROOT_FOLDER_ID = os.getenv("GOOGLE_DRIVE_ROOT_FOLDER_ID")
    DRIVE_LOCAL_ROOT = os.getenv("DRIVE_LOCAL_ROOT","DATA")

    # --- REASONING ENGINE (GROQ) ---
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    GROQ_FALLBACK_API_KEY = os.getenv("GROQ_FALLBACK_API_KEY")
    GROQ_MODEL = "openai/gpt-oss-120b"

    # --- EMBEDDING MODEL (GEMINI) ---
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    EMBEDDING_MODEL = "models/gemini-embedding-001"
    EMBEDDING_DIMENSION = 3072

    # --- VECTOR DB (QDRANT) ---
    QDRANT_CLUSTER_ENDPOINT = os.getenv("QDRANT_CLUSTER_ENDPOINT")
    QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
    QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION","DriveRAG")

    # --- OBSERVABILITY ---
    LANGSMITH_TRACING = os.getenv("LANGSMITH_TRACING","true")
    LANGSMITH_ENDPOINT = os.getenv("LANGSMITH_ENDPOINT","https://api.smith.langchain.com")
    LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY")
    LANGSMITH_PROJECT = os.getenv("LANGSMITH_PROJECT","DriveRAG")


    LOGFIRE_TOKEN = os.getenv("LOGFIRE_TOKEN")

    # --- CHUNCKING SETTING ---
    CHUNK_SIZE = 800
    CHUNK_OVERLAP = 120
    BATCH_SIZE = 2

    # --- CHAT SETTING ---
    MAX_HISTORY_MESSAGES = 10
    MAX_QUERY_LENGTH = 300
    
settings = Settings()