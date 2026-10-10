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
  • 3 Executive Visual Stories:
      - Story 1: Hero Benchmark Ranking (Bar chart)
      - Story 2: Outlier / Anomaly Concentration (Variance bars)
      - Story 3: Bivariate Relationship (True Scatter plot)
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
