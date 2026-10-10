# Adaptive Table Reconstruction Subsystem

> **Parent:** [README.md](../README.md) &rsaquo; [System Architecture](system-architecture.md) &rsaquo; **Adaptive Table Reconstruction**

---

## 1. Architectural Mission

Traditional tabular analytics pipelines assume that every physical row in an uploaded CSV or spreadsheet corresponds directly to one logical database record (`pd.read_csv(...)`). In enterprise reporting, governmental open data, and industrial audits, this assumption fails catastrophically:

- **Document Preambles & Metadata:** Headers are preceded by title blocks, reference identifiers, and classification notes (e.g., `EQ-11099/38/2021-AQMN-HO-CPCB-HO`).
- **Multi-Row Compound Headers:** Metric names and measurement conditions span 2–4 physical rows (e.g., Row 3: `PM 2.5 Data`, Row 4: `SO2`, Row 5: `Annual average`).
- **Wrapped / Continued Records:** Long text strings wrap into adjacent physical rows where column values are split across rows (e.g., Row 17: `Rajahmundry/Rajamahend`, Row 18: `ravaram,6,13,66,30`).
- **Domain Sentinels vs. Numeric Zeros:** Missing observations are encoded as domain-specific text codes (`NM` = Not Monitored, `-` = Not Applicable, `NR` = Not Reported). Naive type coercion converts these to `0.0`, corrupting averages, medians, and distribution tails.

The **Adaptive Table Reconstruction Subsystem** (`backend/app/services/adaptive_table_reconstruction/`) operates **prior to semantic profiling and database persistence**. It reconstructs messy physical grids into validated, source-faithful logical tables while tracking complete reconstruction provenance.

---

## 2. Ingestion Pipeline Data Flow

```text
Physical File (CSV / XLSX)
         │
         ▼
[1. GridCapture] ── Raw token matrix, whitespace & newline preservation
         │
         ▼
[2. RowRoleClassifier] ── Preamble, Header, Data, Wrapped Continuation, Footnote, Blank
         │
         ▼
[3. HeaderTreeBuilder] ── Multi-row hierarchy collapse, delimiter-safe unification
         │
         ▼
[4. ContinuationDetector] ── Heuristic record stitching (prefix/suffix wrap, column alignment)
         │
         ▼
[5. SentinelResolver] ── Typed sentinel taxonomy (NM, -, NR, NA -> distinct missing states)
         │
         ▼
    Ambiguity Check ── Has unresolved wrap or conflicting header roles?
         ├── NO  ──> Fast Deterministic Path (< 50ms, 0 tokens)
         └── YES ──> [6. Governed ModelEscalator] (Typed Pydantic Proposals)
                         │
                         ▼
[7. ConfidenceRiskEngine] ── 3D Confidence (Structural, Semantic, Fidelity) + Field-Role Risk
         │
         ▼
[8. StructuralValidator] ── 6 Deterministic Integrity Gates (Purity, Column Count, Grain)
         │
         ▼
    Final Disposition:
    ├── VALIDATED        ── High confidence, passed all deterministic gates
    ├── PROPOSED         ── Model-assisted recommendation requiring confirmation
    ├── REVIEW_REQUIRED  ── Low confidence or high field-role risk; flagged for user
    └── REJECTED         ── Integrity gate violation; fail-safe fallback to raw table
         │
         ▼
Reconstructed Logical Table (Dataframe)
         │
         ▼
[SQLite Table Persistence] ── Clean records stored in pulsehr.sqlite3
         │
         ▼
[Semantic Profiling & Enrichment] ── Grain detection, domain classification, opportunity map
```

---

## 3. Subsystem Components & Responsibilities

| Module | Primary Class / Functions | Key Responsibility |
| :--- | :--- | :--- |
| `grid_capture.py` | `GridCapture` | Ingests raw bytes; detects file encoding and delimiter without pandas coercion; builds un-mutated 2D string grid. |
| `row_role_classifier.py` | `RowRoleClassifier`, `RowRole` | Categorizes physical rows into `PREAMBLE`, `HEADER`, `DATA_RECORD`, `CONTINUATION_RECORD`, `FOOTNOTE`, or `BLANK`. |
| `header_tree_builder.py` | `HeaderTreeBuilder` | Collapses stacked multi-row headers into canonical compound column identifiers while maintaining hierarchic lineage. |
| `continuation_detector.py` | `ContinuationDetector` | Detects physical lines split across cell borders (hyphenations, partial tokens, unmatched quotes) and merges them into parent records. |
| `sentinel_resolver.py` | `SentinelResolver`, `SentinelType` | Preserves non-numeric domain sentinels (`NM`, `-`, `NR`, `BDL`) as typed sentinels. **Strictly forbids conversion to numeric zero**. |
| `model_escalator.py` | `GovernedModelEscalator` | Invoked strictly upon deterministic ambiguity. Queries local LLM via typed Pydantic output schemas (`ModelProposal`). |
| `confidence_risk_engine.py` | `ConfidenceRiskEngine` | Evaluates 3D confidence scores and weights them against column operational roles. Assigns final reconstruction disposition. |
| `structural_validator.py` | `StructuralValidator` | Six deterministic post-validation gates verifying column homogeneity, grain consistency, and row stability. |
| `safety_benchmark.py` | `ReconstructionSafetyBenchmark` | Golden-fixture regression harness evaluating boundary accuracy, header accuracy, and false merge/split rates. |
| `contracts.py` | Typed Pydantic models | Complete schema contracts for proposals, provenance records, and telemetry payloads. |

---

## 4. Governed Model Escalation & 3D Confidence Framework

### A. Governed Escalation Policy
- **Deterministic-First Principle:** Clean files never invoke the model escalator. They execute deterministically in `< 50ms` with zero token expenditure.
- **Escalation Trigger:** Escalation occurs only when ambiguity heuristics trip (e.g. conflicting column alignments, ambiguous continuation prefixes, unresolvable multi-tier header tokens).
- **Typed Pydantic Contracts:** The model is never permitted to emit free-form text or raw markdown. It must return structured, schema-validated Pydantic payloads (`ReconstructionProposal`).
- **Deterministic Post-Validation:** Every model suggestion passes through `StructuralValidator`. If a model proposal violates schema purity or introduces row count instability, it is immediately discarded.

### B. 3D Confidence Scoring
The system computes three orthogonal confidence dimensions:
1. **Structural Confidence ($C_{struct}$):** Measures grid alignment, row classification stability, and delimiter consistency.
2. **Semantic Confidence ($C_{sem}$):** Measures post-reconstruction data type purity and column value homogeneity.
3. **Fidelity Confidence ($C_{fid}$):** Measures raw token conservation, ensuring characters are neither lost nor hallucinated during record stitching.

$$\text{Composite Confidence} = w_1 \cdot C_{struct} + w_2 \cdot C_{sem} + w_3 \cdot C_{fid}$$

### C. Field-Role-Aware Risk Weighting ($R_{field}$)
Structural changes to columns with high operational risk require higher confidence thresholds:
- **`entity_key` / `primary_measure`:** High risk. Modifications require Composite Confidence $\ge 0.85$.
- **`categorical_dimension`:** Medium risk. Requires Composite Confidence $\ge 0.70$.
- **`text_comment` / `metadata`:** Low risk. Requires Composite Confidence $\ge 0.55$.

### D. Reconstruction Dispositions
- `VALIDATED`: Composite confidence $\ge 0.75$, passed all 6 integrity gates. Automatically committed to SQLite.
- `MODEL_ASSISTED_PROPOSED`: Generated via governed model escalation with high confidence ($\ge 0.75$) and passing all post-validation gates.
- `REVIEW_REQUIRED`: Confidence $< 0.75$ or high field-role risk. Table is staged with a review warning in the Technical Tab.
- `REJECTED`: Fails one or more structural integrity gates. Fallback to raw ingestion path without unverified row joins.

---

## 5. Source-Faithful Sentinel Preservation

Numeric statistical profiles fail when missing value sentinels are coerced to zeros or generic `NaN`s. The `SentinelResolver` registers domain-specific missing states:

| Sentinel Token | Canonical `SentinelType` | Meaning | Downstream Semantic Rule |
| :--- | :--- | :--- | :--- |
| `NM` | `MISSING_NOT_MEASURED` | Station active, parameter not monitored | Excluded from mean/median; counted in coverage deficit. |
| `-` | `NOT_APPLICABLE` | Station not configured for this parameter | Excluded from calculations; noted as non-applicable. |
| `NR` | `NOT_EVALUATED` | Observation not reported in this cycle | Flagged as data completeness lag; zero arithmetic impact. |
| `BDL` | `BELOW_DETECTION_LIMIT` | Concentration below instrument threshold | Preserved as censored observation; never converted to 0. |
| `NA`, `null`, `""` | `UNKNOWN_MISSING` | Unspecified null | Standard missing record handling. |

> [!CAUTION]
> Under no circumstances does the reconstruction engine replace `NM` or `-` with `0.0`. Doing so would artificially depress pollution averages and distort risk ratings.

---

## 6. Golden Regression Fixture: CPCB Ambient Air Quality Report

To ensure the reconstruction engine handles complex real-world layouts without hardcoded heuristics, the CPCB 2022 Ambient Air Quality report (`Location_data_2022.csv`) serves as a permanent regression fixture:

- **Raw Physical Layout:** 455 rows $\times$ 8 columns.
  - Rows 1–2: Office reference preambles (`EQ-11099/38/2021-AQMN-HO-CPCB-HO`).
  - Rows 3–6: Multi-tier compound header (`PM 2.5 Data`, `SO2 / Annual average`, `NO2 / Annual average`).
  - Rows 17–18: Wrapped geographic record (`Rajahmundry/Rajamahend` on line 17, `ravaram,6,13,66,30` on line 18).
  - Data cells containing `NM` and `-` sentinels.
- **Reconstructed Output:** 435 clean logical rows $\times$ 7 columns.
  - Preamble stripped from analytical table.
  - Headers unified: `SO2_Annual_Average`, `NO2_Annual_Average`, `PM10_Annual_Average`, `PM2.5_Annual_Average`.
  - Wrapped record joined into single logical row: `Rajahmundry/Rajamahendravaram`.
  - Sentinels preserved with full provenance.
  - 435 logical rows persisted to SQLite and processed by semantic profiler.

---

## 7. Safety Benchmark & Metrics

The test suite in [`backend/tests/test_reconstruction_safety_benchmark.py`](file:///Users/vinayksharma/Developer/pulsehr-ai/backend/tests/test_reconstruction_safety_benchmark.py) evaluates reconstruction quality against benchmark standards:

| Benchmark Metric | Definition | Production Target | Golden Fixture Result |
| :--- | :--- | :---: | :---: |
| **Boundary Accuracy** | Precision in separating preamble/footnotes from table | $\ge 99.0\%$ | **100.0%** |
| **Header Reconstruction Accuracy** | Correct compound column hierarchy mapping | $\ge 98.0\%$ | **100.0%** |
| **Logical Record Accuracy** | Logical row count vs ground-truth record count | $\ge 99.0\%$ | **100.0% (435/435)** |
| **False Merge Rate** | Merging independent records that should remain distinct | $\le 0.5\%$ | **0.0%** |
| **False Split Rate** | Failing to join wrapped physical records | $\le 1.0\%$ | **0.0%** |
| **Model Overreach Rate** | Model altering non-ambiguous rows | $\le 0.0\%$ | **0.0%** |
| **Review-Required Rate** | Proportion of ambiguous rows safely flagged | Bounded | **0.0% on clean / golden** |

---

## 8. Technical Tab Observability

All reconstruction metadata, confidence scores, and provenance traces are exposed via the **Data Explorer &rarr; Technical** tab:
- **Disposition Badge:** Displays `VALIDATED` or `MODEL_ASSISTED_PROPOSED`.
- **Confidence Radar:** Visualizes Structural, Semantic, and Fidelity scores.
- **Provenance Ledger:** Searchable list of every boundary split, header collapse, and continuation merge with before/after line references.
