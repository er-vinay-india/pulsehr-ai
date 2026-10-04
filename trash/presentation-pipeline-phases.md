# Presentation pipeline repair: implementation and verification

The supplied `WFO_July_2026_Review.pptx` is a reference for a clear HR attendance
story. Its figures are not source data and are never injected into generated
reports. The underlying attendance workbook was not supplied. The repairs use
recorded source cells and synthetic fixtures to verify the reporting behavior.

## Phase 1 — recovery and planner grounding

Commit `662242b`.

Interrupted jobs can resume automatically after reload using their original scope
and job ID. Worker ownership and bounded recovery prevent duplicate processing.
The planner receives actual values, units, periods, denominators and limitations,
instead of a list of evidence titles or a preset commercial thesis. Zero values
are retained. Focused verification: 45 tests passed.

## Phase 2 — attendance report contract

Commit `9c58a45`.

Recognizable attendance data takes a deterministic business-report path before
generic narrative generation. The report covers recorded attendance, separate
leave totals, weekly averages, departments, attendance bands, source exceptions,
arithmetic checks and next actions. Missing values are excluded from averages;
duplicate/missing IDs and ambiguous months withhold employee rollups. Source
figures are not converted into an inferred WFO requirement or working-day rate.
Focused verification: 37 tests passed.

## Phase 3 — presenter language and internal traceability

Commit `e25bf38`.

Technical appendices are encapsulated in the internal deck record. The ordinary
presentation and its speaker notes use business language. Evidence IDs, snapshot
hashes, SQL calculations and model details remain available internally. Canonical
visual specifications are rebuilt after language changes. Focused verification:
58 tests passed, including decision-brief immutability checks.

## Phase 4 — visual binding

Commit `c8848e3`.

A chart must match the cited measure, unit and period. Slide position or chart
family alone cannot select a visual. Metric cards use measured evidence; preset
resilience claims, improvement percentages and invented milestones are hidden.
Category counts retain count units rather than being mislabeled percentages.
Focused verification: 43 tests passed.

## Phase 5 — content validation and release gates

Commit `8aa5a8d`.

Business-report content has an internal integrity contract. Calculations are
recomputed from retained inputs and chart values are checked against their bound
facts. Unsupported claims or unanswered questions invalidate planning. Car
records cannot establish footfall, margins, seasonality or ROI merely because an
objective requests them. Invalid plans use a source-grounded review of the
available measures. Equal numbers in unrelated evidence cannot verify a claim;
data completeness does not establish system resilience. Focused verification:
68 tests passed.

## Phase 6 — job, browser and export parity

The final phase retains the verified report order, checks presenter-note
integrity at export, supports both/PDF-only delivery, and makes the PDF include
the report's bullets, metrics, charts and tables using central slide tokens.
PowerPoint charts and tables remain editable. Axis IDs use unsigned OOXML values;
chart titles, labels and legends use theme text colors. Count axes use whole
units and day measurements use readable decimals. The preview and PPTX renderer
hide invented default priority cards. Table cells wrap and the footer uses a
business source label. Invalid requested sources fail rather than substituting
another sheet. Leave comparison requires a unique identity match; missing values
and duplicate IDs cannot produce fabricated matching totals.

Final verification:

- 255 presentation/decision-deck regression tests passed. Two live speech-service
  tests were excluded after network access to the service failed; actual external
  voice synthesis remains unverified.
- An uploaded attendance fixture completed the real job pipeline, reached
  `ready`, and persisted verified PPTX and PDF output.
- Native export tests check editable chart values, tables, notes, central colors,
  unsigned axis IDs and rejection of modified verified content.
- `npm run test:deck` passed navigation, reset, cancellation, recovery and
  business-content checks in both themes.
- `npm run test:slides` passed 5,400 contrast checks across ten palettes and eleven
  layouts. The palettes are unchanged.
- The frontend production build passed, with existing Sass/chunk-size warnings.
- Eight-slide synthetic attendance exports were rendered and inspected in both
  light and dark themes. They are QA fixtures, not the user's July results.

The PDF renderer uses labeled horizontal bars for legibility; PPTX retains the
selected editable chart family. Neither file invents values when inputs are
missing. Source identity, scope and policy limitations still need review with
the actual attendance workbook. Natural-language semantic checks are bounded
checks, not a proof that arbitrary older model-generated prose is correct.

Publication is pending: automatic approval review rejected the first push because
`main` also contains the older HRIDAY commit `b2fb858`. Approval to publish that
additional commit has been requested. Unrelated working-tree chatbot changes are
excluded from every presentation phase commit.
