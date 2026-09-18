from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core import config
from .db.database import init_db, get_connection
from .services.kaggle_loader import load_and_seed_kaggle_dataset
from .services.rag_service import index_all_employees
from .routers import analytics, employees, upload, copilot, reports

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup sequence
    print("[PulseHR AI] Initializing database and vector tables...")
    init_db()
    print("[PulseHR AI] Loading Kaggle employee attendance & ratings dataset...")
    load_and_seed_kaggle_dataset()
    print("[PulseHR AI] Indexing employee profiles into SQLite vector DB...")
    index_all_employees()
    print("[PulseHR AI] Startup completed. System ready on port", config.PORT)
    yield
    print("[PulseHR AI] Shutting down...")

app = FastAPI(
    title="PulseHR AI API",
    description="Intelligent Tabular & HR Attendance Analytics Platform with RAG Vector Inference & Presentations",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analytics.router)
app.include_router(employees.router)
app.include_router(upload.router)
app.include_router(copilot.router)
app.include_router(reports.router)

@app.get("/api/health")
def health_check():
    conn = get_connection()
    try:
        emp_count = conn.execute("SELECT COUNT(*) FROM employees").fetchone()[0]
        alert_count = conn.execute("SELECT COUNT(*) FROM hr_alerts").fetchone()[0]
        chunk_count = conn.execute("SELECT COUNT(*) FROM tabular_chunks").fetchone()[0]
        return {
            "status": "online",
            "app": config.PROJECT_NAME,
            "version": "1.0.0",
            "database": {
                "employees": emp_count,
                "hr_alerts": alert_count,
                "vector_chunks": chunk_count,
                "db_path": str(config.DB_PATH)
            },
            "models": {
                "llm": config.OLLAMA_MODEL,
                "embeddings": config.OLLAMA_EMBED_MODEL,
                "embedding_dimension": config.EMBEDDING_DIM
            }
        }
    finally:
        conn.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8020, reload=True)
