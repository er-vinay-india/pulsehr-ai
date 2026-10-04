# HighView (PulseHR AI)

**HighView** is a local spreadsheet analytics, industrial workforce intelligence, and executive presentation automation platform powered by **HRIDAY**. Uploaded CSV, Excel, and SQLite tables are the sole source of truth; factual calculations are computed deterministically by code with zero LLM math or hallucinated metrics.

---

## 📚 Documentation Tree (Parent Node)

All project documentation is modularized into focused, small document nodes for rapid scanning:

```
README.md (Root Parent Node)
│
├── docs/architecture/
│   ├── system-overview.md        # HighView & HRIDAY philosophy, zero LLM math, evidence store
│   ├── analytics-pipeline.md     # 9-stage generic evidence discovery & claim verification
│   ├── presentation-engine.md    # 13-phase deck orchestrator, layout standards, native exports
│   └── decision-intelligence.md  # Sub-millisecond rule classification & finding prioritization
│
├── docs/features/
│   ├── adaptive-dashboard.md     # 7 registered domains, 3 progressive disclosure tiers
│   ├── hriday-copilot.md         # Assistant identity layer, leakage guard, grain invariants
│   └── visual-analytics.md       # 9-Box matrix, Bradford Factor, Burnout Strain, Forecasting
│
├── docs/design-system/
│   ├── theme-tokens.md           # HighView palette (Navy, Emerald, Ivory), dark mode, WCAG AAA
│   └── slide-layouts.md          # 16:9 spatial geometry (960×540 pt), typography, table rules
│
└── docs/engineering/
    ├── test-architecture.md      # 3-tier test pyramid, 8 domain modules, pre-push impact runner
    └── job-recovery.md           # Background process recovery, PID verification, bounded retries
```

### Quick Links by Category

| Category | Node | Description |
| :--- | :--- | :--- |
| **Architecture** | [system-overview.md](docs/architecture/system-overview.md) | Architectural axiom: deterministic computation and zero LLM arithmetic. |
| | [analytics-pipeline.md](docs/architecture/analytics-pipeline.md) | 9-stage single-source-of-truth pipeline from raw CSV to verified facts. |
| | [presentation-engine.md](docs/architecture/presentation-engine.md) | 13-phase presentation pipeline with structured speaker notes and native exports. |
| | [decision-intelligence.md](docs/architecture/decision-intelligence.md) | High-speed rule-based classification (<1ms) and brief prioritization. |
| **Features** | [adaptive-dashboard.md](docs/features/adaptive-dashboard.md) | 7 detected domains, 3 progressive disclosure tiers (`GLANCE`, `EXPLAIN`, `INSPECT`). |
| | [hriday-copilot.md](docs/features/hriday-copilot.md) | HRIDAY persona guardrails and analytical query grain integrity. |
| | [visual-analytics.md](docs/features/visual-analytics.md) | McKinsey 9-Box, Bradford Factor ($B=S^2 \times D$), Burnout Index, Holt forecasting. |
| **Design System** | [theme-tokens.md](docs/design-system/theme-tokens.md) | HighView color tokens, dark/light mode pairs, and WCAG contrast standards. |
| | [slide-layouts.md](docs/design-system/slide-layouts.md) | 16:9 stage geometry, typography scale, and table wrapping protection. |
| **Engineering** | [test-architecture.md](docs/engineering/test-architecture.md) | Unit/Integration/Benchmark tiers, pytest markers, and impact analyzer. |
| | [job-recovery.md](docs/engineering/job-recovery.md) | Surviving dev server restarts via SQLite PID-aware job claiming. |

> *Archived & uncompacted historical documents are preserved in the [trash/](trash/README.md) folder for reference and restoration.*

---

## ⚡ Quickstart

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

## 🏛️ Core Principles & Architecture

### 1. Unified Generic Analytics Pipeline (`WorkflowOrchestrator`)
Evidence-grounded analytics pipeline that works across any tabular dataset:
- **Stage 1: Validation**: `DatasetValidator` performs automated data hygiene and boundary verification.
- **Stage 2: Semantic Profiling & Grain**: `SemanticClassifier` determines column semantic roles and row-level grain.
- **Stage 3: Opportunity Mapping**: `OpportunityMapGenerator` identifies admissible mathematical breakdowns.
- **Stage 4: Deterministic Fact Discovery**: `CandidateFactDiscoveryEngine` computes exact empirical facts (`FACT-XXX`).
- **Stage 5: Interestingness Ranking**: `FactInterestingnessRanker` scores findings by business impact and surprise magnitude.
- **Stage 6: Evidence-Grounded Interpretation**: `AnalystAgent` (Qwen 3.5) synthesizes strategic themes bound to verified facts.
- **Stage 7: Deterministic Claim Audit**: `InterpretationClaimValidator` validates assertions against hallucinated metrics.
- **Stage 8: Intelligent Visuals**: `FactVisualizer` maps candidate facts directly to interactive chart specifications.
- **Stage 9: Unified Caching & Consumers**: `WorkflowOrchestrator` caches artifacts via dataset SHA-256 fingerprint (`_GENERIC_WORKFLOW_CACHE`).

### 2. Tiered Local AI Architecture
The system minimizes local compute by executing tasks through a tiered hierarchy:
- **`Layer 1: LRU Brief Cache` (< 5ms)**: Instant retrieval of pre-computed decision briefs.
- **`Layer 2: Pluggable DecisionEngine` (< 1ms)**: `RuleDecisionEngine` and `EmbeddingDecisionEngine` (`nomic-embed-text`) classify business intent, routing deterministic questions (positives, concerns, actions, rankings) directly to code with zero LLM tokens.
- **`Layer 3: Deterministic Data Engine` (< 15ms)**: Pure Python/Pandas calculates rollups, distributions, and rankings, tagged with cryptographic `FACT-XXX` IDs.
- **`Layer 4: Central ModelRouter & ModelManager`**: Directs exploratory/narrative tasks to specialized open-weights models running locally on Ollama:
  - `FAST`: `phi4-mini:latest` (metadata, schemas, edge classification)
  - `ANALYST`: `qwen3.5:9b` (finding discovery, statistical interpretation)
  - `REASONER`: `deepseek-r1:7b` (root cause analysis, causal reasoning)
  - `WRITER`: `gemma4:12b` (executive narratives, slide takeaways)
  - `CRITIC`: `deepseek-r1:7b` (claim verification, hallucination checks)

---

## 🔌 API Endpoints Summary

- **Adaptive Dashboard**:
  - `GET /api/adaptive-dashboard/primary-element`: Top 2 primary visual cards.
  - `GET /api/adaptive-dashboard/findings`: Domain-specific verified findings and narratives.
- **Decision Brief**:
  - `GET /api/analytics/decision-brief`: Deterministic executive brief (strengths, headwinds, initiatives).
  - `POST /api/analytics/decision-brief/prioritize`: Permutation-only finding reordering.
  - `POST /api/analytics/decision-brief/voiceover`: Spoken presenter script.
- **Presentation Engine**:
  - `POST /api/presentations/generate`: Trigger 13-phase presentation generation.
  - `POST /api/presentations/scope-preview`: Preflight slide count, evidence items, and layout preview.
  - `GET /api/presentations/decks/{id}`: Fetch complete presentation specification.
  - `GET /api/reports/presentation/latest`: Download latest generated 16:9 PowerPoint deck.
- **HRIDAY Copilot**:
  - `POST /api/copilot/generic`: Dedicated factual Q&A with 0-LLM math.
  - `POST /api/copilot/query` / `stream`: Conversational chat with intent auto-routing.
  - `POST /api/copilot/war-room`: Multi-model council consensus generation.
  - `GET /api/copilot/identity`: Public HRIDAY identity metadata.
- **Sheets & Ingestion**:
  - `POST /api/upload/file`: Ingest CSV/XLSX and trigger background profiling.
  - `GET /api/sheets`: Sheet catalog, column profiles, and relationships.
  - `GET /api/sheets/{id}/rows`: Paginated source rows.
  - `DELETE /api/upload/datasets/{id}`: Purge dataset and associated cached artifacts.

---

## 🧪 Verification & Testing

```bash
# Run tests strictly impacted by your git changes
python scripts/run_impacted_tests.py --impacted

# Run only ultra-fast unit tests for impacted modules (< 2s)
python scripts/run_impacted_tests.py --impacted --unit

# Run a specific domain module
python scripts/run_impacted_tests.py --module presentation
python scripts/run_impacted_tests.py --module dashboard --unit

# Frontend production build & theme tests
cd frontend
npm run test:theme
npm run build
```
