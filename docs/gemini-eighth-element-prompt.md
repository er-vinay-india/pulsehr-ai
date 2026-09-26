# Gemini Lead Developer Prompt — Adaptive Dashboard Element 8: Exception Watch

You are the lead developer working with a senior data scientist, statistical reviewer, software architect, product manager, executive UX designer, and accessibility specialist.

Repository:

`/Users/vinayksharma/Developer/pulsehr-ai`

Implement **only Element 8** on the existing Adaptive Dashboard at `#adaptive`.

Elements 1–7 are complete. Preserve them and all other application pages. Present Element 8 for client review and stop. Do not implement Element 9, commit, push, merge, restore deleted files, or clean unrelated work.

## 1. Element 8 purpose

The dashboard already explains the headline, trend, composition, comparisons, disparity, decision priority, and executive briefing. The next missing question is:

> **What unusual period, segment, or observation pattern may be easy to miss and deserves inspection?**

Build one compact, statistically defensible **Exception watch** element.

It must identify one lead exception from the currently selected source, show why it is unusual relative to a valid observed baseline, and link the user to supporting detail. It may retain up to two additional eligible exceptions in its inspection details, but the default card must remain focused on one.

This is not an alarm system, performance rating, error detector, or causal diagnosis. A statistical exception means “unusual relative to comparable observations.” It does not automatically mean bad, wrong, fraudulent, or actionable.

## 2. Inspect and preserve the current implementation

Before editing:

```bash
git status --short --branch
git diff --stat
git diff --check
```

Read:

- `docs/adaptive-dashboard-design.md`
- `docs/gemini-sixth-element-prompt.md`
- `docs/gemini-seventh-element-prompt.md`
- `backend/app/services/adaptive_dashboard/contracts.py`
- `backend/app/services/adaptive_dashboard/engine.py`
- `backend/app/services/adaptive_dashboard/briefing.py`
- `backend/app/services/eda/normalizer.py`
- `backend/app/services/eda/report_generator.py`
- `backend/app/services/eda/engine.py`
- `backend/tests/test_adaptive_dashboard.py`
- `backend/tests/test_eda_pipeline.py`
- `frontend/src/pages/AdaptiveDashboardPage.jsx`
- `frontend/src/components/adaptive/ExecutiveBriefingCard.jsx`
- `frontend/src/components/charts/SafeReactECharts.jsx`
- `frontend/src/pages/DataExplorerPage.jsx`
- `frontend/src/styles/adaptive-dashboard.scss`

The branch contains other contributors’ uncommitted Element 6 and Element 7 work. Do not discard, stage, restore, or rewrite it. Do not run `git reset`, `git restore`, `git checkout --`, `git clean`, or broad formatting across unrelated files.

Preserve:

- All calculations and layouts in Elements 1–7.
- The Executive briefing and orb animation.
- Leadership Report, Reference Overview, EDA Explorer, raw/curated records, Copilot, voiceover, and presentations.
- The minimal dashboard language and glance/explain/inspect disclosure model.
- ECharts as the only dashboard chart library.

## 3. User-facing definition

Use this stable title:

**Exception watch**

The default card should show:

1. A short headline naming the unusual period or business segment.
2. The observed value.
3. A clearly labelled **typical observed range** or comparable baseline.
4. The size and direction of the deviation in the metric’s natural unit.
5. The sample or period coverage used.
6. One sentence explaining why inspection is useful without declaring a cause.
7. One link/button: `Inspect supporting data`.
8. One information control containing calculation, method, eligible population, excluded observations, comparison basis, source, snapshot, limitations, and additional eligible exceptions.

When the exception is temporal or categorical and a visual materially improves understanding, show one small ECharts visual:

- **Temporal exception**: an unsmoothed line with the typical observed range and one marked exceptional period.
- **Segment exception**: a horizontal dot plot showing comparable segments, the robust center/range, and the selected segment.
- **No valid geometry**: use the textual card without forcing a chart.

Do not use a bar chart, gauge, speedometer, donut, traffic light, pulsing warning icon, or decorative risk score.

## 4. Examples that teach the intended reasoning

These examples are instructional. Never hard-code their numbers or labels.

### Workforce

`Unusual attendance interval in December 2024`

`7h 12m average · typical observed range 7h 44m–8h 18m · 32m below range · 96 valid records`

`This period differs from comparable attendance intervals. Review source completeness, calendar effects, and scheduling records before interpreting the difference.`

Do not identify an individual employee as an exception. Do not call a department’s attendance a performance failure.

### Retail

`Unusual sales week: W47 ’11`

`$2.4M per store · typical seasonal range $1.2M–$1.8M · Holiday flag recorded`

`The week is unusually high relative to comparable retail weeks. The recorded holiday context should be reviewed before treating it as an operational anomaly.`

A holiday peak can be a valid business event. Do not label it bad or exclude it automatically.

### Ecommerce

`Return-rate exception in Electronics`

`14.8% · typical category range 3.2%–8.6% · 1,240 delivered orders`

The rate is valid only when returned distinct order IDs are divided by eligible delivered distinct order IDs at the same grain. Return rows divided by order lines is prohibited.

### Sales or marketing

`Conversion-rate exception in Enterprise`

`8.2% · typical comparable-segment range 10.9%–15.4% · 317 qualified leads`

Do not compare raw conversion counts when segment denominators differ. Do not attribute the result to campaign quality unless attribution and relevant context exist.

### Support or operations

`Unusual backlog-age concentration`

`46 unresolved tickets older than 7 days · typical weekly range 12–28`

Do not call this an SLA breach without a defined SLA, valid clock, pause rules, and eligibility.

### General tabular data

Use neutral language: `unusual`, `outside the typical observed range`, or `differs from comparable observations`. Do not use `bad`, `failing`, `fraudulent`, `critical`, `high risk`, `best`, or `worst` when meaning and polarity are not verified.

## 5. Statistical analysis policy

### 5.1 EDA output is screening evidence, not final business evidence

The current EDA normalizer detects column-level IQR outliers. That is useful for screening but insufficient by itself for Element 8 because it can:

- Flag identifiers or semantically irrelevant measures.
- Ignore time grain and seasonality.
- Treat a valid holiday peak as an error.
- Mix incomparable populations.
- Use a report that may not be bound to the current source snapshot.
- Return only a truncated sample of flagged rows.

Do not directly copy `recommendations` or `column_diagnostics[*].outliers` into the dashboard.

Use EDA diagnostics to nominate candidates. Recalculate and validate the winning exception deterministically from the current selected source and manifest snapshot.

### 5.2 Eligible measures

A measure is eligible only when:

- It is a verified numeric business measure, rate, duration, count, or currency.
- It is not an ID, row number, postal code, phone number, timestamp encoding, latitude/longitude, arbitrary score without definition, or near-unique numeric code.
- Its unit and aggregation rule are known.
- Its observation grain can be established.
- Missing values remain missing and true zero remains zero.
- Currency values are not mixed across currencies without conversion evidence.

Prefer metrics already selected or validated in Elements 1–6. Do not surface a semantically weak column merely because its statistical deviation is numerically large.

### 5.3 Exception recipe registry

Implement bounded recipes and select one eligible result.

#### Recipe A — Temporal exception

- Aggregate at the metric’s native valid grain: daily, weekly, monthly, or another verified period.
- Preserve complete and partial periods distinctly.
- Require at least 12 comparable periods for a basic robust temporal exception. Use stricter requirements when seasonality is estimated.
- For seasonal data, compare like with like. Use recorded holiday/event flags when present and require at least two cycles before estimating a seasonal baseline from repeated positions.
- A robust rolling median/residual method may be used when there are enough neighboring periods and no reliable seasonal cycle. Document window size and edge policy.
- Do not interpolate missing periods as observed values.
- Do not compare a partial period with complete periods unless normalized by a valid exposure denominator and visibly qualified.
- A simple raw-column IQR across all dates is not sufficient for seasonal time-series exceptions.

#### Recipe B — Segment exception

- Compare group rates/averages only when denominators and grain are compatible.
- Require at least five valid observations per displayed segment; use a stricter guard when metric volatility requires it.
- Use a robust center and spread across eligible segments, such as median and median absolute deviation (MAD).
- If MAD is zero, use a documented IQR fallback only when IQR is nonzero. If both are zero, do not manufacture an exception.
- Keep Unknown separate and do not select Unknown as the business subject.
- Ties must remain ties.

#### Recipe C — Reconciled rate exception

- Use for return rate, conversion rate, defect rate, cancellation rate, attendance reliability, or similar ratios.
- Numerator and denominator must be distinct, reconciled entities from the same eligible population.
- Require positive denominator and disclose exclusions.
- Compare rates with rates, not raw counts.

#### Recipe D — Distribution exception for inspection

- Use record-level IQR/MAD only for a semantically verified measure when no safer temporal or segment analysis exists.
- Aggregate presentation to a period, segment, or count. Do not put personal/customer records on the dashboard.
- The default card may say `12 unusual observations in delivery time`; inspection can link to the filtered Explorer.
- Do not imply the observations are data errors.

### 5.4 Robust deviation rules

- Prefer MAD-based robust z scores for comparable cross-sectional values: `0.6745 × (x − median) / MAD`.
- A conventional descriptive screening guard such as `|robust z| >= 3.5` may nominate an exception, but it must not be shown as a probability or confidence score.
- IQR fences may be used when MAD is zero and IQR is positive: `[Q1 − 1.5×IQR, Q3 + 1.5×IQR]`.
- Store exact unrounded calculations; round only display values.
- Show the expected/typical range as an **observed statistical range**, never as a policy target, guaranteed forecast interval, safety limit, or confidence interval.
- Document how many metrics and candidates were screened. Do not show this technical count in the default card.
- Use deterministic stable tie-breaking after preserving meaningful ties.

### 5.5 Selection policy

Choose lexicographically rather than producing a fake blended risk score:

1. Semantic validity and source-snapshot integrity.
2. Compatible grain and adequate comparison population.
3. Business relevance to the detected domain and selected intent.
4. Robust deviation beyond the recipe guard.
5. Coverage and recency.
6. Non-duplication with Element 6 Decision focus.
7. Stable deterministic tie handling.

If the highest candidate repeats the same subject, measure, and fact already shown in Element 6, prefer the next valid exception. Reuse the Element 6 subject only when Element 8 adds a materially different temporal or distribution fact.

If no candidate passes, return `None` or an honest unavailable state. Elements 1–7 must remain intact.

## 6. Snapshot and provenance correction

Element 8 may consume EDA diagnostics only when they are bound to the current selected source.

The current EDA report structure may omit a source content snapshot. Correct this shared contract safely:

- Store a deterministic source snapshot/hash in newly generated EDA reports.
- Base it on the same canonical selected rows and columns used by the Adaptive Dashboard, or centralize the snapshot helper so both systems use identical logic.
- Persist `sheet_id`, `dataset_id`, snapshot, generation timestamp, and EDA method version.
- Reject stale or snapshotless EDA results for Element 8. Recompute from current rows or abstain; do not silently accept them.
- Keep old EDA endpoints backward compatible where possible.
- Strengthen the shared correlation/EDA validators used by Element 6 so “snapshot missing” is not treated as “snapshot valid.” Preserve correct Element 6 behavior and add regression tests.

Do not broaden the selected source scope to all historical sheets. Upload-time EDA and on-demand EDA must analyze the intended dataset/sheets only.

## 7. Backend architecture and contracts

Do not add another large builder to `engine.py`.

Create:

`backend/app/services/adaptive_dashboard/exceptions.py`

This module should own:

- Candidate discovery from current rows and trusted EDA screening diagnostics.
- Recipe eligibility and calculation.
- Robust statistics.
- Candidate selection and duplicate suppression.
- Typed visual data preparation.
- Evidence and provenance validation.

The main engine should pass the manifest, semantic contract, current rows, trusted EDA report, and existing Elements 1–7 into the builder. It should catch Element 8 errors independently and attach the result without affecting earlier elements.

### Suggested strict contracts

```text
ExceptionPoint
  label
  raw_period_or_segment
  value
  formatted_value
  expected_lower
  expected_upper
  is_exception
  is_partial
  sample_size

ExceptionItem
  exception_id
  exception_type: temporal | segment | reconciled_rate | distribution
  subject_type
  subject_label
  metric_name
  unit
  observed_value
  formatted_observed_value
  expected_lower
  expected_upper
  formatted_expected_range
  deviation_value
  formatted_deviation
  direction: above | below | outside | neutral
  sample_size
  sample_label
  method
  context_flags
  calculation_id
  snapshot

ExceptionVisualSpec
  kind: timeline_band | segment_dotplot | none
  x_axis_title
  y_axis_title
  points

ExceptionWatchSpec
  component_id = "exception_element"
  kind: exception_watch | exception_unavailable
  business_concept
  title
  lead_exception
  additional_exceptions
  total_eligible_exceptions
  why_inspect
  next_check
  visual
  glance
  explain
  inspect
  evidence
  caption
```

Use `ConfigDict(extra="forbid")`, bounded list sizes, typed enums, and finite numeric validation. Adapt names when the existing architecture provides a cleaner equivalent.

Add `exception_element: ExceptionWatchSpec | None` to `AdaptiveDashboardResponse` and update the response version to `adaptive-v8`.

The lead exception’s EvidenceResult must contain:

- Current snapshot.
- Recipe and calculation ID.
- Exact observed value.
- Comparison range components.
- Missing, invalid, and excluded counts.
- Coverage.
- Calculation method.
- Provenance.
- Limitations.

Do not fabricate numerator/denominator fields when the method is not a ratio. Leave optional fields empty rather than inserting meaningless values.

## 8. Minimal UX and ECharts behavior

Create a focused component such as:

`frontend/src/components/adaptive/ExceptionWatchCard.jsx`

Do not add another large rendering block to `AdaptiveDashboardPage.jsx`.

Place Element 8 after Element 7 during this approval stage.

### Default card

- Eyebrow/title: `Exception watch`.
- Lead-exception headline.
- Observed value as the strongest number.
- Typical observed range immediately adjacent or beneath it.
- Deviation and sample/period context.
- One restrained visual when eligible.
- One sentence: `Why inspect`.
- `Inspect supporting data` action.
- Standard information button.

### Temporal visual

- ECharts line only, unsmoothed.
- Chronological x-axis with readable dates.
- Typical observed range as a restrained band.
- Exceptional point uses shape plus color, not color alone.
- Missing periods create gaps.
- Partial periods are visibly marked.
- No zero baseline when it destroys meaningful resolution; display `Focused scale` when the axis is truncated.
- Tooltip shows full value, typical range, method context, sample, period status, and recorded event flag when present.

### Segment visual

- ECharts horizontal dot plot, not bars.
- Full segment name remains accessible.
- Robust center and typical range are visible.
- Selected point uses shape plus color.
- Alphabetical or business order may be used; do not disguise ranking as probability.

### Responsive behavior

- Desktop: compact two-column arrangement only if the card has enough width; otherwise stack.
- 768 px and below: stack narrative and chart.
- 320/390 px: no horizontal scroll, no truncated distinguishing labels, controls at least 44×44 CSS pixels.
- Keep clear of bottom navigation and Copilot.
- Support 200% zoom.

### Accessibility

- Provide a concise chart description and accessible data table/details.
- Do not rely on hover.
- Tooltip information must also be available by keyboard/touch or in details.
- Focus returns correctly after inspection modal closure.
- `Inspect supporting data` must navigate with a meaningful source/filter context.
- No red-only meaning or alarm semantics.

## 9. Data Explorer drill-through

The action should open the existing Explorer for the same sheet and the relevant EDA/diagnostic context.

Use a stable route such as:

`/?sheet_id=<sheet_id>&view=eda#explorer`

Only use parameters supported by the application. If `DataExplorerPage` does not currently initialize `sheet_id` from the query string, add the smallest backward-compatible support and test it. Do not create a second explorer or duplicate raw records inside the dashboard.

Do not expose personal records in URL parameters. Column names and aggregate exception IDs may be included only after safe encoding and validation.

## 10. Wording policy

Use:

- `unusual observation`
- `outside the typical observed range`
- `higher/lower than comparable periods`
- `inspect recorded context`
- `statistical exception`

Avoid:

- `error` unless validation proves a data error.
- `fraud`, `failure`, `critical`, `danger`, `risk`, `bad`, `poor performer`.
- `expected target` for a statistical range.
- `confidence interval` unless a correctly calculated inferential interval exists.
- `because`, `caused by`, `driven by` without causal evidence.
- `forecast` when the range is historical.

For a positive commercial spike, use neutral or positive descriptive language without assuming it is repeatable. For a low value with unknown polarity, remain neutral.

## 11. Required tests

### Statistical/backend tests

Add tests for:

1. Workforce temporal exception with valid duration units and no individual exposure.
2. Retail holiday peak retains its holiday flag and is not labelled an error or negative event.
3. Ecommerce return-rate exception reconciles distinct delivered and returned orders.
4. Sales conversion comparison uses rates and qualified-lead denominators, not raw counts.
5. Support backlog age does not claim SLA breach without a target.
6. General numeric data uses neutral wording.
7. Identifier and near-unique numeric columns are excluded.
8. Missing values are not converted to zero; true zero remains eligible.
9. MAD calculation and `|robust z| >= 3.5` screening with independently known values.
10. MAD zero with valid IQR fallback.
11. MAD and IQR both zero produce no exception.
12. Fewer than 12 periods abstain from temporal-exception claims.
13. Partial-period candidate is excluded or visibly normalized/qualified.
14. Missing time periods remain gaps.
15. Seasonal data requires comparable seasonal positions or recorded event context.
16. Small segments below sample guard are excluded.
17. Ties are preserved.
18. Unknown is never the selected business subject.
19. Mixed currencies and incompatible grains are rejected.
20. Stale and snapshotless EDA reports are rejected.
21. Same-snapshot EDA screening candidate is recalculated from current rows.
22. Lead exception does not duplicate Element 6 when another eligible candidate exists.
23. Element 8 failure preserves Elements 1–7.
24. Response version is `adaptive-v8`, contracts reject extra fields, and all numeric values are finite.

### Frontend and visual tests

Verify:

- Temporal line/band rendering.
- Segment dot-plot rendering.
- Text-only fallback.
- Full values in tooltip/details.
- Missing and partial periods.
- Long labels.
- Explorer drill-through preserves selected sheet and view.
- Keyboard/touch access to details and tooltip-equivalent information.
- Element absence does not leave an empty card.
- Existing Elements 1–7 do not regress.

Run:

```bash
backend/.venv/bin/python -m pytest backend/tests/test_adaptive_dashboard.py backend/tests/test_eda_pipeline.py
backend/.venv/bin/python -m pytest backend/tests
cd frontend && npm test && npm run build
```

## 12. Rendered acceptance

Inspect the real `#adaptive` page with representative datasets at:

- 320 px
- 390 px
- 768 px
- Normal desktop width
- Desktop at 200% zoom

For at least one temporal and one segment exception, confirm:

- The lead exception is understandable within several seconds.
- The number, unit, comparison range, grain, and sample are correct.
- The visual does not imply a target or causal conclusion.
- Holiday/event/partial-period context is not hidden.
- The chart uses ECharts and remains legible.
- Labels, first/last periods, axis titles, and tooltips/details are not clipped.
- `Inspect supporting data` opens the correct source in Explorer.
- The information modal explains the method and limitations.
- No PII appears.
- Elements 1–7 remain unchanged and functional.
- Voice playback and orb remain available.
- Copilot and bottom navigation do not obscure controls.

A passing build is not visual acceptance. Inspect the rendered card and its drill-through.

## 13. Update the design contract

Append **Revision 10: Element 8 — Exception Watch** to `docs/adaptive-dashboard-design.md` covering:

- The executive question answered.
- Statistical exception versus error/risk distinction.
- Eligible measures and recipe registry.
- Robust method and seasonality/partial-period guards.
- EDA screening versus final evidence.
- Snapshot binding.
- Minimal card and ECharts visual rules.
- Explorer drill-through.
- Test and responsive acceptance.
- Status: awaiting client approval.

Do not rewrite earlier revision history or mark Element 8 approved.

## 14. Handoff and stop condition

Report:

1. The lead exception selected for the currently loaded dataset.
2. Its exact observed value, typical range, deviation, sample, and calculation method.
3. Why the metric, grain, and comparison population were eligible.
4. Which candidate exceptions were rejected and why.
5. Whether EDA screening was used and how snapshot matching was verified.
6. Files changed.
7. Focused and full backend test results.
8. Frontend test/build results.
9. Browser widths, visual states, and drill-through actually inspected.
10. Any limitation or abstention.

Then ask:

> Is this exception useful to inspect, and is the presentation clear without overstating what the data proves?

Stop after presenting Element 8. Do not implement Element 9, commit, push, merge, or clean unrelated files.
