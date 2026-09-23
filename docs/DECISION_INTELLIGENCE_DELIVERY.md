# Domain-adaptive decision overview

## Implemented in this change

The Executive Overview now opens with a decision brief, preserving existing models/charts in an expandable section. No files or datasets were restored or deleted by this change.

New read-only endpoints:
- GET /api/analytics/decision-brief?sheet_id=…
- POST /api/analytics/decision-brief/prioritize (sheet_id and snapshot)

Raw uploaded rows remain in the existing sheet catalogue. Derived field roles, comparisons, periods and findings are computed from the selected source rows without modifying them. Workspace analysis keeps sheets separate rather than assuming joins. Content fingerprints identify the source snapshot.

The new engine supports domain hints for people operations, sales, marketing, IT and general operations. It excludes identity columns and binary flags from numeric performance metrics, preserves unknown values, discloses repeated IDs, and labels aggregates as record-level rather than unique-employee or exposure-adjusted KPIs.

Supported analyses:
- Group means/medians and gaps against the selected sheet's record mean; all groups remain inspectable.
- Month-level means from unambiguous ISO dates, with valid observation counts and partial-window caveats.
- Calendar-header rollups for recognized people-operation sheets, retaining month/year and excluding incomplete or invalid period rows. Missing years remain unspecified.
- Pairwise Spearman rank correlations with at least 12 paired observations, constant-column guards, and checks for likely accounting relationships.
- Within-group correlation sign reversal warnings when at least two eligible groups reverse the pooled relationship. This is exploratory evidence, not causality or statistical significance.
- Missing-data findings, source coverage, field-role inspection, and explicit unsupported-analysis states.

Local AI can reorder the verified findings. Its output is restricted to a permutation of existing finding IDs; it cannot change calculations, invent claims, or execute generated code. Model failure preserves the statistical brief. No new model, external plugin, paid service, or dependency was installed. Pandas/NumPy and the configured Ollama model were reused. Method reference: https://pandas.pydata.org/pandas-docs/stable/generated/pandas.DataFrame.corr.html

## User experience

Each result includes observation, implication, proposed action, proposed owner role and expandable evidence. The dashboard includes source/metric selectors, group comparisons, monthly values and a selectable relationship matrix. Findings are diversified by source and identical repeated-upload headlines are collapsed without merging source data.

“Present brief” opens a keyboard-navigable dashboard presentation of the same findings. “Export briefing” downloads self-contained, escaped HTML with charts, source references and a boundaries appendix; it can be viewed offline or printed. Evidence JSON can also be downloaded. The presentation studio now defaults to a decision-brief format built from the same scoped findings and snapshot. It uses the existing native PowerPoint export pipeline with editable charts. The detailed legacy presentation remains selectable. Verified decision text is fixed in the studio; themes and slide ordering remain editable. Presenter notes can be supplied during setup.

## Validation

- Full backend suite passed: 173 tests at the presentation integration checkpoint, including 16 decision-engine tests and 8 decision-deck tests.
- Production frontend build and all eight existing Markdown/math rendering suites passed.
- Export escaping checked against script-like source text.
- Browser checks covered mobile/desktop overview, real current data, presentation mode and its evidence values.

## Deliberate limits

This is a descriptive analytical foundation, not a claim that arbitrary spreadsheets have automatically resolved business definitions. Domain/field hints are heuristic. Ambiguous dates, unexplained formulas, rates without denominators, effective entity grain and causal explanations still require valid mappings or additional evidence. There is no new universal cross-sheet joining engine or forecasting model here. Analytics are bounded to 24 measures, three eligible grouping dimensions, and eight source measures in the relationship matrix, with limits disclosed. AI prioritization is optional and does not replace statistical validation. The original copilot remains a separate integration. The decision-deck mode projects the same overview evidence into the existing PPTX engine; the detailed legacy mode still uses its earlier analytical pipeline.

## Presentation integration follow-through

- A `decision_brief` presentation mode uses exact preflight sheet IDs and preserves the overview snapshot/finding IDs.
- Chart groups are paginated rather than silently truncated; labels have full-name mappings in speaker notes. Coverage pages are marked as appendix content.
- Frozen per-slide claim contracts cover titles, subtitles, narrative, bullets, metrics, charts, tables, sources, speaker notes and narration. Changed claims fail verification and PowerPoint export. Layout repairs are rechecked before publication.
- Integration tests cover overview/deck parity, changed signs and text, actual native chart values, and successful background job persistence.
- Fixed presentation UI status normalization (`PASSED` versus `passed`), numeric discrepancy counts, zero-coverage display, and scope row totals.
- A live workspace decision deck was generated successfully in the presentation studio. Automated tests inspect the exported native PPTX structure and chart values; no claim is made that it was opened in Microsoft PowerPoint.

---

## Decision Engine & Layered Architecture Updates (September 2026)

### 1. Pluggable DecisionEngine (`backend/app/services/decision_engine/`)
The decision evaluation layer now supports pluggable classification via an abstract `DecisionEngine` interface:
- **`RuleDecisionEngine` (`rule_engine.py`)**: High-speed compiled regex patterns and semantic parsers that classify ordinary business questions into structured `DecisionResult` objects in **<1ms** with `confidence >= 0.90`. It recognizes:
  - Positives / highlights ("give me 3 good points") -> `summary_positives`
  - Critical problems / headwinds ("main problems") -> `summary_concerns`
  - Action planning ("what should we do?") -> `summary_actions`
  - Evaluative rankings ("which department is worst?") -> `ranking_lowest` (polarity-aware)
  - Causal / correlation inquiries ("does X cause Y?") -> `correlation` (routes to `ANALYST`)
  - Underlying explanations ("why did that happen?") -> `followup_why`
- **`EmbeddingDecisionEngine` (`embedding_engine.py`)**: Vector similarity classification using local `nomic-embed-text:latest` prototypes with cosine similarity scoring, automatically falling back to `RuleDecisionEngine` if Ollama is offline or embeddings are unavailable.
- **Factory Resolution (`factory.py`)**: Controlled dynamically via `DECISION_ENGINE=rules|embedding` (defaults to `"rules"`).

### 2. Elimination of Blocking LLM Calls in Prioritization
- Previously, `/api/analytics/decision-brief/prioritize` triggered a 25-second synchronous Ollama call just to assign visual types and icons.
- Replaced with [`assign_deterministic_visuals`](file:///Users/vinayksharma/Developer/pulsehr-ai/backend/app/routers/decision_brief.py#L17-L61), which inspects finding kind, metric names, and observation semantics in **<1ms**:
  - `movement` -> `area_trend`, `icon: trending-up`
  - `association` -> `heatmap`, `icon: zap`
  - `comparison` -> `comparison_bar` (or `donut` for distributions, `gauge` for 0-100 scores)
  - Semantics -> `icon: users` (workforce), `icon: dollar-sign` (commercial), `icon: alert-triangle` (risks/reversals), `icon: award` (leaders).

### 3. Structured Cryptographic Fact Registry (`backend/app/services/insight_registry.py`)
- Findings are registered under dataset SHA-256 snapshot hashes with stable, verifiable identifiers (`FACT-001`, `FACT-002`, ...).
- Implements an in-memory brief cache keyed by sheet scope and content digest, reducing repeat overview and brief page renders to **<1ms**.

