# Domain Governance, Responsibility Boundaries & Visual Decision Intelligence

> **Parent:** [README.md](../README.md) &rsaquo; [System Architecture](system-architecture.md) &rsaquo; **Domain Governance & Dashboards**

---

## 1. Architectural Mission

HighView was originally conceived with industrial people analytics models, but has evolved into a cross-domain decision intelligence platform. To maintain mathematical and operational truthfulness across diverse domains (workforce, environmental air quality, commercial retail, operations, education), the platform enforces **domain governance**, **strict UI responsibility boundaries**, **capability-entitlement gating**, and **semantic aggregation invariants**.

---

## 2. Executive Dashboard vs. Data Explorer Responsibility Boundary

HighView enforces a strict division of responsibility between the Executive Dashboard and the Data Explorer:

```text
┌────────────────────────────────────────────────────────┐
│                  EXECUTIVE DASHBOARD                   │
│             "What requires my attention?"              │
└────────────────────────────────────────────────────────┘
  • Dataset Context & Compact Briefing
  • Governed 5-KPI Strip (Single-line metrics)
  • Governed 8–15 Executive Visual Portfolio (Target 10–12):
      - Hero Benchmark Ranking (Bar chart, span 12)
      - Statistical Distribution (Box plot, span 6)
      - Bivariate Association (True scatter plot, span 6)
      - Capacity & Cohort Composition (100% stacked bar, span 6)
      - Target vs Actual Benchmark (Bullet chart, span 4)
      - Metric Entity Comparison (Lollipop chart, span 4)
      - Olympic Top 3 Podium (Gold/Silver/Bronze pedestals, span 4)
      - Disparity Range Spread (Dumbbell chart, span 4)
      - Statistical Anomaly Concentration (Variance bars, span 6)
  • Compact Top 3 / Bottom 3 Ranking Overview
  • Compact Scenario Summary (Gated to entitled domains)
  • Contextual Deep-Links (Explore full ranking →, Explore relationship →)
                             │
                             │  Deep-link Navigation
                             ▼
┌────────────────────────────────────────────────────────┐
│                     DATA EXPLORER                      │
│             "Show me the analysis behind it."          │
└────────────────────────────────────────────────────────┘
  • Tab 1: Overview       ── Dataset statistics, schema catalog, null audits
  • Tab 2: Rankings       ── Full polarity-aware rankings, distribution histogram
  • Tab 3: Trends         ── Longitudinal series, seasonality, forecast models
  • Tab 4: Relationships  ── Bivariate scatter plots, correlation matrices
  • Tab 5: Distributions  ── Quantile spreads, box plots, cohort histograms
  • Tab 6: Evidence       ── Audited FACT-XXX / EVID-XXX cryptographic citations
  • Tab 7: Technical      ── Reconstruction safety telemetry, confidence radar
```

### Prohibited Content on the Executive Dashboard
To preserve executive clarity, the following technical artifacts are **strictly prohibited** on Level 1 (Executive Dashboard) and must reside in the Data Explorer:
- Long observation cards and raw evidence records.
- Calculation proofs and mathematical formula breakdowns.
- Relationship diagnostics and correlation matrix tables.
- Candidate-ranking traces and full cohort lists ($>6$ entities).
- Opportunity execution logs and schema inspection tools.

---

## 3. Domain Capability Entitlement & Gating

Specialized analytical engines must not leak into unrelated business domains:

| Analytical Capability | Entitled Domains | Gating Contract | Behavior for Non-Entitled Domains |
| :--- | :--- | :--- | :--- |
| **Workforce Scenario Explorer** | `workforce_hr` | `governed_scenario_domain == "workforce"` | Hidden from header navigation; scenario summary card suppressed on dashboard. |
| **Talent 9-Box Matrix** | `workforce_hr` | Requires performance & potential ratings | Suppressed from opportunity map and story planner. |
| **Bradford Disruption Factor** | `workforce_hr` | Requires absence spell & day counts | Suppressed when absence dimensions are absent. |
| **NAAQS Air Quality Benchmarks** | `environmental` | `domain == "environmental"` | Benchmarks fixed to statutory standards ($60\ \mu\text{g/m}^3$ for $\text{PM}_{10}$). |
| **Retail Basket & Margin** | `commercial_retail` | `domain == "commercial_retail"` | Gated to transaction line items. |

### Implementation Proof
In [`frontend/src/pages/AdaptiveDashboardPage.jsx`](file:///Users/vinayksharma/Developer/pulsehr-ai/frontend/src/pages/AdaptiveDashboardPage.jsx):
```jsx
{/* Scenario Explorer Header Button - Gated by Domain Entitlement */}
{Boolean(data?.domain_profile?.governed_scenario_domain || data?.domain_profile?.domain === "workforce") && (
  <button
    type="button"
    className="executive-dashboard-header-button executive-dashboard-header-button--scenario"
    onClick={() => setScenarioExplorerOpen(true)}
  >
    Scenario Explorer
  </button>
)}
```

---

## 4. Semantic Aggregation Integrity (`AggregationSemanticsIntegrity`)

### The Non-Additive Axiom
Rate, ratio, percentage, and physical concentration metrics are **mathematically non-additive**. Calculating an arithmetic sum (`SUM`) across monitoring stations or departments produces nonsense:

$$\sum \text{Annual Average Concentration} \quad \implies \quad \text{FATAL SEMANTIC ERROR}$$

### Enforced Rules
1. **Ban on `SUM` and `Total`:** Measures classified as concentrations ($\mu\text{g/m}^3$, $\text{ppm}$), rates ($\%$, turnover rate), or unit averages are barred from additive aggregation.
2. **Mandatory Central Tendency:** The engine enforces arithmetic mean (`mean_measure`), median, or quantile distribution.
3. **Unit Governance:** Physical units ($\mu\text{g/m}^3$) are strictly attached to all KPI nodes and axis labels.
4. **Redundancy Suppression (`VisualStoryRedundancyIntegrity`):** Standalone scalar cards (e.g. `Total SO2 annual average = 4,649` or `Monitored Coverage = 435`) are suppressed from the Executive Visual Stories grid, preventing duplication with the governed KPI strip.

---

## 5. Ordinal & Identifier Exclusion

Columns that serve as sequential row indices or document metadata must never be treated as analytical numbers:
- **Examples:** `Sr. No.`, `Serial Number`, `Record ID`, `EQ-11099/...`.
- **Classification:** Evaluated as `is_ordinal_or_identifier` during semantic profiling.
- **Rule:** Excluded from:
  - Metric rollups and summary statistics.
  - Candidate fact generation (`FACT-XXX`).
  - Ranking entities and comparison bars.
  - Scatter plot axes and correlation analysis.

---

## 6. Visual Intent Truthfulness & Temporal Integrity

### A. True Relationship Rendering (`RELATIONSHIP` Intent)
- **Problem:** Measure-by-measure associations were previously misclassified as `RANKING` and rendered as categorical bar charts with synthetic time labels (`Week 1...5`).
- **Solution:** Measure associations are classified with `intent = "RELATIONSHIP"`. They render as genuine **ECharts scatter plots**:
  - $X$-Axis: Primary measure (e.g. $\text{SO}_2$ Annual Average).
  - $Y$-Axis: Secondary measure (e.g. $\text{NO}_2$ Annual Average).
  - Data Points: Monitored entities (cities, stations) with custom hover tooltips showing entity names and exact coordinates.
  - CTA Button: `"Explore relationship →"`, deep-linking directly to `#explorer?tab=relationships`.

### B. Temporal Label Integrity (`TemporalLabelIntegrity`)
- When a dataset lacks a genuine temporal column (`temporal_point == null`), the system **strictly bans** the generation of synthetic or fallback time labels (`Week 1`, `Month 1`, `Q1`).
- Bivariate or categorical distributions must represent observed entity categories or continuous numeric bins.

### C. Domain Narrative Grounding (`DomainNarrativeIntegrity`)
- The story builder dynamically sanitizes generated text to prevent legacy vocabulary leakage.
- For non-workforce datasets, terms such as `policy adherence`, `logging discrepancies`, `department`, `attendance`, and `leave` are strictly banned.
- Grounded environmental narratives are emitted:
  - **Title:** `PM10 Pollution Outlier Concentration`
  - **Finding:** `"Jharia records the highest observed PM10 level at 281 µg/m³, substantially exceeding the 60 µg/m³ NAAQS annual benchmark."`
  - **Action:** `"Prioritize high-concentration locations for source investigation and pollution-control intervention."`

---

## 7. Generic Ranking Polarity (`LOWER_IS_BETTER`)

Rankings are decoupled from hardcoded business assumptions. Both the Executive Dashboard Top/Bottom 3 and the Data Explorer Rankings tab support directional polarity:

| Polarity Mode | High Value Meaning | Low Value Meaning | Example Measures | Top 3 Represents | Bottom 3 Represents |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`HIGHER_IS_BETTER`** | Strong performance | Underperformance | Sales, Attendance, Revenue | Top Performers | Underperforming / Headwinds |
| **`LOWER_IS_BETTER`** | Critical hazard | Healthy baseline | $\text{PM}_{10}, \text{SO}_2$, Defect rate, Attrition | Highest Risk / Critical Outliers | Cleanest Baseline / Benchmarks |

### Population-Safe Small Cohort Guarantee
On the Executive Dashboard, the Top 3 / Bottom 3 component guarantees:
- Maximum of **6 unique entities** rendered across the card.
- If the total population $N \le 6$, entities are deduplicated and displayed as an ordered spectrum to avoid duplicate card entries.

---

## 8. Dataset Isolation Integrity & Cross-Dataset Non-Contamination

### A. The Dataset Boundary Invariant
To prevent analytical contamination across successively or concurrently uploaded workbooks, HighView enforces the invariant:

$$\text{artifact}.\text{dataset\_id} == \text{active\_dataset\_id}$$

Every visual story, evidence node, narrative element, and relationship candidate must strictly originate from the active dataset.

### B. Two-Sheet Relationship Discovery Hygiene
In [`sheet_catalog.py:rebuild_relationships`](file:///Users/vinayksharma/Developer/pulsehr-ai/backend/app/services/sheet_catalog.py#L826):
1. **Intra-Dataset Join Invariant**: Cross-dataset relationships are forbidden. Sheets are only compared if `left['dataset_id'] == right['dataset_id']`.
2. **Key Candidate Hygiene**: Non-key columns such as date ranges (`1st to 5th July`), temporal slices, and measure aggregates are explicitly excluded from join candidate consideration.
3. **Canonical Key Alias Matching**: Entity IDs (`ID` $\leftrightarrow$ `Employee ID`) are recognized via canonical alias matching, yielding verified $1:1$ entity joins (e.g. `Sheet1.ID` $\leftrightarrow$ `Leave Calculation Check.Employee ID`, 209 matching keys) while preventing false-positive relationship explosions (e.g., 50 spurious cross-sheet links).

### C. Cross-Domain Vocabulary Purity (`DatasetIsolationIntegrity`)
In [`backend/app/services/adaptive_dashboard/dataset_isolation_integrity.py`](file:///Users/vinayksharma/Developer/pulsehr-ai/backend/app/services/adaptive_dashboard/dataset_isolation_integrity.py):
- **Workforce Datasets**: Strictly guarded against environmental pollutant signatures (`SO2`, `NO2`, `PM10`, `PM2.5`, `Jharia`, `Brynihat`). Relationship visuals are grounded in genuine workforce measures (e.g. `Total Attendance` vs `Approved Leaves`, $r = -0.44$).
- **Environmental Datasets**: Strictly guarded against workforce terminology (`Attendance`, `Department`, `Approved Leave`, `Employee`, `WFO`). Anomaly narratives report station exceedances rather than department disparities.

### D. Transactional Cascaded Deletion & Cache Invalidation
In [`backend/app/services/dataset_deletion.py`](file:///Users/vinayksharma/Developer/pulsehr-ai/backend/app/services/dataset_deletion.py):
- **Bidirectional Relationship Purge**: Explicitly deletes `sheet_relationships WHERE left_sheet IN (...) OR right_sheet IN (...)`.
- **Descendant Cascade**: Cleans `sheet_curated_rows`, `sheet_rows`, `sheet_cells`, `tabular_vectors`, `tabular_chunks`, `sheets`, `dataset_uploads`, and presentations within a single transactional block.
- **Cache Invalidation**: Clears `SnapshotManager._SNAPSHOT_CACHE`, `_GENERIC_WORKFLOW_CACHE`, `_facts_by_snapshot`, and embedding memory caches.
- **Post-Deletion Orphan Verification**: Verifies zero residual rows across all tables (`orphan_check = "PASS"`).
- **Regression Contract**: Tested via `backend/tests/test_dataset_isolation_and_deletion_cascade.py` across A &rarr; Delete &rarr; B, B &rarr; Delete &rarr; A, and simultaneous co-existence scenarios.

---

## 9. Executive Visual Diversity & Density Engine Governance

### A. The 8–15 Visual Envelope & Portfolio Optimization
HighView's composition planner operates under an explicit visual budget:
- **Minimum visuals:** 8
- **Target visuals:** 10–12
- **Maximum visuals:** 15
- **Intent diversity:** $\ge 4$ distinct intents, max 3 per intent.
- **Chart family diversity:** $\ge 5$ distinct chart families, max 2 per family.

The portfolio is selected greedily by `VisualPortfolioOptimizer` using multi-factor scoring:
$$\text{Score} = 0.40 \cdot \text{importance} + 0.35 \cdot \text{confidence} + 0.25 \cdot \text{business\_relevance} + \text{Diversity Bonuses} - \text{Redundancy Penalties}$$

### B. Truth > Quota Invariant
HighView prioritizes factual mathematical truth over visual quantity:
1. **Never Fabricate Entities or Stories:** The optimizer will gladly return 8 high-confidence visuals rather than forcing 15 low-confidence or synthetic charts.
2. **Never Fabricate Temporal Dimensions:** Cross-sectional tables never receive line charts, slope charts, or synthetic date buckets.
3. **Strict Archetype Gating (`ChartCapabilityRegistry`):**
   - `BOX_PLOT`: numeric measure with grouping, $\ge 5$ observations.
   - `SCATTER`: 2 continuous numeric measures, $N \ge 3$ points.
   - `PODIUM_TOP_3`: high-confidence ranking $N \ge 3$, strict label truncation ($\le 20$ chars, $\le 2$ lines, full label in hover tooltip).
   - `WORD_CLOUD`: strictly forbidden for quantitative ranking and trends.

### C. Label Truncation on Podium Top 3
In [`backend/app/services/adaptive_dashboard/visual_portfolio_optimizer.py:format_podium_labels`](file:///Users/vinayksharma/Developer/pulsehr-ai/backend/app/services/adaptive_dashboard/visual_portfolio_optimizer.py):
- Entity names exceeding 20 characters are truncated with an ellipsis (`...`) for display on podium cards.
- Multi-line wrapping is capped at 2 lines.
- Unabridged full names and exact values are preserved in tooltips and the underlying data payload.

