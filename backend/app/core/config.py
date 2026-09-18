from pathlib import Path
import os

PROJECT_NAME = "PulseHR AI"
PORT = 8020
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "db" / "pulsehr.sqlite3"
UPLOADS_DIR = DATA_DIR / "uploads"
EXPORTS_DIR = DATA_DIR / "exports"
SCHEMA_PATH = BASE_DIR / "app" / "db" / "schema.sql"

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text:latest")
EMBEDDING_DIM = 768

KAGGLE_DATASET = "yasirub/employee-attendance-ratings"
KAGGLE_LOCAL_CACHE = Path(os.path.expanduser("~/.cache/kagglehub/datasets/yasirub/employee-attendance-ratings/versions/1"))

# Ensure dirs exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
(DATA_DIR / "db").mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
