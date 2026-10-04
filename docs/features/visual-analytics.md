# Industrial Visual Analytics & Models

> **Parent:** [README.md](../../README.md) &rsaquo; Features

## 1. Proprietary Workforce Intelligence Models

PulseHR AI / HighView computes industrial workforce models deterministically through dedicated engine modules in `backend/app/services/industrial/`:

---

### 1. McKinsey / GE 9-Box Matrix (`talent_9box_model.py`)
- **Purpose**: Talent performance vs potential assessment and retention flight risk identification.
- **Axes**: 3×3 grid mapping Performance Rating (Low, Medium, High) against Potential Rating (Low, Medium, High).
- **Core Quadrants**:
  - `High Performers / Stars`: Core succession pool (top right).
  - `Solid Performers`: Core retention and recognition cohort.
  - `Flight Risks`: High potential with low engagement/compensation alignment.
  - `Performance Concerns`: Immediate coaching or intervention targets.

---

### 2. Bradford Factor ($B = S^2 \times D$) (`bradford_model.py`)
- **Purpose**: Measures operational disruption caused by frequent, short-term unplanned employee absences.
- **Mathematical Formula**:
  $$B = S^2 \times D$$
  - $S$ = Number of distinct absence spells (episodes) in the rolling observation window.
  - $D$ = Total cumulative days absent in the window.
- **Non-Linear Disruption**:
  - *Employee A*: 1 continuous 10-day medical leave &rarr; $1^2 \times 10 = 10$ points (low disruption).
  - *Employee B*: 10 separate 1-day casual absences &rarr; $10^2 \times 10 = 1,000$ points (critical disruption).

---

### 3. Burnout Strain Index (`workforce_strain_model.py`)
- **Purpose**: Detects compensatory workload overload before acute employee turnover occurs.
- **Signals**: Correlates overtime intensity (hours worked above scheduled baseline) against department absence spikes and fatigue markers.

---

### 4. Longitudinal Trajectory & Forecasting (`time_series_forecast.py`)
- **Purpose**: Computes 7-day and monthly trendline projections across historical periods.
- **Methodology**: Holt-damped exponential smoothing with seasonal peak detection, cyclical variance analysis, and statistical confidence intervals.

---

## 2. Analytics Overview Endpoints (`backend/app/routers/analytics.py`)

- `GET /api/analytics/overview/base`: Instant base catalogue metrics (< 20ms).
- `GET /api/analytics/overview/visuals`: Visual intelligence dashboard containing 9-Box, Bradford, and trend charts.
- `GET /api/analytics/overview/story`: AI executive narrative synthesis and data quality audit.
- `GET /api/analytics/overview/relational`: Cross-sheet relational intelligence and multi-table joins.
- `GET /api/analytics/investigate`: Deep contextual investigation drill-down with raw record lineage.
