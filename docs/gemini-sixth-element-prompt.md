# Gemini Lead Developer Prompt — Adaptive Dashboard Element 6: Decision Focus

You are the lead developer working with a senior data scientist, software architect, product manager, and executive UX designer.

Repository:

`/Users/vinayksharma/Developer/pulsehr-ai`

Implement **only Element 6** on the existing Adaptive Dashboard at `#adaptive`. Preserve Elements 1–5 and all other application pages. After implementation, present Element 6 for client review and stop. Do not create Element 7, redesign the full page, commit, push, restore deleted files, or overwrite unrelated work.

## 1. Why Element 6 exists

Elements 1–5 already answer:

1. What is the primary headline number?
2. How is an important measure changing over time?
3. How is the population or measure distributed across categories?
4. What verified cohort comparison or relationship exists?
5. Where is meaningful disparity visible across segments?

The missing executive question is:

> **Where should I look first, why does it deserve attention, and what is the safest next action supported by the data?**

Element 6 must answer that question through one compact, evidence-backed **Decision focus** card. It is the interpretation layer connecting verified analysis to a practical next step. It must not become another chart, ranking table, warning wall, generic AI paragraph, or restatement of Element 5.

Element 6 is valuable only if it reduces the executive's reading effort. The viewer should understand one priority in a few seconds and be able to inspect the calculation when needed.

## 2. Preserve the existing implementation

Before editing:

- Read `git status --short --branch` and inspect current diffs.
- Read `docs/adaptive-dashboard-design.md` and the current implementations of Elements 1–5.
- Inspect:
  - `backend/app/services/adaptive_dashboard/contracts.py`
  - `backend/app/services/adaptive_dashboard/engine.py`
  - `backend/app/routers/adaptive_dashboard.py`
  - `backend/app/services/eda/`
  - `backend/app/routers/eda.py`
  - `backend/tests/test_adaptive_dashboard.py`
  - `backend/tests/test_eda_pipeline.py`
  - `frontend/src/pages/AdaptiveDashboardPage.jsx`
  - `frontend/src/styles/adaptive-dashboard.scss`
  - `frontend/src/components/charts/SafeReactECharts.jsx`

The working tree contains other contributors' uncommitted work. Do not run `git reset`, `git restore`, `git checkout --`, `git clean`, or bulk replacement commands. Make the smallest coherent Element 6 changes.

Preserve:

- The approved Employee count tile.
- The existing temporal chart and its date/scale behavior.
- The categorical breakdown.
- The explanatory comparator.
- The segment disparity matrix.
- Leadership Report and Reference Overview.
- EDA Explorer, raw/curated data, voice/orb, Copilot, and presentation creation.
- The minimal visual language and the existing glance/explain/inspect disclosure model.

Do not use a chart library other than ECharts. Element 6 itself should normally be a semantic decision card, so it does not require a chart.

## 3. Element 6 product definition

Use the stable user-facing section label:

**Decision focus**

The card contains only:

1. A short decision headline naming the specific segment, cohort, or measured issue.
2. One compact evidence line with the observed value, comparator, gap, and sample scope when material.
3. One plain-language “Why this matters” sentence grounded in the evidence.
4. One safe “Next check” or “Recommended next step” that investigates or validates the issue without pretending the data proves a cause.
5. One unobtrusive information control for calculation, coverage, provenance, limitations, and selection rationale.
6. A link or button to the existing supporting element/details when that evidence already appears in Elements 2–5.

Do not add:

- A long executive-summary paragraph.
- Multiple recommendations competing for attention.
- A top-three list.
- A second ranking of all departments/stores/categories.
- A fake confidence percentage or “AI confidence” badge.
- A red/amber/green traffic-light system.
- Decorative gradients, oversized icons, large warning blocks, or excessive chips.
- “Critical,” “risk,” “underperforming,” “healthy,” or “poor” unless the source data contains a verified target or the semantic contract explicitly defines the direction of concern.
- Causal language such as “because of,” “driven by,” “caused by,” or “will improve” when the data shows only an association or descriptive difference.

Preferred examples of card shape, not hard-coded output:

### Workforce example

- Section label: `Decision focus`
- Headline: `Review Corporate attendance reliability`
- Evidence: `70.0% · 11.7 pp below the workforce benchmark · 18 employees`
- Why it matters: `This unit has the largest verified attendance-reliability gap among departments with adequate records.`
- Next check: `Review scheduling coverage and approved-leave patterns before changing policy.`

Do not claim leave caused the gap.

### Retail example

- Headline: `Investigate Store 33 sales density`
- Evidence: `$289K per store-week · 63% below the network median · 143 store-weeks`
- Why it matters: `The observed gap is persistent enough to justify a store-level operational review.`
- Next check: `Compare trading days, stock availability, local assortment, and traffic before setting a recovery target.`

Do not claim which factor caused the difference unless the uploaded data measures and validates it.

### Ecommerce example, only when funnel fields exist

- Headline: `Inspect the payment-stage drop-off`
- Evidence: `18.4% of checkout sessions did not reach a verified order · 2.1K sessions`
- Next check: `Break the gap down by payment status, device, and error code.`

Do not calculate abandonment from cart and order totals unless the same eligible population and funnel transitions can be reconciled. Do not invent a reason for abandonment.

### Sales or marketing example, only when denominators exist

- Headline: `Review Enterprise lead conversion`
- Evidence: `8.2% · 4.1 pp below the qualified-lead benchmark · 317 qualified leads`
- Next check: `Compare stage ageing, source mix, and loss reasons for this segment.`

Do not call a segment “worst” merely because it has the fewest raw conversions.

### Service/support example

- Headline: `Inspect ageing unresolved tickets`
- Evidence: `46 tickets older than 7 days · 31% of the open backlog`
- Next check: `Break the backlog down by owner, severity, and blocked status.`

Do not claim an SLA breach without an explicit SLA target and valid business-time rules.

These examples teach the pattern. The live card must use actual uploaded evidence and domain vocabulary.

## 4. Evidence and selection architecture

Add a typed backend contract named for its business purpose, not an awkward ordinal. Prefer:

- `DecisionFocusSpec`
- response field: `decision_element`
- `component_id = "decision_element"`
- response version: `adaptive-v6`

Suggested fields:

```text
component_id
kind: decision_focus | investigation_focus | unavailable_card
business_concept
title
subject_type
subject_label
metric_name
unit
observed_value
formatted_observed_value
comparator_label
comparator_value
formatted_comparator_value
gap_value
formatted_gap_value
sample_size
sample_label
why_it_matters
next_step
monitor_metric
supporting_component_id
supporting_calculation_ids
priority_basis
glance
explain
inspect
evidence
caption
```

Adapt this schema when the existing contract architecture provides a cleaner equivalent, but keep it strictly typed with `extra="forbid"`. Do not pass arbitrary model-generated property paths or free-form chart specifications.

### Candidate generation

Build candidates from verified, same-snapshot evidence only:

- Existing EvidenceResults from Elements 1–5.
- Structured EDA diagnostics tied to the same `sheet_id`, `dataset_id`, source content, and snapshot.
- Safely joined derived tables only when cardinality and coverage are verified.
- Deterministic calculations over the current selected source when an existing element does not already expose the required comparator.

Do not copy the current EDA report’s generic recommendation strings into the executive card. Those recommendations describe data-processing operations, not verified business actions. Consume structured diagnostics and calculations.

The current EDA report does not necessarily prove it was generated from the current Adaptive Dashboard snapshot. Add or validate the smallest reliable snapshot/hash binding needed for safe use. If an EDA result cannot be tied to the current selected source, reject it as stale and continue using current-snapshot evidence. Never silently mix versions.

### Eligible analytical recipes

Use a bounded recipe registry. Element 6 may choose one eligible recipe:

1. **Directional segment gap**
   - A business metric has a verified direction of concern.
   - Segment value, weighted benchmark, sample size, exclusions, and coverage are known.
   - Use the largest material benchmark gap among adequately represented segments.

2. **Verified cohort gap**
   - Two comparable cohorts share a valid denominator/grain.
   - Report absolute and relative gaps only when both are meaningful.
   - Do not compare totals when cohort sizes differ and a rate/average is required.

3. **Concentrated operational burden**
   - A burden metric such as returns, unresolved backlog, approved absence days, defects, or cancellations is semantically verified.
   - The numerator and eligible total reconcile.
   - Use Top N + Other + Unknown only when multiple categories are necessary in supporting details; the default card still shows one priority.

4. **Cross-sheet association to investigate**
   - Join keys and cardinality are validated.
   - Many-to-many multiplication is prohibited.
   - Paired sample is adequate, both variables vary, missingness is disclosed, Pearson and Spearman directions are consistent, and the source snapshot matches.
   - Present as an association to investigate, never a cause or intervention recommendation.

5. **Data-definition blocker**
   - Use only when no business priority can be computed safely because the required metric meaning, denominator, time grain, or join is unresolved.
   - The card should state the single most useful definition needed to unlock analysis. Keep this concise and constructive.

Do not create a forced result. Returning `None` or an honest unavailable/definition card is correct when no recipe passes validation. A failure in Element 6 must preserve Elements 1–5.

### Minimum evidence guards

Implement explicit recipe guards rather than an invented confidence score:

- Exclude identifiers and near-unique numeric codes from measure candidates.
- Exclude missing/invalid observations rather than converting them to zero.
- Require at least two comparable groups for a group gap.
- Require adequate observations for a decision claim. Use a documented minimum such as `n >= 5` per displayed segment for a purely descriptive comparison and a stronger guard such as `paired n >= 30` for correlation-based prioritization. If the domain or recipe needs a stricter threshold, use it and explain it.
- Mark partial periods and do not compare a partial period with a complete period without normalization and a visible qualifier.
- Use weighted overall benchmarks when group sizes differ.
- Preserve ties deterministically. Never manufacture a single “worst” segment when multiple segments tie.
- Keep Unknown separate. Do not hide missing categories inside Other.
- Reject denominator zero, unknown denominator, incompatible grains, mixed currencies, stale snapshots, and unsafe joins.
- Do not treat EDA outliers as errors automatically. An IQR outlier is an observation for review, not proof of bad data or poor performance.

### Priority selection

Do not create an opaque blended score such as `AI priority = 87%`.

Select lexicographically using auditable criteria:

1. Semantic validity and known direction.
2. Current-snapshot integrity.
3. Adequate sample and coverage.
4. Material observed effect using the recipe’s natural unit.
5. Actionability of the next diagnostic check.
6. Non-duplication with the default content of Elements 1–5.
7. Stable deterministic tie-breaking.

Store the winning recipe ID, candidate facts considered, exclusions, and selection rationale in inspection details. The default card should not display internal scoring or implementation language.

An LLM may improve wording only after a deterministic candidate passes validation. Its output must be schema-constrained and checked against the evidence. On timeout, invalid JSON, unsupported values, or an unbound claim, use deterministic domain-aware wording. The model must never calculate the number, choose an unsupported direction, or introduce a cause.

## 5. Business vocabulary and action policy

Use familiar role-specific language inferred from the semantic contract:

- Workforce: employee, department, attendance, approved leave, scheduling coverage.
- Retail: store, store-week, net/weekly sales, trading period, assortment, stock availability.
- Ecommerce: session, cart, checkout, verified order, payment status, return, category.
- Sales: lead, qualified lead, opportunity, stage, conversion, pipeline age.
- Marketing: campaign, impression, click, qualified response, attributed revenue, cost.
- Support: ticket, unresolved backlog, resolution time, severity, owner, SLA target when defined.
- General tabular: segment, observed measure, benchmark, coverage, follow-up analysis.

Never infer protected-trait explanations or recommend adverse employee/customer treatment. For HR data, recommend process review, scheduling validation, workload review, data verification, or a like-for-like comparison. Do not make individual performance judgments from attendance alone.

The recommended step must be proportionate to the evidence:

- Descriptive difference → inspect/compare/validate.
- Association → investigate potential explanations and confounders.
- Verified operational state → review the process owner and the supporting records.
- Explicit target gap → plan against that target, while showing its source.

## 6. Minimal UX specification

Place Element 6 after Element 5 as one responsive card.

### Desktop

- Quiet full-width card aligned with existing content width.
- Small eyebrow: `Decision focus`.
- Headline is the strongest text element, preferably one line and at most two.
- One evidence row with at most three compact facts separated visually.
- Two short text blocks: `Why this matters` and `Next check`.
- Small action link/button: `Open supporting evidence` when a supporting element exists.
- One standard information button using the existing disclosure interaction.

### Mobile

- Natural stacked reading order.
- No horizontal scrolling.
- Do not place evidence facts in a squeezed multi-column grid.
- Names must wrap without truncating the distinguishing part.
- Minimum touch target 44×44 CSS pixels.
- The info control and evidence action must remain reachable above the bottom navigation and Copilot control.

### Visual rules

- Reuse existing design tokens, typography, spacing, border treatment, and focus styles.
- Use compact numbers only in the glance layer; hover/focus/details expose full values.
- Preserve currency symbols, percentage signs, percentage-point language, and duration units.
- Do not append the word `units` when the metric already has a meaningful name.
- No bar chart, gauge, donut, speedometer, decorative score, or animated pulse.
- Do not use color alone to communicate concern.
- Do not show raw column names with underscores. Use the ingestion/semantic display labels.

### Interaction and accessibility

- Reuse the existing glance/explain/inspect interaction pattern.
- Mouse hover and keyboard focus may show a concise preview.
- Click, Enter/Space, or touch opens persistent details.
- Escape closes details and returns focus to the triggering control.
- The supporting-evidence action must move focus to or open the referenced evidence, not merely scroll visually.
- Use a meaningful region label and concise accessible name.
- Sanitize any source-derived text before inserting it into HTML or an ECharts tooltip.

## 7. Frontend behavior

Extend `AdaptiveDashboardPage.jsx` without duplicating the existing modal system:

- Read `data.decision_element`.
- Add `decision` to the existing inspect-target and trigger-ref handling.
- Reuse the common inspection modal and add only the decision-specific supporting facts needed.
- Do not recalculate business metrics in React.
- Do not derive a different comparator or gap from rounded display values.
- Use backend formatted values and raw numeric evidence consistently.
- When `supporting_component_id` exists, connect to the existing component by stable ID and focus it accessibly.
- When Element 6 is `None` or unavailable, preserve the rest of the page. Do not display a broken empty shell.
- A failed Element 6 request/calculation must not fail the complete dashboard response.

Avoid adding more one-off booleans if a small keyed disclosure-state structure can simplify the existing repeated state safely. Do not perform a large frontend refactor in this task.

## 8. Required tests

Add meaningful backend tests for:

1. Workforce directional gap using a weighted benchmark and adequate department samples.
2. Retail store-week density focus with valid grain and full store names.
3. A general dataset whose measure direction is unknown; wording must remain neutral and must not call the lowest value “worst.”
4. Ecommerce funnel fields with reconciled eligible sessions, and a case where missing funnel linkage prohibits abandonment calculation.
5. Tied priority candidates; result must preserve the tie or choose deterministically without a false unique-worst claim.
6. Small segments below the minimum sample guard.
7. Missing values versus true zero.
8. Partial-period data.
9. Stale EDA snapshot rejection.
10. Unsafe many-to-many join rejection.
11. Correlation with small paired sample, zero variance, inconsistent Pearson/Spearman direction, and acceptable paired evidence.
12. Unknown categories remain separate.
13. Source change invalidates Element 6 while preserving prior elements until the new complete response arrives.
14. Element 6 failure preserves Elements 1–5.
15. No source column, number, comparator, action, or cause appears unless bound to verified evidence.

Update response-contract tests to confirm:

- `version == "adaptive-v6"`
- `decision_element` is typed.
- Existing five elements remain unchanged for their established fixtures.
- The decision element shares the response snapshot.
- Extra/unbound fields are rejected.

Run:

```bash
backend/.venv/bin/python -m pytest backend/tests/test_adaptive_dashboard.py backend/tests/test_eda_pipeline.py
backend/.venv/bin/python -m pytest backend/tests
cd frontend && npm test && npm run build
```

## 9. Visual acceptance

Inspect the actual running page at:

- 320 px
- 390 px
- 768 px
- Normal desktop width
- Desktop at 200% zoom

Verify all of these in the rendered UI:

- Element 6 is visually quieter than the analytical charts but still easy to find.
- A manager can understand the priority, evidence, and next check in several seconds.
- The card does not repeat the full disparity table or another chart.
- Long department/store/category names remain understandable.
- Full numbers and calculation details are available.
- The information control works by mouse, keyboard, and touch.
- The supporting-evidence action moves focus correctly.
- No content overlaps the bottom navigation, Copilot, modal close button, or viewport edge.
- Existing Elements 1–5 retain their layout and behavior.
- No unexpected horizontal scroll, clipped text, inaccessible tooltip-only content, or color-only meaning.

A passing build is not visual acceptance. Capture before/after screenshots for the handoff if the environment supports it.

## 10. Update the design contract

Append a concise Element 6 section to `docs/adaptive-dashboard-design.md` covering:

- The executive question answered.
- Eligible evidence recipes.
- Selection and abstention rules.
- The minimal card anatomy.
- Snapshot and EDA binding.
- Non-causal action-language policy.
- Test and visual acceptance requirements.
- Status: awaiting client approval.

Do not rewrite historical approved/rejected decisions.

## 11. Required handoff and stop condition

Report:

1. The specific Element 6 selected for the currently loaded dataset and why that recipe was eligible.
2. The exact calculation, comparator, sample size, exclusions, and source snapshot.
3. Why the wording is descriptive, directional, or investigative.
4. The files changed.
5. Focused and full test results.
6. Frontend test/build results.
7. Browser sizes and interactions actually inspected.
8. Any limitation or abstention.

Then ask the client:

> Is this decision useful, and is its presentation clear enough to approve Element 6?

Stop after presenting Element 6. Do not implement Element 7, commit, push, merge, or clean unrelated files.
