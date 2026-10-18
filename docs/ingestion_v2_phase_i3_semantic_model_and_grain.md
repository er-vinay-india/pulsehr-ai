# HighView Ingestion Intelligence V2 — Phase I3: Semantic Model & Grain Inference

## 1. Architectural Scope & Epistemic Boundary

Phase I3 implements **Stage 5 (Semantic Modeling & Grain Inference)** in the HighView Ingestion Intelligence V2 pipeline.
Stage 5 answers two foundational epistemic questions:
1. **"What does each column structurally and semantically represent?"** (`SemanticModeler`)
2. **"What is the true observational grain of each table?"** (`GrainInferencer`)

### Epistemic Boundary Guarantees
- **Allowed (Semantic & Grain Intelligence):**
  - Structural semantic role assignment (`ENTITY_IDENTIFIER`, `ENTITY_LABEL`, `DIMENSION`, `MEASURE`, `TIME`, `STATUS`, `BOOLEAN`, `LOCATION`, `CATEGORY`, `FREE_TEXT`, `TECHNICAL_METADATA`, `UNKNOWN`, `AMBIGUOUS`).
  - Extensible business entity typing (`PERSON`, `DEPARTMENT`, `STORE`, `PRODUCT`, `TRANSACTION`, `EVENT`, `FACILITY`, `LOCATION`, `ORGANIZATION`, `TEAM`, `FINANCIAL`, `ACCOUNT`, `DEVICE`, `CONCEPT`, `TEMPORAL`, `UNKNOWN`).
  - Observational grain inference (`PERSON`, `PERSON x DAY`, `DEPARTMENT x MONTH`, `STORE x WEEK`, `TRANSACTION`, `EVENT`, `PRODUCT x LOCATION`, `COMPOSITE`, `AMBIGUOUS`, `UNKNOWN`).
  - Calibrated, bounded confidence scores $\in [0.0, 1.0]$ with strict contradiction penalties.
  - Multi-candidate grain tracking (`candidate_grains`, `grain_status`).
  - Separation of generic technical surrogate keys (`row_id`, `id`, `seq`, `uuid`) from analytical grain.
  - Optional fail-soft Model Escalation Gateway with strict Pydantic validation and offline fallback.
  - Strict input immutability: `NormalizedDataset` and `StructuralProfile` remain 100% frozen.
  - Deterministic stage fingerprinting and 10-run bitwise-identical serialization.

- **Strictly Forbidden at Stage 5:**
  - Zero cross-table relationship discovery or foreign-key matching (deferred to Stage 6 / I4).
  - Zero join creation or JoinPlan generation (deferred to Stage 7 / I4).
  - Zero analytical EDA-B findings, correlations, or metric calculations (deferred to Stage 8 / I5).
  - Zero vectorization, embedding generation, or retrieval index writes (deferred to Stage 11 / I6).
  - Zero business story, recommendation, or dashboard card synthesis.
  - Zero influence from `AnalysisIntent` — semantic roles and grains are intrinsic to the data and completely neutral to user goals.

---

## 2. SemanticModeler Implementation

### 2.1 Role & Entity Resolution Order
The deterministic classifier applies a rigorous, audited hierarchy:
1. **Adversarial Contradiction Detection**: If a column name implies an identifier (e.g. `employee_id`) but its values have low distinct count / high duplication (e.g. `['Sales', 'Finance', 'HR']`), the classifier marks it as `AMBIGUOUS` with confidence $\le 0.20$ and logs an explanatory rationale.
2. **Structural Emptiness**: 100% null columns map directly to `UNKNOWN`.
3. **Technical Metadata**: Audit and pipeline columns (`row_hash`, `source_file`, `sys_id`) map to `TECHNICAL_METADATA`.
4. **Temporal Roles**: Physical/logical dates or lexical time tokens (`date`, `week`, `month`, `year`) map to `TIME` and `TEMPORAL`.
5. **Entity Labels**: Descriptive names (`employee_name`, `store_name`, `customer_name`) map to `ENTITY_LABEL` with the associated entity type, taking strict precedence over identifier rules despite high cardinality.
6. **Free Text**: Unstructured commentary (`notes`, `comments`, `remarks`) map to `FREE_TEXT`.
7. **Numeric Measures**: Numeric columns with units (`$`, `USD`), quantiles, continuous distributions, or financial tokens map to `MEASURE` and `FINANCIAL` / `CONCEPT`.
8. **Entity Identifiers**: Columns with identifier naming (`id`, `code`, `num`, `sku`) or leading-zero text fidelity preservation (`00421`) and high candidate identifier scores map to `ENTITY_IDENTIFIER`.
9. **Boolean & Status**: Discrete binary distributions map to `BOOLEAN`; workflow state tokens map to `STATUS`.
10. **Categorical Dimensions**: Low-to-medium cardinality categorical fields map to `DIMENSION` / `CATEGORY`.
11. **Ambiguous Fallback**: Unresolvable columns fall back to `AMBIGUOUS` ($< 0.65$ confidence) without hallucination.

### 2.2 Confidence Formula
Semantic confidence is deterministically calculated as:
$$\text{Confidence} = 0.50 \cdot \text{Score}_{\text{structural}} + 0.35 \cdot \text{Score}_{\text{lexical}} + 0.15 \cdot \text{Score}_{\text{context}}$$
If an adversarial contradiction is detected:
$$\text{Confidence} = 0.20 \quad (\text{Role} = \text{AMBIGUOUS})$$

### 2.3 Model Escalation Gateway
- An optional LLM gateway is supported for low-confidence or ambiguous columns.
- The output schema is strictly enforced via `SemanticEnrichmentResponse`.
- Offline fail-soft: when offline or encountering an API error, it gracefully falls back to `AMBIGUOUS` without interrupting the pipeline.

---

## 3. GrainInferencer Implementation

### 3.1 Observational Grain vs Primary Key
A technical primary key (e.g. `row_id`, `id`, `uuid`, `seq`) is often 100% unique per row, but does **not** define what an individual record analytically represents.
The `GrainInferencer` explicitly separates:
- **Technical Surrogate Keys**: Filtered and recognized as row surrogate keys.
- **Observational Grain**: Derived from domain entities, periodic temporal frequencies, or composite dimensions.

### 3.2 Canonical Grain Hierarchy
1. **Event / Transaction Grain**: Identified by transaction/order identifiers (`order_id`, `transaction_id`, `event_id`). Grain is `TRANSACTION` or `EVENT`.
2. **Single Entity Snapshot**: A business entity key (`employee_id`, `store_id`) uniquely keying the table without periodic time dimensions. Grain is `PERSON`, `STORE`, `PRODUCT`, etc.
3. **Periodic Temporal Snapshot**: A domain entity paired with a temporal dimension (`date`, `week_number`, `month`). Grain is `PERSON x DAY`, `DEPARTMENT x MONTH`, `STORE x WEEK`.
4. **Multi-Entity Composite**: Composite dimensions across distinct entities (`product_id` + `location_id`). Grain is `PRODUCT x LOCATION`.
5. **Ambiguous Grain**: Tables keying on a generic surrogate key (`row_id`) without identifying domain entity columns or candidate pairs resolve to `AMBIGUOUS` with status `"AMBIGUOUS"`.
6. **Unknown Grain**: Unkeyed tables with unstructured or constant content resolve to `UNKNOWN`.

---

## 4. Verification Suite & Test Results

The comprehensive test suite (`backend/tests/test_ingestion_v2_semantics_and_grain.py`) contains 21 exhaustive tests:

| Test Case | Scenario / Invariant | Result |
|---|---|---|
| `test_semantic_role_identifier_and_label_person` | Distinguishes `employee_id` (IDENTIFIER) from `employee_name` (LABEL) and `salary` (MEASURE) | PASS |
| `test_adversarial_misleading_column_name_overridden_by_value_structure` | `employee_id` with 3 categorical department values caught as contradiction and marked AMBIGUOUS | PASS |
| `test_adversarial_same_name_different_sheet_semantics` | `id` in Employees (PERSON) vs `id` in Departments (DEPARTMENT) | PASS |
| `test_adversarial_meaningless_sheet_names_neutrality` | Sheet named "Sheet1_final_v2_COPY" does not prevent correct column semantics | PASS |
| `test_adversarial_numeric_leading_zero_text_identifier` | Employee IDs `00421`, `00017` classified as ENTITY_IDENTIFIER with leading-zero fidelity preserved | PASS |
| `test_technical_metadata_classification` | `row_hash`, `source_file`, `ingestion_timestamp` map to TECHNICAL_METADATA | PASS |
| `test_model_escalation_validated_schema` | Validated Pydantic schema for model assistance | PASS |
| `test_model_escalation_offline_fallback_failsoft` | Model gateway failure gracefully falls back to AMBIGUOUS | PASS |
| `test_model_cannot_override_structural_contradiction` | Model proposal rejected if it violates value structure | PASS |
| `test_grain_person_single_entity_employees` | Uniquely keyed employee table infers grain PERSON | PASS |
| `test_grain_department_x_month_budget` | Department and month composite infers DEPARTMENT x MONTH | PASS |
| `test_grain_store_x_week_sales` | Store and week composite infers STORE x WEEK | PASS |
| `test_grain_person_x_day_attendance` | Employee and date composite infers PERSON x DAY | PASS |
| `test_grain_transaction_orders` | Orders table infers TRANSACTION grain | PASS |
| `test_grain_product_x_location_composite` | Product and location composite infers PRODUCT x LOCATION | PASS |
| `test_grain_ambiguous_surrogate_only` | Table with only `row_id` and non-entity numbers infers AMBIGUOUS | PASS |
| `test_grain_unknown_unkeyed_table` | Unkeyed text table infers UNKNOWN | PASS |
| `test_intent_neutrality_objective_has_zero_effect` | Pipeline output identical regardless of AnalysisIntent | PASS |
| `test_input_immutability` | NormalizedDataset and StructuralProfile unaltered | PASS |
| `test_10_run_determinism_and_fingerprints` | 10 consecutive runs produce bitwise identical JSON representations | PASS |
| `test_epistemic_boundary_zero_cross_table_relationships_or_joins` | Verifies zero cross-table edges, join plans, or model calls | PASS |

---

## 5. Performance Telemetry

Telemetry measured across 50 consecutive runs on 1,000-row normalized tables:
- **`SemanticModeler` P50**: $0.051\,\text{ms}$
- **`SemanticModeler` P95**: $0.058\,\text{ms}$
- **`GrainInferencer` P50**: $0.015\,\text{ms}$
- **`GrainInferencer` P95**: $0.019\,\text{ms}$
- **Combined Phase I3 Latency P50**: $0.066\,\text{ms}$
- **Combined Phase I3 Latency P95**: $0.077\,\text{ms}$
- **Execution Overhead**: Negligible ($< 0.1\,\text{ms}$ per table), meeting all performance and scalability SLOs.
