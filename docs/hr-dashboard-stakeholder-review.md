# Adaptive Dashboard: HR stakeholder review

## Decision

The dashboard is becoming a useful descriptive attendance report, but it is not yet ready to serve as an HR management decision dashboard. It helps a reader notice a departmental difference; it does not yet reliably establish the reporting period, whether that difference warrants action, which records require attention, or what an accountable next step should be.

Do not add more cards before fixing source consistency, units, reconciliation claims, and repetition. The primary design objective should be: **an HR leader can understand the situation, its limits, and the next useful action within one minute.**

This is one review through four stakeholder lenses, not a claim that four human HR professionals were interviewed. Expectations below are product recommendations, not findings about employee performance or legal policy.

## Review scope and evidence

Reviewed the running application at `http://localhost:5175/#adaptive`, its rendered text, a narrow approximately 320px viewport, the priority card's accessible table, the expanded strategy coverage panel, the enterprise audit modal, and a source drill-through. Read relevant local calculation code to investigate claims. No employee-level records are reproduced here. No application code was changed for this review.

The initial dashboard showed **Attendance Data, 30 rows**, Engineering and Sales with 15 employees each, recorded attendance averages of 21 and 18 days, and a company average of 19.5. These are observations from the displayed page, not independently audited workforce facts. The page reported **3 completed strategies, 12 needing inputs, 1 failed, and 4 not implemented**.

Important scope limitation: navigating to the displayed Staff Roster source URL (`sheet_id=83101`) opened a different **211-row Leave Calculation Check** in Data Explorer. Returning to Adaptive Dashboard showed a **259-row Employee Attendance Summary** selection but “No uploaded sheet found.” Refresh did not resolve it during this review. Consequently, this review does not certify the real 259-row HR report, current backend data consistency, or the initial 30-person sample as the intended production dataset. The initial sample resembles an existing test fixture; the cause of the mismatch is not established.

Desktop layouts, full accessibility conformance, actual speech playback, and exported slides were not verified in this review. Transcript content was reviewed. Previous test-pass counts are not substitutes for these checks.

## What each HR stakeholder expects

| Perspective | The question they arrive with | What currently does not help enough | Expected outcome |
|---|---|---|---|
| HR operations / HR executive | “Which attendance or leave records must I resolve today?” | Department averages, technical coverage statuses, and generic advice do not identify a work queue. | An authorized exception queue: issue type, affected count, period, responsible team, and a filtered source link. Distinguish missing punches, pending approvals, and confirmed unplanned absence only when evidence supports each. |
| Senior HR / HR business partner | “Is this department's difference explainable and persistent?” | A lower attendance average is singled out without a visible common period, schedule, employment fraction, or eligibility context. | Comparable department measures, prior-period change, planned versus unplanned time away, and explanations supported by recorded reasons. Alternative explanations should remain hypotheses. |
| HR head | “Where is the material people or service risk, and what decision do I need to make?” | Four versions of the same attendance observation, a large unavailable forecast card, and engineering audit language dilute the message. | At most a few distinct priorities with business impact, confidence boundaries, recommended action, owner role, and review date. Cost or staffing impact only when measurable. |
| HR data analyst | “Can I reproduce this number and defend its interpretation?” | Some units contradict one another; matching IDs is labelled ledger agreement; strategy failures expose internal errors. | Formula, grain, eligible denominator, period, exclusions, missingness, deduplication, metric definition, and source snapshot. Drill-through must preserve the exact source and filters. |

## Findings from the displayed dashboard

### R01 — Source identity is not dependable enough for a management review [P0]

**Observed:** The initial 30-row Attendance Data dashboard linked to Staff Roster, but the link opened an unrelated 211-row sheet. Returning showed another selected source and an unavailable-data error.

**HR reaction:** “Which workforce am I reviewing? Can I trust any conclusion or export?” This is more serious than a cosmetic issue.

**Required:** Preserve dataset, sheet, period, and snapshot through dashboard, Explorer, Copilot, voice, and exports. If a source no longer exists, explicitly say so and offer a deliberate source selection. Never silently substitute a different sheet. Show workbook + sheet in the selector when titles repeat. Investigate cache, backend source availability, and URL selection separately; do not assume which one caused this observation.

**Acceptance:** Click every source link from a known dataset; the destination header, selected sheet, row scope, and calculation evidence must match. A removed source must produce an explicit unavailable-source state, not an unrelated report.

### R02 — A days benchmark is presented as a percentage [P0]

**Observed:** Engineering is shown at 21.0 days and Sales at 18.0 days, but the department panel labels the benchmark **19.5%**. The executive transcript repeats “company attendance averaged 19.5%.”

**HR reaction:** “Is attendance really only 19.5%, or is this 19.5 days?” The two interpretations imply radically different situations.

**Required:** Carry typed units through every card, comparison, accessible table, transcript, and export. Here the displayed comparison requires **19.5 recorded days per employee**, subject to confirmation of row grain and period. Do not calculate an attendance percentage without a valid scheduled-exposure denominator.

### R03 — “100% ledger agreement” exceeds the demonstrated evidence [P0]

**Observed:** Enterprise Synthesis claims 100% attendance/leave ledger agreement for 30 matched employees. Its audit describes ID matching but does not name the paired numerical measures, units, period, or difference tolerance. The code in `enterprise.py` sets `agreed_count = matched_count` when no shared measure is available.

**HR reaction:** “Have leave balances actually been checked, or have employee IDs merely matched?” This could create unjustified confidence before payroll or management reporting.

**Required:** Separate **employee record match coverage** from **metric agreement**. The latter requires explicitly compatible values on both sides and a documented comparison. When only IDs match, say “30 employee IDs matched across the two sources”; withhold any leave-value agreement claim.

**Acceptance:** A roster containing IDs and roles, but no leave measure, must never establish leave ledger agreement. A real reconciliation must show matched, mismatched, unresolved, and unmatched counts with the exact compared metrics.

### R04 — One observation occupies too much of the page [P1]

**Observed:** Priority Insight, departmental disparity, Decision Focus, and Executive Briefing all restate the Engineering/Sales attendance difference.

**HR reaction:** “Am I learning four things, or reading the same thing four times?” Repetition increases perceived importance without adding evidence.

**Required:** One canonical finding, one chart, and one action. Place the fuller department breakdown behind “Compare departments.” Let the briefing summarize distinct findings instead of creating another full card for the same fact. Preserve approved reference pages rather than deleting them.

### R05 — The reporting period is missing from the main decision context [P1]

**Observed:** The header shows “30 records” where a reader needs time coverage. An average of 18 days is not interpretable without knowing the interval and eligibility.

**Required:** Display exact reporting interval, year, refresh time, and completeness of the interval when known. If unknown, state “Reporting period not established.” Do not invent dates. Distinguish upload time from the period represented by the data.

### R06 — Descriptive ranking still looks like performance judgment [P1]

**Observed:** “Top Tier,” “Attention,” ranked departments, and a Sales-focused action accompany recorded-day averages without a verified duty roster. The priority narrative does acknowledge the missing roster, which is an improvement.

**HR reaction:** “Are you penalizing approved leave, part-time schedules, new starters, or different work patterns?” A recorded-day difference alone does not establish poor reliability, disengagement, or misconduct.

**Required:** Use neutral labels such as “Higher recorded average” and “Lower recorded average.” Explain comparability before assigning concern. Schedule-adjusted coverage is a different measure from raw recorded attendance. If all groups are similar, explicitly report no material observed gap rather than selecting a nominal loser.

### R07 — Recommended actions are neither specific nor consistently necessary [P1]

**Observed:** “Review scheduling coverage and approved-leave patterns before changing policy” is generic. Enterprise Synthesis asks the user to “Investigate the 0 primary-only and 0 sibling-only exceptions.”

**Required:** Generate actions conditional on actual evidence. Zero exceptions should produce “No unmatched employee IDs found in this comparison,” not an investigation task. Where schedules are missing, recommend obtaining/confirming the roster for the same period before judging the department. Suggest an owner role, evidence needed, and intended decision; do not invent assignments or deadlines.

### R08 — Engineering diagnostics are too prominent [P1]

**Observed:** “Strategy S09,” “DESCRIPTIVE FACT,” “Observed Measurement,” “Visual Evidence,” “Live Interactive ECharts,” and “Recommended Diagnostic Check” are prominent. The coverage panel exposes an attribute error: `'RelationshipInferenceResult' object has no attribute 'raw_r'`.

**HR reaction:** “Why am I reading system implementation details instead of a workforce report?”

**Required:** Use familiar business labels. Move recipe IDs, libraries, claim classifications, and raw errors into analyst diagnostics. A visible failure can simply say “Relationship analysis unavailable; other results are unaffected.” Provide an actionable retry/details control without claiming a successful analysis.

### R09 — Forecast messaging is oversized and internally inconsistent [P1]

**Observed:** The main card explains a workforce governance exclusion and a rule requiring at least 12 periods. The coverage panel says at least 6 periods are required. Raw mathematical markup is visible in the main rule text.

**Required:** Use one recipe-specific policy and explanation. Distinguish individual-outcome forecasting from permissible aggregate operational planning. A lack of a defensible forecast should appear as a short limitation in the relevant context, not a major empty executive panel. More observations alone must not imply forecast readiness.

### R10 — Narrow-screen reading is obstructed and too lengthy [P1]

**Observed:** In the narrow viewport, the fixed Ask Copilot control overlaps report content, including the priority heading/table area. The number is pushed below several badges and controls. The paragraph includes the redundant wording “presence days/emp per employee.”

**Required:** Put the familiar title and number first. Use one short implication and one short next check. Keep floating controls clear of reading and interaction areas, preserve the requested orb animation, and reserve space for bottom navigation. Use focus/tap-accessible details, not hover-only explanations. Confirm exact numbers and units in the accessible table; it currently says only “Value.”

### R11 — Analysis coverage confuses product capability with data sufficiency [P1]

**Observed:** The panel now honestly distinguishes completed, failed, and not implemented. That is progress. However, “Missing Inputs” also lists engines or implementation capabilities, which an HR user cannot supply. The page foregrounds technical strategy counts ahead of workforce outcomes.

**Required:** Separate “You can add this data” from “Feature not available yet” and “Analysis failed.” Show only decision-relevant gaps in the executive view. Keep the full 20-strategy register in analyst details. A generic HR attendance sheet should not feel defective for lacking sales funnels or commercial cost data.

### R12 — Drill-through currently adds noise rather than resolving doubt [P1]

**Observed:** The different sheet opened in Explorer advertises “verified” cross-sheet linkages including Full Name to July attendance buckets, and many N:N bucket joins. These were not independently validated and cannot support a reliable employee identity join merely because values overlap.

**Required:** A management finding's drill-through must open the exact supporting calculation and relevant rows/aggregates, not an overwhelming generic diagnostics page. Show verified semantic key relationships separately from speculative candidates. Never promote coincidental numerical overlap to verified identity.

## Missing HR information: what can and cannot be expected

These are candidate requirements, not 20 mandatory cards. The reviewed sample does not support every item. Select only evidence-supported, relevant insights; otherwise offer a precise input request in secondary details.

| # | Leadership question / missing item | Evidence needed | Intended presentation and decision |
|---|---|---|---|
| 1 | Which workforce and period does this represent? | Source, unique entity definition, observed period, refresh/snapshot | Compact scope header; prevent misinterpretation before any action. |
| 2 | How many employees are represented, and is that the full workforce? | Distinct IDs; authoritative roster for completeness | Employee count tile; “in this source” until active workforce coverage is verified. |
| 3 | Where are records incomplete or inconsistent? | Missing/invalid/duplicate checks; expected register for missing people | Record-review count and a filtered queue, distinct from employee absence. |
| 4 | What attendance was actually recorded? | Defined attendance measure and verified employee-period grain | Days or hours summary; distribution where useful; no invented attendance rate. |
| 5 | What approved leave was recorded? | Leave units, authorization semantics, compatible interval | Leave total and per-employee measure; show planning implications without treating leave as misconduct. |
| 6 | What required work exposure was covered? | Roster, eligibility, actual worked time, explicit excusal policy | Coverage ratio with numerator/denominator; not applicable when required exposure is zero. |
| 7 | How much absence is explicitly unplanned? | Explicit absence classification plus eligible exposure | Count and rate; unknowns shown separately. Never derive it from calendar days minus attendance. |
| 8 | Are unknown records distorting conclusions? | Expected records and unresolved status | Unknown share beside any rate; prioritize correction when material. |
| 9 | Which departments differ on a comparable basis? | Shared period, units, exposure, employment fraction and eligibility where relevant | Neutral dot comparison with cohort sizes and explicit comparison basis. |
| 10 | Is the concern new, persistent, or improving? | Comparable historical periods | Time line with gaps and partial periods visible; no growth claim from a single period. |
| 11 | Are incidents recurring rather than isolated? | Timestamped, deduplicated incidents and continuity rules | Aggregate recurrence summary; protected drill-down for authorized case review. |
| 12 | Are specific days or shifts repeatedly affected? | Daily schedules and observed attendance by shift | Calendar/shift pattern with exposure normalization. Weekly totals cannot identify Mondays or missed days. |
| 13 | Is planned leave creating an operational coverage gap? | Future approved leave, scheduled demand, skill/role coverage | Coverage-by-period view; suggest backfill review only where a supported shortage exists. |
| 14 | What reasons are actually recorded? | Reason categories, event linkage, missing-reason count | Top reasons + Other + Unknown; separate multi-label reasons and avoid causal inference. |
| 15 | Are approvals or corrections delayed? | Submission/approval timestamps, statuses, applicable service targets | Open queue and aging; no overdue claim without a defined target. |
| 16 | Do the attendance and leave sources agree? | Verified IDs and compatible paired measures/periods | Match coverage and value agreement separately; actionable discrepancy list. |
| 17 | Could roster changes explain the average? | Start/end dates, transfers, FTE/schedule changes | Comparable cohort or standardized comparison, not automatic performance labels. |
| 18 | What is the service or financial impact? | Demand/capacity linkage, rates/cost definitions, overtime or backfill records | Evidence-based impact range or total; no invented monetary cost of leave. |
| 19 | Is the pattern broad or driven by a small subset? | Suitable raw distribution, verified grain, privacy controls | Distribution/tail summary with meaningful units; no public individual ranking. |
| 20 | Did the previous intervention help? | Agreed action, owner, review date, comparable follow-up data | Action tracker with observed change; distinguish improvement from proven causal effect. |

Recruitment, attrition, learning completion, engagement, and compensation should become available when the uploaded subject supports them. They should not be inferred from an attendance sheet merely because the company operates in education or because HR commonly monitors them.

## What the first screen should communicate

For the initially observed 30-person sample, a proposed factual layout is:

1. **Scope:** “Attendance Data · 30 employees represented · Reporting period not established.” Confirm distinct IDs before using the employee count.
2. **Core measures:** Employee count; recorded attendance with its unit; approved leave only after confirming its definition. Avoid presenting active company headcount without an authoritative roster.
3. **One comparison:** “Recorded attendance differs by 3 days per employee.” Supporting text: “Engineering 21; Sales 18. The source does not establish comparable scheduled exposure.” Do not call this a performance deficit.
4. **One next step:** “Confirm that both departments cover the same reporting period and scheduled workdays before interpreting the difference.” Proposed owner role: HR operations with department managers.
5. **Details:** Compare departments, inspect records, or listen to the same concise summary. Keep technical strategy coverage under analysis details.

These numbers illustrate the observed initial screen only; do not hardcode them or apply them to the separate 259-row dataset. A real date range, reliable leave measure, and another independent supported finding should replace unknowns when evidence becomes available.

## Wording and visual rules

| Current wording/pattern | Preferred treatment |
|---|---|
| Department Recorded Presence Disparity | Recorded attendance by department |
| Observed Measurement | Name the actual measure: Attendance gap, Recorded days, or Employee count |
| Observed Peer Comparison / Benchmark comparison baseline | Comparison, followed by its actual reference and unit |
| Recommended Diagnostic Check | Next step |
| DESCRIPTIVE FACT / Strategy S09 | Put claim boundaries and recipe identifiers in details |
| Top Tier / Attention without verified exposure | Higher/lower recorded average; no performance judgment |
| Enterprise Synthesis | Records across sources, or the exact business reconciliation |
| Ledger agreement when only IDs match | Employee ID match coverage |
| Investigate zero exceptions | No exceptions found in this specific check |
| 20 strategies evaluated | Optional analysis-details summary with honest execution states |

Use tiles for scale, lines for actual time series, dot comparisons for unordered departments, and composition visuals only when parts genuinely reconcile. Do not connect department names with a line to imply a time sequence. A chart must add understanding; three equal bars for matched records can often be replaced with a concise reconciliation statement. Keep full labels and exact values accessible by keyboard and touch. Short material limitations remain visible; extended audit detail can be collapsed.

## Prioritized delivery and acceptance

| Order | Work | Owner role | Evidence required before acceptance |
|---|---|---|---|
| 1 | Fix source identity, navigation, and stale/unavailable-source behavior | Backend + frontend lead | Demonstration that dashboard, Explorer and source links retain the same source; explicit error for unavailable source. |
| 2 | Correct unit propagation and separate matching from value agreement | Analytics engineer + HR analyst | Known-answer fixtures; matching days in card, benchmark, transcript and table; no agreement claim without paired values. |
| 3 | Fix the relationship execution error and make coverage states meaningful | Backend lead | Failure-isolation check; no raw exception in the executive view; implementation gaps not blamed on missing user data. |
| 4 | Consolidate repeated findings and simplify the priority card | Product designer + frontend lead | One finding presented once, no technical badge stack, visible title/value/action on narrow screens, no floating-control obstruction. |
| 5 | Add the missing scope and a genuinely actionable drill-through | Product manager + HR operations reviewer | A user can identify period/population and reach the exact supporting records without searching another sheet. |
| 6 | Extend supported HR analyses incrementally | HR analyst + data scientist | Each new insight has required inputs, formula, limitations, action, and realistic acceptance fixture; no fabricated denominators or causes. |

Role-based review tasks for the next sign-off:

- **HR operations:** identify the records needing correction and open the correct filtered view; a zero-issue state should not assign unnecessary work.
- **Senior HR:** explain why departments differ, what is still unknown, and which contextual data is needed before interpretation.
- **HR head:** describe the material issue and next decision in under one minute without reading audit terminology or four versions of one finding.
- **HR analyst:** reproduce displayed values, verify source/period/units/denominators, and show why an unavailable analysis was withheld.

Approval should depend on these tasks succeeding with the intended HR workbook, not on the existence of twenty registry entries or passing helper tests. Keep this review separate from application implementation: the current request is to document the stakeholder assessment, not to redesign the dashboard immediately.
