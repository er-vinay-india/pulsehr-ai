# Layer 5: Platform Reliability & Test Operations

> **Parent:** [README.md](../../README.md) &rsaquo; [System Architecture](../system-architecture.md) &rsaquo; **Layer 5**

---

## 1. Architectural Mission: Operational Resilience & Fast Feedback

Layer 5 is the cross-cutting engineering backbone supporting all active application layers. It ensures that background generation jobs survive process reloads, that pre-semantic table reconstruction satisfies strict safety benchmarks, and that local developers can verify code modifications with sub-second feedback without test suite pollution.

```mermaid
flowchart LR
    subgraph Background Resilience
        Reload[Server Reload / Restart] --> Lifespan[app/main.py Lifespan]
        Lifespan --> Recovery[recover_presentation_jobs]
        Recovery --> DB[(SQLite Job Claims)]
    end

    subgraph Test Operations & Benchmarks
        GitDiff[Git Diff / Working Tree] --> Analyzer[Impact Analyzer]
        Analyzer --> T1[Tier 1: Unit <50ms]
        Analyzer --> T2[Tier 2: Integration 0.5-5s]
        Analyzer --> Bench[Safety Benchmark Suite]
    end
```

---

## 2. Core Subsystems & Codebase Proof

### A. Startup Background Job Recovery
Implemented in `backend/app/services/presentation/pipeline_orchestrator.py` and invoked during `app/main.py` lifespan:
1. **PID Verification**: Scans jobs where status is `pending` or `running`. Checks the recorded worker PID against the host OS process table.
2. **Atomic SQLite Reclaim**: If the owning PID is no longer alive, claims the job atomically via SQLite compare-and-set updates, incrementing `recovery_attempt_count`.
3. **Preserved Generation Scope**: Resumes execution using the identical job ID, retaining source sheet IDs, brief settings, instructions, and theme tokens.
4. **Bounded Recovery Attempts**: Automatic recovery is bounded to **3 attempts** (`retry_count <= 3`). If a job fails 3 times, it transitions to terminal failure to prevent infinite reload loops.
5. **Terminal State Protection**: Completed (`ready`), user-cancelled (`cancelled`), or validation-failed (`failed`) jobs are never relaunched.

### B. Reconstruction Safety Benchmark Harness
Implemented in `backend/app/services/adaptive_table_reconstruction/safety_benchmark.py` and verified by `backend/tests/test_reconstruction_safety_benchmark.py`:
- Evaluates the pre-semantic reconstruction engine against golden regression datasets (including the 455-row CPCB 2022 ambient air quality report):
  - **Boundary Accuracy**: Precision in separating non-tabular metadata, headers, and footnote sentinels ($\ge 99.0\%$).
  - **Header Reconstruction Accuracy**: Verification of compound column collapses and delimiter safety ($\ge 98.0\%$).
  - **Logical Record Accuracy**: 1:1 match of reconstructed rows against verified ground-truth records ($\ge 99.0\%$, achieving 435/435 on golden fixture).
  - **False Merge Rate**: Protection against joining distinct records into a single row ($\le 0.5\%$).
  - **False Split Rate**: Protection against leaving wrapped multi-line cells split across rows ($\le 1.0\%$).
  - **Model Overreach Rate**: Ensuring the governed model escalator is never invoked on unambiguous deterministic rows ($\le 0.0\%$).

### C. Dataset Isolation & Deletion Cascade Regression Harness
Implemented in `backend/tests/test_dataset_isolation_and_deletion_cascade.py`:
- Validates the bidirectional deletion and zero-leakage invariant:
  1. **A &rarr; Delete &rarr; B Semantic Disjointness**: Ingesting Dataset A (environmental), executing cascaded deletion, and ingesting Dataset B (workforce) guarantees exactly zero tokens of A (`SO2`, `NO2`, `PM10`, `PM2.5`, `Jharia`, `Brynihat`) appear anywhere in B's rendered payload.
  2. **B &rarr; Delete &rarr; A Reverse Disjointness**: Ingesting Dataset B, deleting it, and ingesting A guarantees exactly zero tokens of B (`Attendance`, `Department`, `Approved Leave`, `Employee`, `WFO`) appear anywhere in A's payload.
  3. **Simultaneous Co-Existence Isolation**: When multiple datasets co-exist in SQLite, zero cross-dataset joins are allowed in `sheet_relationships` (`left_sheet.dataset_id == right_sheet.dataset_id` for 100% of rows).
  4. **Post-Deletion Orphan Verification**: Deletion is transactional and asserts zero orphan records across all descendant tables (`orphan_check = "PASS"`).

### D. Modular Test Pyramid (`backend/pytest.ini`)

| Execution Tier | Pytest Marker | Latency Target | Scope & Invariants |
| :--- | :--- | :---: | :--- |
| **Tier 1: Unit** | `@pytest.mark.unit` | `< 50ms` / test | Pure in-memory algorithmic transformers. Zero DB writes, zero network, zero LLM calls. |
| **Tier 2: Integration** | `@pytest.mark.integration`, `@pytest.mark.db` | `0.5s - 5s` / mod | FastAPI endpoints, SQLite schema migrations, multi-stage pipelines, reconstruction flows, isolation tests. |
| **Tier 3: Benchmark** | `@pytest.mark.benchmark` | `30s - 15m` | Multi-case LLM evaluations, large matrix latency profiling (quarantined by default). |

### E. The 8 Registered Domain Modules (`tests/module_registry.py`)
1. **`enrichment`**: Semantic enrichment, formula discovery, table synthesizer.
2. **`eda`**: Exploratory data analysis, distributions, group-by metrics.
3. **`dashboard`**: Adaptive multi-domain dashboard, visual presence gates, and disclosure cards.
4. **`presentation`**: Slide director, pipeline orchestrator, layout selection, visual QA.
5. **`copilot`**: Conversational Q&A, query planner, multi-model war room.
6. **`critic`**: Deterministic claim validation and evidence store traceability.
7. **`ingestion`**: Dataset upload, adaptive table reconstruction, sheet catalog.
8. **`decision_intelligence`**: Rule/embedding decision engines, rankings, and executive briefing.

### F. Pre-Push Impact Runner (`scripts/run_impacted_tests.py`)
Inspects `git status` and `git diff` against `origin/main` to identify modified files and executes only the affected module tests:

```bash
# Run tests strictly for modules impacted by your working changes
python scripts/run_impacted_tests.py --impacted

# Run only ultra-fast unit tests for impacted modules (< 2s)
python scripts/run_impacted_tests.py --impacted --unit

# Run a specific domain module
python scripts/run_impacted_tests.py --module ingestion
python scripts/run_impacted_tests.py --module dashboard --unit

# Git pre-push hook mode (used before git push)
python scripts/run_impacted_tests.py --pre-push
```
