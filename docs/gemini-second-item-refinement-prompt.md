# Gemini execution prompt — refine the second dashboard element

Act as the lead developer working with a data scientist, software architect, UX designer, and visual designer. Deliver a verified improvement, not another plan or a declaration that the build passes.

Project: `/Users/vinayksharma/Developer/pulsehr-ai`
Review page: `http://localhost:5175/#adaptive`

Read repository instructions and `docs/adaptive-dashboard-design.md` Revision 5. This prompt supersedes the presentation requirements in `docs/gemini-second-item-prompt.md`, particularly its mandatory zero baseline and prohibition on all area fills. The revised chart permits a clearly disclosed focused duration scale and one meaningful statistical range band. The original metric definition and source-integrity requirements still apply.

## Scope and approval

The client approved the first **Employee count** tile and rejected the second chart's presentation. Preserve the first tile's value, meaning, appearance, position, and interactions. Refine only the second element, its supporting calculations/disclosures, and the shared date/renderer behavior required for it. Read git status and current code before editing; other contributors have uncommitted work.

Keep Apache ECharts as the only chart library. Preserve the existing Report and Reference Overview, voice/orb, and Copilot. Do not add a third element, extra KPI cards, a new dashboard, export features, or new model dependencies. Do not reset/restore unrelated files, commit, push, or deploy. The band, chart caption, and detail table belong to the existing second card.

## What failed, and why

Revalidate these inspected findings against the current checkout:

- The page fixes the y-axis tick interval at two hours. The backend supplies zero as the minimum and an upper bound of at least ten hours. That devotes most of the chart to values far from the observations.
- `Hours` exists in the configuration, but is visibly clipped. A configured title is not a visible title. The fixed 260px canvas and small top/bottom allowances do not reserve space for all labels.
- The legend crowds the month labels. `SafeReactECharts.minimalOptions()` creates a legend object even when none was requested, and overwrites some explicit font, color, tooltip, area, and accessibility choices. Review the FINAL rendered options, not just the page's input options.
- Reporting dates and partial-period messages expose ISO strings. There is no consistent policy separating monthly labels, exact dates, and relative age.
- The chart shows an average without showing the variation that average summarizes. Rounding and a broad axis further conceal small differences.
- Earlier requirements specified metric correctness more precisely than visual acceptance. The previous zero-baseline instruction contributed to this result. Correct the policy, not just a screenshot's coordinates.

An independent read-only inspection of the selected source found 71,200 valid intervals: monthly means ranged from about 479.372 to 480.670 minutes, a spread of about **1 minute 18 seconds**. Individual intervals ranged from **6h 29m to 9h 19m**. Monthly P10–P90 bounds were approximately **7h 35m–8h 25m**. These are audit observations, NOT constants or fallback data. Recalculate for the active source. The nearly flat mean is plausible; it does not mean every entry equals eight hours.

## 1. Improve the analytical expression within the same card

Keep the title **Average logged time** and the interval-weighted monthly mean. Add one subtle **Middle 80% of recorded entries** band, with distinguishable lower/upper boundaries, computed as each month's P10 and P90. The average remains the primary line; the band adds context.

This answers two linked questions: “Has the average changed?” and “How much do recorded entries vary within each month?”

- Calculate mean, P10, P90, minimum, maximum, valid count, observed dates, and exclusion categories in the backend from the SAME validated, deduplicated intervals and source revision.
- Preserve the unrounded mean and sufficient components. Do not round the backend series to three decimal hours and then call the tooltip exact.
- Use documented linear quantiles: for sorted durations, `h = (n - 1) × p`; interpolate between the surrounding order statistics. Record the method and population. Do not average daily percentiles or derive a band from monthly averages.
- For this release, display the band only for months with at least 20 valid entries. Treat this as an explicit presentation guard for sparse data, not a claim of statistical confidence. Below it, retain the mean and put count/min/max in details. Version and test this rule.
- The band describes recorded entries. It is NOT a confidence interval, target, schedule, acceptable range, performance rating, or proof about all employees. Do not label it “normal,” “healthy,” or “expected.” Explain in details that this is the P10–P90 percentile interval; ties/discrete observations can make its actual enclosed share differ from exactly 80%. Only state an actual coverage percentage if separately calculated.
- A skewed dataset can have its mean outside P10–P90. Include that mean in the axis extent and never force it into the band. Exact min/max belong in point details; do not imply the band contains every entry.
- Missing months remain null gaps in BOTH mean and band. No interpolation across missing evidence. With one month show a point/range, without an invented trend. If all durations are identical, a flat/collapsed result is correct.
- If the distribution computation fails but the mean is valid, preserve the mean and accessible data with a concise explanation in details. No fake boundaries and no erasure of the first tile.

A short, evidence-bound caption can say “Monthly averages stayed around 8h; individual entries varied.” Generate the value and any quantified spread from current evidence. Do not hardcode eight hours, claim statistical stability, imply good performance, or describe tiny fluctuations as major changes. State a verified range when a qualitative adjective would need an undefined business threshold. No LLM call is required for arithmetic, axis settings, or fallback copy.

Before extending the calculation, correct integrity defects in this recipe: compare duplicate intervals using normalized start/end values, not duration alone; exclude the ENTIRE ambiguous person/date group rather than retaining the first row; make results row-order independent. Recheck the long-layout use of nonexistent `manifest.columns`. Bind the actual column metadata explicitly. Remove arbitrary partial-month rules such as fewer than 15 observed dates; distinguish an observation window ending mid-month from missing calendar dates, without assuming scheduled workdays. A single month can be partial at both ends. Keep missing/invalid/conflicting counts distinguishable. Replace any tests that currently bless these defects.

## 2. Make the duration axis useful and honest

Use one visible y-axis title, **Logged duration (h/m)**, placed horizontally above the plot at its left edge or vertically with sufficient reserved room. It must be visible at every supported width and at enlarged text sizes.

Format duration ticks as `7h 30m`, `7h 45m`, `8h`, `8h 15m`. These are elapsed durations: do not format them as clock times (`07:45`), decimal hours (`7.75h`), percentages, or K/M/B numbers. Duration formatting must carry correctly across hour boundaries.

Implement a reusable, unit-aware scale policy:

1. Compute the extent from all displayed means and available band bounds. Nulls are excluded, not converted to zero.
2. Select a readable interval from duration steps such as 15, 30, 60, 120 minutes, expanding for genuinely larger ranges. Aim for roughly 4–7 visible ticks based on actual plot height.
3. Pad the plotted extent by approximately one chosen interval and snap both limits to that interval. Keep the default span at least 60 minutes for this recipe; never create a seconds-wide axis to exaggerate the near-flat mean. Clamp the lower limit to zero where appropriate.
4. Align the maximum with the interval so the chart does not end with a stray 11h tick after even-numbered ticks. Include every plotted value.
5. When the lower limit is nonzero, include a discreet **Focused scale** cue with the visible numeric scale; explain the bounds in details. No hidden axis break. Zero is not mandatory for this duration line chart; this exception must not silently change bar-chart baselines.

With the currently inspected distribution, a range around **7h 15m–8h 45m** at 15-minute steps may be suitable. This is an illustrative result of the policy, not a hardcoded range. On narrower/shorter layouts use fewer readable ticks, not smaller text or missing endpoints.

## 3. Fix tick placement, spacing, and composition

Build a small reusable layout policy that uses the chart container's available width/height and formatted label lengths. Do not assume a window resize followed by `chart.resize()` alone recalculates your chosen tick density.

- Put a compact key for **Average** and **Middle 80% of entries** above the plotting area, away from the x-axis. Show only those meaningful encodings. Hide helper series and unwanted default legends.
- Align month ticks with their corresponding observations. Use outward ticks or omit redundant tick marks; never place marks between the represented months.
- Reserve separate room for title/key, y-axis title, y tick labels, plot, and month labels. Start with approximately 12–16px between x-axis and labels and 8–12px beside y labels, then verify the rendered result. These are design starting points, not magic constants.
- Keep first and last displayed month labels readable inside the card. Show fewer intermediate labels as width shrinks while retaining every month in the data and tooltip/table. Preserve unambiguous years across year changes. No default diagonal labels, ellipsized dates, or microscopic fonts.
- Use restrained colors from the approved theme, linear segments, and no smoothing. A subtle fill is allowed only for the computed P10–P90 band. It must not extend to zero or connect through missing periods. Distinguish the mean and bounds beyond color alone.
- Rework the shared wrapper's merge precedence carefully: explicit chart options win over presentation defaults, while null-gap and rendering safety remain intact. Preserve explicit legend visibility/data/position, axis title/formatter/margins, semantic band styling, and custom accessible descriptions. Check other pages for regressions if the wrapper changes.
- Scope any necessary responsive fixes to this experience. Check the source control's `flex-basis: 280px` when its parent becomes a column and the date chip's `white-space: nowrap`; avoid oversized blank areas or overflow.

Do not solve this by globally shrinking text or hiding the y-axis. A simple chart with correct spacing is the goal.

## 4. Human dates with trustworthy context

Store canonical date keys unchanged. Add or use typed metadata for calendar-date versus timestamp, period grain, source timezone where relevant, observation end, and any real comparison event. Format these through shared display helpers; never rewrite raw source dates or use regex replacement on a generated sentence.

| Surface | Example presentation |
| --- | --- |
| Shared reporting range | `1 Jan 2023 – 12 Dec 2024` |
| Monthly axis tick | `Dec ’24` |
| Monthly point heading | `December 2024` |
| Partial-month cue | `Through 12 Dec ’24 · Partial month` |
| Exact day in details | `Thu, 12 Dec 2024` |

The weekday must be calculated correctly. Do not attach a weekday or a fictitious observation date to a monthly aggregate. Ordinals such as `12th` are optional locale-specific presentation; clear month names and accurate dates matter more.

Relative time supplements the absolute date and needs an explicit reference:

- For the shared latest-data disclosure, offer `Data through 12 Dec 2024 · [computed relative age]`, using natural text such as “2 months ago” only when correct. Name today and its actual reference date in details; do not append “before today” to an already formatted “ago” phrase. Show the age once, in a compact secondary line or accessible hover/tap details. It refers to latest observation, not upload time or model run time.
- A comparison such as `3 days before campaign launch` requires a verified event label and date. Without an event, do not invent “A.” Keep event-relative context in details until such a comparison is supported.
- Use a documented calendar-aware rounding policy for days/months/years, an injectable current clock for tests, and the relevant timezone. Do not divide all elapsed milliseconds by 30 days or hardcode “2 months ago.” Handle future dates as future, not negative age.
- Historical charts keep absolute monthly ticks; they do not become a row of changing “months ago” labels. Exported/static views freeze and disclose the reference date if relative wording is used.

Use `Intl.DateTimeFormat` and `Intl.RelativeTimeFormat` where suitable. Calendar dates must not shift to the previous day when formatted in another timezone. Resolve genuinely ambiguous source dates through the semantic contract, not guessing. The page period, chart scope, and details must agree with the validated data.

## 5. Progressive disclosure and accessibility

Keep the default face minimal: title, short metric context, compact encoding key, the chart, essential partial-period/scale cues, and at most one short finding. Reuse the information button for methodology and limitations.

Hover/tap point details show full month, actual observation bounds, mean in hours/minutes, central 80% range if available, valid count, and relevant exclusions. If minute rounding conceals a difference being discussed, offer approximate mean seconds or decimal minutes in expanded details, explicitly marked as a computed average; do not imply source timestamps have second-level accuracy. Preserve sum/count for reconciliation. Escape source-derived tooltip text or use safe text rendering.

Provide a keyboard-accessible data table and meaningful accessible chart description using business values and units, not the current auto-generated coordinate pairs. Helper band series must not pollute the announcement. Touch, focus, Escape, modal close, and focus return must work. Details remain usable on chart-render failure.

## 6. Prevent recurrence: tests and visual release gate

Put the duration/date/layout policies in reusable helpers/contracts and document them in the project's chart-development guidance. Future model-generated specs select a supported policy; they do not improvise ECharts code or bypass unit, date, range, and readability validation. Do not globally migrate unrelated charts in this slice.

Add focused regressions:

- Known mean and quantiles, interval weighting, full-precision evidence, and formatting carry at 59/60 minutes.
- Truly constant data, near-flat means with broad entry variation, a large valid change, skewed mean outside the band, outliers, 0/1/19/20 valid entries, and missing-month band gaps.
- Equal-duration intervals with different endpoints, whole-group conflict exclusion, row-order independence, invalid clocks, and correct counts after exclusion.
- Nonzero focused scale, data crossing zero where supported by another recipe, no clipped plotted values, aligned tick limits, and duration steps that adapt to size/range without changing the underlying numbers.
- Cross-year monthly dates, leap day, actual weekday, partial first/last/single month, timezone-safe calendar dates, future relative age, and explicit relative reference date.
- Final wrapper output preserves chosen legend, formatters, band style, accessible text, and axis-title placement; unrelated charts still work.
- Source changes, stale requests, empty/failed series, and chart failure preserve the correct first tile and an honest second-slot state.

Inspect actual browser rendering at **320, 390, 768, and desktop widths**, plus enlarged text/200% zoom. Recheck AFTER the shared wrapper has transformed the options. Inspect full card, last month, y title, legend, tooltip, and details. Verify no clipping/overlap/page overflow, no hidden final date, no navigation/Copilot obstruction of usable controls, and no change to the approved first tile. Do not claim these checks passed unless performed.

Use before/after screenshots and independent calculation reconciliation as delivery evidence. Passing Python tests and a frontend build does not establish good presentation. Correct visible defects before handoff; if a browser condition cannot be verified, state that concrete limitation.

## Handoff and stop

Report the page link, changed files, a short explanation of the near-flat mean and distribution band, exact metric/scale semantics, and completed test/browser checks. Show the second card for client review. Ask for approval of this revised second element and STOP before adding any third element.

Implementation references: Apache ECharts documents separate axis titles, ticks, and label formatters in its [axis handbook](https://echarts.apache.org/handbook/en/concepts/axis/). Its [version 6 notes](https://echarts.apache.org/handbook/en/basics/release-note/v6-feature/) describe improved label layout; inspect installed-version behavior instead of assuming it prevents every collision. Native locale-aware formatting is documented in [Intl.DateTimeFormat](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Intl/DateTimeFormat) and [Intl.RelativeTimeFormat](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Intl/RelativeTimeFormat).
