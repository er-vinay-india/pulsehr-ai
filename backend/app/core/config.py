from pathlib import Path
import os
from typing import Any
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class HighviewSettings(BaseSettings):
    """Centralized, typed, and environment-validated application settings."""
    model_config = SettingsConfigDict(
        env_prefix="HIGHVIEW_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    PROJECT_NAME: str = Field(default="HighView")
    PORT: int = Field(default_factory=lambda: int(os.getenv("HIGHVIEW_PORT") or os.getenv("PORT") or "8020"))
    ENVIRONMENT: str = Field(default_factory=lambda: os.getenv("HIGHVIEW_ENVIRONMENT") or os.getenv("APP_ENV") or "development")

    # Storage paths
    DATA_DIR: Path = Field(default_factory=lambda: Path(os.getenv("HIGHVIEW_DATA_DIR") or os.getenv("DATA_DIR") or str(BASE_DIR / "data")))
    DB_PATH: Path = Field(default_factory=lambda: Path(os.getenv("HIGHVIEW_DB_PATH") or os.getenv("DATABASE_PATH") or str(BASE_DIR / "data" / "db" / "pulsehr.sqlite3")))
    UPLOADS_DIR: Path = Field(default_factory=lambda: Path(os.getenv("HIGHVIEW_UPLOADS_DIR") or os.getenv("UPLOADS_DIR") or os.getenv("UPLOAD_DIR") or str(BASE_DIR / "data" / "uploads")))
    EXPORTS_DIR: Path = Field(default_factory=lambda: Path(os.getenv("HIGHVIEW_EXPORTS_DIR") or os.getenv("EXPORTS_DIR") or str(BASE_DIR / "data" / "exports")))
    PARQUET_STORAGE_DIR: Path = Field(default_factory=lambda: Path(os.getenv("HIGHVIEW_PARQUET_STORAGE_DIR") or os.getenv("PARQUET_STORAGE_DIR") or str(BASE_DIR / "data" / "datasets")))
    SCHEMA_PATH: Path = Field(default=BASE_DIR / "app" / "db" / "schema.sql")

    # Phase G3 Analytical Plane
    DUCKDB_ANALYTICS_ENABLED: bool = Field(default=True)
    G3_ANALYTICS_MODE: str = Field(default="SHADOW")  # SHADOW, CANARY, PRIMARY
    DUCKDB_MAX_MEMORY: str = Field(default="2GB")
    DUCKDB_THREADS: int = Field(default=2)
    PARQUET_COMPRESSION: str = Field(default="snappy")

    # Security & CORS
    ALLOWED_ORIGINS: list[str] = Field(
        default_factory=lambda: (
            [orig.strip() for orig in (os.getenv("HIGHVIEW_ALLOWED_ORIGINS") or os.getenv("ALLOWED_ORIGINS", "")).split(",") if orig.strip()]
            or [
                "http://localhost:5173",
                "http://localhost:5175",
                "http://127.0.0.1:5173",
                "http://127.0.0.1:5175",
            ]
        )
    )

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            if v.startswith("["):
                import json
                return json.loads(v)
            return [item.strip() for item in v.split(",") if item.strip()]
        return v

    # Ollama & Model configurations (supporting both direct and prefixed env vars)
    OLLAMA_BASE_URL: str = Field(default=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))
    OLLAMA_MODEL: str = Field(default=os.getenv("OLLAMA_MODEL", "qwen3.5:9b"))
    OLLAMA_EMBED_MODEL: str = Field(default=os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text:latest"))
    EMBEDDING_DIM: int = Field(default=768)

    # Kaggle cache
    KAGGLE_DATASET: str = Field(default="yasirub/employee-attendance-ratings")
    KAGGLE_LOCAL_CACHE: Path = Field(
        default=Path(os.path.expanduser("~/.cache/kagglehub/datasets/yasirub/employee-attendance-ratings/versions/1"))
    )

    # Presentation Memory & Semantic Retrieval Configuration
    PRESENTATION_MEMORY_ENABLED: bool = Field(
        default=os.getenv("PRESENTATION_MEMORY_ENABLED", "true").lower() in ("true", "1", "yes")
    )
    PRESENTATION_EMBEDDING_MODEL: str = Field(
        default=os.getenv("PRESENTATION_EMBEDDING_MODEL", "nomic-embed-text:latest")
    )
    PRESENTATION_MEMORY_TOP_K: int = Field(
        default=int(os.getenv("PRESENTATION_MEMORY_TOP_K", "8"))
    )
    PRESENTATION_MEMORY_MAX_CONTEXT_ITEMS: int = Field(
        default=int(os.getenv("PRESENTATION_MEMORY_MAX_CONTEXT_ITEMS", "6"))
    )
    PRESENTATION_MEMORY_MAX_TOTAL_CHARS: int = Field(
        default=int(os.getenv("PRESENTATION_MEMORY_MAX_TOTAL_CHARS", "4000"))
    )
    PRESENTATION_MEMORY_DB_PATH: Path = Field(
        default_factory=lambda: Path(os.getenv("HIGHVIEW_PRESENTATION_MEMORY_DB_PATH") or os.getenv("PRESENTATION_MEMORY_DB_PATH") or str(Path(os.getenv("HIGHVIEW_DATA_DIR") or os.getenv("DATA_DIR") or str(BASE_DIR / "data")) / "db" / "presentation_memory.sqlite3"))
    )
    PRESENTATION_MEMORY_VECTOR_STORE: str = Field(
        default=os.getenv("PRESENTATION_MEMORY_VECTOR_STORE", "sqlite_vec")
    )
    SYSTEM_FUNCTION_LIBRARY_DB_PATH: Path = Field(
        default_factory=lambda: Path(os.getenv("HIGHVIEW_SYSTEM_FUNCTION_LIBRARY_DB_PATH") or os.getenv("SYSTEM_FUNCTION_LIBRARY_DB_PATH") or str(Path(os.getenv("HIGHVIEW_DATA_DIR") or os.getenv("DATA_DIR") or str(BASE_DIR / "data")) / "db" / "system_function_library.sqlite3"))
    )

    # Presentation Director (Phase 2) Configuration
    PRESENTATION_DIRECTOR_ENABLED: bool = Field(
        default=os.getenv("PRESENTATION_DIRECTOR_ENABLED", "true").lower() in ("true", "1", "yes")
    )
    PRESENTATION_DIRECTOR_MODEL: str = Field(
        default=os.getenv("PRESENTATION_DIRECTOR_MODEL", "qwen3.5:9b")
    )
    PRESENTATION_DIRECTOR_MAX_RETRIES: int = Field(
        default=int(os.getenv("PRESENTATION_DIRECTOR_MAX_RETRIES", "2"))
    )
    PRESENTATION_DEFAULT_SLIDE_COUNT_MODE: str = Field(
        default=os.getenv("PRESENTATION_DEFAULT_SLIDE_COUNT_MODE", "ADAPTIVE")
    )

    # Presentation Execution Orchestration (Phase 3) Configuration
    PRESENTATION_ORCHESTRATOR_ENABLED: bool = Field(
        default=os.getenv("PRESENTATION_ORCHESTRATOR_ENABLED", "true").lower() in ("true", "1", "yes")
    )
    PRESENTATION_ORCHESTRATOR_MODEL: str = Field(
        default=os.getenv("PRESENTATION_ORCHESTRATOR_MODEL", "granite4:3b-h")
    )
    PRESENTATION_ORCHESTRATOR_FALLBACK_MODEL: str = Field(
        default=os.getenv("PRESENTATION_ORCHESTRATOR_FALLBACK_MODEL", "granite4:3b")
    )
    PRESENTATION_ANALYTICAL_MODEL: str = Field(
        default=os.getenv("PRESENTATION_ANALYTICAL_MODEL", "phi4-mini:latest")
    )
    PRESENTATION_DEEP_REASONING_MODEL: str = Field(
        default=os.getenv("PRESENTATION_DEEP_REASONING_MODEL", "deepseek-r1:7b")
    )
    PRESENTATION_MAX_TOOL_RETRIES: int = Field(
        default=int(os.getenv("PRESENTATION_MAX_TOOL_RETRIES", "2"))
    )
    PRESENTATION_MAX_MODEL_RETRIES: int = Field(
        default=int(os.getenv("PRESENTATION_MAX_MODEL_RETRIES", "1"))
    )
    PRESENTATION_ENABLE_DEEP_REASONING: bool = Field(
        default=os.getenv("PRESENTATION_ENABLE_DEEP_REASONING", "true").lower() in ("true", "1", "yes")
    )

    # Presentation Visual Intelligence & Modernization (Phase 4) Configuration
    PRESENTATION_VISUAL_ENGINE_ENABLED: bool = Field(
        default=os.getenv("PRESENTATION_VISUAL_ENGINE_ENABLED", "true").lower() in ("true", "1", "yes")
    )
    PRESENTATION_LAYOUT_SYSTEM: str = Field(
        default=os.getenv("PRESENTATION_LAYOUT_SYSTEM", "scoped_bootstrap")
    )
    PRESENTATION_CHART_ENGINE: str = Field(
        default=os.getenv("PRESENTATION_CHART_ENGINE", "echarts")
    )
    PRESENTATION_ENABLE_ADVANCED_CHARTS: bool = Field(
        default=os.getenv("PRESENTATION_ENABLE_ADVANCED_CHARTS", "true").lower() in ("true", "1", "yes")
    )
    PRESENTATION_ENABLE_ANIMATIONS: bool = Field(
        default=os.getenv("PRESENTATION_ENABLE_ANIMATIONS", "true").lower() in ("true", "1", "yes")
    )
    PRESENTATION_ENABLE_ACCESSIBILITY_VALIDATION: bool = Field(
        default=os.getenv("PRESENTATION_ENABLE_ACCESSIBILITY_VALIDATION", "true").lower() in ("true", "1", "yes")
    )

    # Presentation Visual Quality Assurance & Repair (Phase 5) Configuration
    PRESENTATION_VISUAL_QA_ENABLED: bool = Field(
        default=os.getenv("PRESENTATION_VISUAL_QA_ENABLED", "true").lower() in ("true", "1", "yes")
    )
    PRESENTATION_VISUAL_QA_MODEL: str = Field(
        default=os.getenv("PRESENTATION_VISUAL_QA_MODEL", "gemma4:12b")
    )
    PRESENTATION_VISUAL_QA_MODE: str = Field(
        default=os.getenv("PRESENTATION_VISUAL_QA_MODE", "STANDARD").upper()
    )
    PRESENTATION_VISUAL_QA_MAX_REPAIRS: int = Field(
        default=int(os.getenv("PRESENTATION_VISUAL_QA_MAX_REPAIRS", "2"))
    )
    PRESENTATION_VISUAL_QA_MIN_SCORE: float = Field(
        default=float(os.getenv("PRESENTATION_VISUAL_QA_MIN_SCORE", "0.80"))
    )
    PRESENTATION_VISUAL_QA_CAPTURE_SCREENSHOTS: bool = Field(
        default=os.getenv("PRESENTATION_VISUAL_QA_CAPTURE_SCREENSHOTS", "true").lower() in ("true", "1", "yes")
    )
    PRESENTATION_VISUAL_QA_KEEP_SCREENSHOTS: bool = Field(
        default=os.getenv("PRESENTATION_VISUAL_QA_KEEP_SCREENSHOTS", "false").lower() in ("true", "1", "yes")
    )
    PRESENTATION_VISUAL_QA_DIR: Path = Field(
        default=BASE_DIR / "data" / "exports" / "qa"
    )

    # Assistant branding & identity
    ASSISTANT_NAME: str = Field(default=os.getenv("ASSISTANT_NAME", "HRIDAY"))
    ASSISTANT_PRODUCT_NAME: str = Field(default=os.getenv("ASSISTANT_PRODUCT_NAME", "HighView"))
    ASSISTANT_IDENTITY_ENABLED: bool = Field(
        default=os.getenv("ASSISTANT_IDENTITY_ENABLED", "true").lower() in ("true", "1", "yes")
    )
    ASSISTANT_HIDE_MODEL_IDENTITY: bool = Field(
        default=os.getenv("ASSISTANT_HIDE_MODEL_IDENTITY", "true").lower() in ("true", "1", "yes")
    )
    ASSISTANT_ALLOW_MODEL_DISCLOSURE: bool = Field(
        default=os.getenv("ASSISTANT_ALLOW_MODEL_DISCLOSURE", "true").lower() in ("true", "1", "yes")
    )
    ASSISTANT_MAX_IDENTITY_RETRIES: int = Field(
        default=max(0, min(1, int(os.getenv("ASSISTANT_MAX_IDENTITY_RETRIES", "1"))))
    )


# Instantiate centralized settings singleton
settings = HighviewSettings()

# Ensure directories exist
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
(settings.DATA_DIR / "db").mkdir(parents=True, exist_ok=True)
settings.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
settings.EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
settings.PRESENTATION_VISUAL_QA_DIR.mkdir(parents=True, exist_ok=True)

# -----------------------------------------------------------------------------
# Module-level exports for 100% backward compatibility across entire codebase
# -----------------------------------------------------------------------------
PROJECT_NAME = settings.PROJECT_NAME
PORT = settings.PORT
ENVIRONMENT = settings.ENVIRONMENT
DATA_DIR = settings.DATA_DIR
DB_PATH = settings.DB_PATH
UPLOADS_DIR = settings.UPLOADS_DIR
EXPORTS_DIR = settings.EXPORTS_DIR
PARQUET_STORAGE_DIR = settings.PARQUET_STORAGE_DIR
SCHEMA_PATH = settings.SCHEMA_PATH
ALLOWED_ORIGINS = settings.ALLOWED_ORIGINS

OLLAMA_BASE_URL = settings.OLLAMA_BASE_URL
OLLAMA_MODEL = settings.OLLAMA_MODEL
OLLAMA_EMBED_MODEL = settings.OLLAMA_EMBED_MODEL
EMBEDDING_DIM = settings.EMBEDDING_DIM

KAGGLE_DATASET = settings.KAGGLE_DATASET
KAGGLE_LOCAL_CACHE = settings.KAGGLE_LOCAL_CACHE

PRESENTATION_MEMORY_ENABLED = settings.PRESENTATION_MEMORY_ENABLED
PRESENTATION_EMBEDDING_MODEL = settings.PRESENTATION_EMBEDDING_MODEL
PRESENTATION_MEMORY_TOP_K = settings.PRESENTATION_MEMORY_TOP_K
PRESENTATION_MEMORY_MAX_CONTEXT_ITEMS = settings.PRESENTATION_MEMORY_MAX_CONTEXT_ITEMS
PRESENTATION_MEMORY_MAX_TOTAL_CHARS = settings.PRESENTATION_MEMORY_MAX_TOTAL_CHARS
PRESENTATION_MEMORY_DB_PATH = settings.PRESENTATION_MEMORY_DB_PATH
PRESENTATION_MEMORY_VECTOR_STORE = settings.PRESENTATION_MEMORY_VECTOR_STORE
SYSTEM_FUNCTION_LIBRARY_DB_PATH = settings.SYSTEM_FUNCTION_LIBRARY_DB_PATH

PRESENTATION_DIRECTOR_ENABLED = settings.PRESENTATION_DIRECTOR_ENABLED
PRESENTATION_DIRECTOR_MODEL = settings.PRESENTATION_DIRECTOR_MODEL
PRESENTATION_DIRECTOR_MAX_RETRIES = settings.PRESENTATION_DIRECTOR_MAX_RETRIES
PRESENTATION_DEFAULT_SLIDE_COUNT_MODE = settings.PRESENTATION_DEFAULT_SLIDE_COUNT_MODE

PRESENTATION_ORCHESTRATOR_ENABLED = settings.PRESENTATION_ORCHESTRATOR_ENABLED
PRESENTATION_ORCHESTRATOR_MODEL = settings.PRESENTATION_ORCHESTRATOR_MODEL
PRESENTATION_ORCHESTRATOR_FALLBACK_MODEL = settings.PRESENTATION_ORCHESTRATOR_FALLBACK_MODEL
PRESENTATION_ANALYTICAL_MODEL = settings.PRESENTATION_ANALYTICAL_MODEL
PRESENTATION_DEEP_REASONING_MODEL = settings.PRESENTATION_DEEP_REASONING_MODEL
PRESENTATION_MAX_TOOL_RETRIES = settings.PRESENTATION_MAX_TOOL_RETRIES
PRESENTATION_MAX_MODEL_RETRIES = settings.PRESENTATION_MAX_MODEL_RETRIES
PRESENTATION_ENABLE_DEEP_REASONING = settings.PRESENTATION_ENABLE_DEEP_REASONING

PRESENTATION_VISUAL_ENGINE_ENABLED = settings.PRESENTATION_VISUAL_ENGINE_ENABLED
PRESENTATION_LAYOUT_SYSTEM = settings.PRESENTATION_LAYOUT_SYSTEM
PRESENTATION_CHART_ENGINE = settings.PRESENTATION_CHART_ENGINE
PRESENTATION_ENABLE_ADVANCED_CHARTS = settings.PRESENTATION_ENABLE_ADVANCED_CHARTS
PRESENTATION_ENABLE_ANIMATIONS = settings.PRESENTATION_ENABLE_ANIMATIONS
PRESENTATION_ENABLE_ACCESSIBILITY_VALIDATION = settings.PRESENTATION_ENABLE_ACCESSIBILITY_VALIDATION

PRESENTATION_VISUAL_QA_ENABLED = settings.PRESENTATION_VISUAL_QA_ENABLED
PRESENTATION_VISUAL_QA_MODEL = settings.PRESENTATION_VISUAL_QA_MODEL
PRESENTATION_VISUAL_QA_MODE = settings.PRESENTATION_VISUAL_QA_MODE
PRESENTATION_VISUAL_QA_MAX_REPAIRS = settings.PRESENTATION_VISUAL_QA_MAX_REPAIRS
PRESENTATION_VISUAL_QA_MIN_SCORE = settings.PRESENTATION_VISUAL_QA_MIN_SCORE
PRESENTATION_VISUAL_QA_CAPTURE_SCREENSHOTS = settings.PRESENTATION_VISUAL_QA_CAPTURE_SCREENSHOTS
PRESENTATION_VISUAL_QA_KEEP_SCREENSHOTS = settings.PRESENTATION_VISUAL_QA_KEEP_SCREENSHOTS
PRESENTATION_VISUAL_QA_DIR = settings.PRESENTATION_VISUAL_QA_DIR

ASSISTANT_NAME = settings.ASSISTANT_NAME
ASSISTANT_PRODUCT_NAME = settings.ASSISTANT_PRODUCT_NAME
ASSISTANT_IDENTITY_ENABLED = settings.ASSISTANT_IDENTITY_ENABLED
ASSISTANT_HIDE_MODEL_IDENTITY = settings.ASSISTANT_HIDE_MODEL_IDENTITY
ASSISTANT_ALLOW_MODEL_DISCLOSURE = settings.ASSISTANT_ALLOW_MODEL_DISCLOSURE
ASSISTANT_MAX_IDENTITY_RETRIES = settings.ASSISTANT_MAX_IDENTITY_RETRIES
