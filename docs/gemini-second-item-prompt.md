# Gemini execution prompt — second dashboard item

Status: historical initial implementation prompt. The second chart was implemented and then rejected in design review. Use `docs/gemini-second-item-refinement-prompt.md` for current work. Its focused-duration-scale and observed-range-band requirements supersede the zero-baseline and no-fill instructions below; preserve the approved first tile.

Act as the lead developer coordinating data science, architecture, UX, visual design, and delivery.

PROJECT
`/Users/vinayksharma/Developer/pulsehr-ai`

Read the applicable repository instructions and `docs/adaptive-dashboard-design.md` (Revision 4). The client has approved the first tile currently visible at `http://localhost:5175/#adaptive`: Employee count, its number-first layout, and supporting disclosure. Preserve that accepted experience. The previous first-element approval gate has been satisfied; the third-element gate has not.

## Deliverable and scope

Add exactly ONE complementary second element: an Apache ECharts monthly line chart titled **Average logged time**. It answers: “How did the average duration of recorded time entries change over time?”

Preserve the first tile's meaning, number, appearance, position, and information interaction. Do not redesign the page, rebuild the first tile, add another KPI, create a department ranking, or add narration/export/new dashboard sections. Place the new chart beneath the first tile, with a wider responsive card suited to a time axis. Existing Leadership Report and Reference Overview remain unchanged.

Inspect current code and git status before editing. Preserve concurrent work and uncommitted changes. Do not reset files, restore deleted files, broadly refactor, commit, push, or deploy. Implement the authorized slice; do not stop at another plan.

## Why this is the second item

A read-only inspection during planning found one time-tracking sheet with 100 Person_* columns, 712 ISO-formatted recorded dates, and single same-day HH:MM–HH:MM entries. All inspected dates had logs for every tracked person; another people-count chart would largely repeat the first tile. Recorded duration introduces a different measure and the monthly view the client previously requested.

These are observations, NOT production constants. Reinspect the actual selected source and validate values. Never hardcode the source ID, entity count, number of dates, range, eight hours, or current results. Column naming alone does not prove time-interval semantics.

The inspected monthly average durations were nearly flat around eight hours. A nearly flat valid chart is acceptable. Do not invent a dramatic change, crop the axis tightly to amplify seconds, or treat eight hours as a target.

## Metric contract

- Business label: **Average logged time**.
- Short chart context: **Hours per recorded entry · Monthly**.
- Meaning: elapsed clock time between the recorded start and end of each valid entry, averaged within calendar month.
- This is not paid time, verified productive work, attendance rate, overtime, or an assessment of employee performance.

For each supported entry:
`duration_minutes = end_minutes - start_minutes`

For each calendar month:
`average_logged_hours = sum(valid_duration_minutes) / (60 × valid_entry_count)`

Use the interval count as the denominator. Do not divide by the workforce tile's value, calendar days, expected workdays, or scheduled hours. Do not average already-rounded daily/monthly means. Preserve full precision until display formatting.

Validation requirements:
- Parse real dates and keep year/month together; do not rely on lexical sorting of arbitrary strings. Ambiguous date formats require an established mapping.
- Validate clock ranges and supported interval grammar. Keep blank, malformed, invalid, and excluded entries distinguishable.
- Same-day positive intervals are supported in this slice. An end time before the start or equal start/end requires a verified overnight/full-day convention; otherwise exclude as unresolved and disclose. Never silently add 24 hours or turn it into zero.
- Exact duplicate person/date/interval observations must not double-count. Conflicting or overlapping entries for the same person/date require an explicit rule; exclude ambiguous groups rather than silently sum them. Do not invent a new multi-session policy for this slice.
- Missing dates or entire months are not zero. Preserve a null gap for a missing month; do not connect through it or interpolate.
- A month with no valid entries is unavailable, not 0 hours.
- Identify partial first/last months and missing observation dates. A calendar-coverage statement does not prove scheduled-workday coverage.

Use the available real source if validation succeeds. If it does not, keep the approved first tile working and use one compact unavailable state in the second slot explaining what is needed. Do not substitute another metric without client review.

## Evidence and architecture

Implement a reusable time-interval trend recipe, not a special case for this filename or business. It should work with other supported layouts through explicit field bindings; it need not support every possible time format in this slice.

Extend the adaptive contracts with a typed series result and an optional second component. Prefer a backward-compatible response keeping the current `element` and adding `secondary_element`, derived from the SAME immutable source snapshot. Read source rows once per result revision rather than use uncoordinated requests for the tile and chart.

Each point retains its month key, average hours, summed duration minutes, valid-entry count, unique observed-date count, exclusion counts, and coverage flags. Chart data, tooltips, and detail text must come from this evidence. The frontend formats numbers; it does not calculate the metric.

Do not trust the existing date-range formatter or wide-layout heuristic as validation. Add the needed checks behind the new recipe while preserving the approved first tile's output. Failure in the second computation must not erase a valid first tile; snapshot/source invalidation still applies to the whole response.

No new model call is required for arithmetic or styling. If a model contributes wording, bound its output to the verified evidence and keep the chart available when the model is unavailable.

## UX and visual implementation

Reuse the approved theme, quiet border, type style, and information-control pattern. One chart card; no repeated source badges, methodology paragraph, generic warnings, extra numeric tiles, or invented comparison chips.

Use Apache ECharts only:
- Chronological line, linear segments, no smoothing, no connected null gaps.
- Start the default hour axis at zero with a sensible upper bound derived from the data. No arbitrary eight-hour target or performance threshold.
- Show month AND year sufficiently clearly to distinguish different years; keep all periods available on mobile.
- One restrained series color. No decorative area fill or red/green performance interpretation.
- Mark a partial terminal period discreetly with a text cue such as “Latest month partial” and a point distinction; do not rely on color alone.
- Exact average, hours/minutes representation, valid entries, observed dates, and relevant point exclusions are available on hover/tap or accessible data details.
- A short hover/focus definition plus persistent details on activation, following the approved first-tile interaction. Explain in details that the measure does not account for breaks, pay rules, or productive work.
- Default view stays concise. A table within details is supporting disclosure, not a third dashboard element.

Handle resize, 320px/390px widths, keyboard access, touch, enlarged text, loading, source changes, and chart-rendering failure. The details/table must remain usable if the chart fails. No stale first-tile/second-chart combinations or old tooltip content after switching sources.

## Verification and acceptance

Add focused tests for the new behavior:
1. 09:00–17:00 and 09:00–15:00 produce a mean of 7 hours.
2. Unequal numbers of intervals per day are weighted by interval count, not by daily means.
3. Exact duplicates do not inflate numerator or denominator; conflicting person/date entries follow the documented exclusion policy.
4. Malformed clocks, blanks, unresolved overnight entries and zero valid entries never become fabricated zero durations.
5. December/January and January in different years stay chronological and distinct; ambiguous dates are not guessed.
6. Missing months stay null gaps; partial last month is identified.
7. Source edits invalidate both components consistently. A second-element failure preserves a valid first tile for that same scope.
8. Different entity counts and date ranges work without fixture constants.
9. Exactly two dashboard elements render; the accepted first tile has no visual or semantic regression.
10. Live chart values reconcile with an independent calculation; build and relevant tests pass.

Inspect the actual page on desktop and mobile, the tooltip/point interaction, and persistent details. Do not mistake a successful build for metric correctness. Check that a nearly flat series is not visually exaggerated or narrated as a performance story.

## Handoff and mandatory stop

Report the page link, the implemented metric definition, a concise evidence-based reason for this choice, test/browser results, and any concrete limitation. Show the real second item and its details for review. Clearly distinguish completed verification from anything that could not be checked.

Ask: “Does this second item help you understand the data, and do you approve its chart and presentation?”

STOP before implementing any third element. The first approval does not authorize all later elements.
