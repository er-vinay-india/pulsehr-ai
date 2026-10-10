# HighView (PulseHR AI)

**HighView** is a local-first enterprise analytics, cross-domain decision intelligence, and executive presentation automation platform powered by **HRIDAY**. Uploaded spreadsheets and CSVs are ingested through a governed pre-semantic reconstruction layer where physical layouts are reconstructed into validated logical records before semantic profiling. All factual calculations are computed deterministically in code with zero LLM math, hallucinated metrics, or fabricated aggregations.

---

## 📚 Integrated Architectural Layers

All project documentation is structured into **5 integrated architectural layers** and dedicated subsystem specifications:

```
README.md (Root Parent Node)
│
├── docs/system-architecture.md                 # Master Blueprint: End-to-End Layer Integration
├── docs/adaptive-table-reconstruction.md       # Pre-Semantic Reconstruction: Ingestion & Safety Benchmark
├── docs/domain-governance-and-dashboards.md    # Multi-Domain Governance, Boundaries & Entitlements
│
└── docs/layers/
    ├── 01-deterministic-truth-engine.md        # Layer 1: Ingestion, Reconstruction, Profiling, Facts & Aggregations
    ├── 02-cognitive-routing-governance.md      # Layer 2: Decision Routing, Model Escalator, Gateways & Narrative Integrity
    ├── 03-consumer-delivery-engine.md          # Layer 3: Executive Dashboard, Data Explorer, Studio & Copilot
    ├── 04-visual-grammar-spatial.md            # Layer 4: Design Tokens, 16:9 Baseline Geometry & Visual Intent Grammar
    └── 05-platform-reliability-ops.md          # Layer 5: Worker Recovery, Test Pyramid & Impact Runner
```

### Architectural Layer Directory

| Layer | Specification Document | Key Responsibilities & Code Modules |
| :--- | :--- | :--- |
| **Blueprint** | [system-architecture.md](docs/system-architecture.md) | **Master Architectural Blueprint**: End-to-end data flow, physical-to-logical ingestion, cross-domain governance, and inter-layer contracts. |
| **Reconstruction** | [adaptive-table-reconstruction.md](docs/adaptive-table-reconstruction.md) | **Adaptive Table Reconstruction Subsystem**: Pre-semantic grid capture, multi-row header repair, continuation stitching, sentinel preservation, 3D confidence, and safety benchmarks. |
| **Governance** | [domain-governance-and-dashboards.md](docs/domain-governance-and-dashboards.md) | **Domain Governance & Entitlements**: Dashboard vs. Data Explorer boundary, scenario capability gating, generic ranking polarity, and aggregation semantics. |
| **Layer 1** | [01-deterministic-truth-engine.md](docs/layers/01-deterministic-truth-engine.md) | **Deterministic Truth & Evidence Engine**: Physical-to-logical pipeline (`AdaptiveTableReconstructionEngine`), semantic profiling (`profiler.py`), non-additive metric rules, fact discovery (`FACT-XXX`), cross-domain industrial models, and cryptographic evidence ledger (`EVID-XXX`). |
| **Layer 2** | [02-cognitive-routing-governance.md](docs/layers/02-cognitive-routing-governance.md) | **Cognitive Routing & Governance**: Sub-millisecond intent routing (`RuleDecisionEngine` <1ms), governed `ModelEscalator`, role-based gateway (`FAST`, `ANALYST`, `REASONER`, `WRITER`, `CRITIC`), `DomainNarrativeIntegrity`, `TemporalLabelIntegrity`, and deterministic claim verification. |
| **Layer 3** | [03-consumer-delivery-engine.md](docs/layers/03-consumer-delivery-engine.md) | **Consumer Delivery Engine**: Executive Dashboard ("What requires my attention?"), 7-tab Data Explorer ("Show me the analysis behind it."), 13-phase presentation engine, slide mutator, scenario entitlement gating, and HRIDAY Copilot. |
| **Layer 4** | [04-visual-grammar-spatial.md](docs/layers/04-visual-grammar-spatial.md) | **Visual Grammar & Spatial Contract**: HighView WCAG AAA design tokens (`_tokens.scss`), 16:9 spatial baseline (`960 × 540 pt`), ECharts visual intent grammar (bar, scatter, line, waterfall), dense table overflow protection, and native python-pptx / PDF exporters. |
| **Layer 5** | [05-platform-reliability-ops.md](docs/layers/05-platform-reliability-ops.md) | **Platform Reliability & Test Ops**: Startup background worker recovery (`recover_presentation_jobs`), SQLite atomic claims, 3-tier test pyramid, reconstruction safety benchmark, and pre-push impact runner (`scripts/run_impacted_tests.py`). |

---

## 🏛️ Core Architectural Axioms

1. **Physical File &ne; Logical Table**: HighView never assumes one physical CSV/Excel row equals one analytical record. Physical documents pass through `AdaptiveTableReconstructionEngine` to resolve multi-row headers, preambles, wrapped multi-row records, and sentinels before entering SQLite storage or semantic profiling.
2. **Zero LLM Arithmetic**: Language models never execute calculations, compute statistical percentages, or estimate metric aggregates. All numbers are computed strictly in Python/Pandas/NumPy.
3. **Deterministic-First, Governed Model Fallback**: Clean tabular files execute on a fast zero-token deterministic path (<50ms). Structural ambiguity triggers governed model assistance (`ModelEscalator`) with typed Pydantic proposals, 3D confidence scoring, field-role risk weighting, and deterministic post-validation.
4. **Non-Additive Aggregation Semantics**: Rate, ratio, percentage, and environmental concentration measures (e.g. $\text{SO}_2, \text{NO}_2, \text{PM}_{10}, \text{PM}_{2.5}$) are recognized as non-additive. Additive `SUM`/`Total` operations are strictly banned on these metrics in favor of arithmetic means, medians, or distributions.
5. **Ordinal & Identifier Exclusion**: Columns representing sequential indices, document numbers, or unique identifiers (e.g., `Sr. No.`, `ID`, file reference codes) are classified as ordinals/identifiers and permanently excluded from numeric measures and ranking analytics.
6. **Domain Capability Entitlement**: Specialized domain modules (e.g., Workforce Scenario Explorer) are capability-gated. Non-workforce domains (such as environmental air quality or commercial retail) cleanly suppress irrelevant tools, buttons, and narratives.
7. **Strict Architectural Responsibility Boundary**:
   - **Executive Dashboard**: Answers *"What requires my attention?"* (Governed 5-KPI strip, compact briefing, 3 curated visual stories, Top 3 / Bottom 3 ranking overview, scenario summary when entitled).
   - **Data Explorer**: Answers *"Show me the analysis behind it."* (Full deep-dive tabs: Overview, Rankings, Trends, Relationships, Distributions, Evidence, Technical).
8. **Visual Intent Truthfulness**: Visual representations must reflect their analytical intent. Measure-by-measure associations render as true scatter plots with entity coordinates, and synthetic temporal labels (`Week 1...5`) are strictly forbidden when no time dimension exists.
9. **Generic Ranking Polarity**: Rankings support arbitrary entity types (cities, departments, stores, products) with configurable polarity (`HIGHER_IS_BETTER` vs. `LOWER_IS_BETTER`).
10. **Dual Evidence Ledger (`FACT-XXX` & `EVID-XXX`)**: Empirical facts discovered by `CandidateFactDiscoveryEngine` are cryptographically sealed with a SHA-256 hash. Presentation decks, dashboards, and conversational answers inherit from this identical evidence store.

---

## 🔌 API Endpoints Summary

- **Ingestion & Ingestion Intelligence**:
  - `POST /api/upload/file`: Ingest raw CSV/XLSX through `AdaptiveTableReconstructionEngine`, persist clean logical records into SQLite, and run semantic profiling.
  - `GET /api/sheets`: Sheet catalog, column profiles, domain classifications, and relationships.
  - `GET /api/sheets/{id}/rows`: Paginated source logical rows.
  - `DELETE /api/upload/datasets/{id}`: Purge dataset and associated cached artifacts.
- **Adaptive Dashboard & Data Explorer**:
  - `GET /api/adaptive-dashboard/primary-element`: Primary visual story elements for the executive dashboard.
  - `GET /api/adaptive-dashboard/findings`: Domain-governed verified findings and narrative recommendations.
  - `GET /api/adaptive-dashboard/rankings`: Generic entity ranking payload with polarity and distribution metadata.
  - `GET /api/adaptive-dashboard/scenarios`: Governed scenario simulations (gated for workforce domains).
- **Decision Brief & Reporting**:
  - `GET /api/analytics/decision-brief`: Deterministic executive brief (strengths, headwinds, initiatives).
  - `POST /api/analytics/decision-brief/prioritize`: Permutation-only finding reordering.
  - `POST /api/analytics/decision-brief/voiceover`: Spoken presenter script.
  - `POST /api/reports/orchestrate`: Full generic workflow orchestration (Reconstruction &rarr; Profiling &rarr; Opportunities &rarr; Facts &rarr; Ranking &rarr; Interpretation &rarr; Visuals &rarr; Deck Spec).
- **Presentation Engine**:
  - `POST /api/presentations/generate`: Trigger 13-phase presentation generation pipeline.
  - `POST /api/presentations/scope-preview`: Preflight slide count, evidence items, and layout preview.
  - `POST /api/presentations/mutate-slide`: Conversational slide mutation engine (re-slice, re-type, filter, theme, revert) with snapshot rollback.
  - `GET /api/reports/presentation/latest`: Download latest generated 16:9 PowerPoint deck.
- **HRIDAY Copilot**:
  - `POST /api/copilot/generic`: Dedicated factual Q&A with 0-LLM math.
  - `POST /api/copilot/query/stream`: Conversational chat with intent auto-routing & slide mutation events.
  - `POST /api/copilot/war-room`: Multi-model council consensus generation.
  - `GET /api/copilot/identity`: Public HRIDAY identity metadata.

---

## 🧪 Verification & Testing

```bash
# Backend test suite (Deterministic reconstruction, governance, rankings, stories)
cd backend
source .venv/bin/activate
pytest tests/test_adaptive_table_reconstruction.py tests/test_generic_entity_ranking.py tests/test_story_planner_and_governed_pipeline.py

# Run all backend unit and integration tests
pytest

# Frontend test suite & production build
cd frontend
npm test -- --run
npm run build
```

---

## ⚡ Quickstart

```bash
# 1. Backend (FastAPI + Uvicorn)
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 8000 --reload

# 2. Frontend (React + Vite + SCSS)
cd frontend
npm install
npm run dev -- --port 5175
```
