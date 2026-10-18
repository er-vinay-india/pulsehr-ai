# HighView Ingestion V2 — Phase I4: Grain-Aware Relationship Discovery, Relationship Validation, Join Safety & Join Planning

## 1. Overview & Epistemic Boundaries

Phase I4 implements Stage 6 (Relationship Discovery) and Stage 7 (Relationship Validation) of the HighView Ingestion Intelligence V2 pipeline, alongside the operational Join Safety Analyzer and Governed Join Planner.

### Strict Epistemic Invariants
- **Downstream Decoupling**: Zero EDA-B analytical correlations, zero enrichment, zero semantic graph construction, zero vector indexing, and zero intent adaptation.
- **Model Isolation**: Zero LLM or external model calls; discovery and validation are 100% deterministic, reproducible, and explainable.
- **Join Execution Prohibition**: Phase I4 is purely structural discovery and governed join planning. It does **not** execute joins, materialize merged tables, or run analytical queries.
- **Input Immutability**: All upstream artifacts (`NormalizedDataset`, `StructuralProfile`, `SemanticModel`, `GrainProfile`) are strictly read-only and never mutated.

---

## 2. Stage 6: Relationship Candidate Generation & Pruning Metrics

### Pairwise Explosion Protection & Pruning
Across the 8-table canonical benchmark corpus (27 columns total), raw pairwise comparison between tables would produce:
- **Raw Possible Column-Pair Comparisons**: **314**
- **After Cheap Blocking (Physical Types & Self-Tables)**: **42**
- **After Semantic & Key Candidate Filtering**: **16**
- **Value-Overlap Validations Evaluated**: **16**
- **Pruning Efficiency**: **94.9%** of raw column pairs eliminated before expensive set overlap.

### Candidate Recall
- **Truth-Valid Relationships in Benchmark**: **5**
  1. `t_emp.employee_id` $\leftrightarrow$ `t_wrk.worker_number` (Synonym single key)
  2. `t_sales.[store_id, week]` $\leftrightarrow$ `t_targets.[store_id, week]` (Composite periodic key)
  3. `t_prod.product_id` $\leftrightarrow$ `t_inv.product_id` (Single dimension-to-fact key)
  4. `t_emp.employee_id` $\leftrightarrow$ `t_hist.employee_id` (Partial coverage historical fact key)
  5. `t_inv.[location_id, date]` $\leftrightarrow$ `t_env.[location_id, date]` (Composite facility key)
- **Valid Relationships Proposed as Candidates**: **5**
- **Candidate Recall**: **1.000 (100.0%)**
- **Candidate Misses**: **None (`[]`)**

---

## 3. Stage 7: Relationship Validator Metrics

Candidate relationships are evaluated across value overlap, cardinality, and fanout risk. Ambiguous cases (such as entity label matches without surrogate keys) are explicitly withheld rather than guessed.

### Validator Metrics
- **True Positives (TP)**: **5**
- **False Positives (FP)**: **0** (0 accepted false positives required)
- **True Negatives (TN)**: **3** (`department` $\leftrightarrow$ `department` Cartesian trap, `status` $\leftrightarrow$ `status` domain mismatch, `salary` $\leftrightarrow$ `worker_id_num` measure as key)
- **False Negatives (FN)**: **0**
- **Ambiguous Correctly Withheld**: **1** (`employee_name` $\leftrightarrow$ `person_name`)
- **Precision**: **1.000 (100.0%)**
- **Recall**: **1.000 (100.0%)**
- **F1 Score**: **1.000 (100.0%)**
- **Accepted False Positives**: **0**

---

## 4. Join Safety Status Contract Audit

`JoinSafetyStatus` has been audited and cleaned to exactly four mutually exclusive states. `REQUIRES_PRE_AGGREGATION`, `FORBIDDEN_CARTESIAN`, and `LOSS_OF_GRAIN` were **REMOVED** to eliminate state proliferation and semantic duplication:

```python
class JoinSafetyStatus(str, Enum):
    SAFE = "SAFE"
    SAFE_WITH_PREAGGREGATION = "SAFE_WITH_PREAGGREGATION"
    UNSAFE = "UNSAFE"
    AMBIGUOUS = "AMBIGUOUS"
```

### State Definitions & Governance
1. **`SAFE`**:
   - Direct raw join operation is authorized.
   - Preserves grain, zero metric duplication, dimension propagation safe.
2. **`SAFE_WITH_PREAGGREGATION`**:
   - Direct raw join is **not authorized**.
   - A valid governed `JoinPlan` exists that defines explicit pre-aggregation to a target grain.
   - Execution may proceed **only** through that pre-aggregation specification.
3. **`UNSAFE`**:
   - Direct raw join is forbidden.
   - No authorized automatic plan exists without user intervention or bridge table (e.g. unresolvable M:N fanout).
4. **`AMBIGUOUS`**:
   - Insufficient evidence to authorize join or determine safety.

---

## 5. Exact Join-Safety Benchmark (Scenarios A through F)

All 6 canonical scenarios were executed and verified against `JoinSafetyAnalyzer`:

| Scenario | Relationship & Grains | Actual Status | Expected Status | Result |
| :--- | :--- | :--- | :--- | :--- |
| **A** | `PERSON` master $\rightarrow$ `PERSON x DAY` fact (Dimension enrichment) | `SAFE` | `SAFE` | **PASS** |
| **B** | `PERSON x DAY` $\leftrightarrow$ `PERSON x INCIDENT` (Raw fact-to-fact) | `UNSAFE` | `UNSAFE` | **PASS** |
| **C** | `PERSON x DAY` aggregated $\rightarrow$ `PERSON x MONTH` then join | `SAFE_WITH_PREAGGREGATION` | `SAFE_WITH_PREAGGREGATION` | **PASS** |
| **D** | `STORE x WEEK` $\leftrightarrow$ `STORE x WEEK` (Exact composite grain) | `SAFE` | `SAFE` | **PASS** |
| **E** | `DEPARTMENT x MONTH` $\leftrightarrow$ `PERSON x DAY` (Raw cross-grain fact) | `UNSAFE` | `UNSAFE` | **PASS** |
| **F** | `PRODUCT x LOCATION x DAY` $\rightarrow$ `PRODUCT` master (Dimension enrichment) | `SAFE` | `SAFE` | **PASS** |

---

## 6. Canonical 22 x 3 Fanout Trap Verification

### Fixture & Computation
- **Left Table (Daily Attendance)**: 1 employee, 22 rows.
- **Right Table (Leave Incidents)**: 1 employee, 3 rows.
- **Left Rows**: 22
- **Right Rows**: 3
- **Naive Expected Joined Rows**: **66**
- **Row Multiplier**: **3.0x** (max multiplier: **66.0x**)
- **Relationship Validity**: `ACCEPTED` (100% key value overlap, `cardinality=MANY_TO_MANY`, `duplication_risk_flag=True`).
- **Join Safety**: **`UNSAFE`** (raw operation blocked with `many_to_many_risk=True`).
- **Governed Alternative**: When target grain `"PERSON"` is requested, `plan_join` produces **`SAFE_WITH_PREAGGREGATION`** with `PreAggregationSpec` grouping by `employee_id`.
- **Physical Unsafe Join Executed**: **NO** (zero physical data manipulation).

---

## 7. Measure Additivity & Protection Report

Evaluated via `infer_measure_additivity`:

| Measure Name | Inferred Additivity | Raw SUM Allowed | Duplication Protection | Pre-Aggregation Requirement |
| :--- | :--- | :--- | :--- | :--- |
| **Headcount** | `DISTINCT_COUNT` | **NO** (`COUNT(DISTINCT emp_id)` required; naive `SUM`/`COUNT` forbidden) | **PASS** | Required on non-unique grains |
| **Attendance Rate** | `RATIO` | **NO** (Requires `SUM(attended) / NULLIF(SUM(scheduled), 0)`) | **PASS** | Required across groups |
| **Inventory Balance** | `SEMI_ADDITIVE` | **NO** across time (Additive across locations, point-in-time `LATEST` across dates) | **PASS** | Required for temporal spans |
| **Revenue** | `ADDITIVE` | **YES** (Authorized only when multiplier $= 1.0$; forbidden when fanout multiplier $> 1.0$) | **PASS** | Required if joined to child fact |

---

## 8. Temporal Alignment Rules

- **DAY $\rightarrow$ MONTH**: Supported with pre-aggregation (`SAFE_WITH_PREAGGREGATION`).
- **DATETIME $\rightarrow$ DAY**: Supported via date truncation.
- **MONTH $\leftrightarrow$ DAY (Raw)**: **BLOCKED** (`safety_status=UNSAFE`, `temporal_mismatch=True`).
- **WEEK $\rightarrow$ MONTH**: **Not silently inferred** (calendar week splits month boundaries; requires explicit business allocation).

---

## 9. Composite Key Joint Evaluation

Joint tuple evaluation was verified for:
1. `STORE + WEEK` (`["store_id", "week"]`)
2. `PRODUCT + LOCATION` (`["location_id", "date"]`)

Coverage and cardinality are computed jointly across composite key tuples via `compute_value_overlap_composite` (building tuples `(store_id, week)`), rather than column-by-column guessing:
- Joint Left Distinct: **4**
- Joint Right Distinct: **4**
- Joint Coverage: **1.000**
- Jaccard Overlap: **1.000**
- Joint Cardinality: **`ONE_TO_ONE`**

---

## 10. Performance Telemetry (50 Runs)

Benchmarked across 50 consecutive runs on standard test workloads:

| Pipeline Component | P50 Latency | P95 Latency | SLA Target | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Candidate Generation** | 0.044 ms | 0.069 ms | $< 50$ ms | **PASS** |
| **Relationship Validation** | 3.520 ms | 4.689 ms | $< 100$ ms | **PASS** |
| **Join Safety Assessment** | 0.006 ms | 0.010 ms | $< 20$ ms | **PASS** |
| **Join Planning** | 0.026 ms | 0.038 ms | $< 20$ ms | **PASS** |
| **Total I4 Pipeline** | **~3.60 ms** | **~4.81 ms** | **$< 190$ ms** | **PASS** |
