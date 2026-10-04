# HighView (PulseHR AI)

**HighView** is a local-first enterprise analytics, industrial workforce intelligence, and executive presentation automation platform powered by **HRIDAY**. Uploaded CSV, Excel, and SQLite tables are the sole source of truth; factual calculations are computed deterministically by code with zero LLM math or hallucinated metrics.

---

## 📚 Integrated Architectural Layers (Parent Node)

All project documentation is structured into **5 integrated architectural layers**, eliminating artificial separation:

```
README.md (Root Parent Node)
│
├── docs/system-architecture.md             # Master Blueprint: End-to-End Layer Integration
│
└── docs/layers/
    ├── 01-deterministic-truth-engine.md    # Layer 1: Ingestion, Profiling, Candidate Facts & Industrial Models
    ├── 02-cognitive-routing-governance.md  # Layer 2: Decision Routing, Model Gateway, HRIDAY Identity & Claim Audit
    ├── 03-consumer-delivery-engine.md      # Layer 3: Adaptive Dashboard, 13-Phase Presentation Studio & Copilot
    ├── 04-visual-grammar-spatial.md        # Layer 4: Design Tokens, 16:9 Baseline Geometry & Table Wrapping
    └── 05-platform-reliability-ops.md      # Layer 5: Startup Job Recovery, 3-Tier Test Pyramid & Impact Runner
```

### Architectural Layer Directory

| Layer | Architecture Specification | Key Responsibilities & Code Modules |
| :--- | :--- | :--- |
| **Blueprint** | [system-architecture.md](docs/system-architecture.md) | **Master Architectural Blueprint**: End-to-end data flow, system axioms, and inter-layer contracts. |
| **Layer 1** | [01-deterministic-truth-engine.md](docs/layers/01-deterministic-truth-engine.md) | **Deterministic Truth & Evidence Engine**: Ingestion (`upload.py`), semantic profiling (`semantic_classifier.py`), fact discovery (`FACT-XXX`), industrial models (McKinsey 9-Box, Bradford Factor $B=S^2 \times D$, Burnout Strain, Holt-damped forecast), cryptographic evidence ledger (`EVID-XXX`, SHA-256 seal). |
| **Layer 2** | [02-cognitive-routing-governance.md](docs/layers/02-cognitive-routing-governance.md) | **Cognitive Routing & Governance**: Sub-millisecond intent routing (`RuleDecisionEngine` <1ms), `ModelRouter` escalation, role-based gateway (`FAST`, `ANALYST`, `REASONER`, `WRITER`, `CRITIC`), `assistant_identity.py` (HRIDAY persona, `identity_leak` guard), and deterministic claim verification. |
| **Layer 3** | [03-consumer-delivery-engine.md](docs/layers/03-consumer-delivery-engine.md) | **Consumer Delivery Engine**: Adaptive dashboard (7 registered domains, 3 progressive disclosure tiers `GLANCE`/`EXPLAIN`/`INSPECT`), automated 13-phase presentation engine (`PIPELINE_PHASES`), interactive copilot & council war room, and executive decision brief API. |
| **Layer 4** | [04-visual-grammar-spatial.md](docs/layers/04-visual-grammar-spatial.md) | **Visual Grammar & Spatial Contract**: HighView WCAG AAA tokens (`_tokens.scss`), unified 16:9 baseline geometry (`960 × 540 pt`), typography scale (38pt cover, 30pt header, 18pt body), dense table overflow protection, and native python-pptx / headless PDF exporters. |
| **Layer 5** | [05-platform-reliability-ops.md](docs/layers/05-platform-reliability-ops.md) | **Platform Reliability & Test Ops**: Startup background worker recovery (`recover_presentation_jobs`), SQLite atomic claims, 3-tier test pyramid, and pre-push impact analyzer (`scripts/run_impacted_tests.py`). |

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

## 🏛️ Core Architectural Axioms

1. **Spreadsheets are Sole Ground Truth**: Uploaded CSV, XLSX, and SQLite tables are the immutable source of analytical facts.
2. **Zero LLM Arithmetic**: Language models never execute arithmetic calculations, generate statistical percentages, or estimate metric aggregates.
3. **Dual Evidence Identification**:
   - `FACT-XXX`: Raw empirical candidate facts discovered by `CandidateFactDiscoveryEngine` (e.g., `FACT-001`).
   - `EVID-XXX`: Audited evidence claims anchored to presentation slides and decision briefs (e.g., `EVID-EXEC-01`).
4. **100% Direct Inheritance Guarantee**: Downstream presentation decks, dashboards, and conversational answers inherit directly from the same evidence store.
5. **Permutation-Only Prioritization**: AI prioritization is restricted to reordering existing finding IDs; models cannot mutate calculations or invent claims.
6. **Query Grain Invariant**: Retrieving a department-level aggregate is never accepted as an answer for an employee-level calculation.

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
