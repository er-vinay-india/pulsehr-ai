# PulseHR AI

Local spreadsheet analytics, industrial workforce intelligence, and enterprise AI report generation platform. Uploaded CSV and Excel sheets are the sole source of truth; factual calculations are computed deterministically by code with zero LLM math or hallucinated metrics.

---

## Quickstart

```bash
# Backend (FastAPI + Uvicorn)
cd backend
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 8020 --reload
```

```bash
# Frontend (React + Vite + SCSS)
cd frontend
npm install
npm run dev -- --port 5175
```

---

## Core Capabilities & Architecture

### 1. Role-Based AI Report Architecture & Offline Model Orchestration
The reporting engine completely decouples business code from concrete model strings, routing requests via a central `ModelGateway` to specialized local models running on Ollama:
- **`FAST` (`Phi-4 Mini 3.8B`)**: Real-time classification, schema labeling, instant UI suggestions.
- **`ANALYST` (`Qwen 3.5 9.7B`)**: Materiality scoring, finding discovery, classifying operational gaps.
- **`REASONER` (`DeepSeek-R1 7.6B`)**: Multi-step business logic, root cause analysis, strategic trade-offs (with `<think>` token stripping).
- **`WRITER` (`Google Gemma 4 12B`)**: Executive narrative prose, slide bullet points, leadership-level synthesis.
- **`CRITIC` (`DeepSeek-R1 7.6B`)**: Strict mathematical claim verification, hallucination detection, automated repair loop.

### 2. Deterministic Calculation Engine (Zero LLM Math)
- **`DatasetValidator`**: Automated quality checks for empty files, duplicate column headers, boundary violations, and null ratios with structured `DataQualityReport`.
- **`DatasetProfiler`**: Classifies columns into measures, dimensions, timelines, and identifiers with descriptive statistical distributions.
- **`MetricEngine`**: Computes baseline aggregates, segment groupings, period-over-period differences, and candidate facts ranked by statistical significance (`abs(diff) * log(sample_size)`).
- **LLMs are strictly forbidden from calculating metrics.**

### 3. Canonical Evidence Store & Sentence Lineage
- **`EvidenceStore`**: Canonical ledger indexing and storing structured `Finding` objects (`F-001`, `F-002`, ...).
- **Sentence-Level Lineage**: Every claim in the executive narrative logs an audit record in `TraceRegistry` linking the exact sentence to its cited finding ID, backing metric, and underlying CSV source rows.
- **Critic Verification & Repair**: The Critic audits every claim as `SUPPORTED`, `PARTIALLY_SUPPORTED`, `UNSUPPORTED`, or `CONTRADICTORY`. Unsupported claims automatically trigger a correction loop.

### 4. Upload-Driven Ingestion & Zero-Leakage Pipeline
- **Ingestion Studio**: Upload CSV or Excel workbooks (.xlsx, .xls, .csv). Each file and sheet retains its original rows and columns.
- **Automated Industrial Ingestion**: Every upload immediately computes verified People Analytics models without human intervention.
- **Complete Deletion Pipeline**: Deleting a dataset cascades to sheets, rows, search entries, vectors, relationships, and purges all cached narratives (`executive_narratives`).
- **Bulk Cleanup Endpoint**: `DELETE /api/upload/datasets` completely purges all workspace data in a single operation.

### 5. Executive Overview: Chart-First Intelligence & Prioritised Facts
- **Desktop 2/3 + 1/3 Split Canvas**: A wide main area contains the most meaningful charts above the fold, paired with a column of prioritised facts linked directly to supporting charts with focus animations.
- **Contextual Investigation Drawer (`GET /api/analytics/investigate`)**: Deep drill-downs displaying formula steps, episode breakdown, raw SQLite rows, and cross-sheet connected evidence.
- **Progressive Chunked Loading**: Decoupled into 4 parallel asynchronous streams with dedicated skeleton loaders (`/base`, `/visuals`, `/story`, `/relational`).

### 6. AI Presentation Engine & PowerPoint Export
- **Acoustic Orb Presenter**: Immersive voiceover narration with visual soundwave particles synced to presentation slides.
- **Native 16:9 PPTX Slides**: High-contrast widescreen presentations with editable chart components and an embedded cryptographic evidence ledger.

---

## API Summary

- `POST /api/reports/orchestrate`: Full 8-stage role-based workflow execution (Validate -> Profile -> Metrics -> Findings -> Plan -> Write -> Critic -> Render).
- `GET /api/reports/presentation`: Download latest generated 16:9 PowerPoint deck.
- `GET /api/reports/executive-html`: Printable executive brief in self-contained HTML.
- `GET /api/sheets`: All sheets, column profiles, and relationship evidence.
- `GET /api/sheets/{id}/rows`: Paginated source rows.
- `GET /api/sheets/{id}/projections`: Direct data extract charts and column summary statistics.
- `GET /api/analytics/overview/base`: Instant base catalogue metrics (< 20ms).
- `GET /api/analytics/overview/visuals`: Industrial visual intelligence dashboard (~95ms).
- `GET /api/analytics/overview/story`: AI executive story and quality audit.
- `GET /api/analytics/overview/relational`: Cross-sheet relational intelligence.
- `GET /api/analytics/investigate`: Deep contextual investigation drill-down.
- `DELETE /api/upload/datasets/{id}`: Delete dataset and purge associated cached narratives.
- `DELETE /api/upload/datasets`: Bulk workspace purge.
- `POST /api/copilot/query`: Grounded chat or tool execution (`calculate`, `industrial_metric`, `presentation`, `arithmetic`).

---

## Verification

```bash
# Backend unit & integration suite (212 tests)
cd backend
PYTHONPATH=. .venv/bin/pytest tests/ -v

# Architecture-specific test suite
PYTHONPATH=. .venv/bin/pytest tests/test_model_gateway_roles.py \
  tests/test_data_engine_deterministic.py \
  tests/test_evidence_store_traceability.py \
  tests/test_critic_claim_verification.py \
  tests/test_workflow_orchestrator.py -v

# Frontend production build & test suite
cd ../frontend
npm run build
npm run test
```
