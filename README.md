# PulseHR AI

Local spreadsheet analytics, industrial workforce intelligence, and HR copilot. Uploaded CSV and Excel sheets are the
sole source of truth; there is no automatic demo population, assumed workforce, or hallucinated metrics.

## Quickstart

```bash
# Backend (FastAPI + Uvicorn)
cd backend
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 8020 --reload
```

```bash
# Frontend (React + Vite + SCSS)
cd frontend
npm install
npm run dev -- --port 5175
```

---

## Core Capabilities & Architecture

### 1. Upload-Driven Ingestion & Zero-Leakage Pipeline
- **Ingestion Studio:** Upload CSV or Excel workbooks (.xlsx, .xls, .csv). Each file and sheet retains its original rows and columns.
- **Automated Industrial Ingestion:** Every upload immediately computes verified People Analytics models without human intervention.
- **Complete Deletion Pipeline:** Deleting a dataset cascades to sheets, rows, search entries, vectors, relationships, and purges all cached narratives (`executive_narratives`). Deleting the last dataset leaves an empty application with a dedicated zero-state screen.
- **Bulk Cleanup Endpoint:** `DELETE /api/upload/datasets` completely purges all workspace data in a single operation.

### 2. Executive Overview: Progressive Chunked Loading & Industrial Science
The Executive Overview decouples into 4 parallel asynchronous streams with dedicated skeleton loaders:
- **Chunk 1: Base Catalog & Scope Metadata (`/api/analytics/overview/base`):** Instant rendering (< 20ms) of header banner, analytics scope selector tabs, KPI metrics, and sheet profiles.
- **Chunk 2: Visual Intelligence Suite (`/api/analytics/overview/visuals`):** Computes formula-grounded industrial People Analytics models:
  - **McKinsey / GE 9-Box Strategic Talent & Risk Matrix:** 3x3 talent-potential diagnostic with interactive roster drilldowns.
  - **Bradford Factor Absenteeism Disruption Index ($B = S^2 \times D$):** Department disruption spectrum with recognized HR threshold tiers (<50 Normal, 51–200 Moderate, 201–500 High, >500 Critical).
  - **Workforce Burnout & Workload Strain Index:** Overtime vs absenteeism multiplier ($(\text{OT}/160\text{h}) \times (1 + \text{Absent}/20\text{d}) \times 100\%$) pinpointing teams exceeding the 20% critical threshold.
  - **Cross-Sheet Performance-Absenteeism Elasticity:** OLS regression slope ($\beta$), model fit ($R^2$), and operational tipping point days.
  - **Longitudinal Attendance Trajectory Forecasting:** Multi-year daily hours model with Holt's damped smoothing and 95% confidence intervals.
- **Chunk 3: AI Executive Story & Verifiable Audit (`/api/analytics/overview/story`):** Grounded executive narrative with numerical fact-checking and AI Quality Audit modal.
- **Chunk 4: Cross-Sheet Relational Story (`/api/analytics/overview/relational`):** Automatic exact-key join correlation and talent quadrant segmentation.

### 3. Data Explorer: Dual View Modes
- **📋 Raw Table & Joins:** Paginated rows, column search, and inner joins between connected sheets.
- **📊 Sheet Visual Projections & Column Profiles:** Relocated direct data extracts (Average Rating by Dept, Attendance Rate, Overtime Hours, Absent Days) alongside statistical profiles (Mean, Median, Min, Max, Distinct, Missing) for every column.

### 4. AI HR Copilot & Verified Tools
- **Rank-BM25 & Vector RAG:** Grounded strictly in uploaded rows and exact-key relationships.
- **Verified Arithmetic & Calculation Tool:** Exact sums, means, medians, mins, maxs, counts, groupings, and filters across full datasets.
- **Native Industrial Tool (`industrial_metric`):** Answers queries on Bradford scores, 9-Box matrices, burnout strain, and elasticity using validated formulas rather than LLM guesswork.
- **PowerPoint & PDF Export:** One-click export of executive slides (`.pptx`) and printable HTML reports with data provenance.

### 5. UI & Responsive Design Refinements
- **Adaptive Layout:** High-density desktop workspace gracefully transforms into touch-friendly compact mobile view with bottom tab navigation on viewports under 760px.
- **Accessibility & Motion:** Skip-to-content links, visible focus outlines, ARIA tab roles, and `prefers-reduced-motion` compliance.
- **Human-Centered Microcopy:** Clean, streamlined language and onboarding across Copilot, Ingestion, and Overview.

---

## Relationship Semantics

Column names are normalized and common aliases (`Employee ID` / `Emp ID`, `Department` / `Dept`, etc.) are recognized.
Overlapping values and uniqueness determine cardinality (one-to-one, one-to-many, many-to-many).
- **Exact Links:** Matching key columns with a unique side create automatic equality joins. Empty values never match; leading zeroes are preserved.
- **Suggested Links:** Vector similarity over column descriptors produces suggestions for review, never automatic joins or silent merges.

---

## API Summary

- `GET /api/sheets`: All sheets, column profiles, and relationship evidence.
- `GET /api/sheets/{id}/rows`: Paginated source rows.
- `GET /api/sheets/{id}/projections`: Direct data extract charts and column summary statistics.
- `GET /api/sheets/relationships/{id}/rows`: Linked inner-join records.
- `GET /api/analytics/overview/base`: Instant base catalogue metrics (< 20ms).
- `GET /api/analytics/overview/visuals`: Industrial visual intelligence dashboard (~95ms).
- `GET /api/analytics/overview/story`: AI executive story and quality audit.
- `GET /api/analytics/overview/relational`: Cross-sheet relational intelligence.
- `GET /api/analytics/overview`: Full monolithic payload (100% backward-compatible).
- `DELETE /api/upload/datasets/{id}`: Delete dataset and purge associated cached narratives.
- `DELETE /api/upload/datasets`: Bulk workspace purge.
- `POST /api/copilot/query`: Grounded chat or tool execution (`calculate`, `industrial_metric`, `presentation`, `arithmetic`).

---

## Verification

```bash
# Backend unit & integration suite (78 tests)
cd backend
PYTHONPATH=. .venv/bin/pytest tests/ -v

# Frontend production build
cd ../frontend
npm run build
```
