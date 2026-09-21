# PulseHR AI: Presentation Engine & Executive Overview Unified Reference

**Document Version:** 1.0  
**Purpose:** Single source of truth for presentation generation, visual intelligence parity, and styling specifications. Consult this file instead of re-analyzing requirements.

---

## 1. The Core Disconnect Identified

### What Executive Overview Already Computes:
The Executive Overview (`backend/app/services/visual_intelligence.py` and `frontend/src/components/VisualAnalyticsPanel.jsx`) already computes industrial-grade analytics:
1. **McKinsey / GE 9-Box Matrix**: Talent performance-potential and retention flight risk quadrants.
2. **Bradford Factor Index ($B = S^2 \times D$)**: Unplanned short-term absenteeism disruption scoring.
3. **Burnout Strain Index**: Overtime intensity vs absence ratios identifying compensatory workload.
4. **Longitudinal Trajectory & Forecasting**: Holt-damped 7-day trendlines across chronological periods.
5. **Cross-Sheet Comparative Groupings**: Multi-series grouped bars (e.g. Performance vs Absence across departments).
6. **Prioritized HR Facts**: Deterministically ranked strengths and attention areas with direct chart anchors.
7. **Contextual Investigation Drilldown**: Formula steps, episode breakdown, and raw record lineage.

### The Previous Flaw in PPT Generation:
The PPT generator (`deck_generator.py`) previously operated in isolation from the Executive Overview. When generating slides, it bypassed the rich `visual_dashboard` and `prioritized_facts`, falling back onto hardcoded retail templates (`"Store 20"`, `"8.11x Spread"`, generic line charts).

### The Solution:
**100% Direct Inheritance.** The presentation deck specification must be constructed directly from the Executive Overview's `visual_dashboard` (`workspace_visuals`) and `prioritized_facts`. If a chart or report appears on the Executive Overview screen, it becomes a slide in the deck.

---

## 2. Executive Overview to Slide Mapping Specification

| Executive Overview Component | Slide Layout | Slide Narrative Content | Source Data Hook |
|---|---|---|---|
| **Base Catalog & Scope Header** | `title_hero` + `kpi_summary` | Total records, observation period, completeness %, source table badges. | `baseData.stats`, `detect_sheet_date_range` |
| **Longitudinal Forecast / Trajectory** | `full_chart_takeaway` | Baseline mean, cyclical surge %, volume stability, seasonal peaks. | `visual_dashboard.visualizations[type=forecast\|line]` |
| **Workforce Burnout Strain Index** | `chart_narrative` | Top strained departments, overtime vs absence ratio, turnover risk. | `visual_dashboard.visualizations[type=burnout_strain]` |
| **Bradford Factor Disruption** | `comparison_split` / `kpi_summary` | Org average Bradford score, high-disruption clusters ($S^2 \times D$). | `industrial_models.bradford_factor` |
| **McKinsey / GE 9-Box Matrix** | `chart_narrative` / `comparison_split` | High-performer counts vs retention flight-risk personnel. | `industrial_models.talent_9box` |
| **Comparative Grouped Bars** | `chart_narrative` | Cross-sheet correlation (e.g. Overtime load vs Absence rate). | `visual_dashboard.visualizations[type=comparative_bar]` |
| **Prioritized Strengths & Headwinds** | `comparison_split` | Top positive findings & critical risk areas answering the 4 questions. | `visual_dashboard.prioritized_facts` |
| **Column Profiles / Distribution Table** | `table_detail` | Highest-variance categorical distribution with non-null row counts. | `sheet_rows`, `profile_sheet_data` |
| **Strategic Action Plan** | `action_plan` | 3 prioritized initiatives linked directly to the discovered facts. | `candidate_findings`, `actionable_recommendations` |
| **Cryptographic Evidence Ledger** | `table_detail` | Record-level audit ledger with SHA-256 seal and EVID-xxx citations. | `evidence_ledger`, `snapshot_hash` |

---

## 3. UI, CSS Framework & Design System Standards

The presentation deck must not look like unstyled raw HTML. It must follow modern CSS component frameworks (Bootstrap/Tailwind-caliber design tokens):

### 1. Layout & Grid System:
- **Fixed 16:9 Stage ($1920 \times 1080$)**: Scaled uniformly via CSS transform `matrix` or `scale(min(W/1920, H/1080))` to preserve exact spatial alignment without overflowing or clipping.
- **2-Column & 3-Column Grids**: Standardized grid system:
  - `.row { display: flex; flex-wrap: wrap; margin: -12px; }`
  - `.col-8 (66.66% main chart) + .col-4 (33.33% facts panel)`
  - `.col-6 + .col-6 (50/50 split comparison)`
  - `.col-4 + .col-4 + .col-4 (3-metric card row)`
  - `.col-3 + .col-3 + .col-3 + .col-3 (4-KPI summary strip)`

### 2. Component System:
- **Card Panels (`.card-panel`, `.slide-card`)**:
  - Background: Glassmorphism / solid themed container (`rgba(255, 255, 255, 0.04)` on dark, `#ffffff` on light).
  - Border: `1px solid rgba(255, 255, 255, 0.08)`.
  - Border Radius: `12px` / `16px`.
  - Box Shadow: `0 8px 24px -4px rgba(0, 0, 0, 0.25)`.
- **Evidence Pill Badges**:
  - Green (`#10b981`): `[Evidence]`
  - Blue (`#60a5fa`): `[Derived Metric]`
  - Purple (`#c084fc`): `[Interpretation]`
  - Amber (`#fbbf24`): `[Hypothesis]`
  - Red (`#f87171`): `[Data Limitation]`
  - Pink (`#f472b6`): `[Open Question]`
  - Teal (`#2dd4bf`): `[Recommendation]`
- **Typography Scale**:
  - Eyebrow / Category: `0.85rem`, `letter-spacing: 0.08em`, uppercase, `font-weight: 700`.
  - Slide Headline: `2.25rem` to `2.75rem`, `font-weight: 800`, `line-height: 1.15`, conclusion-driven.
  - Subtitle: `1.15rem`, `color: var(--fg-secondary)`, `line-height: 1.4`.
  - Body Narrative: `1.05rem`, `line-height: 1.6`.
  - KPI Stat Values: `2.5rem` to `3.5rem`, `font-weight: 900`, `font-variant-numeric: tabular-nums`.

---

## 4. Ground-Truth Data Profiling Rules

1. **Never Invent Data**: No placeholder companies, no synthetic stores (`"Store 20"`), no fabricated quotas.
2. **Exact Phrasing**: State counts as `X of Y records (Z%)`.
3. **Four Core Questions for Every Major Finding**:
   - **What happened?** (Empirical observation)
   - **How significant is it?** (Magnitude, percentage, spread ratio)
   - **Where is it concentrated?** (Top department, cohort, date window)
   - **Why does it matter?** (Operational/business consequence)
4. **Full Traceability**: Every number stated on any slide must exist in `evidence_ledger` with an associated `EVID-xxx` identifier.
