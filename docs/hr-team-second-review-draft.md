# HR team second review — dashboard and source workbook

## Recommendation

Keep the compact workforce summary and one neutral department comparison. Before the next HR sign-off, correct the reconciliation, remove unsupported utilization/performance claims, and make the meaning of “Final Attendance” explicit. The most useful new content is a short source-reconciliation and record-review summary, not more versions of the department ranking.

This draft combines three collaborating review agents representing all sixteen requested HR roles, with the lead reviewer's live dashboard inspection and read-only source analysis. These are simulated professional perspectives, not interviews or decisions by sixteen human employees. No application changes, personnel decisions, broad test runs, or source-file edits were made.

## Evidence and client clarification

Reviewed the live Adaptive Dashboard for dataset 99674, Sheet1 (sheet 9967302) and its sibling Leave Calculation Check (9967303). Unlike the earlier review, this screen showed the intended 259-record attendance source rather than the 30-person sample. The earlier navigation failure was not re-established in this review and is not asserted as a current reproduced failure.

The client requested checking the provided CSV. The located upload is **WFO_July_2026_Test.xlsx**, stored as `backend/data/uploads/2b10b3ac8ed6466c8abdec8541f547a8.xlsx`. No CSV was found in the checked upload and attachment locations. This review uses that original workbook, its formulas and input values, and the current ingested records. If a separate CSV is authoritative, it remains unreviewed; do not claim that a CSV was inspected.

The filename states July 2026. The sheet headers specify July intervals but contain no year. The dashboard should identify the year as sourced from filename metadata until confirmed, and use that policy consistently. The current header says the reporting period is not established while the briefing says July 2026.

**Client-confirmed rule:** individual leave amounts may be whole or half days, not arbitrary tenths. This rule applies to source leave quantities, not automatically to calculated averages or differences between averages.

## What the source actually establishes

| Item | Independently checked result | Interpretation boundary |
|---|---|---|
| Primary population | 259 records with 259 distinct IDs; 11 department labels | Employees represented in this sheet, not proof of complete active-company headcount. |
| Secondary population | 211 distinct IDs in Leave Calculation Check | Different scope from the attendance sheet; do not assume missing employees are absent. |
| ID intersection | 209 matched; 50 primary-only; 2 sibling-only | Match coverage is 209/259 = 80.7% of primary and 209/211 = 99.1% of sibling records. Denominator must be named. |
| Total Attendance | 3,449 days in ingested totals; every employee's total matches the five attendance inputs | Recorded measure, not a verified duty-day denominator. |
| Approved Leaves | 540.5 days; every total matches the five leave inputs | Retain half-day precision. Approval wording does not prove paid status or policy compliance. |
| Employees with recorded leave | 209 of 259, or 80.7% | Share with some recorded leave; not an absenteeism rate. |
| Individual leave granularity | Source weekly leave inputs use valid 0.5-day increments; 31 primary employee leave totals are fractional | No invalid tenth-day source leave entries found in the examined inputs. |
| Average leave | 540.5/259 = 2.0869…, displayed as 2.1 days per employee | A valid average. It does not claim any person took 2.1 days. |
| Average attendance | 3,449/259 = 13.3166…, displayed as 13.3 days per employee | A valid recorded average; not utilization or reliability. |
| Formula definitions | N = sum of D,F,H,J,L; O = sum of E,G,I,K,M; P = N−O | The workbook explicitly calculates Final Attendance by subtracting Approved Leaves from Total Attendance. Business purpose remains unresolved. |
| Final Attendance | 2,908.5 overall; 9 negative employee results; minimum −31 | Arithmetic can be correct while the metric's business interpretation is unsuitable. Not “negative days worked” or automatic payroll deductions. |
| Zero attendance | 4 records have Total Attendance = 0 | Requires context. Not proof of unauthorized absence. |
| Correct leave comparison | Approved Leaves vs Total Approved Leaves agree for all 209 matched IDs | Numerical agreement on that matched cohort, not completeness of the entire workforce or proof both sources are independently correct. |
| Primary-only records | All 50 have zero recorded approved leave in the primary sheet | Consistent with a leave-only register, but its inclusion rule needs confirmation. Do not assign 50 discrepancy investigations automatically. |
| Sibling-only records | 2 IDs contribute 46 leave days | Accounts for the total difference: 586.5−540.5 = 46.0 days. Check roster scope, effective dates, and source eligibility before calling this an error. |
| Time buckets | July 1–5, 6–12, 13–19, 20–26, 27–31 | Five unequal calendar intervals: 5/7/7/7/5 days. They are not equal exposure weeks. |

Source references: Sheet1 headers A1:P1 and employee data A2:P260; formulas N2:P260; Leave Calculation Check A1:G212. Original formulas were read, not modified or recalculated in Excel. Aggregate calculations were independently checked from source inputs/ingested values; this is not certification of payroll meaning.

## Sixteen-role review table

| Role | What is useful now | Remove or de-emphasize | Missing item / deeper question |
|---|---|---|---|
| HR Assistant | Employee scope and recorded totals | Repeated headcount, technical strategy codes | A restricted correction queue with issue type and exact records; unknown records must not be labelled absence. |
| HR Coordinator | Department names and source links | Generic “review policy” instructions | Period, source owner, proposed responsible role, and a precise handoff for unresolved definitions or records. |
| HR Generalist | Attendance and approved-leave summaries | Unsupported reliability/utilization framing | Separate recorded leave, unknown records, off-duty time and explicit unplanned absence where available. The latter two require more data. |
| HR Specialist | Inspectable definitions and genuine reconciliations | Generic conclusions that pretend to answer every HR specialty | Confirm the specialist decision first: leave administration, benefits, compliance, or another subject. Bind the relevant policy and population. |
| HR Manager | One neutral comparison plus operational next step | Four restatements of the same low-average department | Distinguish data correction from scheduling/backfill needs. Coverage decisions require verified rosters and demand. |
| HR Director | Department coverage and a concise reconciliation | Big unavailable forecast panels and unqualified rankings | Materiality, comparable history, and whether differences are broad or driven by a few records. No worsening claim from one month. |
| CHRO | Clear scale, one priority, one next decision | Technical badges, speculative employee judgments, duplicated charts | “What should I decide now?” For this file, resolve definitions and source scope before workforce-policy conclusions. |
| Recruiter | Reliable department/employee scope as context | Recruitment conclusions inferred from low attendance | Approved requisitions, skills, location, budget and start dates. Attendance does not establish a vacancy. |
| Talent Acquisition Specialist | Clean IDs for possible future linkage | Empty recruiting cards on an attendance report | Candidate/application IDs, stage transitions, dates and outcomes to analyze conversion and aging. Not present here. |
| Talent Acquisition Manager | Verified staffing context if later joined | Hiring recommendations based on leave volume | Hiring plan, authorized positions, starts/exits, vacancy dates and pipeline evidence. Distinguish temporary cover from permanent hiring. |
| Compensation and Benefits Manager | Exact half-day leave totals and matched-value checks | “Authorized under company policy” without a policy source | Leave type, paid/unpaid status, accruals, eligibility, effective policy and balances. No entitlement/cost conclusion yet. |
| Training and Development Specialist | Department scope; possible scheduling context | Inferring employee learning from an elearning employer's attendance file | Assignment, eligibility, due/completion dates, assessments and skills. Do not infer training need from nonattendance. |
| Employee Relations Manager | Reliable records and neutral explanation | “Attention/Top Tier” as employee or department judgment | Clarification/correction route and contextual investigation. Never infer disengagement, misconduct or motive from these totals. |
| Payroll Specialist | Reconciled leave totals and source formulas | Treating Final Attendance as payable days or negatives as deductions | Payroll period, paid/unpaid rules, standard working exposure and the approved meaning of the subtraction. Prioritize the 9 negative results for definition review. |
| HR Operations Analyst | Known-answer totals, unique IDs and bucket reconciliation | First-same-header metric joins and unexplained scores | Semantic pairing, exact denominators, grain, units, source version and paired-value audit. Reconcile the 46-day cross-source difference. |
| Diversity and Inclusion Specialist | Neutral cohorts and comparison limitations | Public singleton ranking or demographic inference | Consistent small-cohort treatment and exposure comparability. Demographic fairness analysis is a separate scope requiring appropriate data and access—not mandatory for this attendance upload. |

## Requests to remove, consolidate, or correct

### P0 — Replace the misleading 15.3% ledger agreement

The displayed 15.3% is 32/209 matches between **attendance in the first July bucket** and **leave in the sibling's identically named bucket**. Same header text does not mean same measure. This is a semantic comparison error, not evidence that 84.7% of leave records disagree.

Remove that percentage and its “Agreed records” chart from the HR narrative. Pair primary Approved Leaves with sibling Total Approved Leaves, and pair weekly primary `Leaves(...)` fields with the sibling's leave buckets after verifying definitions. The checked total comparison is **209 of 209 matched leave totals agree**. Show the remaining scope difference separately: 50 primary-only with zero recorded leave; 2 sibling-only with 46 leave days. Do not combine the mismatch narrative with a false urgency score.

Current code location: `backend/app/services/adaptive_dashboard/enterprise.py`, shared-measure selection around lines 845–866 chooses same-named columns. Require measure identity and units, not string equality.

### P0 — Remove unsupported utilization and preserve half-day totals

“86.5% attendance utilization” and “13.5% leave impact” use attendance/(attendance+leave), without a documented scheduled-day denominator. That fraction does not establish workforce utilization, shortage or policy compliance.

Replace the comparator with recorded attendance and leave totals only if useful. Display **540.5 leave days**, not 540; **2,908.5 Final Attendance units** must not be truncated to 2,908 or presented as worked/payable days until the definition is confirmed. Avoid showing an unexplained subtraction as a “lift.”

### P0 — Withhold operational interpretation of Final Attendance

The formula is known: Total Attendance minus Approved Leaves. Its meaning is not. If Total Attendance already counts attended days, subtracting leave again may be conceptually wrong for a “worked days” metric; if it is another bookkeeping balance, negative results may have a different meaning.

Keep the original values intact. Add a definition-review item for the 9 negative results, and do not generate “unusual attendance,” performance, pay or absence conclusions from this field until clarified. Do not clamp negatives to zero.

### P1 — Consolidate duplicate findings

Keep the compact employee count; remove its separate duplicate full card from the primary view. Combine the priority comparison, legacy disparity and Decision Focus into one canonical finding with expandable detail. Keep a Listen control; a transcript need not become a fourth visual restatement. Keep workforce-by-department only as useful secondary context.

The page currently says **6.1 days across 10 qualified departments** in one place and **6.2 days across 11 departments** elsewhere because the latter includes a one-person group. Use one explicit comparison population; show excluded/small-group counts without exposing a singleton's attendance. Preserve that group's contribution to overall totals while withholding identifiable detail as appropriate.

### P1 — Remove evaluative tiers and technical filler

Remove “Top Tier,” “Attention,” and “relative reliability & capacity” from raw attendance averages. More recorded days are not automatically better performance. Replace the long “Department Recorded Presence Disparity…” headline with “Recorded attendance by department,” followed by a short factual finding.

Move “Strategy Coverage & Audit Screening,” recipe numbers, chart-library names and all-domain missing inputs into details. Keep the useful distinction between failed analysis and unavailable product features. Do not request recruiting or commercial inputs merely because their recipes exist.

### P1 — Correct anomaly distance and period narrative

Exception Watch displays **16.1 days**, a typical range **7.9–13.8**, and **5.2 days above range**. From those displayed values, distance above the upper bound is approximately **2.3 days**. If 5.2 measures a distance from a central baseline, name that baseline instead; do not label it distance above the range. This exception also depends on the unresolved Final Attendance meaning.

Replace “weekly” where it implies equal exposure with “Recorded attendance by July interval,” showing exact interval dates. The last and first buckets are shorter. Remove claims that all five are comparable complete weeks. Resolve the year once from documented source metadata rather than presenting “unknown” and “July 2026” simultaneously.

### P1 — Make controls do what their wording promises

The priority card's Listen callback currently scrolls to the separate briefing. Either start the narration from the button or call it “Open briefing.” Source-wide View Records links do not yet constitute a filtered issue queue; use honest wording or pass the finding/cohort/period filters. Preserve the voice orb and avoid content obstruction.

Use labels and next-step roles from the actual selected finding. The card currently contains department-gap wording that would mislabel a reconciliation or data-quality finding if that becomes the priority.

## Requests to add now from the available data

| Addition | Proposed display | Why HR benefits |
|---|---|---|
| Explicit aggregate labels | “Average recorded leave: 2.1 days per employee”; details “540.5 ÷ 259” | Resolves the decimal ambiguity without corrupting the calculation. |
| Exact recorded totals | 3,449 attendance days; 540.5 leave days; known period/source qualification | Useful for reconciliation; retain source precision. |
| Correct matched-leave check | “209 matched employee leave totals agree” | Replaces the false discrepancy story with defensible evidence. |
| Scope reconciliation | “2 leave-register IDs not in attendance source; 46 leave days” plus contextual note about 50 zero-leave primary-only IDs | A focused source/roster review instead of 52 automatic error tickets. |
| Definition review | “Confirm Final Attendance meaning; 9 negative results” | Prevents misuse in payroll or performance reporting. Restricted supporting records, no public named list. |
| Leave participation | 209 employees with recorded leave, clearly identified as such | Separates how many people took leave from how much leave was recorded. Optional secondary detail, not another compulsory tile. |
| Department context | Cohort size, mean, median and leave total in one accessible comparison table | Distinguishes broad patterns from averages affected by a few observations. |
| Arithmetic integrity result | “Attendance and leave bucket sums reconcile for 259 employee records” in details | A supported strength; no invented issue when arithmetic checks pass. |

## Deeper analysis worth pursuing

1. **Explain cross-source totals before searching for correlations.** The 46-day excess in the leave-check sheet is fully accounted for by two sibling-only IDs. Determine whether they are joiners, leavers, transfers, a broader roster scope or erroneous inclusions. The file alone does not identify the cause.
2. **Distinguish leave volume from leave intensity.** RQI 1stop/LLP records 166 leave days across 65 employees; Corporate Functions records 64.5 across 19. The former has greater recorded volume; the latter averages about 3.4 days versus 2.6. Neither is automatically “worst.” Show the metric requested by the manager and the population behind it.
3. **Look behind attendance means.** Operations and Infrastructure has mean 17.23 and median 18.5 recorded days; Design has mean 11.11 and median 11.0. These descriptive differences persist in the medians, but exposure, roles and work patterns remain unknown. Do not claim statistical significance or causes from this observation.
4. **Audit the measure definition rather than correlate derived columns.** Final Attendance is exactly Total Attendance minus Approved Leaves. Correlation among these three contains built-in arithmetic dependence and is not discovery of an independent HR driver.
5. **Check weekly leave reconciliation with correct semantics.** Compare primary leave buckets, not attendance buckets, against the sibling's matching intervals. Preserve half-days and count unresolved comparisons separately from disagreements.
6. **Evaluate within-month concentration cautiously.** Show recorded attendance/leave across the five exact intervals. Do not infer weekday patterns, consecutive missed shifts, or trends from unequal buckets without schedules and daily records.
7. **Check department labels before ranking.** A one-person “Alliance Initiative” group could be legitimate or incomplete categorization. Request mapping confirmation; do not automatically merge it with other similarly named departments.
8. **Separate recorded activity from expected activity.** Rosters, holidays, work fraction, joining/leaving dates, remote-work rules and attendance capture definitions are needed before unplanned-absence rates, required coverage, staffing deficits or pay conclusions.

## Realism and formatting rules

| Value type | Rule | Example |
|---|---|---|
| Employee headcount or number of events | Whole-number count of distinct eligible entities/events | 259 employees; never 259.2 employees. FTE is a different measure. |
| Individual source leave amount | Under the client's rule, nonnegative multiples of 0.5; confirm adjustment handling separately | 2 or 2.5 valid; 2.1 flagged, not silently rounded. |
| Total leave days | Preserve 0.5-day increments where present | 540.5 days; do not truncate to 540. |
| Per-employee average or difference of averages | Decimal results are mathematically valid; explicitly label the aggregation | 2.1 days per employee on average, or 6.1-day difference between averages. |
| Individual attendance | Observed source values are integers; attendance capture policy still needs definition | Do not impose leave granularity on attendance or infer remote-work treatment. |
| Negative derived balance | Preserve source value, withhold unsupported duration/pay interpretation | −31 in Final Attendance requires definition review, not rounding or zero substitution. |
| Day-to-hour conversion | Require a documented hours-per-workday rule | 0.1 workday is not inherently 2h24m or 48m. |
| Percent | Show its eligible denominator; distinct ratios need distinct names | 80.7% primary ID match coverage is not attendance rate. |

If the client prefers fewer decimals on the executive page, use the exact whole/half-day **total** as the hero number and put the clearly labelled average in details. Do not round every average to a half-day: doing so changes the reported statistic and can hide meaningful differences.

## Questions still requiring business ownership

Do not ask again for arithmetic that the workbook answers. The source already establishes the subtraction formula, half-day leave inputs, and the July intervals. The remaining questions concern meaning and policy:

1. What does Final Attendance represent operationally—net recorded attendance, payable balance, adjustment, or another measure—and is subtraction intended? What should a negative value mean?
2. Does the filename's July 2026 identify the actual reporting year or a test copy's label? The sheet itself does not establish a year.
3. Does Total Attendance represent office presence, all work including remote work, logged punches, or another activity? The WFO filename is a clue, not a definition.
4. Is Leave Calculation Check intentionally limited to employees with leave? All 50 primary-only employees have zero recorded leave, which supports that hypothesis but does not prove the inclusion rule.
5. Why are two leave-register IDs outside the attendance source, and which population is authoritative for this report?
6. Are missing workdays explicitly unplanned absence, off-duty days, remote work, or simply unrecorded? The current fields cannot separate them.
7. Are schedules comparable across departments, and what is the organization's materiality threshold before action?
8. Should the one-person department be corrected, retained as a real group, or rolled into a privacy-safe reporting group under a documented rule?

Recruitment, training, benefits, payroll costs and D&I outcomes need their own relevant inputs only if the client wants those decisions. Do not request every HR system field at once or label this attendance workbook incomplete for unrelated roles.

## Proposed next-review story and execution order

**Suggested story, after correcting the calculations:** “This source represents 259 employees. Recorded attendance totals 3,449 days and approved leave 540.5 days. Leave totals agree for all 209 matched employees across the two sheets. Two leave-register IDs outside the attendance source account for 46 additional leave days. Confirm their inclusion and the meaning of Final Attendance before using that derived measure operationally.”

A neutral department comparison can be secondary. This story is more decision-useful than repeatedly ranking the lowest attendance average or presenting a false 15.3% agreement rate.

1. Correct semantic reconciliation and half-day display; quarantine unsupported Final Attendance interpretation.
2. Consolidate duplicate cards; remove utilization/performance tiers and unavailable forecast from the main view.
3. Add exact totals, the source-scope reconciliation, and a precise next action with restricted supporting records.
4. Align period, population, units and small-group policy across chart, table, narrative and voice.
5. Return this bounded result for review. Defer additional role dashboards and unsupported analyses.

Verification should remain light: reproduce each identified failure once, fix it, then perform one final affected-path check on this actual source. Confirm 209 matched leave totals, the 46-day scope difference, preservation of 540.5 days, no fabricated source 0.1 increments, and consistent display/narration. Re-run only failed or directly affected checks. No broad repeated testing is requested for this review draft.
