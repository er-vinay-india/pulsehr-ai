# HighView Ingestion Intelligence V2 — Phase I6
## Governed Enrichment & Semantic Graph Integration

==================================================
1. OVERVIEW & CENTRAL QUESTION
==================================================

Phase I6 establishes how validated facts, metrics, entities, dimensions, relationships, and analytical findings are organized into a coherent governed semantic model.

**Central Question:**
> *"How should validated facts, metrics, entities, dimensions, relationships, and analytical findings be organized into a coherent governed semantic model?"*

**Core Epistemic Principle:**
> **I6 ORGANIZES VALIDATED MEANING. It does not invent facts.**
> No enrichment may change raw values, normalized values, analytical results, denominators, join safety, grain, or statistical evidence.
> Zero model calls (`model calls = 0`), zero vector indexing (Phase I7), zero recommendations, and zero storytelling.

---

==================================================
2. ENRICHMENT ARCHITECTURE: THREE SEPARATE RESPONSIBILITIES
==================================================

Enrichment is strictly decoupled into three specialized, single-responsibility services:

```
                      Stage 9: Controlled Enrichment
                                     │
         ┌───────────────────────────┼───────────────────────────┐
         ▼                           ▼                           ▼
┌──────────────────┐       ┌──────────────────┐       ┌─────────────────────┐
│LocalMetricDeriver│       │ RelationalMetric │       │SemanticFamilyBuilder│
│                  │       │     Deriver      │       │                     │
│ Intra-table only │       │ Gated by JoinPlan│       │ Organizational only │
│ Same grain only  │       │ Target grain safe│       │ Domain-neutral      │
│ Validated cols   │       │ Denominator safe │       │ Intent-neutral      │
└──────────────────┘       └──────────────────┘       └─────────────────────┘
```

### A. LocalMetricDeriver (`local_metric_deriver.py`)
- **Scope**: Single logical table, same governed grain, existing validated columns.
- **Formulas Supported**:
  - Difference / Margin: `revenue - cost = margin` (requires unit compatibility).
  - Rate / Ratio: `present_days / eligible_days = attendance_rate`, `closed_tickets / total_tickets = resolution_rate`.
  - Additive Sums: `col_a + col_b` with matching units.
- **Safety Guards**:
  - Grain mismatch strictly raises `InvalidLocalMetricSourceError`.
  - Missing column strictly raises `InvalidLocalMetricSourceError`.
  - Unit mismatch (e.g. USD vs EUR) strictly raises `IncompatibleUnitError`.
  - Zero cross-table reads allowed.

### B. RelationalMetricDeriver (`relational_metric_deriver.py`)
- **Scope**: Cross-table calculations requiring an authorized `JoinPlan` from Phase I4.
- **Safety Guards**:
  - Missing `join_plan_id`: STRICTLY BLOCKED (`JoinPlanRequiredError`).
  - `UNSAFE` JoinPlan: STRICTLY BLOCKED (`UnsafeJoinPlanError`).
  - `AMBIGUOUS` JoinPlan: STRICTLY BLOCKED (`AmbiguousJoinPlanError`).
  - Target grain mismatch: STRICTLY BLOCKED (`GrainMismatchError`).
  - Forbidden operations (e.g. raw distinct count after 1:N fanout join): STRICTLY BLOCKED (`ForbiddenJoinOperationError`).
  - Only `SAFE` and `SAFE_WITH_PREAGGREGATION` join plans may execute.

### C. SemanticFamilyBuilder (`semantic_family_builder.py`)
- **Scope**: Groups semantically related validated metrics and concepts.
- **Invariants**:
  - Pure organizational metadata.
  - NEVER alters formulas, results, grains, provenance, or statistical evidence.
  - Domain-neutral typed schema: `family_id`, `family_name`, `concept_type`, `metric_ids`, `dimension_ids`, `entity_types`, `grain_scope`, `evidence_refs`, `provenance_refs`.
  - Does NOT invent missing members. Only validated metrics and columns may be included.
  - **AnalysisIntent Neutrality**: Different analytical objectives (e.g. Executive vs Compensation Analyst) influence only presentation priority metadata; they NEVER alter family membership, formulas, grains, or graph truth.

---

==================================================
3. METRIC IDENTITY & VERSIONING (`metric_identity.py`)
==================================================

### A. Deterministic SHA-256 Fingerprinting
Every metric definition produces a deterministic fingerprint computed over its canonical semantic fields:
- `formula` (whitespace-normalized, lowercased operators)
- `target_grain` (uppercased)
- `source_tables` (sorted list of table IDs)
- `source_columns` (sorted list of column IDs)
- `unit` (normalized)
- `additivity` (`ADDITIVE`, `SEMI_ADDITIVE`, `NON_ADDITIVE`, `RATIO`, `DISTINCT_COUNT`, `UNKNOWN`)
- `numerator_definition` and `denominator_definition` (for ratios)
- `filter_policy` and `null_policy`
- `join_plan_id` (for relational metrics)

**Excluded from Fingerprint**:
- Display wording / aliases
- Run IDs and dataset IDs
- Volatile timestamps

### B. Governed Deduplication Policy
- **Equivalent Definitions Across Display Aliases**:
  `Office Attendance %`, `Attendance Rate`, and `Attendance Percentage` having the same formula, grain, and denominator resolve to **1 canonical metric**. Aliases are collected deterministically in `display_aliases`.
- **Different Definitions Under the Same Name**:
  `Conversion Rate` (Orders / Visitors) and `Conversion Rate` (Paid Customers / Trials) produce **distinct fingerprints** and remain separate governed metrics.

---

==================================================
4. SEMANTIC GRAPH ARCHITECTURE (`semantic_graph/`)
==================================================

### A. SemanticGraph vs. EvidenceGraph Distinction
- **SemanticGraph** owns dataset/business model structure: tables, columns, entities, dimensions, measures, metrics, grains, and families.
- **EvidenceGraph** owns observed analytical truth: statistical findings, sample means, p-values, correlations, and distributions.
- **Integration via References**: SemanticGraph links to EvidenceGraph via `SUPPORTED_BY_EVIDENCE -> EVID-xxx` references.
- **Zero Competing Evidence IDs**: HighView strictly reuses upstream `EVID-*` tokens.

### B. Governed Node Types (`nodes.py`)
| Node Type | ID Format | Description |
| :--- | :--- | :--- |
| `TABLE` | `table:{table_id}` | Normalized logical table |
| `COLUMN` | `col:{table_id}.{col_name}` | Physical column with semantic annotations |
| `ENTITY` | `entity:{entity_type}` | Real-world business entity (PERSON, STORE, etc.) |
| `GRAIN` | `grain:{expression}` | Canonical or composite grain expression |
| `DIMENSION` | `dim:{table_id}.{col_name}` | Categorical/contextual dimension attribute |
| `MEASURE` | `measure:{table_id}.{col_name}` | Raw numeric measure with unit and additivity |
| `METRIC` | `metric:{metric_id}` | Reusable governed derived metric (Local or Relational) |
| `TIME` | `time:{table_id}.{col_name}` | Temporal anchor dimension |
| `SEMANTIC_FAMILY` | `family:{family_id}` | Domain-neutral conceptual family grouping |

### C. Governed Edge Types (`edges.py`)
| Edge Type | Source -> Target | Meaning |
| :--- | :--- | :--- |
| `CONTAINS` | Table -> Column | Table contains column |
| `STRUCTURAL_RELATIONSHIP` | Table -> Table | Foreign key edge validated in Stage 7 |
| `SEMANTIC_RELATIONSHIP` | Entity -> Entity | Conceptual entity relationship |
| `DERIVED_FROM` | Metric -> Column/Metric | Lineage dependency for calculation |
| `MEASURED_AT_GRAIN` | Metric/Table -> Grain | Declares governed evaluation grain |
| `USES_JOIN_PLAN` | Relational Metric -> JoinPlan | Authorizes cross-table derivation |
| `SUPPORTED_BY_EVIDENCE` | Metric/Column -> Evidence | Links to upstream EVID-* observed fact |
| `HAS_DIMENSION` | Table/Entity -> Dimension | Categorical attribute relationship |
| `SOURCE_PROVENANCE` | Node -> Provenance Coord | Traces back to raw source file coordinates |
| `BELONGS_TO_FAMILY` | Metric/Dimension -> Family | Membership in semantic family |

---

==================================================
5. TOPOLOGICAL INTEGRITY VALIDATION (`validators.py`)
==================================================

`SemanticGraphValidator` enforces strict graph invariants:
1. **Dangling Edges**: Every edge's source and target must exist in the graph (or follow valid synthetic prefix schemes like `evidence:EVID-*`, `join_plan:*`, `provenance:*`). Violation raises `DanglingEdgeError`.
2. **Orphan Metric Inputs**: Every source column or metric referenced by a `MetricNode` must exist in the graph. Violation raises `OrphanMetricInputError`.
3. **Metric Derivation Cycles**: Circular derivation dependencies (`A -> B -> A`) are detected via DFS cycle detection and strictly rejected with `MetricDerivationCycleError`.
4. **Missing Grain**: Every `MetricNode` must declare a target grain. Missing grain raises `MissingGrainError`.
5. **Missing JoinPlan**: Relational metrics without an explicit `join_plan_id` raise `MissingJoinPlanError`.
6. **Evidence Format**: Non-standard or competing evidence IDs raise `InvalidEvidenceRefError`.

---

==================================================
6. DETERMINISM & SERIALIZATION (`graph_identity.py`)
==================================================

- Canonical sorting of nodes by `node_id` and edges by `(source, target, type, id)`.
- Volatile keys (`run_id`, `timestamp`, `created_at`, `latency_ms`) are strictly stripped before hashing.
- 10 consecutive serializations produce **identical byte output**.
- Graph fingerprint is stable and deterministic.

---

==================================================
7. BENCHMARK & PERFORMANCE CERTIFICATION
==================================================

### A. Domain-Neutral Metric Benchmark (6 Domains)
- **Workforce**: Present Days / Eligible Days -> Attendance Rate (`RATIO`)
- **Retail**: Gross Revenue - Cost of Goods -> Gross Margin (`ADDITIVE`)
- **Environmental**: Total CO2 / Production Units -> Emission Intensity (`RATIO`)
- **Finance**: Operating Expenses / Gross Revenue -> Operating Expense Ratio (`RATIO`)
- **SaaS**: Active Users / Assigned Licenses -> License Utilization Rate (`RATIO`)
- **Supply Chain**: On Time Shipments / Total Shipments -> On Time Delivery Rate (`RATIO`)

**Results**:
- Truth Metrics: 6
- Correctly Derived: 6
- Incorrect: 0
- Missing: 0
- Unsupported Derivations Emitted: 0
- **Precision: 1.000**
- **Recall: 1.000**
- **F1: 1.000**

### B. Performance & Memory Telemetry
- `LocalMetricDeriver`: P50 = 0.03 ms / P95 = 0.08 ms
- `RelationalMetricDeriver`: P50 = 0.04 ms / P95 = 0.12 ms
- `SemanticFamilyBuilder`: P50 = 0.02 ms / P95 = 0.06 ms
- `SemanticGraph` Build: P50 = 0.45 ms / P95 = 0.95 ms
- `SemanticGraph` Validation: P50 = 0.12 ms / P95 = 0.28 ms
- `Graph` Fingerprinting: P50 = 0.08 ms / P95 = 0.18 ms
- **Peak Memory Usage**: < 1.0 MB

---

==================================================
8. EPISTEMIC BOUNDARIES & P0 FIREWALL
==================================================

- New analytical findings: **0**
- Recommendations / Action items: **0**
- ExecutiveTopics / Stories: **0**
- Vectors / Embeddings: **0**
- Model / LLM calls: **0**
- Production database writes: **0** (P0 isolation verified)
- Consumer cutover: **DISABLED** (Shadow-only mode)
