# Gemini Lead Developer Prompt — Complete Adaptive Dashboard Elements 9 and 10

You are the lead developer working with a senior data scientist, forecasting specialist, software architect, data governance reviewer, product manager, executive UX designer, and accessibility specialist.

Repository:

`/Users/vinayksharma/Developer/pulsehr-ai`

Implement the final two planned Adaptive Dashboard elements:

- **Element 9: Forward outlook**
- **Element 10: Enterprise synthesis**

Implement them sequentially in two controlled phases. Element 8 must already be complete and passing before Phase A starts. Complete and verify Element 9 before beginning Element 10.

After Element 10, stop adding dashboard elements. Run full integration, responsive, audio, Explorer, and regression checks. Present Elements 9 and 10 together for client review. Do not implement Element 11, commit, push, merge, restore deleted files, or clean unrelated work.

---

# Shared safety and architecture rules

## 1. Confirm prerequisites before editing

Run:

```bash
git status --short --branch
git diff --stat
git diff --check
```

Inspect the current contracts, engine, tests, and rendered dashboard. Confirm:

- `AdaptiveDashboardResponse.version == "adaptive-v8"`.
- `exception_element` exists and is typed.
- Element 8 tests pass.
- Elements 1–8 render without a broken state.
- EDA reports used by the dashboard are bound to the current source snapshot.

If Element 8 is absent, incomplete, or still failing tests, stop and report the prerequisite rather than guessing its contract or overwriting active work.

Read:

- `docs/adaptive-dashboard-design.md`
- `docs/gemini-eighth-element-prompt.md`
- `backend/app/services/adaptive_dashboard/contracts.py`
- `backend/app/services/adaptive_dashboard/engine.py`
- `backend/app/services/adaptive_dashboard/briefing.py`
- `backend/app/services/adaptive_dashboard/exceptions.py`
- `backend/app/services/eda/`
- `backend/tests/test_adaptive_dashboard.py`
- `backend/tests/test_eda_pipeline.py`
- `frontend/src/pages/AdaptiveDashboardPage.jsx`
- `frontend/src/components/adaptive/`
- `frontend/src/components/charts/SafeReactECharts.jsx`
- `frontend/src/pages/DataExplorerPage.jsx`
- `frontend/src/styles/adaptive-dashboard.scss`

The branch contains uncommitted work from earlier approved elements. Preserve it. Do not run `git reset`, `git restore`, `git checkout --`, `git clean`, bulk formatting, or broad file replacement.

## 2. Preserve existing behavior

Preserve:

- Elements 1–8 and their source-snapshot integrity.
- Employee count, temporal chart, breakdown, comparator, disparity, Decision focus, Executive briefing/orb, and Exception watch.
- Leadership Report, Reference Overview, Data Explorer, EDA, raw/curated data, Copilot, voiceover, and presentations.
- Existing mobile navigation and responsive behavior.
- ECharts as the only dashboard chart library.
- Glance/explain/inspect disclosure and accessible details.

Element 9 or 10 failure must never remove or invalidate an earlier element.

## 3. Keep modules bounded

Do not continue growing `engine.py` or `AdaptiveDashboardPage.jsx` with large feature implementations.

Create focused backend modules:

- `backend/app/services/adaptive_dashboard/outlook.py`
- `backend/app/services/adaptive_dashboard/enterprise.py`

Create focused frontend components:

- `frontend/src/components/adaptive/ForwardOutlookCard.jsx`
- `frontend/src/components/adaptive/EnterpriseSynthesisCard.jsx`

The engine should orchestrate typed builders, isolate failures, and attach results. The page should pass typed data into focused components and reuse the existing inspection system.

---

# Phase A — Element 9: Forward outlook

## 4. Executive question

Element 9 answers:

> **What may happen next, or how far are we from a verified target, based only on evidence strong enough to support a forward-looking view?**

Use this stable user-facing title:

**Forward outlook**

Element 9 may render one of three strictly distinguished modes:

1. **Target gap** — preferred when an explicit target, plan, quota, SLA, budget, or required threshold is present and semantically verified.
2. **Statistical forecast** — allowed only when a time series has sufficient clean history, stable grain, and acceptable backtest performance.
3. **Outlook unavailable** — when neither a target comparison nor a defensible forecast is supported.

Do not force a forecast for every spreadsheet.

## 5. Target-gap mode

Use a target only when its source and meaning are explicit:

- Target exists as a verified column, sheet, metadata field, user analysis brief, or reviewed configuration.
- Metric, unit, population, period, and grain match the actual measure.
- Target is not inferred from an average, maximum, percentile, historical best, or model output.
- Multiple targets are not silently collapsed.
- A target for one department/store/product is not applied to all entities unless scope states that rule.

Calculate:

- Current actual.
- Target.
- Absolute gap in the metric’s natural unit.
- Relative gap only when meaningful and denominator is positive.
- Period and coverage.

Use correct language:

- `4.2 percentage points below the recorded target`
- `$120K below the monthly plan`
- `3.5 hours above the SLA threshold`

Do not call an inferred statistical range a target.

## 6. Statistical forecast mode

### 6.1 Eligibility

Forecast only when:

- A verified temporal measure and native grain exist.
- Periods are chronological, unique after valid aggregation, and sufficiently regular.
- Missing periods, duplicates, invalid dates, partial periods, and exposure changes are handled explicitly.
- At least 12 complete periods exist for a basic nonseasonal candidate.
- Seasonal models require at least two full cycles; prefer three when practical. Examples: at least 24 monthly observations for annual seasonality and at least 104 weekly observations for yearly weekly seasonality.
- Forecast horizon is short and proportionate: normally 1–3 periods and never more than 10% of usable history without a reviewed reason.
- Structural breaks or definition changes do not invalidate the training history.
- The measure is suitable for aggregation and future interpretation.

Do not forecast:

- Employee-level attendance, performance, attrition, health, or protected outcomes.
- IDs, categorical codes, one-time snapshots, cumulative totals without transformation, or mixed-grain series.
- A partial latest period as though it were complete.
- A series dominated by missingness, unrecorded exposure, or incompatible currency.

### 6.2 Candidate models

Use a small transparent model registry appropriate to the available data. Candidates may include:

- Last-observation naïve.
- Seasonal naïve when a verified seasonal period exists.
- Drift/trend naïve.
- Simple exponential smoothing.
- Holt trend.
- Holt-Winters only with adequate repeated seasonality.

Reuse a tested existing forecasting service only if its assumptions, grain, leakage controls, and evaluation satisfy this specification. Do not reuse generated presentation narratives as forecast evidence.

Avoid introducing a large ML stack. If a mature lightweight open-source statistical dependency is required, justify it, pin it, and keep a deterministic fallback. Do not download remote models or call external forecasting services.

### 6.3 Rolling-origin validation

Select a forecast only after backtesting:

- Use chronological rolling-origin or expanding-window validation.
- Never shuffle temporal data.
- Keep preprocessing inside each training fold to avoid leakage.
- Compare every candidate against the relevant naïve baseline.
- Use MAE and WAPE or another zero-safe metric. Do not rely on MAPE when actuals can be zero.
- Record fold count, training observations, test observations, and per-model metrics.
- Publish the selected forecast only when it performs at least as well as the naïve baseline within a documented tolerance and has no invalid output.
- If no model passes, return outlook unavailable rather than publishing the least-bad model.

Do not show a fabricated `accuracy` or `confidence` percentage.

### 6.4 Forecast range

- Show a forecast range only when it is computed from a documented residual or probabilistic method.
- Label it `forecast range`, not `guaranteed range`.
- If using empirical residual quantiles or bootstrap residuals, say so in details.
- Range must widen or remain stable with horizon unless the method justifies otherwise.
- Clamp only when the measure has a real physical/logical bound, e.g. a nonnegative count or 0–100 percentage. Record the clamp.
- Do not present the range as a business target or SLA.

### 6.5 Forecast wording

Allowed:

- `The selected model estimates $1.8M next week, with an empirical forecast range of $1.4M–$2.2M.`
- `The recorded target is 92%; the current complete period is 88.4%, a gap of 3.6 percentage points.`
- `The available history did not outperform a seasonal-naïve baseline, so no forecast is shown.`

Prohibited:

- `Sales will be $1.8M.`
- `We are 95% confident.` without a valid interval definition.
- `AI predicts employee performance will decline.`
- `The target should be 92%.` when no target exists.

## 7. Element 9 contracts

Use strict Pydantic contracts with `extra="forbid"`. Suggested structure:

```text
OutlookPoint
  period
  period_label
  actual_value
  forecast_value
  lower_bound
  upper_bound
  is_partial

ModelValidationResult
  model_id
  model_label
  fold_count
  mae
  wape
  baseline_mae
  baseline_wape
  passed
  rejection_reason

ForwardOutlookSpec
  component_id = "outlook_element"
  kind: target_gap | statistical_forecast | outlook_unavailable
  business_concept
  title
  metric_name
  unit
  temporal_grain
  horizon
  actual_value
  target_value
  gap_value
  forecast_value
  lower_bound
  upper_bound
  model_id
  validation
  points
  next_review_period
  why_available_or_unavailable
  glance
  explain
  inspect
  evidence
  caption
```

Fields that do not apply to the active mode should be optional and validated consistently. Reject impossible combinations, such as `statistical_forecast` without forecast points or `target_gap` without an explicit target source.

Add `outlook_element: ForwardOutlookSpec | None` and update response version to `adaptive-v9` after Phase A.

Every displayed value must use the current manifest snapshot and a deterministic calculation/model version.

## 8. Element 9 minimal UX

Create `ForwardOutlookCard.jsx`. Place it after Element 8 during review.

### Target-gap card

- Title: `Forward outlook`.
- Plain mode label: `Recorded target comparison`.
- Current actual, target, and gap.
- Source and target period.
- One concise next review statement.
- No forecast line when this is only a target comparison.

### Forecast card

- Title and short context.
- Next-period estimate as the leading value.
- Forecast range.
- One ECharts line showing historical actuals, a visible forecast boundary, dashed forecast, and restrained range band.
- Actual and forecast must remain visually distinguishable by line style and labels, not color alone.
- No smoothed curve.
- Missing periods remain gaps.
- Partial latest period is marked and excluded or normalized according to the model policy.
- Tooltip shows full value, period, actual/forecast state, range, and status.
- Axis titles and units remain visible.

### Unavailable mode

Render a compact constructive card only when it helps the user understand what evidence is missing. Example:

`A forward outlook needs at least 12 complete monthly periods; this source contains 7.`

Do not display a broken chart or generic `No data` message.

### Accessibility and responsiveness

- Use ECharts only.
- Provide accessible table/details for forecast points.
- Do not rely on hover.
- Test at 320, 390, 768, desktop, and 200% zoom.
- Forecast labels, range, final period, and axis title must not clip.
- Card must not overlap Copilot or bottom navigation.

## 9. Element 9 tests and checkpoint

Add tests for:

1. Explicit target with compatible metric/unit/grain.
2. Target scope mismatch rejection.
3. Target zero and unknown target handling.
4. Monthly forecast with adequate history.
5. Weekly seasonal forecast requiring adequate cycles.
6. Insufficient history abstention.
7. Missing and duplicate periods.
8. Partial latest period.
9. Structural definition change rejection.
10. Zero-safe WAPE/MAE calculations.
11. Rolling-origin order and no leakage.
12. Candidate model loses to naïve baseline and is withheld.
13. Candidate model passes and exposes validation evidence.
14. Negative forecast prevented only for a nonnegative metric with clamp recorded.
15. Percentage bounds.
16. Mixed currency rejection.
17. Individual/protected-outcome forecast rejection.
18. Element 9 failure preserves Elements 1–8.
19. `adaptive-v9` contract and extra-field rejection.

Run:

```bash
backend/.venv/bin/python -m pytest backend/tests/test_adaptive_dashboard.py
backend/.venv/bin/python -m pytest backend/tests
cd frontend && npm test && npm run build
```

Inspect the real rendered target-gap, forecast, and unavailable modes before Phase B. Fix any Element 9 defects before continuing.

---

# Phase B — Element 10: Enterprise synthesis

## 10. Executive question

Element 10 answers:

> **What do the safely connected sources collectively establish, and where can leadership inspect the linked evidence?**

Use this stable title:

**Enterprise synthesis**

This final element should summarize one verified cross-source insight, not combine every uploaded sheet into a single noisy report.

It must distinguish:

- Separate sources that are merely available.
- Sources that share a verified entity/time key.
- Sources that can be reconciled into a lifecycle metric.
- Sources that support only an association.
- Sources that cannot be connected safely.

Never broaden a selected dataset to all historical uploads. Default scope is the selected sheet’s `dataset_id` and its sibling sheets from the same upload. Cross-dataset synthesis requires an explicit user-selected scope that does not currently exist; do not invent it.

## 11. Cross-source recipe registry

Choose one eligible recipe in this order.

### Recipe A — Reconciled lifecycle metric

Preferred when records can be connected through distinct entities and stages:

- Ecommerce: delivered orders ↔ accepted returns.
- Marketing/sales: qualified leads ↔ opportunities ↔ won deals.
- Support: tickets ↔ resolution events ↔ satisfaction responses.
- Workforce learning: employees ↔ training completion.

Requirements:

- Verified join key.
- Declared cardinality.
- Numerator entities are a subset of eligible denominator entities when required.
- Duplicate events do not multiply entities.
- Time/as-of relationship is defined.
- Coverage and unmatched keys are reported.

### Recipe B — Matched cohort comparison

Use when two sources provide different measures for the same safely matched entities or groups.

- Aggregate to a defensible privacy-safe grain before display.
- Compare like-for-like populations.
- Require adequate matched sample and report unmatched coverage.
- Do not expose personal rows.

### Recipe C — Cross-source association

Use only when:

- Join is 1:1 or safely aggregated N:1/1:N.
- Many-to-many multiplication is rejected.
- Paired sample is at least 30, with a stricter threshold when screening many pairs.
- Both variables have nonzero variance.
- Missingness and match coverage are disclosed.
- Pearson and Spearman directions agree.
- Sensitivity to extreme points is checked.
- Metric semantics make the relationship meaningful.

Present correlation as association, never cause.

### Recipe D — Aligned temporal co-movement

Raw trending series often correlate spuriously. Therefore:

- Align periods and units exactly.
- Require adequate overlapping periods.
- Do not correlate raw levels when both series have strong trends or seasonality.
- Use changes, detrended residuals, or comparable seasonal deviations when justified.
- Report the transformation and lost periods.
- Withhold the finding when results are unstable across reasonable transformations.

### Recipe E — Coverage-only synthesis

If multiple sources exist but no analytical join passes:

- Show which sources were evaluated.
- State that no safe combined metric was produced.
- Identify the specific missing key, grain, or definition needed.
- Provide links to inspect each source separately.

This is preferable to a fabricated enterprise conclusion.

## 12. Multi-source manifest and integrity

Create a typed enterprise manifest or equivalent containing:

- Selected `dataset_id`.
- Ordered included sheet IDs and display names.
- Per-sheet content snapshots.
- Combined deterministic snapshot derived from ordered source identities and snapshots.
- Join keys and cardinalities.
- Row/entity counts before and after matching.
- Matched and unmatched counts.
- Time alignment/as-of policy.
- Calculation and recipe versions.

The combined snapshot must change when any included source value, schema, definition, or scope changes. A content hash is an identity record, not proof of correctness or authorization.

Reject:

- Stale EDA/derived tables.
- Snapshotless cross-source evidence.
- Unsafe N:N joins.
- Duplicate normalized keys that violate declared cardinality.
- Mismatched date grains.
- Mixed currencies without verified conversion.
- Joins based only on similar-looking labels with insufficient overlap.
- Cross-dataset data not explicitly selected.

## 13. Element 10 contracts

Suggested strict contracts:

```text
EnterpriseSourceRef
  sheet_id
  display_name
  snapshot
  entity_count
  period
  role

CrossSourceEvidence
  finding_id
  recipe_id
  title
  observation
  interpretation
  metric_names
  values
  units
  paired_or_eligible_count
  matched_count
  unmatched_count
  coverage_ratio
  join_description
  calculation_id
  source_sheet_ids
  snapshot

EnterpriseVisualSpec
  kind: scatter | paired_dot | lifecycle_flow | none
  x_axis_title
  y_axis_title
  points
  reference_line

EnterpriseSynthesisSpec
  component_id = "enterprise_element"
  kind: reconciled_metric | matched_comparison | cross_source_association | temporal_comovement | coverage_only
  business_concept
  title
  sources
  source_count
  lead_finding
  visual
  what_it_establishes
  what_it_does_not_establish
  next_check
  drilldown_targets
  glance
  explain
  inspect
  evidence
  caption
```

Use `extra="forbid"`, typed enums, bounded lists, finite numbers, and cross-field validators.

Add `enterprise_element: EnterpriseSynthesisSpec | None` and update response version to `adaptive-v10`.

If the selected dataset contains only one sheet, return `None` or a concise coverage-only state. Do not reuse the Executive briefing as fake enterprise synthesis.

## 14. Element 10 minimal UX

Create `EnterpriseSynthesisCard.jsx`. Place it after Element 9 as the final dashboard element during review.

Default card:

1. Eyebrow/title: `Enterprise synthesis`.
2. A small source-scope line: e.g. `3 safely evaluated sources · 2 connected`.
3. One cross-source headline.
4. One compact evidence line: metric values, matched sample, and coverage.
5. `What this establishes`.
6. `What this does not establish`.
7. One safe next check.
8. Links to each supporting source/derived table in Data Explorer.
9. Standard information control with full join, snapshot, exclusions, and calculation audit.

### Visual choice

Use a visual only when it makes the relationship materially clearer:

- Association: ECharts scatter plot with privacy-safe aggregated points and an optional descriptive fitted line.
- Matched comparison: paired dot plot.
- Lifecycle metric: simple ECharts flow/funnel only when stages and populations reconcile; otherwise use a compact textual ratio.
- Coverage-only: no chart.

Do not create a network-spaghetti diagram, 3D chart, dashboard-within-dashboard, or collection of mini charts.

### Visual integrity

- Axis titles include metric names and units.
- Scatter points do not expose record-level PII.
- Jitter is visual only and must not alter tooltip values.
- Trend line is labelled descriptive, not causal or predictive.
- Full values, paired sample, match coverage, and source names are available in details.
- Long source names wrap safely.
- Mobile may use a text-first card and collapsible visual/details when space is insufficient.

### Drill-through

Use stable Data Explorer links for:

- Each source sheet.
- The relevant derived table when one was safely materialized.
- Cross-correlation/EDA view when applicable.

Do not put personal identifiers or raw join keys in URLs.

## 15. Element 10 examples

These teach expected reasoning and must not be hard-coded.

### Workforce and learning

`Training completion and attendance reliability differ together across 42 matched departments (Spearman ρ = 0.48). This is a moderate association, not evidence that training changes attendance. Compare department size, role mix, and reporting periods before planning an intervention.`

### Marketing and sales

`Campaign-attributed qualified leads reconcile to 1,284 opportunities, of which 216 reached verified won status. The matched lead-to-win rate is 16.8% across 82% of eligible campaign leads. Unmatched leads remain excluded.`

### Ecommerce orders and returns

`Electronics records 184 accepted returns among 1,240 eligible delivered orders, a return rate of 14.8%. The calculation uses distinct order IDs and excludes unmatched return records.`

### Support and satisfaction

`Resolution time and satisfaction are negatively associated across 3,420 matched tickets. This does not prove that response time alone determines satisfaction.`

### No safe connection

`Three sources were evaluated, but no verified entity or period key supports a combined metric. Review Customer ID consistency between Orders and Returns to enable lifecycle analysis.`

## 16. Element 10 tests

Add tests for:

1. Same-dataset sibling sheet scope only.
2. Combined snapshot changes when any source changes.
3. Safe 1:1 join.
4. Safe N:1 aggregation with explicit grain.
5. N:N rejection.
6. Duplicate-key/cardinality violation.
7. Matched and unmatched reconciliation.
8. Ecommerce distinct delivered-order return rate.
9. Marketing lead-to-win lifecycle rate without event-row multiplication.
10. Workforce-learning matched cohort comparison with privacy-safe aggregation.
11. Cross-source correlation sample/variance/direction/sensitivity guards.
12. Trending time-series spurious correlation withheld or detrended.
13. Mixed currency rejection.
14. Mismatched periods/as-of policy rejection.
15. Stale or snapshotless EDA/derived table rejection.
16. Single-sheet coverage-only/abstention behavior.
17. Unknown or unsafe join labels do not become verified keys.
18. Element 10 failure preserves Elements 1–9.
19. `adaptive-v10` contract and extra-field rejection.
20. No row-level PII in the response or chart points.

Run:

```bash
backend/.venv/bin/python -m pytest backend/tests/test_adaptive_dashboard.py backend/tests/test_eda_pipeline.py
backend/.venv/bin/python -m pytest backend/tests
cd frontend && npm test && npm run build
```

---

# Final integrated acceptance after Element 10

## 17. Dashboard-wide review

Do not stop after isolated unit tests. Test the complete Adaptive Dashboard with representative:

- Workforce/attendance data.
- Retail weekly sales data.
- Ecommerce funnel/orders/returns data when fixtures exist.
- General tabular data with unknown polarity.
- Multi-sheet dataset with one safe relationship.
- Multi-sheet dataset with no safe relationship.

Inspect at:

- 320 px.
- 390 px.
- 768 px.
- Normal desktop width.
- Desktop at 200% zoom.

Verify:

- Elements 1–10 appear only when supported.
- The page does not feel like ten equally loud cards. Visual hierarchy guides the user from state → explanation → decision → briefing → exception → outlook → enterprise context.
- No duplicate headline or finding appears in multiple default cards without adding a distinct purpose.
- All numbers use compact display and full-value disclosure appropriately.
- Dates, units, denominators, samples, partial periods, and source scopes are clear.
- No raw underscores or truncated distinguishing labels remain.
- ECharts is the only dashboard chart library.
- No chart is forced where text is clearer.
- Loading, partial, unavailable, stale, and error states preserve valid earlier elements.
- Voice/orb playback still works and does not overlap controls.
- Copilot, bottom navigation, modal close buttons, and presentation actions remain usable.
- Explorer drill-through opens the correct source and view.
- Keyboard, touch, focus restoration, reduced motion, transcript, and chart-details access work.
- No PII or untrusted HTML enters narration, tooltips, URLs, or chart labels unsafely.

## 18. Performance and request integrity

- Measure dashboard API latency and frontend render time on representative datasets.
- Avoid recalculating expensive EDA, forecasting, or enterprise joins repeatedly during a single request.
- Reuse validated intermediate artifacts within the same immutable snapshot.
- Cache only with explicit source/definition/model version dependencies.
- Source changes invalidate forecast and enterprise results.
- Late results from an old sheet selection cannot replace the active dashboard.
- A failure in Elements 8–10 does not make the entire API return 500 when Elements 1–7 remain valid.

Do not claim a performance target unless it was measured and agreed.

## 19. Update the design contract

Append two sections to `docs/adaptive-dashboard-design.md`:

### Revision 11: Element 9 — Forward Outlook

Document:

- Target-gap versus forecast distinction.
- Eligibility and abstention.
- Candidate models and rolling-origin validation.
- Naïve baseline comparison.
- Forecast-range meaning.
- Protected/individual prediction prohibition.
- Minimal visual and responsive acceptance.
- Status: awaiting client approval.

### Revision 12: Element 10 — Enterprise Synthesis

Document:

- Same-dataset source scope.
- Multi-source manifest.
- Join/cardinality/time policies.
- Lifecycle, matched comparison, association, temporal, and coverage-only recipes.
- Non-causal wording and PII protection.
- Minimal card, ECharts options, and drill-through.
- Final integrated acceptance.
- Status: awaiting client approval.

Do not rewrite historical revisions or mark Elements 9/10 approved.

## 20. Required final handoff and stop condition

Report Element 9:

1. Active mode: target gap, forecast, or unavailable.
2. Exact metric, grain, history, horizon, actual/target/forecast, and range.
3. Candidate models and chronological backtest results.
4. Naïve baseline and why the result was published or withheld.
5. Partial/missing period handling.

Report Element 10:

1. Included sources and combined snapshot.
2. Join keys, cardinality, before/after/matched/unmatched counts, and coverage.
3. Selected recipe and exact cross-source calculation.
4. What the finding establishes and does not establish.
5. Drill-through destinations.

Report overall:

1. Files changed.
2. Focused and full backend test results.
3. Frontend test/build results.
4. Browser sizes, audio, charts, unavailable states, and drill-through actually inspected.
5. Measured performance information.
6. Any unresolved limitation or abstention.

Then ask:

> Are the Forward outlook and Enterprise synthesis useful, trustworthy, and clear enough to approve the completed ten-element dashboard?

Stop. Do not implement Element 11, commit, push, merge, or clean unrelated files.
