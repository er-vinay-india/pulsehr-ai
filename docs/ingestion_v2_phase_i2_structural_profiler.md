# HighView Ingestion Intelligence V2 — Phase I2: Deterministic Structural Profiler (EDA-A)

## 1. Architectural Scope & Epistemic Boundary

Phase I2 establishes the **Structural Profiler** (Stage 4 / EDA-A) within the Ingestion Intelligence V2 architecture.
The central mandate of Stage 4 is:

> **"Can HighView deterministically describe the STRUCTURE of a normalized dataset without making any business interpretation?"**

### The Epistemic Boundary
- **Allowed (Structural Truth):**
  - Physical and logical type candidates (`STRING`, `INTEGER`, `FLOAT`, `DECIMAL`, `BOOLEAN`, `DATE`, `DATETIME`, `TIME`, `CATEGORICAL`, `UNKNOWN`).
  - True normalized null counts and ratios.
  - Distinct counts and uniqueness ratios.
  - Linear quantiles ($Q_1, Q_2, Q_3$), mean, standard deviation, min, max.
  - Deterministic Shannon entropy ($H$) and normalized entropy ($H_{\text{norm}}$).
  - Constant ($1.0$) and near-constant ($\ge 0.95$) classification.
  - Pattern signatures (`DDDDD`, `AAA-DDDDD`), token coverage, fixed-length ratios.
  - Leading-zero detection (`00421`, `00017`), strictly preventing numeric coercion.
  - Temporal date span and coverage.
  - Value-structure candidate identifier scores ($\in [0, 1]$).
  - Structural candidate dimension scores ($\in [0, 1]$).
  - Exact duplicate row counts and ratios.
  - Table-level `StructuralDataQuality` (completeness, validity, role-neutral uniqueness, consistency, fidelity).
  - Deterministic stage fingerprints.

- **Strictly Forbidden at Stage 4:**
  - Business evaluative language (*best, worst, risk, underperform, high-performing, anomaly, recommend, opportunity, kpi*).
  - Semantic role classification (*PERSON, DEPARTMENT, STORE, REVENUE, ATTENDANCE* — deferred to Stage 5 / I3).
  - Grain inference (*TableGrainProfile, composite grain* — deferred to Stage 5 / I3).
  - Relationship discovery or join planning (*ValidatedRelationshipGraph, JoinPlan* — deferred to Stages 6 & 7 / I4).
  - Business correlation or analytical ranking (*EDA-B* — deferred to Stage 8 / I5).
  - Vectorization, embeddings, or LLM calls (*retrieval manifest* — deferred to Stage 11 / I6).

---

## 2. Type Profiling & Candidate Logical Types

Type profiling at Stage 4 is structural only. Candidate logical types are constrained to:
- `STRING`: Arbitrary textual sequences, or text-encoded identifiers.
- `INTEGER`: Integer values without fractional components.
- `FLOAT`: Real numbers with fractional or scientific notation.
- `DECIMAL`: Fixed-point numeric representations.
- `BOOLEAN`: Binary truth states (`True`, `False`, `0`, `1`).
- `DATE`: Calendar date values (`YYYY-MM-DD`).
- `DATETIME`: Calendar dates with time components.
- `TIME`: Standalone time expressions.
- `CATEGORICAL`: Low-cardinality discrete sets ($\le 20$ distinct values with repetition).
- `UNKNOWN`: All-null columns or ambiguous representations.

---

## 3. Leading-Zero Identifier Preservation

Identifier preservation is critical for HR and operational records (e.g. employee IDs `00421`, `00017`, `09382`, badge numbers `0012`):
- When `leading_zero_ratio > 0` and `all_digit_ratio > 0.8`:
  $$\text{logical\_type\_candidate} = \text{STRING}$$
- Numeric coercion into integers (`421`, `17`) is **strictly forbidden**, protecting identifier fidelity against leading-zero truncation.

---

## 4. Quantile Policy

HighView standardizes on one deterministic quantile method across all integer, float, and decimal data:
- **Method:** Linear interpolation (`method="linear"`) on sorted non-null values.
- **Quantiles Computed:**
  - $Q_1$: 25th percentile ($0.25$)
  - $Q_2$: 50th percentile / median ($0.50$)
  - $Q_3$: 75th percentile ($0.75$)
- Yields bit-for-bit identical results across runs and implementations.

---

## 5. Shannon Entropy Formulation

Deterministic categorical information density is measured via Shannon entropy:
$$H = -\sum_{i=1}^K p_i \log_2(p_i)$$
where $p_i = \frac{\text{count}_i}{N_{\text{non\_null}}}$ for $K$ distinct values.
- If $N_{\text{non\_null}} \le 0$ or $K \le 1$: $H = 0.0$.
- **Normalized Entropy ($H_{\text{norm}}$):**
  $$H_{\text{norm}} = \frac{H}{\log_2(K)} \quad (\text{for } K > 1, \text{ else } 0.0)$$
  where $H_{\text{norm}} \in [0.0, 1.0]$. Both metrics are stored explicitly without semantic conflation.

---

## 6. Governed Constant Thresholds

Inline magic numbers are eliminated in favor of governed thresholds:
- `CONSTANT_THRESHOLD = 1.0`: Column has exactly 1 distinct non-null value (`is_constant = True`).
- `NEAR_CONSTANT_THRESHOLD = 0.95`: Dominant value ratio $\ge 0.95$ across multiple distinct values (`is_quasi_constant = True`).
- `constant_ratio`: Exact proportion of the dominant value relative to non-null rows.

---

## 7. Pattern Signatures

String values are mapped deterministically to canonical structural token signatures:
- Digit `[0-9]` $\to$ `D`
- Uppercase `[A-Z]` $\to$ `A`
- Lowercase `[a-z]` $\to$ `a`
- Whitespace $\to$ `_`
- Punctuation (`-`, `/`, `.`, `@`, `_`, etc.) $\to$ literal character

### Examples:
- `00421` $\to$ `DDDDD`
- `EMP-00123` $\to$ `AAA-DDDDD`
- `2026-10-18` $\to$ `DDDD-DD-DD`

Metrics computed:
- `dominant_pattern`: Most frequent structural pattern.
- `pattern_coverage`: Proportion of non-null values conforming to the dominant pattern.
- `pattern_variants`: Total distinct patterns observed (capped at 20 for complexity bounding).
- `fixed_length_ratio`: Proportion of values matching the mode character length.

---

## 8. Candidate Identifier & Dimension Scoring

Scoring relies strictly on value-structure evidence; zero column-name semantics are inspected.

### Candidate Identifier Score:
$$u = \text{uniqueness\_ratio}, \quad c = \text{completeness}, \quad p = \text{pattern\_coverage}, \quad f = \text{fixed\_length\_ratio}$$
$$\text{candidate\_identifier\_score} = \begin{cases}
0.0 & \text{if } u < 0.10 \text{ or } K \le 1 \\
1.0 & \text{if } u = 1.0, \text{null\_ratio} = 0, f \ge 0.95, p \ge 0.80 \\
\min(1.0, 0.50 u + 0.25 c + 0.15 p + 0.10 f) & \text{if } u \ge 0.90 \\
\min(1.0, 0.40 u + 0.30 c + 0.20 p + 0.10 f) & \text{otherwise}
\end{cases}$$

### Candidate Dimension Score:
High repetition, low cardinality, and balanced entropy indicate dimension-like structures:
$$\text{candidate\_dimension\_score} = \begin{cases}
0.0 & \text{if is\_constant or null\_ratio} > 0.80 \text{ or identifier\_score} > 0.85 \\
c \cdot (1.0 - u) \cdot \max(0.2, H_{\text{norm}}) & \text{if } 2 \le K \le 100 \text{ and } u \le 0.30 \\
\max(0.0, 0.50 \cdot (1.0 - u) \cdot c) & \text{otherwise}
\end{cases}$$

---

## 9. Structural Data Quality Formula

Data quality at Stage 4 measures physical and structural attributes only, decoupled from business metrics:
$$\text{overall} = 0.30 \cdot \text{completeness} + 0.25 \cdot \text{validity} + 0.20 \cdot \text{uniqueness} + 0.15 \cdot \text{consistency} + 0.10 \cdot \text{reconstruction\_fidelity}$$

- **Completeness ($0.30$):** Average non-null ratio across all columns.
- **Validity ($0.25$):** Conformance of non-null cells to physical type boundaries.
- **Uniqueness ($0.20$):** Physical row deduplication ($1.0 - \text{duplicate\_row\_ratio}$). Role-neutral: does not penalize repeated categorical column values.
- **Consistency ($0.15$):** Average pattern coverage across columns.
- **Reconstruction Fidelity ($0.10$):** Upstream grid reconstruction score ($1.0$).

---

## 10. Complexity Budget & Performance

To guarantee predictable latency on large datasets:
- **Max rows exact evaluation:** Evaluates up to $100,000$ rows deterministically.
- **Top-K values:** Strictly capped at $K=10$.
- **Pattern variants:** Strictly capped at $20$ distinct patterns.
- **Pairwise composite keys:** Strictly capped at evaluating top $5$ candidate column pairs by cardinality (avoiding $O(C^2 \times N)$ combinatorial explosion).
- **Latency Benchmarks:**
  - $100$ rows: $P_{50} = 8.85\text{ ms}, \quad P_{95} = 12.52\text{ ms}$
  - $1,000$ rows: $P_{50} = 23.37\text{ ms}, \quad P_{95} = 32.55\text{ ms}$
  - $10,000$ rows: $P_{50} = 134.71\text{ ms}, \quad P_{95} = 141.29\text{ ms}$
- **Peak Memory:** $2.12\text{ MB}$.
