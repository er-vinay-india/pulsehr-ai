# Gemini Lead Developer Prompt — Finalize, Commit, and Push Adaptive Dashboard + EDA

You are the lead developer responsible for safely finalizing and publishing the current PulseHR AI work.

Repository:

`/Users/vinayksharma/Developer/pulsehr-ai`

The current work includes:

- The new Adaptive Dashboard. Element 5 is currently being implemented.
- The upload-time EDA and data-curation pipeline.
- The Leadership Report.
- Shared semantic labels, number formatting, and ECharts presentation infrastructure.
- Navigation and responsive integration for these features.

Your responsibility is to finish the current implementation, verify it, organize it into reviewable commits, and push it to GitHub without losing, restoring, or overwriting anyone else's work.

## Non-negotiable safety rules

1. Finish Element 5 before starting Git operations. Do not commit a half-rendered element, temporary placeholder, debug output, unfinished API contract, or partially updated test.
2. Treat every existing tracked and untracked source file as potentially valuable work. Do not run `git reset`, `git checkout --`, `git restore`, `git clean`, destructive deletion, or any bulk rollback command.
3. Do not restore files that were intentionally deleted.
4. Do not use `git add .`, `git add -A`, or broad wildcard staging. Stage explicit files or reviewed hunks only.
5. Never commit runtime databases, uploaded datasets, generated presentations, caches, secrets, `.env` files, build output, or Python bytecode.
6. Specifically exclude `backend/database.sqlite`. Add `*.sqlite` to `.gitignore` because the existing ignore rules cover `*.sqlite3` and `*.db`, but not `*.sqlite`.
7. Do not force-push. Do not push unfinished work directly to `main`.
8. Do not rewrite or squash existing history.
9. Preserve the existing Leadership Report, Reference Overview, voice/orb, Copilot, presentation workflow, and approved Adaptive Dashboard elements.
10. Use ECharts for the new dashboard charts. Do not introduce a second chart library.
11. Do not fabricate metrics, thresholds, targets, findings, dates, confidence, or causal conclusions. Every displayed result must remain traceable to uploaded data and the implemented calculation.

## Step 1 — Freeze and inspect the final workspace

Complete Element 5 and its tests first. Then stop editing briefly and inspect:

```bash
git status --short --branch
git diff --stat
git diff --check
git log --oneline --decorate -8
git remote -v
git branch -vv
```

Confirm that files are no longer changing while the commit sequence is being prepared. If another process is still writing to the same files, stop and wait for that process to finish. Do not create commits from an unstable working tree.

At the previously reviewed checkpoint, `main` matched `origin/main` at commit `de45a38`. Re-check this rather than assuming it is still true.

If the remote has advanced, fetch it and report the divergence. Do not rebase, merge, or discard a dirty working tree without first preserving and understanding all local work.

## Step 2 — Remove commit blockers

Make only these justified cleanup changes:

- Add `*.sqlite` to `.gitignore`.
- Ensure `backend/database.sqlite` remains untracked and unstaged.
- Correct the trailing whitespace currently reported in `backend/app/routers/sheets.py`.
- Remove debugging statements only when they were introduced by this implementation and are not purposeful application logging.
- Confirm `__pycache__`, `*.pyc`, `node_modules`, `dist`, uploaded files, and generated artifacts are not staged.

Run:

```bash
git diff --check
git status --short
```

`git diff --check` must pass before committing.

## Step 3 — Create a feature branch

If still on `main`, create:

```bash
git switch -c codex/adaptive-dashboard-eda
```

If that branch already exists, inspect its relationship to the current commit before using it. Do not delete or overwrite an existing branch.

## Step 4 — Create cohesive commits

Create the following commits in dependency order. The file lists are guidance based on the current workspace. Re-inspect every diff and adjust grouping only when a real dependency requires it. Use `git add -p` for files containing changes from more than one group.

### Commit 1

Message:

`feat(analytics): add semantic labels and shared chart presentation`

Expected scope:

- `backend/app/services/display_formatters.py`
- `backend/app/services/sheet_catalog.py`
- Relevant semantic-display changes in `backend/app/services/decision_intelligence.py`
- `backend/tests/test_decision_intelligence.py`
- `frontend/src/components/charts/DataChart.jsx`
- `frontend/src/components/charts/SafeReactECharts.jsx`
- `frontend/src/components/charts/chartOptions.js`
- `.gitignore`

This commit should establish reusable semantic naming, compact/full value formatting, accessible chart behavior, and the shared ECharts contract used by later commits.

Review the staged diff before committing:

```bash
git diff --cached --check
git diff --cached --stat
git diff --cached
```

### Commit 2

Message:

`feat(reporting): add evidence-backed leadership report`

Expected scope:

- Leadership-report additions in `backend/app/routers/decision_brief.py`
- `backend/app/services/leadership_report.py`
- `backend/tests/test_leadership_report.py`
- `frontend/src/pages/LeadershipReportPage.jsx`
- `frontend/src/styles/leadership-report.scss`
- `frontend/src/utils/reportPresentation.js`
- Any directly required report-only decision-intelligence hunks not included in Commit 1

The report must retain evidence, calculation details, source scope, action guidance, compact numbers with full-value access, and graceful chart failure behavior.

### Commit 3

Message:

`feat(eda): add upload-time EDA and curated data explorer`

Expected scope:

- `backend/app/db/database.py`
- `backend/app/routers/eda.py`
- EDA-specific changes in `backend/app/routers/sheets.py`
- EDA-specific changes in `backend/app/routers/upload.py`
- `backend/app/services/eda/`
- `backend/tests/test_eda_pipeline.py`
- EDA API changes in `frontend/src/api/client.js`
- `frontend/src/components/ingestion/UploadProgressCard.jsx`
- `frontend/src/pages/DataExplorerPage.jsx`
- `frontend/src/pages/IngestionPage.jsx`
- `frontend/src/styles/eda-explorer.scss`

Verify that:

- Raw rows remain immutable and retrievable.
- Curated rows are stored separately.
- Normalization retains source traceability and anomaly information.
- Missing values are not silently converted into real zeroes.
- Cross-sheet joins enforce defensible cardinality and do not multiply records silently.
- EDA failure is reported clearly and does not leave corrupt partial state.
- Upload completion and the progress display reflect the real backend workflow. Do not present timer-driven stages as completed proof when backend completion is unknown.
- EDA runs for the uploaded dataset/sheets in scope and does not unexpectedly recompute unrelated historical datasets.

### Commit 4

Message:

`feat(adaptive-dashboard): add evidence-backed dashboard elements 1 through 5`

Expected scope:

- `backend/app/routers/adaptive_dashboard.py`
- `backend/app/services/adaptive_dashboard/`
- `backend/tests/test_adaptive_dashboard.py`
- `frontend/src/pages/AdaptiveDashboardPage.jsx`
- `frontend/src/styles/adaptive-dashboard.scss`
- `docs/adaptive-dashboard-design.md`
- `docs/gemini-first-tile-refinement-prompt.md`
- `docs/gemini-second-item-prompt.md`
- `docs/gemini-second-item-refinement-prompt.md`
- `docs/gemini-two-element-design-review-prompt.md`

Before committing, verify all five elements use the same source snapshot and preserve approved earlier elements. Element 5 must have real empty, loading, unavailable, partial-data, and success states. Unsupported analysis must be skipped or shown as unavailable rather than invented.

For every number or chart, confirm:

- Metric definition and unit are correct.
- Aggregation grain and denominator are correct.
- Date/time grain is explicit and readable.
- Missing and excluded observations are accounted for.
- Tooltip/details show full values and evidence.
- Labels are readable on desktop and mobile.
- The chart is chosen from data structure and business question, not personal preference or forced variety.
- Any percentile band, benchmark, ranking, or threshold has a computed definition and is not presented as a business target unless a target exists in the source data.

### Commit 5

Message:

`feat(app): wire adaptive reporting and EDA into application navigation`

Expected scope:

- `backend/app/main.py`
- `frontend/src/App.jsx`
- `frontend/src/components/Header.jsx`
- `frontend/src/main.jsx`
- Relevant navigation/layout changes in `frontend/src/styles/refinements.scss`
- Any small integration hunk that cannot logically live in an earlier commit

This commit should register backend routers, expose the new pages, and complete responsive navigation. Confirm that existing routes still open correctly and the mobile navigation does not hide content or controls.

## Step 5 — Verification gates

Run focused backend tests first:

```bash
backend/.venv/bin/python -m pytest \
  backend/tests/test_decision_intelligence.py \
  backend/tests/test_leadership_report.py \
  backend/tests/test_eda_pipeline.py \
  backend/tests/test_adaptive_dashboard.py
```

Then run the complete backend test suite:

```bash
backend/.venv/bin/python -m pytest backend/tests
```

Run frontend verification:

```bash
cd frontend
npm test
npm run build
cd ..
```

Do not treat a successful build as visual acceptance.

Inspect the running application using the real browser at these widths:

- 320 px
- 390 px
- 768 px
- A normal desktop width
- Desktop at 200% zoom

Verify:

- Uploading a representative spreadsheet completes successfully.
- EDA is produced from the uploaded data.
- Raw and curated records can be distinguished and inspected.
- Adaptive Dashboard Elements 1–5 render without duplicate findings.
- Employee count and already approved elements have not regressed.
- Charts use ECharts and do not overflow, clip labels, hide final periods, or overlap navigation/Copilot.
- Details and tooltips expose full values, sample counts, exclusions, periods, and calculation meaning.
- Leadership Report, Reference Overview, voice/orb, Copilot, and presentation creation still work.
- Keyboard focus, close buttons, touch targets, contrast, loading feedback, and error messages remain usable.

If verification exposes a defect, fix it in the commit that owns that behavior. Amend only the new local commits when appropriate. Never rewrite remote/shared history.

## Step 6 — Final repository audit

Run:

```bash
git diff --check
git status --short
git log --oneline --decorate -10
git show --stat --oneline HEAD
```

Also inspect the complete branch diff against its base:

```bash
git diff --stat origin/main...HEAD
git diff --name-status origin/main...HEAD
```

Confirm explicitly that none of the following appear in the branch diff:

- `backend/database.sqlite`
- Other database files or uploaded user data
- `.env` or secrets
- `node_modules/`
- `dist/`
- `__pycache__/` or `*.pyc`
- Generated presentations or temporary artifacts

The final working tree should be clean. If it is not clean, identify every remaining file and explain why it remains uncommitted. Do not silently discard it.

## Step 7 — Push safely

Push only after all required checks pass:

```bash
git push -u origin codex/adaptive-dashboard-eda
```

Do not force-push. Do not merge into `main` as part of this task.

If GitHub CLI is available and authenticated, create a pull request into `main` with a clear summary covering:

- Evidence-backed adaptive dashboard Elements 1–5
- Upload-time EDA and curated/raw data handling
- Leadership reporting and semantic presentation improvements
- Tests and browser widths verified
- Known limitations, if any

If pull-request creation is unavailable, provide the pushed branch name and the GitHub comparison URL so the owner can open it.

## Required final handoff

Report:

1. Branch name and pushed commit hashes.
2. Each commit message with its functional scope.
3. Focused and full backend test results.
4. Frontend test and production-build results.
5. Browser widths and workflows actually verified.
6. Confirmation that runtime databases and uploaded data were excluded.
7. Any unresolved limitation or failure, with the exact affected behavior.
8. Pull-request URL, if created.

Do not claim a test, browser check, push, or pull request succeeded unless you personally ran it and observed the result.
