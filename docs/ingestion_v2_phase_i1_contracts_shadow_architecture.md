# HighView Ingestion Intelligence V2 — Phase I1 Architecture Document
## Contracts, Epistemic Provenance Boundaries, Shadow Orchestration & Pipeline Disagreement Ledger

---

### Executive Overview

Phase I1 establishes the complete architectural contract foundation, deterministic provenance mechanisms, epistemic ordering boundaries, shadow execution harness, and divergence auditing system for **HighView Ingestion Intelligence V2**. 

Under Phase I1:
- **Production Autoritativeness**: V1 remains 100% authoritative for all production consumers (Dashboards, HRIDAY, Executive Presentation Studio, and public REST/SSE APIs).
- **Shadow Mode Execution**: V2 executes in strict shadow mode without mutating live state.
- **Consumer Cutover Firewall**: Cutover is explicitly blocked in code (`consumer_cutover_allowed = False`).
- **P0 Database Isolation**: Zero mutations to production `pulsehr.sqlite3` tables.
- **Model Invariant**: Exactly 0 LLM calls are invoked during contract parsing, structural profiling, or shadow auditing.

---

### 1. Epistemic Stage Ordering

The V2 pipeline enforces a strict 12-stage epistemic sequence. The cardinal architectural rule is:
> **A later stage may consume outputs from earlier stages.**  
> **An earlier stage may NEVER depend on intelligence that belongs to a later stage.**

```text
RAW WORKBOOK / CSV
   ↓
1. Raw Fidelity Ingestion (Bronze Layer: raw files, sheet geometries, physical cells)
   ↓
2. Adaptive Table Reconstruction (Bronze/Silver: headers, table bounds, EDA-0)
   ↓
3. Sanitization + Type/Unit Normalization (Silver: canonical types, ISO-8601, units, Parquet)
   ↓
4. Structural Profiling / EDA-A (Deterministic characterization: nulls, cardinalities, types)
   ↓
5. Semantic Modeling & Grain Inference (Entities, roles, personas, composite row grains)
   ↓
6. Relationship Discovery (Candidate associations via heuristics and name matching)
   ↓
7. Relationship Validation & Governed Join Planning (Mathematical referential verification & JoinPlans)
   ↓
8. Analytical EDA-B (Tukey IQR rule-based outliers, distributions, correlations across validated joins)
   ↓
9. Controlled Enrichment (Intra-table and cross-table derived metrics with safe denominators)
   ↓
10. Semantic Graph (Knowledge graph integrating schema, semantics, relationships, metrics)
   ↓
11. Vectorization / Retrieval Indexing (Namespace-isolated indexing: SCHEMA, SEMANTIC, REL, ANALYTIC)
   ↓
12. Context Reconciliation + Pre-Warm (Silver/Gold reconciliation for downstream consumers)
   ↓
DASHBOARD / HRIDAY / PRESENTATION STUDIO
```

---

### 2. Public vs Internal Stage Mapping (10 SSE Milestones Preserved)

While V2 contains 12 internal intelligence stages, public SSE events and client-side progress bars continue reporting the exact 10 visual progress groups without frontend contract disruption:

| Internal Stage | Public Progress Group | Public Label |
| :--- | :--- | :--- |
| `1. RAW_INGESTION` | `STAGE_1_FILE_RECEIVED` | File Received & Verified |
| `2. ADAPTIVE_RECONSTRUCTION` | `STAGE_2_STRUCTURE_DETECTED` | Tables & Headers Detected |
| `3. SANITIZATION_NORMALIZATION` | `STAGE_3_TYPES_NORMALIZED` | Types & Units Normalized |
| `4. STRUCTURAL_PROFILING_EDA_A` | `STAGE_4_DATA_PROFILED` | Data Characteristics Profiled |
| `5. SEMANTIC_MODELING_GRAIN` | `STAGE_5_ENTITIES_RESOLVED` | Entities & Grains Resolved |
| `6. RELATIONSHIP_DISCOVERY` | `STAGE_6_RELATIONSHIPS_DISCOVERED` | Candidate Relationships Found |
| `7. RELATIONSHIP_VALIDATION_JOIN_PLAN` | `STAGE_7_RELATIONSHIPS_VERIFIED` | Relationships & Joins Verified |
| `8. ANALYTICAL_EDA_B` | `STAGE_8_STATISTICS_COMPUTED` | Statistical Distributions Computed |
| `9. CONTROLLED_ENRICHMENT` | `STAGE_8_STATISTICS_COMPUTED` | Governed Derived Metrics Evaluated |
| `10. SEMANTIC_GRAPH` | `STAGE_9_KNOWLEDGE_GRAPH_BUILT` | Semantic Knowledge Graph Built |
| `11. VECTORIZATION_INDEXING` | `STAGE_9_KNOWLEDGE_GRAPH_BUILT` | Retrieval Namespaces Indexed |
| `12. CONTEXT_RECONCILIATION_PREWARM` | `STAGE_10_READY` | Intelligence Pre-warmed & Ready |

---

### 3. Decoupled Data Quality & Analytical Reliability

To prevent conflation of physical cleanliness with analytical confidence, the quality scoring architecture is split into two orthogonal metrics:

#### StructuralDataQuality (Stage 4: Structural Profiling / EDA-A)
- **Completeness Score**: Ratio of non-null physical values.
- **Validity Score**: Adherence to canonical physical data types.
- **Uniqueness Score**: Ratio of unique items across candidate identifier columns.
- **Consistency Score**: Uniformity of casing, whitespace, and formatting.
- **Reconstruction Fidelity Score**: Sheet cell preservation and merged-cell unmerging accuracy.

#### AnalyticalReliability (Stage 8: Analytical EDA-B)
- **Grain Confidence Score**: Unambiguous row identity validation.
- **Join Coverage Score**: Referential integrity match rates on foreign keys.
- **Metric Definition Confidence**: Denominator availability and safe measure additivity.
- **Evidence Sufficiency Score**: Grounding coordinates connecting finding to source coordinates.

---

### 4. Mathematical Grounding & Denominator Calibration

1. **Rule-Based Tukey IQR**:
   - Tukey IQR is strictly rule-based: $\text{Outlier} \iff x < Q_1 - 1.5 \times \text{IQR} \lor x > Q_3 + 1.5 \times \text{IQR}$.
   - It **never** outputs a $p$-value.
   - Hypothesis tests (Pearson correlation, Welch t-test, ANOVA) are isolated into `HypothesisTestEvidence` with explicit degrees of freedom, test statistics, and $p$-values.

2. **Denominator Safety & Fanout Prevention**:
   - `JoinPlan` governs join execution separately from structural relationship edges.
   - If a join involves differing grains (e.g. `PERSON` to `PERSON x DAY`), `JoinPlan.safety_status` is marked `REQUIRES_PRE_AGGREGATION`.
   - `PreAggregationSpec` forces pre-aggregation of the multi-row table before joining, preventing Cartesian expansion ($N \times M$ fanout) and metric inflation.
   - Measures are explicitly tagged with `MeasureAdditivity`: `ADDITIVE`, `SEMI_ADDITIVE`, `NON_ADDITIVE`, `RATIO`, or `DISTINCT_COUNT`.

3. **Grounding & Evidence Calibration**:
   - Grounding errors, grain ambiguity, and unsupported relationship assumptions are systematically reduced by requiring `SourceCoordinateRef` and `evidence_ref` bindings.

---

### 5. Multi-Namespace Retrieval Isolation

To prevent semantic cross-contamination during retrieval queries, vector indexing is segregated into 4 dedicated namespaces:
- `RAW_SCHEMA`: Physical table names, sheet indices, column headers, data types.
- `SEMANTIC`: Domain entities (`PERSON`, `DEPARTMENT`), business synonyms, descriptions.
- `RELATIONSHIP`: Validated foreign keys, grain bridges, cardinality constraints.
- `ANALYTICAL`: EDA-B findings, Tukey outlier thresholds, governed metric formulas.

---

### 6. Pipeline Disagreement Ledger & Comparison Classes

Shadow validation evaluates differences between V1 and V2 outputs without false equivalence traps. Divergences are classified into:

1. **`UNCHANGED`**:
   - Behavior and contracts must match V1 exactly: row fidelity, raw source coordinates, SSE protocol, ExecutiveTopic schema, and evidence IDs.
   - Any divergence is flagged as a `BLOCKER` or `CRITICAL` violation.

2. **`EXPECTED_IMPROVEMENT`**:
   - Measurable V2 superiority: rejected invalid Cartesian joins, precision of foreign key match rates, detection of composite grains, and governed derived denominators.

3. **`EXPECTED_DIFFERENCE`**:
   - Intentional architectural shifts: low-confidence semantic assignments resolving to `AMBIGUOUS` rather than being forced into incorrect roles; deletion of ungrounded cross-sheet assumptions.

---

### 7. Contract Implementations Summary

| File | Primary Contract Classes | Epistemic Role |
| :--- | :--- | :--- |
| `contracts/provenance.py` | `SourceCoordinateRef` | Silver-level source coordinate binding |
| `contracts/base.py` | `IngestionContractBase`, `compute_stage_fingerprint` | Immutable contract base & deterministic SHA-256 |
| `contracts/raw.py` | `RawIngestionResult`, `PhysicalSheet` | Stage 1 raw file fidelity |
| `contracts/reconstruction.py` | `ReconstructedDataset`, `LogicalTable` | Stage 2 table boundary detection |
| `contracts/normalization.py` | `NormalizedDataset`, `NormalizedColumn` | Stage 3 canonical typing & units |
| `contracts/profiling.py` | `StructuralProfile`, `StructuralDataQuality` | Stage 4 deterministic EDA-A |
| `contracts/semantics.py` | `SemanticModel`, `SemanticColumnAssignment` | Stage 5 semantic role resolution |
| `contracts/grain.py` | `GrainProfile`, `TableGrainProfile`, `CanonicalGrain` | Stage 5 grain resolution & composite keys |
| `contracts/relationships.py` | `RelationshipCandidateSet`, `ValidatedRelationshipGraph` | Stage 6 & 7 discovery & validation |
| `contracts/joins.py` | `JoinPlan`, `GovernedJoinPlanSet`, `PreAggregationSpec` | Stage 7 governed join execution |
| `contracts/analytics.py` | `AnalyticalProfile`, `AnalyticalReliability`, `TukeyIqrEvidence` | Stage 8 analytical EDA-B |
| `contracts/enrichment.py` | `EnrichedDataset`, `LocalDerivedMetric`, `RelationalDerivedMetric` | Stage 9 governed derived metrics |
| `contracts/semantic_graph.py`| `SemanticGraph`, `SemanticGraphNode`, `SemanticGraphEdge` | Stage 10 structured knowledge graph |
| `contracts/retrieval.py` | `MultiNamespaceRetrievalManifest`, `RetrievalNamespace` | Stage 11 namespace-isolated search |
| `contracts/intent.py` | `AnalysisIntent` | Cross-cutting user focus invariant |
| `contracts/shadow.py` | `ShadowPipelineRun`, `InternalStage`, `PublicProgressGroup` | Milestone mapping & shadow state |
| `contracts/disagreement.py` | `PipelineDisagreementLedger`, `PipelineDisagreementRecord` | Disagreement tracking across 3 classes |
| `dependency_guard.py` | `validate_stage_transition`, `audit_contract_ast_dependencies` | AST & runtime integrity firewall |
| `shadow_runner.py` | `ShadowStorageManager`, `ShadowHarness` | Isolated shadow harness & cutover blocker |
