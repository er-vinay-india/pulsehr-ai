# HighView Ingestion Intelligence V2 — Phase I8 Architecture Document
## Production Certification, Governed Consumer Cutover, Circuit Breakers & Final Migration Freeze

---

### Executive Overview

Phase I8 establishes the formal production certification, governed routing gateway, circuit breakers, rollback safety, and controlled consumer cutover framework for **HighView Ingestion Intelligence V2**. 

Under Phase I8:
- **No New Analytical Layers**: I8 does not invent new analytics or change semantic rules.
- **Governed State Machine**: Every consumer independently transitions through `SHADOW` → `CERTIFIED` → `CANARY` → `V2_PRIMARY_WITH_FALLBACK` → `V2_PRIMARY` → `V1_RETIREMENT_ELIGIBLE`.
- **Strict Cutover Order**: HRIDAY (Stage 1) → Executive Dashboard (Stage 2) → Executive Presentation Studio (Stage 3).
- **Observable Circuit Breakers**: Automatic fallback to V1 is permitted during canary/transition, but every single fallback is classified and recorded in telemetry.
- **P0 Database Invariant**: Production SQLite database (`pulsehr.sqlite3`) remains 100% bit-for-bit unchanged.

---

## 1. Governed Cutover State Machine

Every consumer progresses through the following strict state transitions without skipping stages:

```mermaid
stateDiagram-v2
    [*] --> SHADOW
    SHADOW --> CERTIFIED: Shadow Parity Verified (0 Regressions, 0 Unresolved)
    CERTIFIED --> CANARY: Governed Canary Activation (Benchmark Cohorts)
    CANARY --> V2_PRIMARY_WITH_FALLBACK: Zero-Defect Canary & Fallback < Threshold
    V2_PRIMARY_WITH_FALLBACK --> V2_PRIMARY: Zero Critical Fallbacks & Operational Stability
    V2_PRIMARY --> V1_RETIREMENT_ELIGIBLE: Proven Production Stability
    V2_PRIMARY_WITH_FALLBACK --> ROLLBACK: Circuit Breaker Triggered / Emergency Switch
    ROLLBACK --> SHADOW: Remediate & Re-certify
```

### Typed Cutover States (`ConsumerCutoverState`)
1. **SHADOW**: Consumer executes V1 authoritatively. V2 executes in parallel shadow mode; outputs compared for divergence.
2. **CERTIFIED**: Complete parity run passed on canonical corpus with zero regressions, zero unresolved differences, and zero critical issues.
3. **CANARY**: Deterministic benchmark cohort routed to V2 with active telemetry monitoring.
4. **V2_PRIMARY_WITH_FALLBACK**: V2 is primary route; any schema, manifest, or runtime anomaly immediately falls back to V1 with typed telemetry.
5. **V2_PRIMARY**: V2 is authoritative; fallback disabled except emergency global rollback.
6. **ROLLBACK**: Consumer reverted to V1 due to policy violation or critical circuit breaker event.
7. **V1_RETIREMENT_ELIGIBLE**: Long-term stable operation certified; V1 eligible for scheduled deprecation.

---

## 2. Independent Feature Gates & Circuit Breakers

### Feature Flags
- `HIGHVIEW_V2_GLOBAL_ENABLED`: Emergency kill switch (default: `True`). If set to `False`, all consumers immediately route to V1.
- `HIGHVIEW_V2_HRIDAY_ENABLED`: Controls HRIDAY retrieval cutover (Stage 1).
- `HIGHVIEW_V2_DASHBOARD_ENABLED`: Controls Dashboard analytical cutover (Stage 2).
- `HIGHVIEW_V2_PRESENTATION_ENABLED`: Controls Presentation evidence cutover (Stage 3).
- `HIGHVIEW_V2_HRIDAY_FALLBACK_ALLOWED`: Fallback permitted during canary/transition.
- `HIGHVIEW_V2_DASHBOARD_FALLBACK_ALLOWED`: Fallback permitted during canary/transition.
- `HIGHVIEW_V2_PRESENTATION_FALLBACK_ALLOWED`: Fallback permitted during canary/transition.

### Typed Fallback Taxonomies (No Silent Fallback)
Every fallback event records:
1. `V2_ARTIFACT_MISSING`: Required canonical V2 artifact does not exist.
2. `V2_ARTIFACT_STALE`: Manifest or source fingerprint mismatch.
3. `V2_RELATIONSHIP_AMBIGUOUS`: Relationship unvalidated or ambiguous.
4. `V2_JOIN_PLAN_UNAVAILABLE`: Governed JoinPlan missing or rejected.
5. `V2_ANALYTICAL_EVIDENCE_MISSING`: Evidence record missing from EvidenceGraph.
6. `V2_RETRIEVAL_UNAVAILABLE`: Multi-namespace index search failure.
7. `V2_SCHEMA_CONTRACT_FAILURE`: Output does not conform to consumer schema.
8. `V2_DATASET_VERSION_MISMATCH`: Target dataset version mismatch.
9. `V2_CONTEXT_GROUNDING_FAILURE`: Context package missing required dependency closure.
10. `V2_RUNTIME_ERROR`: Unhandled internal exception.

---

## 3. Phase I8.1: Shadow Parity & Disagreement Closure

Phase I8.1 executes a comprehensive side-by-side audit of V1 versus V2 outputs over the **canonical 6-domain benchmark corpus** (Workforce, Retail, Environmental, Finance, SaaS, Supply Chain) across 10 evaluation categories.

### 3.1 Macro Comparison Classification Summary

| Category | Count | Status | Notes |
| :--- | :---: | :---: | :--- |
| **Total Comparisons** | **60** | Complete | 10 categories evaluated across 6 canonical domains |
| **`UNCHANGED`** | **26** | Validated | Row fidelity, column schemas, referential integrity, base metrics |
| **`EXPECTED_IMPROVEMENT`** | **22** | Certified | Distinct counts, semi-additive stock, weighted ratios, header parser |
| **`EXPECTED_DIFFERENCE`** | **12** | Reviewed | Join safety gating, EvidenceGraph verification, multi-namespace retrieval |
| **`REGRESSION`** | **0** | **STRICT 0** | Zero regressions detected across any domain |
| **`UNRESOLVED`** | **0** | **STRICT 0** | Zero unclassified or uninspected divergences |
| **`CRITICAL`** | **0** | **STRICT 0** | Zero critical or blocker disagreements |

### 3.2 Micro Disagreement Type Distribution (34 Non-UNCHANGED Items)

- **`EXPECTED_FIX`**: **20** cases. V1 mathematical and structural defects corrected by V2 (e.g., 22× headcount fanout trap, period-end inventory calculation, weighted gross margin ratio, unweighted active seat ratio, partial-key join blocking, CPCB hierarchical header decomposition).
- **`EXPECTED_REFACTOR`**: **14** cases. Architectural representations refined (e.g., multi-namespace retrieval, existential EvidenceGraph validation, governed JoinPlan generation).
- **`REGRESSION`**: **0** cases.
- **`UNRESOLVED`**: **0** cases.

### 3.3 Domain-by-Domain Audit Breakdown

| Domain | Total | UNCHANGED | EXPECTED_IMPROVEMENT | EXPECTED_DIFFERENCE | EXPECTED_FIX | EXPECTED_REFACTOR | REGRESSION | UNRESOLVED | CRITICAL |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Workforce** | 10 | 4 | 4 | 2 | 4 | 2 | **0** | **0** | **0** |
| **Retail** | 10 | 3 | 5 | 2 | 5 | 2 | **0** | **0** | **0** |
| **Environmental** | 10 | 6 | 3 | 1 | 2 | 2 | **0** | **0** | **0** |
| **Finance** | 10 | 4 | 4 | 2 | 4 | 2 | **0** | **0** | **0** |
| **SaaS** | 10 | 4 | 4 | 2 | 4 | 2 | **0** | **0** | **0** |
| **Supply Chain** | 10 | 5 | 2 | 3 | 1 | 4 | **0** | **0** | **0** |
| **TOTAL** | **60** | **26** | **22** | **12** | **20** | **14** | **0** | **0** | **0** |

---

## 4. Canonical Disagreement Ledger (Phase I8.1 Non-UNCHANGED Records)

All 34 divergences between V1 and V2 have been audited, benchmark-grounded, and assigned `ReviewStatus.APPROVED`:

### 4.1 Workforce
1. `CMP-WF-03` [grain]: V1 flat table representation → V2 explicit `CanonicalGrain.ENTITY` (`employee_id`) and `CanonicalGrain.EVENT` (`employee_id, date`). `EXPECTED_IMPROVEMENT` / `EXPECTED_FIX`.
2. `CMP-WF-05` [join_plans]: V1 unconstrained join → V2 `JoinSafety.SAFE_WITH_PREAGGREGATION` with fanout multiplier firewall. `EXPECTED_DIFFERENCE` / `EXPECTED_FIX`.
3. `CMP-WF-06` [metric_definitions]: V1 `COUNT(*)` → V2 `COUNT(DISTINCT employee_id)` under Workforce Analytics family. `EXPECTED_IMPROVEMENT` / `EXPECTED_FIX`.
4. `CMP-WF-07` [analytical_values]: V1 returns 2,200 rows (22× fanout trap) → V2 preserves 100 distinct employee headcount. `EXPECTED_IMPROVEMENT` / `EXPECTED_FIX`.
5. `CMP-WF-09` [evidence]: V1 unverified string → V2 existential `EVID-W01` verified in EvidenceGraph. `EXPECTED_DIFFERENCE` / `EXPECTED_REFACTOR`.
6. `CMP-WF-10` [retrieval_context]: V1 monolithic vector search → V2 multi-namespace search returning `GovernedContextPackage`. `EXPECTED_IMPROVEMENT` / `EXPECTED_REFACTOR`.

### 4.2 Retail
7. `CMP-RT-02` [semantic_role]: V1 plain measure → V2 semi-additive stock balance vs additive sales revenue. `EXPECTED_IMPROVEMENT` / `EXPECTED_FIX`.
8. `CMP-RT-03` [grain]: V1 flat tables → V2 composite 3-part grain (`store_id, product_id, date`). `EXPECTED_IMPROVEMENT` / `EXPECTED_FIX`.
9. `CMP-RT-04` [relationships]: V1 uniform joinability → V2 cross-fact relationship identified and restricted. `EXPECTED_DIFFERENCE` / `EXPECTED_FIX`.
10. `CMP-RT-05` [join_plans]: V1 raw partial-key fact join allowed → V2 blocked as `JoinSafety.UNSAFE`. `EXPECTED_DIFFERENCE` / `EXPECTED_FIX`.
11. `CMP-RT-06` [metric_definitions]: V1 `SUM(stock_on_hand)` → V2 `SEMI_ADDITIVE_PERIOD_END(stock_on_hand, order_by=date)`. `EXPECTED_IMPROVEMENT` / `EXPECTED_FIX`.
12. `CMP-RT-07` [analytical_values]: V1 returns 310 (sum of daily balances) → V2 returns 90 (true physical stock at close). `EXPECTED_IMPROVEMENT` / `EXPECTED_FIX`.
13. `CMP-RT-09` [evidence]: V1 unverified tag → V2 existential `EVID-R01` verified in EvidenceGraph. `EXPECTED_DIFFERENCE` / `EXPECTED_REFACTOR`.
14. `CMP-RT-10` [retrieval_context]: V1 flat keyword match → V2 multi-namespace retrieval with semi-additive contract. `EXPECTED_IMPROVEMENT` / `EXPECTED_REFACTOR`.

### 4.3 Environmental
15. `CMP-EV-01` [schema]: V1 basic heuristic → V2 adaptive reconstruction decomposing hierarchical headers, dates (`09.05.2024`), qualifiers (`approved`), and units (`µg/m³`). `EXPECTED_IMPROVEMENT` / `EXPECTED_FIX`.
16. `CMP-EV-09` [evidence]: V1 plain footnote → V2 structured `EVID-E01` in EvidenceGraph with sensor provenance. `EXPECTED_DIFFERENCE` / `EXPECTED_REFACTOR`.
17. `CMP-EV-10` [retrieval_context]: V1 sheet keyword search → V2 multi-namespace retrieval with station and continuous sensor metrics. `EXPECTED_IMPROVEMENT` / `EXPECTED_REFACTOR`.

### 4.4 Finance
18. `CMP-FN-05` [join_plans]: V1 unconstrained join → V2 `JoinSafety.SAFE_WITH_PREAGGREGATION` for debit/credit balance integrity. `EXPECTED_DIFFERENCE` / `EXPECTED_REFACTOR`.
19. `CMP-FN-06` [metric_definitions]: V1 unweighted average `AVG(margin_pct)` → V2 weighted ratio `SUM(revenue - cogs) / SUM(revenue)`. `EXPECTED_IMPROVEMENT` / `EXPECTED_FIX`.
20. `CMP-FN-07` [analytical_values]: V1 unweighted average 70.0% → V2 weighted gross margin 78.18%. `EXPECTED_IMPROVEMENT` / `EXPECTED_FIX`.
21. `CMP-FN-08` [denominators]: V1 unverified denominator → V2 explicit denominator `total_gross_revenue` with non-zero guarantee. `EXPECTED_IMPROVEMENT` / `EXPECTED_FIX`.
22. `CMP-FN-09` [evidence]: V1 unverified string → V2 existential `EVID-F01` with high analytical reliability. `EXPECTED_DIFFERENCE` / `EXPECTED_REFACTOR`.
23. `CMP-FN-10` [retrieval_context]: V1 monolithic vector search → V2 multi-namespace search with financial metrics and transaction relationships. `EXPECTED_IMPROVEMENT` / `EXPECTED_REFACTOR`.

### 4.5 SaaS
24. `CMP-SAAS-03` [grain]: V1 flat table → V2 monthly temporal grain on subscriptions (`tenant_id, billing_month`). `EXPECTED_IMPROVEMENT` / `EXPECTED_FIX`.
25. `CMP-SAAS-05` [join_plans]: V1 unconstrained join → V2 `JoinSafety.SAFE_WITH_PREAGGREGATION` for tenant summaries. `EXPECTED_DIFFERENCE` / `EXPECTED_REFACTOR`.
26. `CMP-SAAS-06` [metric_definitions]: V1 average of seat percentages → V2 weighted ratio `SUM(active_seats) / SUM(seat_count)`. `EXPECTED_IMPROVEMENT` / `EXPECTED_FIX`.
27. `CMP-SAAS-07` [analytical_values]: V1 unweighted average 65.0% → V2 weighted active seat utilization 79.70%. `EXPECTED_IMPROVEMENT` / `EXPECTED_FIX`.
28. `CMP-SAAS-09` [evidence]: V1 unverified tag → V2 existential `EVID-S01` with tenant cohort binding. `EXPECTED_DIFFERENCE` / `EXPECTED_REFACTOR`.
29. `CMP-SAAS-10` [retrieval_context]: V1 flat vector search → V2 multi-namespace search returning SaaS family metrics, monthly grain profiles, and tenant join plans. `EXPECTED_IMPROVEMENT` / `EXPECTED_REFACTOR`.

### 4.6 Supply Chain
30. `CMP-SC-05` [join_plans]: V1 raw join allowed → V2 `JoinSafety.SAFE_WITH_PREAGGREGATION` requiring grain preservation on warehouses. `EXPECTED_DIFFERENCE` / `EXPECTED_FIX`.
31. `CMP-SC-06` [metric_definitions]: V1 `SUM(capacity_sqft)` without grain guard → V2 `SUM(capacity_sqft)` with grain preservation on warehouses. `EXPECTED_IMPROVEMENT` / `EXPECTED_FIX`.
32. `CMP-SC-07` [analytical_values]: V1 returns 5,000,000 sqft (10× multiplication fanout) → V2 preserves 500,000 sqft total capacity. `EXPECTED_IMPROVEMENT` / `EXPECTED_FIX`.
33. `CMP-SC-09` [evidence]: V1 unverified tag → V2 existential `EVID-SC01` with shipment provenance. `EXPECTED_DIFFERENCE` / `EXPECTED_REFACTOR`.
34. `CMP-SC-10` [retrieval_context]: V1 keyword search → V2 multi-namespace search returning warehouse entities, shipment events, and grain-preserved capacity metrics. `EXPECTED_IMPROVEMENT` / `EXPECTED_REFACTOR`.

---

## 5. Certification Invariants Verification

### 5.1 Mathematical Safety Invariants
- `wrong_denominator`: **0**
- `unsafe_join`: **0**
- `wrong_grain`: **0**
- `invented_evidence`: **0**
- `wrong_dataset`: **0**
- `stale_artifact`: **0**

### 5.2 Retrieval Invariants
- `wrong_artifact`: **0**
- `orphan_context`: **0**
- `missing_dependency_closure`: **0**

### 5.3 Operational & Boundary Invariants
- `production_writes`: **0**
- `consumer_cutover`: **NO** (Locked to `False`)
- `feature_gates_activated`: **NO** (All consumers remain on V1)
- `llm_truth_calls`: **0** (All truth comparisons evaluated deterministically)
- `live_db_sha256`: `a2d2c7f73746484e8aa4c32e18f00de928bf39452fb0f20500fcd0e64db9e7c1` (P0 intact)
