# Gemini lead execution brief: HR dashboard ready for the next business review

## Mandate

Act as the lead developer working from a senior business analyst's requirements. Implement this plan; do not respond with another long proposal. The client needs a quick, visibly improved review build, with trustworthy figures and a concise HR story. Preserve useful existing work. Complete the smallest coherent business outcome before expanding analytical breadth.

Read `docs/hr-dashboard-stakeholder-review.md` for the observed issues R01–R12. Those observations came from an earlier running state: inspect the current implementation once, retain fixes already made, and address the gaps that remain. The source mismatch's root cause was not established; investigate rather than assuming it was caused by tests, caching, or the database.

Do not spend this iteration implementing all twenty analytical strategies, replacing the architecture, adding libraries, or creating another dashboard route. Improve the existing Adaptive Dashboard. Keep Leadership Report and Reference Overview available. Preserve the voice orb and its animation.

## Business outcome

An HR reader must be able to answer, within one minute:

1. Which workforce and period am I looking at?
2. What was recorded, and what deserves attention?
3. Which department or records need a closer look, and why?
4. What can I conclude, what remains unknown, and what should I do next?
5. Where can I inspect the exact supporting data?

This is an attendance-and-leave review when the uploaded sheet supports that subject. Do not infer engagement, productivity, attrition, misconduct, or employee performance from attendance totals. The underlying system remains domain-adaptive; do not hardcode the current workbook, department names, counts, or period.

## Release boundary: one improved business section

Deliver one cohesive HR review section above the existing detailed analysis. Reuse current components and findings where possible. Consolidate overlapping cards into expandable details on this page; do not delete their underlying calculations or approved reference pages.

The visible section consists of:

| Part | Required content | Rule |
|---|---|---|
| Scope line | Workbook/sheet, reporting interval, population scope, last refreshed time | Unknown reporting year or interval stays unknown. Upload time is not the reporting period. |
| Compact measures | Up to three supported measures: employees represented, recorded attendance, approved leave | Values must have verified definitions and units. Fewer tiles are preferable to fabricated metrics. |
| Main insight | One distinct business finding, one suitable visual if useful, and a short implication | Select from valid findings; a data integrity issue may outrank a department difference. |
| Next step | One specific action, suggested responsible role, exact evidence link | Suggested role is not an assignment. Do not invent deadlines or financial impact. |
| Secondary controls | Compare departments, View records, Listen, Analysis details | Evidence and implementation diagnostics belong behind controls. Material limitations remain visible briefly. |

Do not add a new role-selection interface. The same concise section should serve the HR head, with progressive detail for senior HR and analysts. Ask the client for design feedback after delivering this section; do not wait for permission to finish the already-authorized foundation and repairs.

## Work package 1 — Restore a trustworthy source and calculation context

Priority: P0. References: R01, R02, R03, R12.

### 1A. Source identity

- Trace the selected dataset/sheet through the API, page state, source selector, and Explorer link. Check stale requests and cached responses as possible causes, not assumed causes.
- Keep dataset, sheet, period/filter scope, and snapshot consistent. A selection change must not retain the previous source's finding, chart, or spoken text.
- Honor an explicit source URL. If that source is missing, show an explicit unavailable-source message and a deliberate selection control. Never quietly select another sheet.
- Disambiguate repeated titles with workbook and sheet names. If source identity is unresolved, withhold its numbers; a truthful selectable state is better than a polished wrong report.
- Reuse existing drill-through capability. Where precise row filtering is supported, pass the relevant filters. Otherwise open the exact source with clear filter context; do not claim a filtered case queue exists if it does not.

### 1B. Units and exposure

- Propagate the same typed metric/unit through number tiles, benchmarks, axes, tooltips, tables, narrative, speech transcript, and existing presentation inputs.
- Days are not percentages; hours are not days. Per-employee averages require a verified employee-period grain and distinct population.
- Keep recorded attendance separate from scheduled coverage. Calculate coverage only when schedules, actual time, eligible population, compatible units, and explicit excusal policy are established.
- Missing values remain unknown. Zero required exposure produces “Not applicable.” Reject inconsistent partitions; do not clamp invalid input into a plausible percentage.
- Do not invent a 30-day period or a year. Preserve uneven weekly intervals. Create monthly totals only when interval boundaries, metric additivity, and non-overlap support them; do not add cumulative totals or prorate unknown daily activity.

### 1C. Reconciliation

- ID matching establishes match coverage, not attendance/leave value agreement.
- Require verified compatible paired measures, grain, period, and a defined tolerance before saying values agree.
- Otherwise display a plain employee-ID matching statement, with primary-only and sibling-only counts. Do not call it ledger agreement.
- If no exceptions exist, state that fact without recommending investigation of zero exceptions.
- In any evidence view reached from this section, never call coincidental value overlaps verified identity joins. Downgrade/hide unsupported candidates from the verified path; defer a wholesale Explorer redesign.

Completion outcome: a user can identify the source and interpret each number without contradictory units or overstated reconciliation claims.

## Work package 2 — Convert analysis into useful HR findings

Priority: P1. References: R04–R07, R11.

Reuse the current orchestrator and shared findings. Avoid a new parallel findings system.

1. Preserve all valid candidates in the shared result. Select one main insight for display; keep other distinct supported findings available in details/chat.
2. Deduplicate the underlying business fact across Priority Insight, disparity, Decision Focus, and briefing. One department gap must not appear as four separate priorities.
3. Use this decision order as a transparent fallback, not a universal fixed recipe score:
   - source/integrity problem that makes interpretation unsafe;
   - a verified actionable exception or unmet documented obligation;
   - a material comparable change or department difference;
   - a supported descriptive summary when stronger conclusions are unavailable.
   Consider affected scope and evidence reliability within eligible candidates. Preserve the existing data-dependent ranking if it already meets this intent. Record the selection reason in details; do not build a new scoring framework for this review.
4. Raw attendance averages should use neutral language. Without comparable schedules and eligibility, label a difference as recorded attendance, not reliability or poor performance.
5. Handle ties and flat results honestly. Do not create urgency just because a sorting operation identifies a last department. Do not invent a materiality threshold; if none is documented, report the magnitude descriptively.
6. Make the next step conditional on the evidence:
   - source mismatch → confirm/reselect the correct source;
   - missing schedule → confirm the same-period duty roster before interpretation;
   - verified unmatched records → reconcile those records in the exact sources;
   - approved leave with verified capacity shortfall → review backfill;
   - no actionable exception → state no issue identified within the supported checks.
7. Suggested owner roles can be HR operations, HR business partner, or department manager, according to the task. No actual assignment, notification, policy change, or employee judgment is authorized.

For the currently uploaded HR workbook, discover what is available; do not reuse the prior 30-person test example. The next review should show genuine source-supported employee count, attendance/leave measures, a useful comparison or reconciliation, and an honest next step. If some are unsupported, explain the specific missing evidence briefly in details.

## Work package 3 — Make the section minimal and readable

Priority: P1. References: R08–R11.

- Put the business title and number first, before badges and controls. Prefer “Employee count,” “Recorded attendance,” “Approved leave,” “Attendance by department,” and “Next step.” Scope employee count as “in this source” unless active workforce membership is verified.
- Remove “Strategy S09,” “DESCRIPTIVE FACT,” library names, “Observed Measurement,” and repeated benchmark headings from the main view. Keep identifiers and methodology in an accessible details drawer.
- Aim for a short title, one sentence explaining the finding, and one sentence stating the next step. Treat length as an editorial target, not a reason to omit a material qualification.
- Use the existing SCSS system and ECharts only. Prefer a dot comparison for unordered departments and a line for actual time. Do not force charts or connect unordered departments as if they were a time sequence.
- Use k/M/B where helpful, with exact numbers on hover, focus, or tap and in the table. Percentages require valid ratios. Table headers and chart axes must state units. Keep department names readable in full.
- Keep unavailable forecasting out of the main executive space. Provide a concise reason in analysis details, using one consistent recipe policy. No new forecast modelling in this iteration.
- Keep all twenty strategy statuses in secondary diagnostics. Distinguish completed, missing data, not implemented, and failed. Do not list an unimplemented engine as data the HR user must upload.
- Fix the `raw_r` contract mismatch if still present; do not fabricate correlation to bypass it. If analysis remains unavailable, isolate the failure and show a business-friendly message while retaining technical details for diagnosis.
- Preserve the voice orb. Prevent Ask Copilot and bottom navigation from covering headings, values, tables, or controls on narrow screens. Keep controls touch-friendly and keyboard reachable.

Completion outcome: one coherent, compact business section with expandable depth, not another decorated analytics wall.

## Work package 4 — Align existing chat and narration

Keep this bounded to the same selected source and findings; no broad chatbot rewrite.

- Narration summarizes the distinct visible findings and the same limitation/next step. It must not repeat an old percentage benchmark when the UI now shows days.
- Chat must preserve the requested measure and direction. Highest attendance, lowest attendance, most employees, and lowest approved leave are different questions.
- Never answer “highest” by changing the heading of a lowest-value finding. If the requested result is not supported, say what is missing or use the existing verified calculation path.
- Check that existing presentation inputs receive corrected units and claims. Do not generate a full deck or redesign the presentation pipeline unless a failure is found in that touched path.

## Minimized verification policy — mandatory

The client explicitly wants fast delivery and no repetitive testing. Apply the following policy instead of rerunning suites after every edit:

1. **Start with inspection, not a baseline suite run.** Review the current diff and the specific reported failures once. Confirm the intended real source before using its figures.
2. **During implementation, test only a failure or unresolved consequential uncertainty.** Use the smallest relevant reproducer for source mismatch, wrong units, invalid reconciliation, or similar observed defects. Fix the root cause, then rerun that focused check. Do not run the full suite for wording, spacing, or reversible styling changes.
3. **Add only essential regression assertions for the defects being fixed**, preferably to existing tests. Do not create twenty new test files, duplicate coverage, snapshot every card, or write assertions that simply mirror implementation.
4. **Batch implementation changes, then perform one final verification pass** after all four work packages are complete:
   - run the affected existing adaptive/EDA/orchestrator backend suites once;
   - run the frontend production build once;
   - perform one combined browser walkthrough on the intended HR source at desktop and a narrow 320–390px width;
   - within that walkthrough check source drill-through, units/table, one main insight, details, overlay clearance, and one short narration playback;
   - check the four distinct chat questions once if that path changed.
5. **After a final-pass failure, rerun only the failed check and directly affected checks.** Repeat the broader pass only if a shared-contract change or unresolved cross-feature risk justifies it. Record why a repeat was necessary.
6. Use isolated test storage. Never seed, reset, or replace the running application's dataset to make tests pass. Do not claim a visual, audio, export, or integration check was performed if it was not.

Suggested final backend command, provided these files still match the touched scope:

```sh
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_adaptive_dashboard.py backend/tests/test_eda_pipeline.py backend/tests/test_insight_strategy_reproduction.py backend/tests/test_strategy_orchestrator_integration.py -q
```

Run `npm run build` once from `frontend`. Reuse existing relevant checks rather than introducing a new browser testing framework for this review.

## Deferred until after client review

- Completing all twenty strategies, advanced forecasts, causal analysis, and new domain recipe packs.
- Recruitment, attrition, engagement, learning, compensation, or financial impact without supporting uploaded data.
- New task-assignment infrastructure, notification integrations, role-specific dashboard builders, or a full case-management product.
- New chart libraries, design systems, large refactors, full historical migrations, and unrelated cleanup.
- Comprehensive load/security/accessibility certification. Do not claim these from the limited review checks.

Keep these as backlog items; do not hide their incomplete state in the analyst coverage panel.

## Handoff for the next review

Deliver a short completion note with:

1. The exact route and source used for the review, including the reporting-period limitation if applicable.
2. What visibly changed: scope, concise measures, one distinct insight, next step, and details.
3. Which R01–R12 issues were fixed, already fixed, or explicitly deferred.
4. One desktop and one mobile screenshot using the intended source, without unnecessary employee-level disclosure.
5. The single final verification result and any targeted reruns actually needed.
6. Remaining material limitations, especially missing schedules, dates, or incompatible source definitions.

Do not report “100% complete” for the whole insight platform. Report completion of this bounded HR review slice. Do not commit or push unrelated work, restore deleted files, or publish changes; provide a concise list of files changed and leave the result ready for client review.

The review is successful when HR can understand the report quickly, defend its numbers, and identify a sensible next action—not when the page displays the maximum number of metrics or strategies.
