# PulseHR AI

Local spreadsheet analytics and HR copilot. Uploaded CSV and Excel sheets are the
source of truth; there is no automatic demo population or assumed workforce.

## Run

```bash
cd backend
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 8020 --reload
```

```bash
cd frontend
npm install
npm run dev -- --port 5175
```

## Upload-driven workflow

- **Ingestion Studio:** upload CSV or Excel workbooks. Each file and sheet retains
  its original rows and columns. Same-name uploads are separate sources, never
  silent replacements. Every dataset, including a previously loaded Kaggle file,
  has a Delete control. Deletion cascades to rows, search entries and relationships.
- **Executive Overview:** dataset/sheet/row counts, source-specific numeric metrics,
  missing values and discovered relationships. No missing metric is replaced with
  a demo statistic. Row counts are not employee headcounts.
- **Data Explorer:** select any file/sheet, search all values, paginate all rows, or
  inspect an available exact-key inner join. Left/right column prefixes preserve
  duplicate field names and conflicting values.
- **Copilot:** Rank-BM25 and available Ollama vector matches retrieve original rows.
  Exact-key relationship expansion adds connected records with file/sheet/row
  provenance. No synthetic employee profiles enter the answer context.
- **Calculate from data:** choose a file/sheet or connected view, numeric column,
  operation, grouping and optional equality filter. Full persisted source rows
  are used. Counts count rows; means exclude blanks. Joined measures can repeat
  on a one-to-many join, so choose the intended source measure. Explicit percentage
  strings retain percent units; consistent rating fractions retain their scale.
- **Presentations:** current source counts and sheet profiles, or a calculation
  result, export as editable PowerPoint tables with source notes. Reports no longer
  depend on the old employee database. Previously downloaded files remain snapshots.

## Relationship semantics

Column names are normalized and common aliases (Employee ID / Emp ID, Department /
Dept, etc.) are recognized. Observed overlapping values and uniqueness determine
join cardinality. Compatible key columns with a unique side get automatic equality
joins. Empty values never match; leading zeroes are preserved. Matching ignores
case and surrounding/repeated whitespace, but not punctuation.

Ollama embeddings also compare column descriptors. Vector similarity with shared
values produces **suggestions**, never an identity claim or silent merge. Duplicate
keys on both sides and generic shared measures remain suggestions. These are record
relationships, not statistical correlations or evidence of causation. Suggested
relationships are visible but cannot be used as automatic joins. Composite keys and
fuzzy value joins are not yet supported. Review source identity where IDs may be
reused across unrelated systems.

When Ollama is unavailable, all rows still enter keyword search, the overview,
calculations and exact relationships. Vector ranking/suggestions require the local
embedding model and a compatible dimension (768 by default). Missing legacy column
vectors are populated on a later upload when that model is available. Migrated rows
are keyword-indexed; re-upload a file to add row embeddings. Retrieval samples are
not used to estimate full-dataset totals.

## Existing installation migration

Startup imports original existing files into the sheet catalogue once. A previous
Kaggle attendance file, if present in the local cache, becomes a normal deletable
sheet. No network download or reseeding occurs. Missing source files remain visible
with a re-upload notice. Legacy synthesized employee/alert/punch tables are retired
and cleared only after a recovery database is saved at
`backend/data/db/before_sheet_catalog_v1.sqlite3`. Original uploads remain intact.
Legacy employee-list endpoints return no synthetic roster. The old reseed endpoint
returns 410. Deleting the last source leaves an empty application across restarts.

## Limits and API

Uploads are limited to 20 MB, 20,000 total rows per file and 200 columns per sheet.
All accepted rows are retained (no 300-row truncation). Legacy `.xls` requires a
compatible Pandas Excel engine; CSV and `.xlsx` use installed dependencies.
Relationship calculation views have a 20,000 joined-row limit. The catalogue,
keyword index and relationship detection are local and intended for modest datasets.

- `GET /api/sheets`: all sheets, column profiles and relationship evidence.
- `GET /api/sheets/{id}/rows?page=1&limit=25&search=...`: original rows.
- `GET /api/sheets/relationships/{id}/rows`: linked inner-join rows.
- `GET /api/analytics/overview`: current catalogue statistics.
- `POST /api/copilot/query`: normal grounded chat or a validated tool request:

```json
{"query":"Calculate absences","tool":{"name":"calculate","calculation":{"dataset_id":2,"sheet":"Sheet1","operation":"sum","column":"Absent days"}}}
```

Use `relationship_id` instead of dataset/sheet for joined calculations. Use
`name: "presentation"` with a calculation to export it, or without one for a source
overview. `name: "arithmetic"` accepts a bounded expression with +, -, *, / and
parentheses. No generated Python or SQL is executed.

## Verification

```bash
cd backend
.venv/bin/python -m pytest -q
cd ../frontend
npm run build
```

Tests use temporary databases and files, including migration, deletion/restart,
multisheet completeness, joins, ambiguity, vector fallback and tool results.
