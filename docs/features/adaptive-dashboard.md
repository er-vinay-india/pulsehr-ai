# Adaptive Multi-Domain Dashboard

> **Parent:** [README.md](../../README.md) &rsaquo; Features

## 1. Domain Detection & Expert Personas

The Adaptive Dashboard (`backend/app/services/adaptive_dashboard/`) detects dataset structure and adopts the corresponding expert analyst persona across 7 registered domains:

| Registered Domain | Expert Persona Title | Focus Metrics & Dimensions |
| :--- | :--- | :--- |
| `commercial_retail` | Commercial Retail Revenue Analyst | Order Value, Conversion Rate, Unit Sales, Product Margins |
| `workforce_hr` | People Analytics Business Partner | Headcount, Turnover, Absenteeism Spells, Overtime Strain |
| `demographics_public` | Public Policy & Census Demographer | Population Density, Cohort Distribution, Socioeconomic Indices |
| `household_budget` | Household Financial Specialist | Expense Categories, Monthly Burn, Savings Rate, Discretionary Spend |
| `operations_support` | Operations & Logistics Engineer | Fulfillment Latency, Defect Rate, Backlog Volume, Throughput |
| `education_academic` | Academic Performance Specialist | Test Scores, Attendance Consistency, Completion Ratios |
| `general_tabular` | Senior Quantitative Data Analyst | Distributions, Quantiles, Outliers, Correlation Coefficients |

---

## 2. Three Progressive Disclosure Layers

Every metric card implements three strict disclosure tiers to avoid information overload while preserving mathematical transparency:

```
┌────────────────────────────────────────────────────────┐
│ 1. GLANCE  │ Dominant number, familiar label, short badge│
├────────────┼───────────────────────────────────────────┤
│ 2. EXPLAIN │ Hover/focus non-interactive definition    │
├────────────┼───────────────────────────────────────────┤
│ 3. INSPECT │ Clickable persistent modal: SQL, formula, │
│            │ source cell coordinates, confidence level │
└────────────────────────────────────────────────────────┘
```

1. **`GLANCE`**: Displayed on immediate render. Shows concise label (e.g., "Active Headcount"), dominant formatted value (e.g., "1,248"), and context qualifier.
2. **`EXPLAIN`**: Non-interactive tooltip on hover or keyboard focus, explaining the metric in plain language.
3. **`INSPECT`**: Deep-dive accessible modal containing full formula derivation, sample row count, excluded null rows, and cryptographic provenance hash.

---

## 3. Endpoints & Invariants

Implemented in `backend/app/routers/adaptive_dashboard.py`:
- **`GET /api/adaptive-dashboard/primary-element?sheet_id=...`**: Fetches the top two deterministically selected primary visual cards.
- **`GET /api/adaptive-dashboard/findings?sheet_id=...`**: Fetches verified findings and domain-specific narrative insights.

**Core Invariant**: Every sheet displays exactly two primary dashboard elements on initial load to ensure instant visual clarity without cognitive overload.
