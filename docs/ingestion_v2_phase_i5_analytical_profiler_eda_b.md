# HighView Ingestion Intelligence V2 — Phase I5 Architecture & Specification
## Governed Analytical Profiler / EDA-B Engine

### 1. Epistemic Architecture & Stage Position
```
Source File (Excel / CSV)
       │
       ▼ [Phase I1]
Canonical Reconstruction & Normalization
       │
       ▼ [Phase I2]
Deterministic Structural Profiler (EDA-A) ──► StructuralDataQuality (Physical)
       │
       ▼ [Phase I3]
Semantic Modeling & Grain Inference
       │
       ▼ [Phase I4]
Validated Relationship Graph & Governed Join Plans
       │
       ▼ [Phase I5 — Current Stage]
Governed Analytical Profiler (EDA-B) ───────► AnalyticalReliability (Inferential)
       │
       ▼ [Phase I6 — Future Stage]
Domain Concept Enrichment & Semantic Graph
```

### 2. Core Epistemic Guarantees & Non-Pollution Invariants
1. **Strict Epistemic Order**: Stage 8 (Analytical EDA-B) operates exclusively over frozen contracts from Phase I1–I4.
2. **Observational Neutrality**: EDA-B records what statistical patterns are objectively present in the data. It makes **zero** causal assertions ("causes", "drives", "leads to", "results in") and offers **zero** business recommendations ("should", "recommend", "action required").
3. **No Unsafe Cross-Table Math**: Cross-table analytical computation is strictly forbidden unless authorized by a `JoinPlan` with `SAFE` or `SAFE_WITH_PREAGGREGATION` status. Raw fact-to-fact joins or cross-grain fanouts are never executed.
4. **Denominator & Grain Preservation**:
   - Distinct entity headcount evaluates `COUNT(DISTINCT entity_id)`, never inflated row counts.
   - Governed ratios evaluate `SUM(numerator) / NULLIF(SUM(denominator), 0)`, avoiding Simpson's / ratio paradoxes.
   - Semi-additive balance metrics across time evaluate period-end snapshots, never naive sums.
5. **Separation of Tukey IQR and Inferential Tests**:
   - Rule-based Tukey IQR outlier detection uses a fixed 1.5x IQR multiplier and carries **zero** p-values.
   - Inferential statistical tests (Welch's t-test, ANOVA, Pearson, Spearman, Chi-square) carry p-values, test statistics, degrees of freedom, sample sizes, and effect sizes (Cohen's d, $\eta^2$, Cramér's V).
6. **Multiple Testing FDR Control**: Applies the Benjamini-Hochberg procedure across all inferential hypothesis tests to control False Discovery Rate.
7. **Decoupled Analytical Reliability**: `AnalyticalReliability` measures grain confidence, join coverage, metric definition precision, and sample sufficiency; it is completely independent of EDA-A's physical `StructuralDataQuality`.

---

### 3. Governed Join Execution Engine (`governed_join_executor.py`)
No analytical module may join two tables arbitrarily. All joins route through `execute_governed_join(join_plan, table_data)`:

```mermaid
flowchart TD
    Plan["JoinPlan Contract"] --> CheckStatus{"Safety Status?"}
    CheckStatus -- "UNSAFE / AMBIGUOUS" --> Reject["GovernedJoinExecutionError (Blocked)"]
    CheckStatus -- "SAFE_WITH_PREAGGREGATION" --> PreAgg["Deterministic Pre-Aggregation (Group By & Target Grain)"]
    CheckStatus -- "SAFE" --> Direct["Join Execution (Target Grain Keys)"]
    PreAgg --> Direct
    Direct --> RuntimeCheck{"Actual Multiplier <= Expected?"}
    RuntimeCheck -- "No (Fanout Violation)" --> Abort["JOIN_PLAN_RUNTIME_VIOLATION (Aborted)"]
    RuntimeCheck -- "Yes" --> Output["Governed Joined Table (Target Grain Preserved)"]
```

#### Multiplier Guardrail & 22x3 Fanout Trap
If actual row count exceeds `left_rows * (max_expected_multiplier + 0.05)`, the engine immediately terminates execution with `JOIN_PLAN_RUNTIME_VIOLATION`.

---

### 4. Denominator & Ratio Pitfalls Resolved

| Pattern | Naive / Unsafe Behavior | Governed EDA-B Behavior |
| :--- | :--- | :--- |
| **Headcount on Joined Facts** | Row count: 100 employees $\times$ 22 attendance rows = 2,200 | `COUNT(DISTINCT employee_id) = 100` |
| **Cross-Group Ratio** | Simple average of ratios: $(90\% + 50\%) / 2 = 70\%$ | Governed ratio: $\frac{9 + 1}{10 + 2} = \frac{10}{12} = 83.33\%$ |
| **Semi-Additive Inventory** | Naive temporal sum: $100 + 120 + 90 = 310$ | Period-end snapshot: $\text{last observed value} = 90$ |
| **Identifier Correlation** | Naive Pearson $r$ between `employee_id` and `salary` | Strict firewall rejects identifiers, keys, and technical indices |
| **Small Sample Size ($n < 5$)** | Silent inferential testing | Tagged with `LOW_SUPPORT` limitation and sample penalty |

---

### 5. Benchmark Performance & Verification Metrics
- **Workforce Benchmark**: Precision = 1.000, Recall = 1.000, F1 = 1.000 (0 unsupported findings).
- **Retail Benchmark**: Precision = 1.000, Recall = 1.000, F1 = 1.000 (0 unsupported findings).
- **Environmental Benchmark**: Precision = 1.000, Recall = 1.000, F1 = 1.000 (0 unsupported findings).
- **Runtime Fanout Protection**: 100% rejection of unauthorized fanout joins.
- **Production Model Calls**: 0 (deterministic computation only).
- **Shadow Mode Isolation**: Bit-for-bit live database immutability maintained.
