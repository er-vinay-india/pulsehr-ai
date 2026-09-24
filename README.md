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

### 1. Unified Generic Analytics Pipeline (Single Source of Truth)
PulseHR AI implements an evidence-grounded analytics pipeline that works across any tabular dataset (retail, manufacturing, logistics, finance, HR):
- **Stage 1: Validation**: `DatasetValidator` performs automated data hygiene and boundary verification.
- **Stage 2: Semantic Profiling & Grain**: `SemanticClassifier` determines column semantic roles and row-level grain without domain coupling.
- **Stage 3: Opportunity Mapping**: `OpportunityMapGenerator` identifies admissible mathematical breakdowns (distributions, trends, segment comparisons, correlations).
- **Stage 4: Deterministic Fact Discovery**: `CandidateFactDiscoveryEngine` computes exact statistical facts (`FACT-XXX`) with zero LLM math.
- **Stage 5: Interestingness Ranking**: `FactInterestingnessRanker` scores findings by surprise, penalizing derived identities (`A = B * C`) and small-baseline percentage spikes.
- **Stage 6: Evidence-Grounded Interpretation**: `AnalystAgent` (Qwen 3.5) synthesizes strategic themes strictly bound to verified facts.
- **Stage 7: Deterministic Claim Audit**: `InterpretationClaimValidator` validates assertions against hallucinated intersections or unsupported causality.
- **Stage 8: Intelligent Visuals**: `FactVisualizer` maps candidate facts directly to interactive chart specifications (scatter, column, line, donut, boxplot).
- **Stage 9: Unified Caching & Consumers**: `WorkflowOrchestrator` caches the artifact via dataset SHA-256 fingerprint, serving PPTX decks, dashboards, and `GenericCopilotEngine` with 0-LLM factual Q&A.
- *Detailed specification*: See [Generic Analytics Pipeline Docs](docs/GENERIC_ANALYTICS_PIPELINE.md).

### 2. Layered "Cheapest Path First" Local AI Architecture
The system minimizes local compute by executing tasks through a tiered hierarchy:
- **`Layer 1: LRU Brief Cache` (< 5ms)**: Instant retrieval of pre-computed decision briefs.
- **`Layer 2: Pluggable DecisionEngine` (< 1ms)**: `RuleDecisionEngine` and `EmbeddingDecisionEngine` (`nomic-embed-text`) classify business intent, routing deterministic questions (positives, concerns, actions, rankings) directly to code with zero LLM tokens.
- **`Layer 3: Deterministic Data Engine` (< 15ms)**: Pure Python/Pandas calculates rollups, distributions, and rankings, tagged with cryptographic `FACT-XXX` IDs.
- **`Layer 4: Central ModelRouter & ModelManager`**: Directs exploratory/narrative tasks to specialized open-weights models running locally on Ollama:
  - **`FAST` (`Phi-4 Mini 3.8B`)**: Real-time classification, schema naming, metadata extraction (~250ms).
  - **`ANALYST` (`Qwen 3.5 9.7B`)**: Materiality scoring, finding discovery, classifying operational gaps (~1.5s).
  - **`REASONER` (`DeepSeek-R1 7.6B`)**: Multi-step business logic, root cause analysis, strategic trade-offs (with `<think>` token stripping, ~3.5s).
  - **`WRITER` (`Google Gemma 4 12B`)**: Executive narrative prose, slide bullet points, leadership-level synthesis (~1.8s).
  - **`CRITIC` (`DeepSeek-R1 7.6B`)**: Strict mathematical claim verification, hallucination detection, automated repair loop.
  - **Confidence-based Escalation**: Automatic escalation from `FAST` -> `ANALYST` -> `REASONER` if confidence drops below thresholds (< 0.65 / < 0.50).

### 3. Conversational Copilot with 0-LLM Calculations
- **`GenericCopilotEngine`**: Provides conversational drill-downs and Q&A over uploaded spreadsheets.
- **0 LLM Calls for Factual Math**: Arithmetic totals, averages, segment rankings, and period trends are resolved deterministically in code with instant response times.
- **Pre-computed Evidence Reuse**: "Surprise me" and entity inquiries reuse existing ranked facts and interpretation insights from ingestion.

---

## API Summary

- `POST /api/reports/orchestrate`: Full generic workflow execution (Validation → Profiling → Opportunities → Facts → Ranking → Interpretation → Audit → Visuals → Deck Spec).
- `POST /api/copilot/generic`: Dedicated generic conversational Q&A via `GenericCopilotEngine`.
- `POST /api/copilot/query`: Conversational endpoint with deterministic auto-routing (generic tabular analysis vs legacy HR operations).
- `POST /api/reports/presentation`: Export 16:9 presentation deck (generic or legacy).
- `GET /api/reports/presentation/latest`: Download latest generated 16:9 PowerPoint deck.
- `GET /api/reports/executive-html`: Printable executive brief in self-contained HTML.
- `GET /api/sheets`: All sheets, column profiles, and relationship evidence.
- `GET /api/sheets/{id}/rows`: Paginated source rows.
- `GET /api/sheets/{id}/projections`: Direct data extract charts and column summary statistics.
- `GET /api/analytics/overview/base`: Instant base catalogue metrics (< 20ms).
- `GET /api/analytics/overview/visuals`: Visual intelligence dashboard.
- `GET /api/analytics/overview/story`: AI executive story and quality audit.
- `GET /api/analytics/overview/relational`: Cross-sheet relational intelligence.
- `GET /api/analytics/investigate`: Deep contextual investigation drill-down.
- `DELETE /api/upload/datasets/{id}`: Delete dataset and purge associated cached narratives.
- `GET /api/sheets`: All sheets, column profiles, and relationship evidence.
- `GET /api/sheets/{id}/rows`: Paginated source rows.
- `GET /api/sheets/{id}/projections`: Direct data extract charts and column summary statistics.
- `GET /api/analytics/overview/base`: Instant base catalogue metrics (< 20ms).
- `GET /api/analytics/overview/visuals`: Visual intelligence dashboard.
- `GET /api/analytics/overview/story`: AI executive story and quality audit.
- `GET /api/analytics/overview/relational`: Cross-sheet relational intelligence.
- `GET /api/analytics/investigate`: Deep contextual investigation drill-down.
- `DELETE /api/upload/datasets/{id}`: Delete dataset and purge associated cached narratives.
- `DELETE /api/upload/datasets`: Bulk workspace purge.

---

## Verification

```bash
# Backend generic pipeline tests
cd backend
PYTHONPATH=. .venv/bin/pytest \
  tests/test_generic_semantic_profiler.py \
  tests/test_generic_candidate_fact_discovery.py \
  tests/test_generic_interestingness_ranker.py \
  tests/test_evidence_grounded_interpretation.py \
  tests/test_fact_visualizer.py \
  tests/test_generic_workflow_orchestrator.py \
  tests/test_generic_copilot_engine.py -v

# Layered architecture benchmarks & role verification
PYTHONPATH=. .venv/bin/pytest tests/test_model_architecture_benchmarks.py \
  tests/test_model_gateway_roles.py \
  tests/test_copilot_contextual_business.py \
  tests/test_data_engine_deterministic.py \
  tests/test_evidence_store_traceability.py \
  tests/test_critic_claim_verification.py \
  tests/test_workflow_orchestrator.py -v

# Frontend production build & test suite
cd ../frontend
npm run build
npm run test
```
