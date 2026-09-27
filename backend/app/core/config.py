from pathlib import Path
import os

PROJECT_NAME = "HighView"
PORT = 8020
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "db" / "pulsehr.sqlite3"
UPLOADS_DIR = DATA_DIR / "uploads"
EXPORTS_DIR = DATA_DIR / "exports"
SCHEMA_PATH = BASE_DIR / "app" / "db" / "schema.sql"

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3.5:9b")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text:latest")
EMBEDDING_DIM = 768

KAGGLE_DATASET = "yasirub/employee-attendance-ratings"
KAGGLE_LOCAL_CACHE = Path(os.path.expanduser("~/.cache/kagglehub/datasets/yasirub/employee-attendance-ratings/versions/1"))

# Ensure dirs exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
(DATA_DIR / "db").mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

# Presentation Memory & Semantic Retrieval Configuration
PRESENTATION_MEMORY_ENABLED = os.getenv("PRESENTATION_MEMORY_ENABLED", "true").lower() in ("true", "1", "yes")
PRESENTATION_EMBEDDING_MODEL = os.getenv("PRESENTATION_EMBEDDING_MODEL", OLLAMA_EMBED_MODEL)
PRESENTATION_MEMORY_TOP_K = int(os.getenv("PRESENTATION_MEMORY_TOP_K", "8"))
PRESENTATION_MEMORY_MAX_CONTEXT_ITEMS = int(os.getenv("PRESENTATION_MEMORY_MAX_CONTEXT_ITEMS", "6"))
PRESENTATION_MEMORY_MAX_TOTAL_CHARS = int(os.getenv("PRESENTATION_MEMORY_MAX_TOTAL_CHARS", "4000"))
PRESENTATION_MEMORY_DB_PATH = DATA_DIR / "db" / "presentation_memory.sqlite3"
PRESENTATION_MEMORY_VECTOR_STORE = os.getenv("PRESENTATION_MEMORY_VECTOR_STORE", "sqlite_vec")

# Presentation Director (Phase 2) Configuration
PRESENTATION_DIRECTOR_ENABLED = os.getenv("PRESENTATION_DIRECTOR_ENABLED", "true").lower() in ("true", "1", "yes")
PRESENTATION_DIRECTOR_MODEL = os.getenv("PRESENTATION_DIRECTOR_MODEL", OLLAMA_MODEL)
PRESENTATION_DIRECTOR_MAX_RETRIES = int(os.getenv("PRESENTATION_DIRECTOR_MAX_RETRIES", "2"))
PRESENTATION_DEFAULT_SLIDE_COUNT_MODE = os.getenv("PRESENTATION_DEFAULT_SLIDE_COUNT_MODE", "ADAPTIVE")

# Presentation Execution Orchestration (Phase 3) Configuration
PRESENTATION_ORCHESTRATOR_ENABLED = os.getenv("PRESENTATION_ORCHESTRATOR_ENABLED", "true").lower() in ("true", "1", "yes")
PRESENTATION_ORCHESTRATOR_MODEL = os.getenv("PRESENTATION_ORCHESTRATOR_MODEL", "granite4:3b-h")
PRESENTATION_ORCHESTRATOR_FALLBACK_MODEL = os.getenv("PRESENTATION_ORCHESTRATOR_FALLBACK_MODEL", "granite4:3b")
PRESENTATION_ANALYTICAL_MODEL = os.getenv("PRESENTATION_ANALYTICAL_MODEL", "phi4-mini:latest")
PRESENTATION_DEEP_REASONING_MODEL = os.getenv("PRESENTATION_DEEP_REASONING_MODEL", "deepseek-r1:7b")
PRESENTATION_MAX_TOOL_RETRIES = int(os.getenv("PRESENTATION_MAX_TOOL_RETRIES", "2"))
PRESENTATION_MAX_MODEL_RETRIES = int(os.getenv("PRESENTATION_MAX_MODEL_RETRIES", "1"))
PRESENTATION_ENABLE_DEEP_REASONING = os.getenv("PRESENTATION_ENABLE_DEEP_REASONING", "true").lower() in ("true", "1", "yes")

# Presentation Visual Intelligence & Modernization (Phase 4) Configuration
PRESENTATION_VISUAL_ENGINE_ENABLED = os.getenv("PRESENTATION_VISUAL_ENGINE_ENABLED", "true").lower() in ("true", "1", "yes")
PRESENTATION_LAYOUT_SYSTEM = os.getenv("PRESENTATION_LAYOUT_SYSTEM", "scoped_bootstrap")
PRESENTATION_CHART_ENGINE = os.getenv("PRESENTATION_CHART_ENGINE", "echarts")
PRESENTATION_ENABLE_ADVANCED_CHARTS = os.getenv("PRESENTATION_ENABLE_ADVANCED_CHARTS", "true").lower() in ("true", "1", "yes")
PRESENTATION_ENABLE_ANIMATIONS = os.getenv("PRESENTATION_ENABLE_ANIMATIONS", "true").lower() in ("true", "1", "yes")
PRESENTATION_ENABLE_ACCESSIBILITY_VALIDATION = os.getenv("PRESENTATION_ENABLE_ACCESSIBILITY_VALIDATION", "true").lower() in ("true", "1", "yes")

# Presentation Visual Quality Assurance & Repair (Phase 5) Configuration
PRESENTATION_VISUAL_QA_ENABLED = os.getenv("PRESENTATION_VISUAL_QA_ENABLED", "true").lower() in ("true", "1", "yes")
PRESENTATION_VISUAL_QA_MODEL = os.getenv("PRESENTATION_VISUAL_QA_MODEL", "gemma4:12b")
PRESENTATION_VISUAL_QA_MODE = os.getenv("PRESENTATION_VISUAL_QA_MODE", "STANDARD").upper()
PRESENTATION_VISUAL_QA_MAX_REPAIRS = int(os.getenv("PRESENTATION_VISUAL_QA_MAX_REPAIRS", "2"))
PRESENTATION_VISUAL_QA_MIN_SCORE = float(os.getenv("PRESENTATION_VISUAL_QA_MIN_SCORE", "0.80"))
PRESENTATION_VISUAL_QA_CAPTURE_SCREENSHOTS = os.getenv("PRESENTATION_VISUAL_QA_CAPTURE_SCREENSHOTS", "true").lower() in ("true", "1", "yes")
PRESENTATION_VISUAL_QA_KEEP_SCREENSHOTS = os.getenv("PRESENTATION_VISUAL_QA_KEEP_SCREENSHOTS", "false").lower() in ("true", "1", "yes")
PRESENTATION_VISUAL_QA_DIR = EXPORTS_DIR / "qa"
PRESENTATION_VISUAL_QA_DIR.mkdir(parents=True, exist_ok=True)



