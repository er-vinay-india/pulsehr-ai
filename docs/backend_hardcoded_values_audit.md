# Backend Hardcoded Values Audit Log

- **Total Backend Python Files Scanned:** 539
- **Files with Hardcoded Values Found:** 36
- **Files Clean (No Hard Values Found):** 503
- **Total Hardcoded Occurrences Detected:** 168

---

## Module Overview

| Module Directory | Total Files | Flagged Files | Clean Files |
|---|---|---|---|
| `app/__init__.py` | 1 | 0 | 1 |
| `app/agent` | 24 | 0 | 24 |
| `app/analytics` | 8 | 0 | 8 |
| `app/api` | 5 | 0 | 5 |
| `app/cache` | 7 | 0 | 7 |
| `app/context` | 3 | 0 | 3 |
| `app/core` | 5 | 3 | 2 |
| `app/db` | 14 | 1 | 13 |
| `app/jobs` | 7 | 0 | 7 |
| `app/main.py` | 1 | 1 | 0 |
| `app/mcp` | 13 | 0 | 13 |
| `app/observability` | 18 | 1 | 17 |
| `app/optimization` | 18 | 3 | 15 |
| `app/routers` | 17 | 0 | 17 |
| `app/services` | 398 | 27 | 371 |

---

## File-By-File Audit: Files With Hardcoded Values

### 1. `app/core/config.py`
- **Total Lines:** 278
- **Hard values found:** 22 places

| Line | Category | Hardcoded Value | Code Snippet |
|---|---|---|---|
| 25 | Hardcoded Database Filename | `pulsehr.sqlite3` | `DB_PATH: Path = Field(default_factory=lambda: Path(os.getenv("HIGHVIEW_DB_PATH") or os.getenv("DATABASE_PATH")` |
| 43 | Hardcoded Endpoint / URL | `http://localhost:5173` | `"http://localhost:5173",` |
| 43 | Hardcoded Port | `5173` | `"http://localhost:5173",` |
| 44 | Hardcoded Endpoint / URL | `http://localhost:5175` | `"http://localhost:5175",` |
| 44 | Hardcoded Port | `5175` | `"http://localhost:5175",` |
| 45 | Hardcoded Endpoint / URL | `http://127.0.0.1:5173` | `"http://127.0.0.1:5173",` |
| 45 | Hardcoded Port | `5173` | `"http://127.0.0.1:5173",` |
| 46 | Hardcoded Endpoint / URL | `http://127.0.0.1:5175` | `"http://127.0.0.1:5175",` |
| 46 | Hardcoded Port | `5175` | `"http://127.0.0.1:5175",` |
| 62 | Hardcoded Endpoint / URL | `http://localhost:11434` | `OLLAMA_BASE_URL: str = Field(default=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))` |
| 62 | Hardcoded Port | `11434` | `OLLAMA_BASE_URL: str = Field(default=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))` |
| 63 | Hardcoded AI Model Tag | `qwen3.5:9b` | `OLLAMA_MODEL: str = Field(default=os.getenv("OLLAMA_MODEL", "qwen3.5:9b"))` |
| 64 | Hardcoded AI Model Tag | `nomic-embed-text:latest` | `OLLAMA_EMBED_MODEL: str = Field(default=os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text:latest"))` |
| 78 | Hardcoded AI Model Tag | `nomic-embed-text:latest` | `default=os.getenv("PRESENTATION_EMBEDDING_MODEL", "nomic-embed-text:latest")` |
| 90 | Hardcoded Database Filename | `presentation_memory.sqlite3` | `default_factory=lambda: Path(os.getenv("HIGHVIEW_PRESENTATION_MEMORY_DB_PATH") or os.getenv("PRESENTATION_MEMO` |
| 96 | Hardcoded Database Filename | `system_function_library.sqlite3` | `default_factory=lambda: Path(os.getenv("HIGHVIEW_SYSTEM_FUNCTION_LIBRARY_DB_PATH") or os.getenv("SYSTEM_FUNCTI` |
| 104 | Hardcoded AI Model Tag | `qwen3.5:9b` | `default=os.getenv("PRESENTATION_DIRECTOR_MODEL", "qwen3.5:9b")` |
| 118 | Hardcoded AI Model Tag | `granite4:3b-h` | `default=os.getenv("PRESENTATION_ORCHESTRATOR_MODEL", "granite4:3b-h")` |
| 121 | Hardcoded AI Model Tag | `granite4:3b` | `default=os.getenv("PRESENTATION_ORCHESTRATOR_FALLBACK_MODEL", "granite4:3b")` |
| 124 | Hardcoded AI Model Tag | `phi4-mini:latest` | `default=os.getenv("PRESENTATION_ANALYTICAL_MODEL", "phi4-mini:latest")` |
| 127 | Hardcoded AI Model Tag | `deepseek-r1:7b` | `default=os.getenv("PRESENTATION_DEEP_REASONING_MODEL", "deepseek-r1:7b")` |
| 164 | Hardcoded AI Model Tag | `gemma4:12b` | `default=os.getenv("PRESENTATION_VISUAL_QA_MODEL", "gemma4:12b")` |

### 2. `app/core/db_isolation.py`
- **Total Lines:** 66
- **Hard values found:** 1 places

| Line | Category | Hardcoded Value | Code Snippet |
|---|---|---|---|
| 12 | Hardcoded Database Filename | `pulsehr.sqlite3` | `LIVE_DB_PATH = (Path(__file__).resolve().parent.parent.parent / "data" / "db" / "pulsehr.sqlite3").resolve()` |

### 3. `app/core/models_config.py`
- **Total Lines:** 81
- **Hard values found:** 12 places

| Line | Category | Hardcoded Value | Code Snippet |
|---|---|---|---|
| 30 | Hardcoded AI Model Tag | `qwen3.5:2b` | `primary=os.getenv("MODEL_ROLE_COORDINATOR_PRIMARY", "qwen3.5:2b"),` |
| 31 | Hardcoded AI Model Tag | `phi4-mini:latest` | `fallback=os.getenv("MODEL_ROLE_COORDINATOR_FALLBACK", "phi4-mini:latest"),` |
| 37 | Hardcoded AI Model Tag | `phi4-mini:latest` | `primary=os.getenv("MODEL_ROLE_FAST_PRIMARY", "phi4-mini:latest"),` |
| 38 | Hardcoded AI Model Tag | `llama3.1:8b` | `fallback=os.getenv("MODEL_ROLE_FAST_FALLBACK", "llama3.1:8b"),` |
| 44 | Hardcoded AI Model Tag | `qwen3.5:9b` | `primary=os.getenv("MODEL_ROLE_ANALYST_PRIMARY", "qwen3.5:9b"),` |
| 45 | Hardcoded AI Model Tag | `gemma4:12b` | `fallback=os.getenv("MODEL_ROLE_ANALYST_FALLBACK", "gemma4:12b"),` |
| 51 | Hardcoded AI Model Tag | `deepseek-r1:7b` | `primary=os.getenv("MODEL_ROLE_REASONER_PRIMARY", "deepseek-r1:7b"),` |
| 52 | Hardcoded AI Model Tag | `qwen3.5:9b` | `fallback=os.getenv("MODEL_ROLE_REASONER_FALLBACK", "qwen3.5:9b"),` |
| 58 | Hardcoded AI Model Tag | `gemma4:12b` | `primary=os.getenv("MODEL_ROLE_WRITER_PRIMARY", "gemma4:12b"),` |
| 59 | Hardcoded AI Model Tag | `qwen3.5:9b` | `fallback=os.getenv("MODEL_ROLE_WRITER_FALLBACK", "qwen3.5:9b"),` |
| 65 | Hardcoded AI Model Tag | `deepseek-r1:7b` | `primary=os.getenv("MODEL_ROLE_CRITIC_PRIMARY", "deepseek-r1:7b"),` |
| 66 | Hardcoded AI Model Tag | `llama3.1:8b` | `fallback=os.getenv("MODEL_ROLE_CRITIC_FALLBACK", "llama3.1:8b"),` |

### 4. `app/db/migrations/0004_add_industry_personas.py`
- **Total Lines:** 72
- **Hard values found:** 2 places

| Line | Category | Hardcoded Value | Code Snippet |
|---|---|---|---|
| 36 | Mock / Synthetic Data Marker | `INDUSTRY_PERSONAS` | `from app.services.presentation.industry_personas_seed import INDUSTRY_PERSONAS` |
| 37 | Mock / Synthetic Data Marker | `INDUSTRY_PERSONAS` | `for p in INDUSTRY_PERSONAS:` |

### 5. `app/main.py`
- **Total Lines:** 89
- **Hard values found:** 2 places

| Line | Category | Hardcoded Value | Code Snippet |
|---|---|---|---|
| 89 | Hardcoded Localhost / IP | `0.0.0.0` | `uvicorn.run("app.main:app", host="0.0.0.0", port=8020, reload=True)` |
| 89 | Hardcoded Port | `8020` | `uvicorn.run("app.main:app", host="0.0.0.0", port=8020, reload=True)` |

### 6. `app/observability/service.py`
- **Total Lines:** 208
- **Hard values found:** 2 places

| Line | Category | Hardcoded Value | Code Snippet |
|---|---|---|---|
| 93 | Hardcoded AI Model Tag | `qwen3.5:9b` | `primary_model="qwen3.5:9b",` |
| 94 | Hardcoded AI Model Tag | `qwen3.5:9b` | `actual_model=models_used[0] if models_used else "qwen3.5:9b",` |

### 7. `app/optimization/analyzers/model_routing.py`
- **Total Lines:** 103
- **Hard values found:** 6 places

| Line | Category | Hardcoded Value | Code Snippet |
|---|---|---|---|
| 69 | Hardcoded AI Model Tag | `qwen3.5:9b` | `"target_model": "qwen3.5:9b",` |
| 86 | Hardcoded AI Model Tag | `qwen3.5:9b` | `actual_model = first_slow.get("actual_model", "qwen3.5:9b")` |
| 87 | Hardcoded AI Model Tag | `gemma4:12b` | `alternate_model = "gemma4:12b" if actual_model != "gemma4:12b" else "qwen3.5:9b"` |
| 87 | Hardcoded AI Model Tag | `gemma4:12b` | `alternate_model = "gemma4:12b" if actual_model != "gemma4:12b" else "qwen3.5:9b"` |
| 87 | Hardcoded AI Model Tag | `qwen3.5:9b` | `alternate_model = "gemma4:12b" if actual_model != "gemma4:12b" else "qwen3.5:9b"` |
| 94 | Hardcoded AI Model Tag | `phi4-mini:latest` | `"cascade": {task_type: [alternate_model, actual_model, "phi4-mini:latest"]},` |

### 8. `app/optimization/contracts.py`
- **Total Lines:** 241
- **Hard values found:** 15 places

| Line | Category | Hardcoded Value | Code Snippet |
|---|---|---|---|
| 90 | Hardcoded AI Model Tag | `phi4-mini:latest` | `"STRUCTURAL_AI": ["phi4-mini:latest", "qwen3.5:2b", "llama3.1:8b"],` |
| 90 | Hardcoded AI Model Tag | `qwen3.5:2b` | `"STRUCTURAL_AI": ["phi4-mini:latest", "qwen3.5:2b", "llama3.1:8b"],` |
| 90 | Hardcoded AI Model Tag | `llama3.1:8b` | `"STRUCTURAL_AI": ["phi4-mini:latest", "qwen3.5:2b", "llama3.1:8b"],` |
| 91 | Hardcoded AI Model Tag | `qwen3.5:2b` | `"SEMANTIC_AI": ["qwen3.5:2b", "phi4-mini:latest", "qwen3.5:9b"],` |
| 91 | Hardcoded AI Model Tag | `phi4-mini:latest` | `"SEMANTIC_AI": ["qwen3.5:2b", "phi4-mini:latest", "qwen3.5:9b"],` |
| 91 | Hardcoded AI Model Tag | `qwen3.5:9b` | `"SEMANTIC_AI": ["qwen3.5:2b", "phi4-mini:latest", "qwen3.5:9b"],` |
| 92 | Hardcoded AI Model Tag | `gemma4:12b` | `"NARRATIVE_AI": ["gemma4:12b", "qwen3.5:9b", "phi4-mini:latest"],` |
| 92 | Hardcoded AI Model Tag | `qwen3.5:9b` | `"NARRATIVE_AI": ["gemma4:12b", "qwen3.5:9b", "phi4-mini:latest"],` |
| 92 | Hardcoded AI Model Tag | `phi4-mini:latest` | `"NARRATIVE_AI": ["gemma4:12b", "qwen3.5:9b", "phi4-mini:latest"],` |
| 93 | Hardcoded AI Model Tag | `qwen3.5:9b` | `"AGENTIC_AI": ["qwen3.5:9b", "gemma4:12b", "phi4-mini:latest"],` |
| 93 | Hardcoded AI Model Tag | `gemma4:12b` | `"AGENTIC_AI": ["qwen3.5:9b", "gemma4:12b", "phi4-mini:latest"],` |
| 93 | Hardcoded AI Model Tag | `phi4-mini:latest` | `"AGENTIC_AI": ["qwen3.5:9b", "gemma4:12b", "phi4-mini:latest"],` |
| 94 | Hardcoded AI Model Tag | `gemma4:12b` | `"PRESENTATION_AI": ["gemma4:12b", "qwen3.5:9b", "phi4-mini:latest"],` |
| 94 | Hardcoded AI Model Tag | `qwen3.5:9b` | `"PRESENTATION_AI": ["gemma4:12b", "qwen3.5:9b", "phi4-mini:latest"],` |
| 94 | Hardcoded AI Model Tag | `phi4-mini:latest` | `"PRESENTATION_AI": ["gemma4:12b", "qwen3.5:9b", "phi4-mini:latest"],` |

### 9. `app/optimization/shadow_evaluator.py`
- **Total Lines:** 65
- **Hard values found:** 2 places

| Line | Category | Hardcoded Value | Code Snippet |
|---|---|---|---|
| 54 | Hardcoded AI Model Tag | `qwen3.5:9b` | `active_model="qwen3.5:9b",` |
| 55 | Hardcoded AI Model Tag | `qwen3.5:9b` | `candidate_model=candidate_policy.model_routing_policy.cascades.get("AGENTIC_AI", ["qwen3.5:9b"])[0],` |

### 10. `app/services/adaptive_dashboard/scenario_engine.py`
- **Total Lines:** 887
- **Hard values found:** 2 places

| Line | Category | Hardcoded Value | Code Snippet |
|---|---|---|---|
| 253 | Mock / Synthetic Data Marker | `mock_data` | `mock_data = [` |
| 264 | Mock / Synthetic Data Marker | `mock_data` | `return mock_data, "Total_Attendance", "Approved_Leaves", "Department"` |

### 11. `app/services/adaptive_table_reconstruction/model_escalator.py`
- **Total Lines:** 397
- **Hard values found:** 5 places

| Line | Category | Hardcoded Value | Code Snippet |
|---|---|---|---|
| 45 | Hardcoded AI Model Tag | `qwen3.5:2b` | `LIGHTWEIGHT_MODELS = ["qwen3.5:2b", "phi4-mini:latest", "granite4:3b", "qwen3.5:9b"]` |
| 45 | Hardcoded AI Model Tag | `phi4-mini:latest` | `LIGHTWEIGHT_MODELS = ["qwen3.5:2b", "phi4-mini:latest", "granite4:3b", "qwen3.5:9b"]` |
| 45 | Hardcoded AI Model Tag | `granite4:3b` | `LIGHTWEIGHT_MODELS = ["qwen3.5:2b", "phi4-mini:latest", "granite4:3b", "qwen3.5:9b"]` |
| 45 | Hardcoded AI Model Tag | `qwen3.5:9b` | `LIGHTWEIGHT_MODELS = ["qwen3.5:2b", "phi4-mini:latest", "granite4:3b", "qwen3.5:9b"]` |
| 68 | Hardcoded AI Model Tag | `qwen3.5:2b` | `return getattr(config, "OLLAMA_MODEL", "qwen3.5:2b")` |

### 12. `app/services/copilot/control_plane/contracts.py`
- **Total Lines:** 321
- **Hard values found:** 1 places

| Line | Category | Hardcoded Value | Code Snippet |
|---|---|---|---|
| 220 | Hardcoded AI Model Tag | `qwen2.5:7b-instruct` | `"model_name": "qwen2.5:7b-instruct",` |

### 13. `app/services/copilot/council_coordinator.py`
- **Total Lines:** 1296
- **Hard values found:** 1 places

| Line | Category | Hardcoded Value | Code Snippet |
|---|---|---|---|
| 236 | Hardcoded AI Model Tag | `qwen3.5:2b` | `"model": "qwen3.5:2b",` |

### 14. `app/services/copilot/semantic_router.py`
- **Total Lines:** 202
- **Hard values found:** 1 places

| Line | Category | Hardcoded Value | Code Snippet |
|---|---|---|---|
| 135 | Hardcoded AI Model Tag | `nomic-embed-text:latest` | `def get_embedding(cls, text: str, model: str = "nomic-embed-text:latest") -> list[float] \| None:` |

### 15. `app/services/copilot/union_war_room.py`
- **Total Lines:** 849
- **Hard values found:** 11 places

| Line | Category | Hardcoded Value | Code Snippet |
|---|---|---|---|
| 54 | Hardcoded AI Model Tag | `qwen3.5:9b` | `primary_model="qwen3.5:9b",` |
| 55 | Hardcoded AI Model Tag | `phi4-mini:latest` | `fallback_model="phi4-mini:latest"` |
| 59 | Hardcoded AI Model Tag | `DeepSeek-R1` | `name="DeepSeek-R1",` |
| 64 | Hardcoded AI Model Tag | `deepseek-r1:7b` | `primary_model="deepseek-r1:7b",` |
| 65 | Hardcoded AI Model Tag | `qwen3.5:9b` | `fallback_model="qwen3.5:9b"` |
| 74 | Hardcoded AI Model Tag | `llama3.1:8b` | `primary_model="llama3.1:8b",` |
| 75 | Hardcoded AI Model Tag | `phi4-mini:latest` | `fallback_model="phi4-mini:latest"` |
| 84 | Hardcoded AI Model Tag | `granite4:3b` | `primary_model="granite4:3b",` |
| 85 | Hardcoded AI Model Tag | `phi4-mini:latest` | `fallback_model="phi4-mini:latest"` |
| 94 | Hardcoded AI Model Tag | `gemma4:12b` | `primary_model="gemma4:12b",` |
| 95 | Hardcoded AI Model Tag | `qwen3.5:9b` | `fallback_model="qwen3.5:9b"` |

### 16. `app/services/critic/critic_agent.py`
- **Total Lines:** 540
- **Hard values found:** 1 places

| Line | Category | Hardcoded Value | Code Snippet |
|---|---|---|---|
| 36 | Hardcoded AI Model Tag | `phi4-mini:latest` | `CRITIC_SEMANTIC_MODEL = os.getenv("CRITIC_SEMANTIC_MODEL", "phi4-mini:latest")` |

### 17. `app/services/decision_engine/embedding_engine.py`
- **Total Lines:** 136
- **Hard values found:** 1 places

| Line | Category | Hardcoded Value | Code Snippet |
|---|---|---|---|
| 75 | Hardcoded AI Model Tag | `nomic-embed-text:latest` | `def __init__(self, embedding_model: str = "nomic-embed-text:latest"):` |

### 18. `app/services/gateway/model_gateway.py`
- **Total Lines:** 498
- **Hard values found:** 3 places

| Line | Category | Hardcoded Value | Code Snippet |
|---|---|---|---|
| 172 | Hardcoded AI Model Tag | `qwen3.5:2b` | `candidates = [getattr(config, "OLLAMA_MODEL", "qwen3.5:2b")]` |
| 204 | Hardcoded AI Model Tag | `deepseek-r1` | `if not any(k in model_candidate.lower() for k in ("deepseek-r1", "r1")):` |
| 377 | Hardcoded AI Model Tag | `deepseek-r1` | `if role != ModelRole.REASONER and not any(k in model_candidate.lower() for k in ("deepseek-r1", "r1")):` |

### 19. `app/services/gateway/model_router.py`
- **Total Lines:** 168
- **Hard values found:** 21 places

| Line | Category | Hardcoded Value | Code Snippet |
|---|---|---|---|
| 17 | Hardcoded AI Model Tag | `phi4-mini:latest` | `"phi4-mini:latest",` |
| 18 | Hardcoded AI Model Tag | `qwen3.5:2b` | `"qwen3.5:2b",` |
| 19 | Hardcoded AI Model Tag | `llama3.1:8b` | `"llama3.1:8b"` |
| 22 | Hardcoded AI Model Tag | `qwen3.5:2b` | `"qwen3.5:2b",` |
| 23 | Hardcoded AI Model Tag | `phi4-mini:latest` | `"phi4-mini:latest",` |
| 24 | Hardcoded AI Model Tag | `qwen3.5:9b` | `"qwen3.5:9b"` |
| 27 | Hardcoded AI Model Tag | `gemma4:12b` | `"gemma4:12b",` |
| 28 | Hardcoded AI Model Tag | `qwen3.5:9b` | `"qwen3.5:9b",` |
| 29 | Hardcoded AI Model Tag | `phi4-mini:latest` | `"phi4-mini:latest"` |
| 32 | Hardcoded AI Model Tag | `qwen3.5:9b` | `"qwen3.5:9b",` |
| 33 | Hardcoded AI Model Tag | `gemma4:12b` | `"gemma4:12b",` |
| 34 | Hardcoded AI Model Tag | `phi4-mini:latest` | `"phi4-mini:latest"` |
| 37 | Hardcoded AI Model Tag | `gemma4:12b` | `"gemma4:12b",` |
| 38 | Hardcoded AI Model Tag | `qwen3.5:9b` | `"qwen3.5:9b",` |
| 39 | Hardcoded AI Model Tag | `phi4-mini:latest` | `"phi4-mini:latest"` |
| 62 | Hardcoded AI Model Tag | `deepseek-r1:7b` | `deepseek_model = getattr(config, "MODEL_ROLE_REASONER_PRIMARY", "deepseek-r1:7b")` |
| 65 | Hardcoded AI Model Tag | `qwen3.5:9b` | `qwen_model = getattr(config, "MODEL_ROLE_ANALYST_PRIMARY", "qwen3.5:9b")` |
| 70 | Hardcoded AI Model Tag | `qwen3.5:9b` | `base_cascade = TASK_MODEL_CASCADES.get(request.task_type, ["qwen3.5:9b", "phi4-mini:latest"])` |
| 70 | Hardcoded AI Model Tag | `phi4-mini:latest` | `base_cascade = TASK_MODEL_CASCADES.get(request.task_type, ["qwen3.5:9b", "phi4-mini:latest"])` |
| 77 | Hardcoded AI Model Tag | `phi4-mini:latest` | `fast_model = "phi4-mini:latest"` |
| 83 | Hardcoded AI Model Tag | `qwen3.5:2b` | `sys_default = getattr(config, "OLLAMA_MODEL", "qwen3.5:2b")` |

### 20. `app/services/governance/contracts.py`
- **Total Lines:** 290
- **Hard values found:** 1 places

| Line | Category | Hardcoded Value | Code Snippet |
|---|---|---|---|
| 78 | Hardcoded AI Model Tag | `qwen2.5:7b-instruct` | `model_name: str = "qwen2.5:7b-instruct"` |

### 21. `app/services/kaggle_loader.py`
- **Total Lines:** 271
- **Hard values found:** 4 places

| Line | Category | Hardcoded Value | Code Snippet |
|---|---|---|---|
| 11 | Mock / Synthetic Data Marker | `FIRST_NAMES` | `FIRST_NAMES = [` |
| 20 | Mock / Synthetic Data Marker | `LAST_NAMES` | `LAST_NAMES = [` |
| 40 | Mock / Synthetic Data Marker | `FIRST_NAMES` | `first = rnd.choice(FIRST_NAMES)` |
| 41 | Mock / Synthetic Data Marker | `LAST_NAMES` | `last = rnd.choice(LAST_NAMES)` |

### 22. `app/services/presentation/director/presentation_director.py`
- **Total Lines:** 142
- **Hard values found:** 1 places

| Line | Category | Hardcoded Value | Code Snippet |
|---|---|---|---|
| 48 | Hardcoded AI Model Tag | `qwen3.5:9b` | `self.model_name = model_name or getattr(config, "PRESENTATION_DIRECTOR_MODEL", "qwen3.5:9b")` |

### 23. `app/services/presentation/image_provider.py`
- **Total Lines:** 196
- **Hard values found:** 28 places

| Line | Category | Hardcoded Value | Code Snippet |
|---|---|---|---|
| 13 | Mock / Synthetic Data Marker | `CURATED_WORKPLACE_IMAGES` | `CURATED_WORKPLACE_IMAGES: list[dict[str, Any]] = [` |
| 17 | Hardcoded Endpoint / URL | `https://images.unsplash.com/photo-1542744173-8e7e53415bb0?auto=format&fit=crop&w=1600&q=80` | `"url": "https://images.unsplash.com/photo-1542744173-8e7e53415bb0?auto=format&fit=crop&w=1600&q=80",` |
| 18 | Hardcoded Endpoint / URL | `https://images.unsplash.com/photo-1542744173-8e7e53415bb0?auto=format&fit=crop&w=400&q=80` | `"thumbnail": "https://images.unsplash.com/photo-1542744173-8e7e53415bb0?auto=format&fit=crop&w=400&q=80",` |
| 27 | Hardcoded Endpoint / URL | `https://images.unsplash.com/photo-1586528116311-ad8dd3c8310d?auto=format&fit=crop&w=1600&q=80` | `"url": "https://images.unsplash.com/photo-1586528116311-ad8dd3c8310d?auto=format&fit=crop&w=1600&q=80",` |
| 28 | Hardcoded Endpoint / URL | `https://images.unsplash.com/photo-1586528116311-ad8dd3c8310d?auto=format&fit=crop&w=400&q=80` | `"thumbnail": "https://images.unsplash.com/photo-1586528116311-ad8dd3c8310d?auto=format&fit=crop&w=400&q=80",` |
| 37 | Hardcoded Endpoint / URL | `https://images.unsplash.com/photo-1522071820081-009f0129c71c?auto=format&fit=crop&w=1600&q=80` | `"url": "https://images.unsplash.com/photo-1522071820081-009f0129c71c?auto=format&fit=crop&w=1600&q=80",` |
| 38 | Hardcoded Endpoint / URL | `https://images.unsplash.com/photo-1522071820081-009f0129c71c?auto=format&fit=crop&w=400&q=80` | `"thumbnail": "https://images.unsplash.com/photo-1522071820081-009f0129c71c?auto=format&fit=crop&w=400&q=80",` |
| 47 | Hardcoded Endpoint / URL | `https://images.unsplash.com/photo-1551836022-d5d88e9218df?auto=format&fit=crop&w=1600&q=80` | `"url": "https://images.unsplash.com/photo-1551836022-d5d88e9218df?auto=format&fit=crop&w=1600&q=80",` |
| 48 | Hardcoded Endpoint / URL | `https://images.unsplash.com/photo-1551836022-d5d88e9218df?auto=format&fit=crop&w=400&q=80` | `"thumbnail": "https://images.unsplash.com/photo-1551836022-d5d88e9218df?auto=format&fit=crop&w=400&q=80",` |
| 57 | Hardcoded Endpoint / URL | `https://images.unsplash.com/photo-1556742049-0a67c5574f73?auto=format&fit=crop&w=1600&q=80` | `"url": "https://images.unsplash.com/photo-1556742049-0a67c5574f73?auto=format&fit=crop&w=1600&q=80",` |
| 58 | Hardcoded Endpoint / URL | `https://images.unsplash.com/photo-1556742049-0a67c5574f73?auto=format&fit=crop&w=400&q=80` | `"thumbnail": "https://images.unsplash.com/photo-1556742049-0a67c5574f73?auto=format&fit=crop&w=400&q=80",` |
| 67 | Hardcoded Endpoint / URL | `https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?auto=format&fit=crop&w=1600&q=80` | `"url": "https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?auto=format&fit=crop&w=1600&q=80",` |
| 68 | Hardcoded Endpoint / URL | `https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?auto=format&fit=crop&w=400&q=80` | `"thumbnail": "https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?auto=format&fit=crop&w=400&q=80",` |
| 77 | Hardcoded Endpoint / URL | `https://images.unsplash.com/photo-1554224155-8d04cb21cd6c?auto=format&fit=crop&w=1600&q=80` | `"url": "https://images.unsplash.com/photo-1554224155-8d04cb21cd6c?auto=format&fit=crop&w=1600&q=80",` |
| 78 | Hardcoded Endpoint / URL | `https://images.unsplash.com/photo-1554224155-8d04cb21cd6c?auto=format&fit=crop&w=400&q=80` | `"thumbnail": "https://images.unsplash.com/photo-1554224155-8d04cb21cd6c?auto=format&fit=crop&w=400&q=80",` |
| 87 | Hardcoded Endpoint / URL | `https://images.unsplash.com/photo-1553413077-190dd305871c?auto=format&fit=crop&w=1600&q=80` | `"url": "https://images.unsplash.com/photo-1553413077-190dd305871c?auto=format&fit=crop&w=1600&q=80",` |
| 88 | Hardcoded Endpoint / URL | `https://images.unsplash.com/photo-1553413077-190dd305871c?auto=format&fit=crop&w=400&q=80` | `"thumbnail": "https://images.unsplash.com/photo-1553413077-190dd305871c?auto=format&fit=crop&w=400&q=80",` |
| 97 | Hardcoded Endpoint / URL | `https://images.unsplash.com/photo-1517245386807-bb43f82c33c4?auto=format&fit=crop&w=1600&q=80` | `"url": "https://images.unsplash.com/photo-1517245386807-bb43f82c33c4?auto=format&fit=crop&w=1600&q=80",` |
| 98 | Hardcoded Endpoint / URL | `https://images.unsplash.com/photo-1517245386807-bb43f82c33c4?auto=format&fit=crop&w=400&q=80` | `"thumbnail": "https://images.unsplash.com/photo-1517245386807-bb43f82c33c4?auto=format&fit=crop&w=400&q=80",` |
| 107 | Hardcoded Endpoint / URL | `https://images.unsplash.com/photo-1576091160399-112ba8d25d1d?auto=format&fit=crop&w=1600&q=80` | `"url": "https://images.unsplash.com/photo-1576091160399-112ba8d25d1d?auto=format&fit=crop&w=1600&q=80",` |
| 108 | Hardcoded Endpoint / URL | `https://images.unsplash.com/photo-1576091160399-112ba8d25d1d?auto=format&fit=crop&w=400&q=80` | `"thumbnail": "https://images.unsplash.com/photo-1576091160399-112ba8d25d1d?auto=format&fit=crop&w=400&q=80",` |
| 117 | Hardcoded Endpoint / URL | `https://images.unsplash.com/photo-1503387762-592deb58ef4e?auto=format&fit=crop&w=1600&q=80` | `"url": "https://images.unsplash.com/photo-1503387762-592deb58ef4e?auto=format&fit=crop&w=1600&q=80",` |
| 118 | Hardcoded Endpoint / URL | `https://images.unsplash.com/photo-1503387762-592deb58ef4e?auto=format&fit=crop&w=400&q=80` | `"thumbnail": "https://images.unsplash.com/photo-1503387762-592deb58ef4e?auto=format&fit=crop&w=400&q=80",` |
| 127 | Hardcoded Endpoint / URL | `https://images.unsplash.com/photo-1460925895917-afdab827c52f?auto=format&fit=crop&w=1600&q=80` | `"url": "https://images.unsplash.com/photo-1460925895917-afdab827c52f?auto=format&fit=crop&w=1600&q=80",` |
| 128 | Hardcoded Endpoint / URL | `https://images.unsplash.com/photo-1460925895917-afdab827c52f?auto=format&fit=crop&w=400&q=80` | `"thumbnail": "https://images.unsplash.com/photo-1460925895917-afdab827c52f?auto=format&fit=crop&w=400&q=80",` |
| 148 | Hardcoded Endpoint / URL | `https://api.openverse.org/v1/images/?q={encoded_query}&license_type=commercial&page_size={page_size}` | `url = f"https://api.openverse.org/v1/images/?q={encoded_query}&license_type=commercial&page_size={page_size}"` |
| 184 | Mock / Synthetic Data Marker | `CURATED_WORKPLACE_IMAGES` | `for img in CURATED_WORKPLACE_IMAGES:` |
| 192 | Mock / Synthetic Data Marker | `CURATED_WORKPLACE_IMAGES` | `curated_matches = CURATED_WORKPLACE_IMAGES` |

### 24. `app/services/presentation/industry_personas_seed.py`
- **Total Lines:** 620
- **Hard values found:** 1 places

| Line | Category | Hardcoded Value | Code Snippet |
|---|---|---|---|
| 10 | Mock / Synthetic Data Marker | `INDUSTRY_PERSONAS` | `INDUSTRY_PERSONAS: list[dict[str, Any]] = [` |

### 25. `app/services/presentation/memory/memory_models.py`
- **Total Lines:** 95
- **Hard values found:** 1 places

| Line | Category | Hardcoded Value | Code Snippet |
|---|---|---|---|
| 94 | Hardcoded AI Model Tag | `nomic-embed-text:latest` | `embedding_model_used: str = "nomic-embed-text:latest"` |

### 26. `app/services/presentation/orchestrator/benchmark.py`
- **Total Lines:** 268
- **Hard values found:** 4 places

| Line | Category | Hardcoded Value | Code Snippet |
|---|---|---|---|
| 3 | Hardcoded AI Model Tag | `granite4:3b-h` | `Compares 'granite4:3b-h' (hybrid architecture) vs 'granite4:3b' (standard dense)` |
| 3 | Hardcoded AI Model Tag | `granite4:3b` | `Compares 'granite4:3b-h' (hybrid architecture) vs 'granite4:3b' (standard dense)` |
| 236 | Hardcoded AI Model Tag | `granite4:3b-h` | `def compare_models(model_a: str = "granite4:3b-h", model_b: str = "granite4:3b") -> dict[str, Any]:` |
| 236 | Hardcoded AI Model Tag | `granite4:3b` | `def compare_models(model_a: str = "granite4:3b-h", model_b: str = "granite4:3b") -> dict[str, Any]:` |

### 27. `app/services/presentation/orchestrator/granite_orchestrator.py`
- **Total Lines:** 752
- **Hard values found:** 2 places

| Line | Category | Hardcoded Value | Code Snippet |
|---|---|---|---|
| 68 | Hardcoded AI Model Tag | `granite4:3b-h` | `self.model_name = model_name or getattr(config, "PRESENTATION_ORCHESTRATOR_MODEL", "granite4:3b-h")` |
| 69 | Hardcoded AI Model Tag | `granite4:3b` | `self.fallback_model = fallback_model or getattr(config, "PRESENTATION_ORCHESTRATOR_FALLBACK_MODEL", "granite4:` |

### 28. `app/services/presentation/orchestrator/orchestrator_models.py`
- **Total Lines:** 145
- **Hard values found:** 1 places

| Line | Category | Hardcoded Value | Code Snippet |
|---|---|---|---|
| 122 | Hardcoded AI Model Tag | `granite4:3b-h` | `orchestrator_model: str = "granite4:3b-h"` |

### 29. `app/services/presentation/orchestrator/specialists/deepseek_reasoner.py`
- **Total Lines:** 125
- **Hard values found:** 2 places

| Line | Category | Hardcoded Value | Code Snippet |
|---|---|---|---|
| 30 | Hardcoded AI Model Tag | `deepseek-r1:7b` | `self.model_name = model_name or getattr(config, "PRESENTATION_DEEP_REASONING_MODEL", "deepseek-r1:7b")` |
| 79 | Hardcoded AI Model Tag | `deepseek-resolve-conflict` | `report_id="deepseek-resolve-conflict",` |

### 30. `app/services/presentation/orchestrator/specialists/phi_verifier.py`
- **Total Lines:** 247
- **Hard values found:** 1 places

| Line | Category | Hardcoded Value | Code Snippet |
|---|---|---|---|
| 31 | Hardcoded AI Model Tag | `phi4-mini:latest` | `self.model_name = model_name or getattr(config, "PRESENTATION_ANALYTICAL_MODEL", "phi4-mini:latest")` |

### 31. `app/services/presentation/orchestrator/task_graph.py`
- **Total Lines:** 208
- **Hard values found:** 1 places

| Line | Category | Hardcoded Value | Code Snippet |
|---|---|---|---|
| 198 | Hardcoded AI Model Tag | `granite4:3b-h` | `def to_execution_plan(self, execution_id: str, orchestrator_model: str = "granite4:3b-h") -> ExecutionPlan:` |

### 32. `app/services/presentation/persona_router.py`
- **Total Lines:** 198
- **Hard values found:** 2 places

| Line | Category | Hardcoded Value | Code Snippet |
|---|---|---|---|
| 71 | Mock / Synthetic Data Marker | `INDUSTRY_PERSONAS` | `from .industry_personas_seed import INDUSTRY_PERSONAS` |
| 72 | Mock / Synthetic Data Marker | `INDUSTRY_PERSONAS` | `personas = INDUSTRY_PERSONAS` |

### 33. `app/services/presentation/photo_background.py`
- **Total Lines:** 95
- **Hard values found:** 3 places

| Line | Category | Hardcoded Value | Code Snippet |
|---|---|---|---|
| 23 | Hardcoded Localhost / IP | `localhost` | `if hostname in ("localhost", "127.0.0.1", "0.0.0.0", "::1") or hostname.endswith(".local") or hostname.endswit` |
| 23 | Hardcoded Localhost / IP | `127.0.0.1` | `if hostname in ("localhost", "127.0.0.1", "0.0.0.0", "::1") or hostname.endswith(".local") or hostname.endswit` |
| 23 | Hardcoded Localhost / IP | `0.0.0.0` | `if hostname in ("localhost", "127.0.0.1", "0.0.0.0", "::1") or hostname.endswith(".local") or hostname.endswit` |

### 34. `app/services/presentation/qa/gemma_critic.py`
- **Total Lines:** 222
- **Hard values found:** 3 places

| Line | Category | Hardcoded Value | Code Snippet |
|---|---|---|---|
| 42 | Hardcoded AI Model Tag | `gemma4:12b` | `self.model_name = model_name or getattr(config, "PRESENTATION_VISUAL_QA_MODEL", "gemma4:12b")` |
| 43 | Hardcoded Endpoint / URL | `http://localhost:11434` | `self.base_url = base_url or getattr(config, "OLLAMA_BASE_URL", "http://localhost:11434")` |
| 43 | Hardcoded Port | `11434` | `self.base_url = base_url or getattr(config, "OLLAMA_BASE_URL", "http://localhost:11434")` |

### 35. `app/services/presentation/validation/validation_harness.py`
- **Total Lines:** 361
- **Hard values found:** 1 places

| Line | Category | Hardcoded Value | Code Snippet |
|---|---|---|---|
| 161 | Hardcoded AI Model Tag | `Phi-4` | `phi_tasks = sum(1 for p in slide_packages for tr in p.execution_trace if "Phi-4" in str(tr.get("executor", "")` |

### 36. `app/services/sheet_catalog.py`
- **Total Lines:** 1060
- **Hard values found:** 1 places

| Line | Category | Hardcoded Value | Code Snippet |
|---|---|---|---|
| 987 | Hardcoded Database Filename | `before_sheet_catalog_v1.sqlite3` | `backup_path = config.DB_PATH.parent / 'before_sheet_catalog_v1.sqlite3'` |

---

## File-By-File Audit: Clean Files (No Hard Values Found)

A total of **503 files** were verified with **no hard values found**.

| # | File Path | Total Lines | Status |
|---|---|---|---|
| 1 | `app/__init__.py` | 0 | No hard value found |
| 2 | `app/agent/__init__.py` | 48 | No hard value found |
| 3 | `app/agent/bypass_audit.py` | 101 | No hard value found |
| 4 | `app/agent/execution_record.py` | 103 | No hard value found |
| 5 | `app/agent/graph.py` | 180 | No hard value found |
| 6 | `app/agent/guards.py` | 82 | No hard value found |
| 7 | `app/agent/nodes/__init__.py` | 28 | No hard value found |
| 8 | `app/agent/nodes/approval.py` | 43 | No hard value found |
| 9 | `app/agent/nodes/classify_intent.py` | 71 | No hard value found |
| 10 | `app/agent/nodes/compose_response.py` | 73 | No hard value found |
| 11 | `app/agent/nodes/evidence_sufficiency.py` | 42 | No hard value found |
| 12 | `app/agent/nodes/execute_tool.py` | 86 | No hard value found |
| 13 | `app/agent/nodes/governance_check.py` | 59 | No hard value found |
| 14 | `app/agent/nodes/plan_tools.py` | 141 | No hard value found |
| 15 | `app/agent/nodes/presentation.py` | 66 | No hard value found |
| 16 | `app/agent/nodes/resolve_context.py` | 31 | No hard value found |
| 17 | `app/agent/nodes/scenario.py` | 75 | No hard value found |
| 18 | `app/agent/nodes/verify_claim.py` | 74 | No hard value found |
| 19 | `app/agent/router.py` | 180 | No hard value found |
| 20 | `app/agent/state.py` | 50 | No hard value found |
| 21 | `app/agent/workflows/__init__.py` | 14 | No hard value found |
| 22 | `app/agent/workflows/analytical_investigation.py` | 61 | No hard value found |
| 23 | `app/agent/workflows/presentation_creation.py` | 44 | No hard value found |
| 24 | `app/agent/workflows/quick_answer.py` | 44 | No hard value found |
| 25 | `app/agent/workflows/scenario_analysis.py` | 38 | No hard value found |
| 26 | `app/analytics/__init__.py` | 41 | No hard value found |
| 27 | `app/analytics/backfill.py` | 94 | No hard value found |
| 28 | `app/analytics/contracts.py` | 108 | No hard value found |
| 29 | `app/analytics/duckdb_engine.py` | 182 | No hard value found |
| 30 | `app/analytics/parquet_materializer.py` | 382 | No hard value found |
| 31 | `app/analytics/query_service.py` | 530 | No hard value found |
| 32 | `app/analytics/shadow_validator.py` | 126 | No hard value found |
| 33 | `app/analytics/storage_integrity.py` | 105 | No hard value found |
| 34 | `app/api/__init__.py` | 1 | No hard value found |
| 35 | `app/api/v1/__init__.py` | 1 | No hard value found |
| 36 | `app/api/v1/endpoints/__init__.py` | 1 | No hard value found |
| 37 | `app/api/v1/endpoints/copilot.py` | 22 | No hard value found |
| 38 | `app/api/v1/endpoints/reports.py` | 22 | No hard value found |
| 39 | `app/cache/__init__.py` | 37 | No hard value found |
| 40 | `app/cache/contracts.py` | 94 | No hard value found |
| 41 | `app/cache/dashboard_cache.py` | 135 | No hard value found |
| 42 | `app/cache/integrity.py` | 108 | No hard value found |
| 43 | `app/cache/key_builder.py` | 139 | No hard value found |
| 44 | `app/cache/metrics.py` | 82 | No hard value found |
| 45 | `app/cache/repository.py` | 199 | No hard value found |
| 46 | `app/context/__init__.py` | 27 | No hard value found |
| 47 | `app/context/contracts.py` | 145 | No hard value found |
| 48 | `app/context/store.py` | 409 | No hard value found |
| 49 | `app/core/__init__.py` | 0 | No hard value found |
| 50 | `app/core/test_firewall.py` | 48 | No hard value found |
| 51 | `app/db/__init__.py` | 0 | No hard value found |
| 52 | `app/db/database.py` | 73 | No hard value found |
| 53 | `app/db/migrate_temporal_cadence.py` | 176 | No hard value found |
| 54 | `app/db/migration_runner.py` | 101 | No hard value found |
| 55 | `app/db/migrations/0001_baseline_schema.py` | 18 | No hard value found |
| 56 | `app/db/migrations/0002_add_context_and_enrichment.py` | 26 | No hard value found |
| 57 | `app/db/migrations/0003_add_curated_derived_and_eda.py` | 62 | No hard value found |
| 58 | `app/db/migrations/0005_add_vector_tables.py` | 22 | No hard value found |
| 59 | `app/db/migrations/0006_add_parquet_and_cache_metadata.py` | 36 | No hard value found |
| 60 | `app/db/migrations/0007_enhance_dashboard_cache_metadata.py` | 45 | No hard value found |
| 61 | `app/db/migrations/0008_add_parquet_analytical_plane.py` | 41 | No hard value found |
| 62 | `app/db/migrations/0009_add_background_jobs_plane.py` | 40 | No hard value found |
| 63 | `app/db/session.py` | 15 | No hard value found |
| 64 | `app/jobs/__init__.py` | 22 | No hard value found |
| 65 | `app/jobs/contracts.py` | 55 | No hard value found |
| 66 | `app/jobs/handlers/analytics_handler.py` | 58 | No hard value found |
| 67 | `app/jobs/handlers/eda_handler.py` | 36 | No hard value found |
| 68 | `app/jobs/handlers/export_handler.py` | 98 | No hard value found |
| 69 | `app/jobs/repository.py` | 255 | No hard value found |
| 70 | `app/jobs/worker_plane.py` | 159 | No hard value found |
| 71 | `app/mcp/__init__.py` | 59 | No hard value found |
| 72 | `app/mcp/analytics_server.py` | 585 | No hard value found |
| 73 | `app/mcp/bypass_audit.py` | 125 | No hard value found |
| 74 | `app/mcp/context_server.py` | 283 | No hard value found |
| 75 | `app/mcp/contracts.py` | 729 | No hard value found |
| 76 | `app/mcp/dataset_server.py` | 362 | No hard value found |
| 77 | `app/mcp/evidence_server.py` | 264 | No hard value found |
| 78 | `app/mcp/execution_ledger.py` | 127 | No hard value found |
| 79 | `app/mcp/gateway.py` | 264 | No hard value found |
| 80 | `app/mcp/governance_server.py` | 246 | No hard value found |
| 81 | `app/mcp/presentation_server.py` | 213 | No hard value found |
| 82 | `app/mcp/registry.py` | 67 | No hard value found |
| 83 | `app/mcp/scenario_server.py` | 261 | No hard value found |
| 84 | `app/observability/__init__.py` | 75 | No hard value found |
| 85 | `app/observability/benchmark/__init__.py` | 13 | No hard value found |
| 86 | `app/observability/benchmark/corpus.py` | 529 | No hard value found |
| 87 | `app/observability/benchmark/runner.py` | 245 | No hard value found |
| 88 | `app/observability/contracts.py` | 291 | No hard value found |
| 89 | `app/observability/evaluators/__init__.py` | 20 | No hard value found |
| 90 | `app/observability/evaluators/evidence_sufficiency.py` | 62 | No hard value found |
| 91 | `app/observability/evaluators/governance_health.py` | 66 | No hard value found |
| 92 | `app/observability/evaluators/grounding.py` | 163 | No hard value found |
| 93 | `app/observability/evaluators/intent_alignment.py` | 94 | No hard value found |
| 94 | `app/observability/evaluators/model_routing.py` | 62 | No hard value found |
| 95 | `app/observability/evaluators/tool_selection.py` | 59 | No hard value found |
| 96 | `app/observability/evaluators/workflow_outcome.py` | 76 | No hard value found |
| 97 | `app/observability/latency_budget.py` | 101 | No hard value found |
| 98 | `app/observability/metrics.py` | 171 | No hard value found |
| 99 | `app/observability/trace_context.py` | 60 | No hard value found |
| 100 | `app/observability/trace_store.py` | 72 | No hard value found |
| 101 | `app/optimization/__init__.py` | 62 | No hard value found |
| 102 | `app/optimization/analyzers/__init__.py` | 19 | No hard value found |
| 103 | `app/optimization/analyzers/evidence_policy.py` | 52 | No hard value found |
| 104 | `app/optimization/analyzers/latency.py` | 51 | No hard value found |
| 105 | `app/optimization/analyzers/retry_policy.py` | 50 | No hard value found |
| 106 | `app/optimization/analyzers/tool_efficiency.py` | 62 | No hard value found |
| 107 | `app/optimization/analyzers/workflow_efficiency.py` | 70 | No hard value found |
| 108 | `app/optimization/benchmark/__init__.py` | 6 | No hard value found |
| 109 | `app/optimization/benchmark/candidate_runner.py` | 26 | No hard value found |
| 110 | `app/optimization/comparison.py` | 109 | No hard value found |
| 111 | `app/optimization/optimizer.py` | 264 | No hard value found |
| 112 | `app/optimization/policy_registry.py` | 150 | No hard value found |
| 113 | `app/optimization/promotion_gate.py` | 42 | No hard value found |
| 114 | `app/optimization/recommendation_engine.py` | 118 | No hard value found |
| 115 | `app/optimization/rollback.py` | 213 | No hard value found |
| 116 | `app/routers/__init__.py` | 0 | No hard value found |
| 117 | `app/routers/adaptive_dashboard.py` | 259 | No hard value found |
| 118 | `app/routers/analytics.py` | 198 | No hard value found |
| 119 | `app/routers/context.py` | 155 | No hard value found |
| 120 | `app/routers/copilot.py` | 1555 | No hard value found |
| 121 | `app/routers/decision_brief.py` | 211 | No hard value found |
| 122 | `app/routers/decision_ledger.py` | 187 | No hard value found |
| 123 | `app/routers/eda.py` | 237 | No hard value found |
| 124 | `app/routers/employees.py` | 110 | No hard value found |
| 125 | `app/routers/jobs.py` | 81 | No hard value found |
| 126 | `app/routers/observability.py` | 43 | No hard value found |
| 127 | `app/routers/optimization.py` | 198 | No hard value found |
| 128 | `app/routers/presentations.py` | 842 | No hard value found |
| 129 | `app/routers/reports.py` | 188 | No hard value found |
| 130 | `app/routers/sheets.py` | 177 | No hard value found |
| 131 | `app/routers/upload.py` | 622 | No hard value found |
| 132 | `app/routers/workspace_context.py` | 193 | No hard value found |
| 133 | `app/services/__init__.py` | 0 | No hard value found |
| 134 | `app/services/adaptive_dashboard/__init__.py` | 54 | No hard value found |
| 135 | `app/services/adaptive_dashboard/briefing.py` | 548 | No hard value found |
| 136 | `app/services/adaptive_dashboard/claim_validator.py` | 21 | No hard value found |
| 137 | `app/services/adaptive_dashboard/composition/__init__.py` | 69 | No hard value found |
| 138 | `app/services/adaptive_dashboard/composition/candidate_builder.py` | 138 | No hard value found |
| 139 | `app/services/adaptive_dashboard/composition/contracts.py` | 444 | No hard value found |
| 140 | `app/services/adaptive_dashboard/composition/integrity.py` | 264 | No hard value found |
| 141 | `app/services/adaptive_dashboard/composition/planner.py` | 652 | No hard value found |
| 142 | `app/services/adaptive_dashboard/composition_planner.py` | 1627 | No hard value found |
| 143 | `app/services/adaptive_dashboard/contracts.py` | 829 | No hard value found |
| 144 | `app/services/adaptive_dashboard/dataset_isolation_integrity.py` | 476 | No hard value found |
| 145 | `app/services/adaptive_dashboard/dataset_orchestrator.py` | 565 | No hard value found |
| 146 | `app/services/adaptive_dashboard/domain_governance.py` | 292 | No hard value found |
| 147 | `app/services/adaptive_dashboard/engine.py` | 473 | No hard value found |
| 148 | `app/services/adaptive_dashboard/enterprise.py` | 1470 | No hard value found |
| 149 | `app/services/adaptive_dashboard/evaluation_contracts.py` | 193 | No hard value found |
| 150 | `app/services/adaptive_dashboard/evaluator.py` | 290 | No hard value found |
| 151 | `app/services/adaptive_dashboard/evidence/__init__.py` | 64 | No hard value found |
| 152 | `app/services/adaptive_dashboard/evidence/claim_binding.py` | 128 | No hard value found |
| 153 | `app/services/adaptive_dashboard/evidence/contracts.py` | 234 | No hard value found |
| 154 | `app/services/adaptive_dashboard/evidence/evidence_binding.py` | 237 | No hard value found |
| 155 | `app/services/adaptive_dashboard/evidence/integrity.py` | 207 | No hard value found |
| 156 | `app/services/adaptive_dashboard/evidence/provenance.py` | 77 | No hard value found |
| 157 | `app/services/adaptive_dashboard/evidence_graph.py` | 21 | No hard value found |
| 158 | `app/services/adaptive_dashboard/exceptions.py` | 798 | No hard value found |
| 159 | `app/services/adaptive_dashboard/executive_analytics.py` | 928 | No hard value found |
| 160 | `app/services/adaptive_dashboard/findings.py` | 338 | No hard value found |
| 161 | `app/services/adaptive_dashboard/forecast_gatekeeper.py` | 262 | No hard value found |
| 162 | `app/services/adaptive_dashboard/formatter_validator.py` | 117 | No hard value found |
| 163 | `app/services/adaptive_dashboard/formatting/__init__.py` | 50 | No hard value found |
| 164 | `app/services/adaptive_dashboard/formatting/metric_formatter.py` | 387 | No hard value found |
| 165 | `app/services/adaptive_dashboard/formatting/presentation_labels.py` | 47 | No hard value found |
| 166 | `app/services/adaptive_dashboard/global_ranker.py` | 379 | No hard value found |
| 167 | `app/services/adaptive_dashboard/insight_ranker.py` | 160 | No hard value found |
| 168 | `app/services/adaptive_dashboard/layout_engine.py` | 231 | No hard value found |
| 169 | `app/services/adaptive_dashboard/legacy_elements.py` | 4341 | No hard value found |
| 170 | `app/services/adaptive_dashboard/mcp_gateway.py` | 557 | No hard value found |
| 171 | `app/services/adaptive_dashboard/narrative/__init__.py` | 53 | No hard value found |
| 172 | `app/services/adaptive_dashboard/narrative/briefing_service.py` | 164 | No hard value found |
| 173 | `app/services/adaptive_dashboard/narrative/contracts.py` | 72 | No hard value found |
| 174 | `app/services/adaptive_dashboard/narrative/deduplication.py` | 126 | No hard value found |
| 175 | `app/services/adaptive_dashboard/narrative/finding_builder.py` | 127 | No hard value found |
| 176 | `app/services/adaptive_dashboard/narrative/integrity.py` | 213 | No hard value found |
| 177 | `app/services/adaptive_dashboard/narrative/title_builder.py` | 113 | No hard value found |
| 178 | `app/services/adaptive_dashboard/obligations.py` | 1710 | No hard value found |
| 179 | `app/services/adaptive_dashboard/opportunity_planner/__init__.py` | 22 | No hard value found |
| 180 | `app/services/adaptive_dashboard/opportunity_planner/contracts.py` | 126 | No hard value found |
| 181 | `app/services/adaptive_dashboard/opportunity_planner/executor.py` | 421 | No hard value found |
| 182 | `app/services/adaptive_dashboard/opportunity_planner/family_aggregator.py` | 184 | No hard value found |
| 183 | `app/services/adaptive_dashboard/opportunity_planner/planner.py` | 644 | No hard value found |
| 184 | `app/services/adaptive_dashboard/opportunity_planner/portfolio.py` | 142 | No hard value found |
| 185 | `app/services/adaptive_dashboard/orchestrator.py` | 2354 | No hard value found |
| 186 | `app/services/adaptive_dashboard/outlook.py` | 801 | No hard value found |
| 187 | `app/services/adaptive_dashboard/policy_engine.py` | 230 | No hard value found |
| 188 | `app/services/adaptive_dashboard/ranking_engine.py` | 1023 | No hard value found |
| 189 | `app/services/adaptive_dashboard/semantic_catalog.py` | 223 | No hard value found |
| 190 | `app/services/adaptive_dashboard/semantic_visual_compression.py` | 576 | No hard value found |
| 191 | `app/services/adaptive_dashboard/source_data_loader.py` | 173 | No hard value found |
| 192 | `app/services/adaptive_dashboard/spatial_composition_optimizer.py` | 61 | No hard value found |
| 193 | `app/services/adaptive_dashboard/story_builder.py` | 1331 | No hard value found |
| 194 | `app/services/adaptive_dashboard/story_planner.py` | 187 | No hard value found |
| 195 | `app/services/adaptive_dashboard/telemetry.py` | 261 | No hard value found |
| 196 | `app/services/adaptive_dashboard/theme_validator.py` | 507 | No hard value found |
| 197 | `app/services/adaptive_dashboard/topics/__init__.py` | 29 | No hard value found |
| 198 | `app/services/adaptive_dashboard/topics/contracts.py` | 200 | No hard value found |
| 199 | `app/services/adaptive_dashboard/topics/factory.py` | 161 | No hard value found |
| 200 | `app/services/adaptive_dashboard/topics/integrity.py` | 113 | No hard value found |
| 201 | `app/services/adaptive_dashboard/visual_compiler.py` | 406 | No hard value found |
| 202 | `app/services/adaptive_dashboard/visual_decision/__init__.py` | 38 | No hard value found |
| 203 | `app/services/adaptive_dashboard/visual_decision/archetypes.py` | 107 | No hard value found |
| 204 | `app/services/adaptive_dashboard/visual_decision/contracts.py` | 152 | No hard value found |
| 205 | `app/services/adaptive_dashboard/visual_decision/engine.py` | 163 | No hard value found |
| 206 | `app/services/adaptive_dashboard/visual_decision/intent_classifier.py` | 127 | No hard value found |
| 207 | `app/services/adaptive_dashboard/visual_decision/question_builder.py` | 309 | No hard value found |
| 208 | `app/services/adaptive_dashboard/visual_decision/semantic_validator.py` | 94 | No hard value found |
| 209 | `app/services/adaptive_dashboard/visual_decision/suitability_matrix.py` | 81 | No hard value found |
| 210 | `app/services/adaptive_dashboard/visual_decision/suitability_ranker.py` | 198 | No hard value found |
| 211 | `app/services/adaptive_dashboard/visual_portfolio_optimizer.py` | 625 | No hard value found |
| 212 | `app/services/adaptive_dashboard/visual_presence_gates.py` | 481 | No hard value found |
| 213 | `app/services/adaptive_dashboard/visuals/__init__.py` | 43 | No hard value found |
| 214 | `app/services/adaptive_dashboard/visuals/capability_registry.py` | 127 | No hard value found |
| 215 | `app/services/adaptive_dashboard/visuals/contracts.py` | 176 | No hard value found |
| 216 | `app/services/adaptive_dashboard/visuals/integrity.py` | 190 | No hard value found |
| 217 | `app/services/adaptive_dashboard/visuals/spec_factory.py` | 107 | No hard value found |
| 218 | `app/services/adaptive_table_reconstruction/__init__.py` | 73 | No hard value found |
| 219 | `app/services/adaptive_table_reconstruction/confidence_risk_engine.py` | 252 | No hard value found |
| 220 | `app/services/adaptive_table_reconstruction/continuation_detector.py` | 294 | No hard value found |
| 221 | `app/services/adaptive_table_reconstruction/contracts.py` | 275 | No hard value found |
| 222 | `app/services/adaptive_table_reconstruction/engine.py` | 326 | No hard value found |
| 223 | `app/services/adaptive_table_reconstruction/grid_capture.py` | 177 | No hard value found |
| 224 | `app/services/adaptive_table_reconstruction/header_tree_builder.py` | 158 | No hard value found |
| 225 | `app/services/adaptive_table_reconstruction/row_role_classifier.py` | 460 | No hard value found |
| 226 | `app/services/adaptive_table_reconstruction/safety_benchmark.py` | 250 | No hard value found |
| 227 | `app/services/adaptive_table_reconstruction/sentinel_resolver.py` | 156 | No hard value found |
| 228 | `app/services/adaptive_table_reconstruction/structural_validator.py` | 243 | No hard value found |
| 229 | `app/services/ai_copilot.py` | 606 | No hard value found |
| 230 | `app/services/ai_evaluation.py` | 179 | No hard value found |
| 231 | `app/services/analysis_planner.py` | 27 | No hard value found |
| 232 | `app/services/analyst/__init__.py` | 5 | No hard value found |
| 233 | `app/services/analyst/analyst_agent.py` | 518 | No hard value found |
| 234 | `app/services/analyst/interpretation_models.py` | 44 | No hard value found |
| 235 | `app/services/analyst/interpretation_validator.py` | 580 | No hard value found |
| 236 | `app/services/analytics/__init__.py` | 10 | No hard value found |
| 237 | `app/services/analytics/temporal_categorical_engine.py` | 605 | No hard value found |
| 238 | `app/services/copilot/attendance_visuals.py` | 78 | No hard value found |
| 239 | `app/services/copilot/chat_visuals.py` | 262 | No hard value found |
| 240 | `app/services/copilot/context_enrichment.py` | 223 | No hard value found |
| 241 | `app/services/copilot/control_plane/__init__.py` | 65 | No hard value found |
| 242 | `app/services/copilot/control_plane/budget_manager.py` | 115 | No hard value found |
| 243 | `app/services/copilot/control_plane/bypass_audit.py` | 137 | No hard value found |
| 244 | `app/services/copilot/control_plane/capability_router.py` | 106 | No hard value found |
| 245 | `app/services/copilot/control_plane/claim_governor.py` | 170 | No hard value found |
| 246 | `app/services/copilot/control_plane/classifiers.py` | 172 | No hard value found |
| 247 | `app/services/copilot/control_plane/facade.py` | 307 | No hard value found |
| 248 | `app/services/copilot/control_plane/model_router.py` | 110 | No hard value found |
| 249 | `app/services/copilot/control_plane/orchestrator.py` | 169 | No hard value found |
| 250 | `app/services/copilot/conversation_context.py` | 30 | No hard value found |
| 251 | `app/services/copilot/coordinator_models.py` | 97 | No hard value found |
| 252 | `app/services/copilot/copilot_models.py` | 38 | No hard value found |
| 253 | `app/services/copilot/council_contracts.py` | 167 | No hard value found |
| 254 | `app/services/copilot/council_evidence_service.py` | 324 | No hard value found |
| 255 | `app/services/copilot/dataset_context.py` | 81 | No hard value found |
| 256 | `app/services/copilot/dataset_query.py` | 188 | No hard value found |
| 257 | `app/services/copilot/generic_copilot_engine.py` | 444 | No hard value found |
| 258 | `app/services/copilot/response_formatter.py` | 232 | No hard value found |
| 259 | `app/services/copilot/sheet_quality.py` | 120 | No hard value found |
| 260 | `app/services/copilot_query_planner.py` | 2791 | No hard value found |
| 261 | `app/services/copilot_tools.py` | 359 | No hard value found |
| 262 | `app/services/critic/__init__.py` | 27 | No hard value found |
| 263 | `app/services/critic/deterministic_claim_validator.py` | 461 | No hard value found |
| 264 | `app/services/data_engine/__init__.py` | 27 | No hard value found |
| 265 | `app/services/data_engine/analysis_context.py` | 299 | No hard value found |
| 266 | `app/services/data_engine/candidate_fact.py` | 124 | No hard value found |
| 267 | `app/services/data_engine/candidate_fact_discovery.py` | 1468 | No hard value found |
| 268 | `app/services/data_engine/fact_visualizer.py` | 753 | No hard value found |
| 269 | `app/services/data_engine/interestingness_ranker.py` | 609 | No hard value found |
| 270 | `app/services/data_engine/metric_engine.py` | 259 | No hard value found |
| 271 | `app/services/data_engine/opportunity_map.py` | 323 | No hard value found |
| 272 | `app/services/data_engine/profiler.py` | 184 | No hard value found |
| 273 | `app/services/data_engine/semantic_classifier.py` | 904 | No hard value found |
| 274 | `app/services/data_engine/validator.py` | 155 | No hard value found |
| 275 | `app/services/data_engine/visualization_models.py` | 45 | No hard value found |
| 276 | `app/services/data_lifecycle.py` | 4 | No hard value found |
| 277 | `app/services/dataset_deletion.py` | 445 | No hard value found |
| 278 | `app/services/decision_engine/__init__.py` | 14 | No hard value found |
| 279 | `app/services/decision_engine/base.py` | 25 | No hard value found |
| 280 | `app/services/decision_engine/factory.py` | 22 | No hard value found |
| 281 | `app/services/decision_engine/rule_engine.py` | 148 | No hard value found |
| 282 | `app/services/decision_intelligence.py` | 340 | No hard value found |
| 283 | `app/services/display_formatters.py` | 249 | No hard value found |
| 284 | `app/services/eda/__init__.py` | 32 | No hard value found |
| 285 | `app/services/eda/cross_correlator.py` | 385 | No hard value found |
| 286 | `app/services/eda/derived_tables.py` | 128 | No hard value found |
| 287 | `app/services/eda/engine.py` | 191 | No hard value found |
| 288 | `app/services/eda/group_by_analyzer.py` | 257 | No hard value found |
| 289 | `app/services/eda/normalizer.py` | 508 | No hard value found |
| 290 | `app/services/eda/predictive_models.py` | 425 | No hard value found |
| 291 | `app/services/eda/report_generator.py` | 159 | No hard value found |
| 292 | `app/services/eda/temporal_analyzer.py` | 196 | No hard value found |
| 293 | `app/services/enrichment/__init__.py` | 48 | No hard value found |
| 294 | `app/services/enrichment/adapters/__init__.py` | 18 | No hard value found |
| 295 | `app/services/enrichment/adapters/feature_synthesis_adapter.py` | 159 | No hard value found |
| 296 | `app/services/enrichment/adapters/profiling_adapter.py` | 95 | No hard value found |
| 297 | `app/services/enrichment/adapters/statistical_adapter.py` | 113 | No hard value found |
| 298 | `app/services/enrichment/adapters/symbolic_adapter.py` | 110 | No hard value found |
| 299 | `app/services/enrichment/adapters/unit_adapter.py` | 183 | No hard value found |
| 300 | `app/services/enrichment/column_grouping.py` | 256 | No hard value found |
| 301 | `app/services/enrichment/config.py` | 133 | No hard value found |
| 302 | `app/services/enrichment/formula_engine.py` | 549 | No hard value found |
| 303 | `app/services/enrichment/formula_registry.py` | 255 | No hard value found |
| 304 | `app/services/enrichment/interaction_engine.py` | 158 | No hard value found |
| 305 | `app/services/enrichment/models.py` | 133 | No hard value found |
| 306 | `app/services/enrichment/pipeline.py` | 163 | No hard value found |
| 307 | `app/services/enrichment/primitive_deriver.py` | 376 | No hard value found |
| 308 | `app/services/enrichment/profiler.py` | 340 | No hard value found |
| 309 | `app/services/enrichment/relationship_engine.py` | 320 | No hard value found |
| 310 | `app/services/enrichment/table_synthesizer.py` | 176 | No hard value found |
| 311 | `app/services/enrichment/utility_evaluator.py` | 102 | No hard value found |
| 312 | `app/services/evidence/__init__.py` | 19 | No hard value found |
| 313 | `app/services/evidence/candidate_findings.py` | 795 | No hard value found |
| 314 | `app/services/evidence/chart_converters.py` | 83 | No hard value found |
| 315 | `app/services/evidence/coverage_manifest.py` | 91 | No hard value found |
| 316 | `app/services/evidence/evidence_models.py` | 47 | No hard value found |
| 317 | `app/services/evidence/evidence_store.py` | 78 | No hard value found |
| 318 | `app/services/executive_story.py` | 243 | No hard value found |
| 319 | `app/services/fact_discovery.py` | 389 | No hard value found |
| 320 | `app/services/function_library/__init__.py` | 36 | No hard value found |
| 321 | `app/services/function_library/base.py` | 173 | No hard value found |
| 322 | `app/services/function_library/catalog/__init__.py` | 1 | No hard value found |
| 323 | `app/services/function_library/catalog/financial/__init__.py` | 1 | No hard value found |
| 324 | `app/services/function_library/catalog/financial/margin_leakage.py` | 125 | No hard value found |
| 325 | `app/services/function_library/catalog/operational/__init__.py` | 1 | No hard value found |
| 326 | `app/services/function_library/catalog/operational/compound_cohort_disparity.py` | 109 | No hard value found |
| 327 | `app/services/function_library/catalog/workforce/__init__.py` | 1 | No hard value found |
| 328 | `app/services/function_library/catalog/workforce/bradford_disruption.py` | 146 | No hard value found |
| 329 | `app/services/function_library/catalog/workforce/lost_capacity_hours.py` | 113 | No hard value found |
| 330 | `app/services/function_library/catalog/workforce/talent_9box.py` | 94 | No hard value found |
| 331 | `app/services/function_library/catalog/workforce/turnover_exposure.py` | 128 | No hard value found |
| 332 | `app/services/function_library/registry.py` | 147 | No hard value found |
| 333 | `app/services/function_library/storage.py` | 183 | No hard value found |
| 334 | `app/services/gateway/__init__.py` | 39 | No hard value found |
| 335 | `app/services/gateway/assistant_identity.py` | 293 | No hard value found |
| 336 | `app/services/gateway/contracts.py` | 142 | No hard value found |
| 337 | `app/services/gateway/model_health.py` | 181 | No hard value found |
| 338 | `app/services/gateway/model_manager.py` | 89 | No hard value found |
| 339 | `app/services/gateway/observability.py` | 75 | No hard value found |
| 340 | `app/services/governance/__init__.py` | 60 | No hard value found |
| 341 | `app/services/governance/data_sanitizer.py` | 163 | No hard value found |
| 342 | `app/services/governance/drift_monitor.py` | 239 | No hard value found |
| 343 | `app/services/governance/eval_engine.py` | 580 | No hard value found |
| 344 | `app/services/governance/ledger.py` | 350 | No hard value found |
| 345 | `app/services/governance/resilience.py` | 124 | No hard value found |
| 346 | `app/services/hr_period_analytics.py` | 449 | No hard value found |
| 347 | `app/services/hybrid_retrieval.py` | 108 | No hard value found |
| 348 | `app/services/industrial/__init__.py` | 18 | No hard value found |
| 349 | `app/services/industrial/bradford_model.py` | 165 | No hard value found |
| 350 | `app/services/industrial/pipeline_runner.py` | 66 | No hard value found |
| 351 | `app/services/industrial/talent_9box_model.py` | 130 | No hard value found |
| 352 | `app/services/industrial/workforce_strain_model.py` | 193 | No hard value found |
| 353 | `app/services/industrial_analytics.py` | 27 | No hard value found |
| 354 | `app/services/ingestion_job_manager.py` | 276 | No hard value found |
| 355 | `app/services/input_intelligence/__init__.py` | 95 | No hard value found |
| 356 | `app/services/input_intelligence/classifier.py` | 257 | No hard value found |
| 357 | `app/services/input_intelligence/dashboard_bridge.py` | 166 | No hard value found |
| 358 | `app/services/input_intelligence/eda_bridge.py` | 118 | No hard value found |
| 359 | `app/services/input_intelligence/intent_engine.py` | 317 | No hard value found |
| 360 | `app/services/input_intelligence/memory_bridge.py` | 126 | No hard value found |
| 361 | `app/services/input_intelligence/models.py` | 379 | No hard value found |
| 362 | `app/services/input_intelligence/multi_sheet.py` | 220 | No hard value found |
| 363 | `app/services/input_intelligence/presentation_bridge.py` | 86 | No hard value found |
| 364 | `app/services/input_intelligence/profiler.py` | 349 | No hard value found |
| 365 | `app/services/input_intelligence/service.py` | 228 | No hard value found |
| 366 | `app/services/input_intelligence/snapshot_manager.py` | 365 | No hard value found |
| 367 | `app/services/insight_registry.py` | 121 | No hard value found |
| 368 | `app/services/investigation/__init__.py` | 31 | No hard value found |
| 369 | `app/services/investigation/dimension_investigation.py` | 216 | No hard value found |
| 370 | `app/services/investigation/entity_investigation.py` | 163 | No hard value found |
| 371 | `app/services/investigation/investigation_common.py` | 171 | No hard value found |
| 372 | `app/services/investigation/model_group_investigation.py` | 101 | No hard value found |
| 373 | `app/services/investigation/store_investigation.py` | 141 | No hard value found |
| 374 | `app/services/investigation/timeseries_investigation.py` | 134 | No hard value found |
| 375 | `app/services/investigation_service.py` | 195 | No hard value found |
| 376 | `app/services/leadership_report.py` | 98 | No hard value found |
| 377 | `app/services/local_voiceover.py` | 26 | No hard value found |
| 378 | `app/services/planner/__init__.py` | 13 | No hard value found |
| 379 | `app/services/planner/chart_evaluator.py` | 190 | No hard value found |
| 380 | `app/services/planner/chart_plans.py` | 324 | No hard value found |
| 381 | `app/services/planner/entity_classifier.py` | 66 | No hard value found |
| 382 | `app/services/planner/numeric_parser.py` | 38 | No hard value found |
| 383 | `app/services/planner/sanitizer.py` | 18 | No hard value found |
| 384 | `app/services/pptx/__init__.py` | 66 | No hard value found |
| 385 | `app/services/pptx/pptx_card_layouts.py` | 406 | No hard value found |
| 386 | `app/services/pptx/pptx_charts.py` | 618 | No hard value found |
| 387 | `app/services/pptx/pptx_layouts.py` | 36 | No hard value found |
| 388 | `app/services/pptx/pptx_styles.py` | 127 | No hard value found |
| 389 | `app/services/pptx/pptx_visual_layouts.py` | 231 | No hard value found |
| 390 | `app/services/pptx/resolved_layout.py` | 171 | No hard value found |
| 391 | `app/services/presentation/__init__.py` | 52 | No hard value found |
| 392 | `app/services/presentation/ai_deck_planner.py` | 159 | No hard value found |
| 393 | `app/services/presentation/ai_enrichment.py` | 264 | No hard value found |
| 394 | `app/services/presentation/ai_slide_materializer.py` | 463 | No hard value found |
| 395 | `app/services/presentation/audience_content.py` | 46 | No hard value found |
| 396 | `app/services/presentation/builders/__init__.py` | 51 | No hard value found |
| 397 | `app/services/presentation/builders/common.py` | 234 | No hard value found |
| 398 | `app/services/presentation/builders/governance_builder.py` | 324 | No hard value found |
| 399 | `app/services/presentation/builders/headwinds_builder.py` | 149 | No hard value found |
| 400 | `app/services/presentation/builders/industrial_builder.py` | 251 | No hard value found |
| 401 | `app/services/presentation/builders/roadmap_builder.py` | 212 | No hard value found |
| 402 | `app/services/presentation/builders/strengths_builder.py` | 137 | No hard value found |
| 403 | `app/services/presentation/builders/summary_builder.py` | 224 | No hard value found |
| 404 | `app/services/presentation/chart_fallbacks.py` | 389 | No hard value found |
| 405 | `app/services/presentation/chart_synthesizer.py` | 296 | No hard value found |
| 406 | `app/services/presentation/claim_verifier.py` | 637 | No hard value found |
| 407 | `app/services/presentation/content_validation.py` | 147 | No hard value found |
| 408 | `app/services/presentation/data_profiler.py` | 305 | No hard value found |
| 409 | `app/services/presentation/decision_deck.py` | 142 | No hard value found |
| 410 | `app/services/presentation/deck_generator.py` | 786 | No hard value found |
| 411 | `app/services/presentation/director/__init__.py` | 54 | No hard value found |
| 412 | `app/services/presentation/director/director_models.py` | 272 | No hard value found |
| 413 | `app/services/presentation/director/evidence_context.py` | 38 | No hard value found |
| 414 | `app/services/presentation/director/information_extractor.py` | 187 | No hard value found |
| 415 | `app/services/presentation/director/intent_planner.py` | 178 | No hard value found |
| 416 | `app/services/presentation/director/narrative_planner.py` | 202 | No hard value found |
| 417 | `app/services/presentation/director/plan_adapter.py` | 337 | No hard value found |
| 418 | `app/services/presentation/director/plan_validator.py` | 115 | No hard value found |
| 419 | `app/services/presentation/director/slide_planner.py` | 493 | No hard value found |
| 420 | `app/services/presentation/governed_presentation_builder.py` | 243 | No hard value found |
| 421 | `app/services/presentation/grounded_review.py` | 106 | No hard value found |
| 422 | `app/services/presentation/hr_report.py` | 279 | No hard value found |
| 423 | `app/services/presentation/job_manager.py` | 273 | No hard value found |
| 424 | `app/services/presentation/memory/__init__.py` | 41 | No hard value found |
| 425 | `app/services/presentation/memory/backfill.py` | 101 | No hard value found |
| 426 | `app/services/presentation/memory/embedding_service.py` | 112 | No hard value found |
| 427 | `app/services/presentation/memory/memory_indexer.py` | 366 | No hard value found |
| 428 | `app/services/presentation/memory/memory_provenance.py` | 75 | No hard value found |
| 429 | `app/services/presentation/memory/memory_store.py` | 385 | No hard value found |
| 430 | `app/services/presentation/memory/retrieval_service.py` | 224 | No hard value found |
| 431 | `app/services/presentation/narration_service.py` | 255 | No hard value found |
| 432 | `app/services/presentation/observer_ai.py` | 334 | No hard value found |
| 433 | `app/services/presentation/orchestrator/__init__.py` | 68 | No hard value found |
| 434 | `app/services/presentation/orchestrator/specialists/__init__.py` | 11 | No hard value found |
| 435 | `app/services/presentation/orchestrator/specialists/deterministic_executors.py` | 115 | No hard value found |
| 436 | `app/services/presentation/orchestrator/tool_contracts.py` | 80 | No hard value found |
| 437 | `app/services/presentation/orchestrator/tool_registry.py` | 536 | No hard value found |
| 438 | `app/services/presentation/pdf_export.py` | 123 | No hard value found |
| 439 | `app/services/presentation/pipeline_orchestrator.py` | 690 | No hard value found |
| 440 | `app/services/presentation/presentation_reorderer.py` | 208 | No hard value found |
| 441 | `app/services/presentation/presentation_visual_spec.py` | 998 | No hard value found |
| 442 | `app/services/presentation/qa/__init__.py` | 35 | No hard value found |
| 443 | `app/services/presentation/qa/deck_consistency_auditor.py` | 84 | No hard value found |
| 444 | `app/services/presentation/qa/deterministic_qa.py` | 224 | No hard value found |
| 445 | `app/services/presentation/qa/qa_models.py` | 131 | No hard value found |
| 446 | `app/services/presentation/qa/qa_orchestrator.py` | 195 | No hard value found |
| 447 | `app/services/presentation/qa/repair_engine.py` | 227 | No hard value found |
| 448 | `app/services/presentation/qa/screenshot_service.py` | 160 | No hard value found |
| 449 | `app/services/presentation/resolved_pdf.py` | 359 | No hard value found |
| 450 | `app/services/presentation/review_gates.py` | 423 | No hard value found |
| 451 | `app/services/presentation/scope_detector.py` | 564 | No hard value found |
| 452 | `app/services/presentation/slide_layout.py` | 286 | No hard value found |
| 453 | `app/services/presentation/slide_mutator.py` | 618 | No hard value found |
| 454 | `app/services/presentation/spatial_overflow_monitor.py` | 686 | No hard value found |
| 455 | `app/services/presentation/spatial_planner.py` | 1180 | No hard value found |
| 456 | `app/services/presentation/storyline_generator.py` | 142 | No hard value found |
| 457 | `app/services/presentation/theme_background.py` | 24 | No hard value found |
| 458 | `app/services/presentation/topic_contract.py` | 576 | No hard value found |
| 459 | `app/services/presentation/validation/__init__.py` | 54 | No hard value found |
| 460 | `app/services/presentation/validation/golden_corpus.py` | 181 | No hard value found |
| 461 | `app/services/presentation/validation/scenarios.py` | 580 | No hard value found |
| 462 | `app/services/presentation/validation/theme_integrity_gate.py` | 140 | No hard value found |
| 463 | `app/services/presentation/validation/validation_models.py` | 145 | No hard value found |
| 464 | `app/services/presentation/visual/__init__.py` | 73 | No hard value found |
| 465 | `app/services/presentation/visual/adapters/__init__.py` | 7 | No hard value found |
| 466 | `app/services/presentation/visual/adapters/echarts_adapter.py` | 177 | No hard value found |
| 467 | `app/services/presentation/visual/adapters/html_adapter.py` | 186 | No hard value found |
| 468 | `app/services/presentation/visual/adapters/pptx_adapter.py` | 127 | No hard value found |
| 469 | `app/services/presentation/visual/chart_models.py` | 192 | No hard value found |
| 470 | `app/services/presentation/visual/chart_selector.py` | 232 | No hard value found |
| 471 | `app/services/presentation/visual/design_tokens.py` | 138 | No hard value found |
| 472 | `app/services/presentation/visual/diagram_models.py` | 126 | No hard value found |
| 473 | `app/services/presentation/visual/layout_registry.py` | 351 | No hard value found |
| 474 | `app/services/presentation/visual/layout_selector.py` | 94 | No hard value found |
| 475 | `app/services/presentation/visual/visual_intelligence.py` | 251 | No hard value found |
| 476 | `app/services/presentation/visual/visual_models.py` | 105 | No hard value found |
| 477 | `app/services/presentation/visual/visual_validator.py` | 213 | No hard value found |
| 478 | `app/services/presentation/visual_binding.py` | 36 | No hard value found |
| 479 | `app/services/presentation_quality_auditor.py` | 414 | No hard value found |
| 480 | `app/services/presentation_service.py` | 49 | No hard value found |
| 481 | `app/services/rag_service.py` | 96 | No hard value found |
| 482 | `app/services/report_generator.py` | 280 | No hard value found |
| 483 | `app/services/reporting/__init__.py` | 16 | No hard value found |
| 484 | `app/services/reporting/report_planner.py` | 197 | No hard value found |
| 485 | `app/services/reporting/workflow_orchestrator.py` | 264 | No hard value found |
| 486 | `app/services/reporting/writer_agent.py` | 147 | No hard value found |
| 487 | `app/services/semantic_mapping.py` | 329 | No hard value found |
| 488 | `app/services/shared_evidence_package.py` | 186 | No hard value found |
| 489 | `app/services/sheet_merger.py` | 210 | No hard value found |
| 490 | `app/services/sheet_naming_pipeline.py` | 415 | No hard value found |
| 491 | `app/services/storytelling/__init__.py` | 20 | No hard value found |
| 492 | `app/services/storytelling/story_generator.py` | 96 | No hard value found |
| 493 | `app/services/storytelling/story_profiler.py` | 367 | No hard value found |
| 494 | `app/services/storytelling/story_relational.py` | 262 | No hard value found |
| 495 | `app/services/time_series_forecast.py` | 373 | No hard value found |
| 496 | `app/services/visual_intelligence.py` | 28 | No hard value found |
| 497 | `app/services/visuals/__init__.py` | 21 | No hard value found |
| 498 | `app/services/visuals/comparative_suite.py` | 218 | No hard value found |
| 499 | `app/services/visuals/dashboard_builder.py` | 65 | No hard value found |
| 500 | `app/services/visuals/dynamic_suite.py` | 183 | No hard value found |
| 501 | `app/services/visuals/industrial_suite.py` | 128 | No hard value found |
| 502 | `app/services/visuals/raw_projections.py` | 160 | No hard value found |
| 503 | `app/services/visuals/visual_common.py` | 108 | No hard value found |