# Why HighView presentations do not match the HR reference deck

Review date: 2 October 2026. This is a diagnostic report, not an implementation change.

## Materials inspected and limits

- Reference: `/Users/vinayksharma/Downloads/WFO_July_2026_Review.pptx`. All ten slides' text, tables, chart series, and available notes were extracted. The reference was rendered, and representative slides were inspected visually.
- Generated output: `backend/data/exports/presentation_deck_5064d9746f04.pptx`, together with its saved presentation specification and validation metadata. A second saved deck showed similar wording.
- Existing standard generation route, director prompts, plan adaptation, deterministic builders, shared evidence collection, HR attendance analysis, claim verification, and review gates.

The reference's underlying Excel workbook was not supplied. Its numbers and interpretations are examples of the desired communication, not independently verified facts about the current workspace. The inspected workspace currently contains car data, not that WFO workbook. The generated car deck is useful evidence of a general pipeline defect, not a same-dataset comparison with the reference.

The reference rendered successfully. Rendering the generated deck with the independent artifact-tool importer failed on a negative chart-axis identifier. Its exported text and native chart data were inspected through the PPTX package instead. That compatibility finding does not establish how PowerPoint displays the file, and is separate from the content problem.

## What the reference gets right for an HR presenter

It organizes the review around questions HR can explain:

| Slides | Purpose | Communication pattern |
|---|---|---|
| 1–2 | Identify the month and summarize attendance | Employee count, office days, median days, approved leave, a short reporting caveat |
| 3 | Explain weekly patterns | A clearly labelled chart plus specific observations |
| 4 | Compare departments | Average office days and headcounts, with a caution about long leave |
| 5 | Identify the group needing attention | Attendance bands and a concrete employee count |
| 6–7 | Explain problems with the measures | A worked example, calendar/working-day distinction, and affected IDs |
| 8 | Identify records to verify | Specific exceptions, missing roster entries, and gaps |
| 9 | Say what reconciles correctly | Concrete counts of successful checks |
| 10 | Give practical next steps | Confirm policy, correct the formula, review leave units, verify records |

This is substantial analysis. Its explanations connect the analysis to attendance decisions instead of requiring the presenter to explain software verification machinery. Data-quality findings remain visible where they affect the HR conclusion.

## Confirmed root causes

### 1. The planner starts with an unrelated, predetermined business conclusion

`backend/app/services/presentation/director/narrative_planner.py:132` puts this literal example inside the requested JSON response:

> Operational throughput is anchored by strong core volume, while top-quartile performance dispersion presents an immediate margin optimization opportunity.

The narrative prompt supplies the **count** of evidence items but does not present their actual findings in that portion of the prompt. It encourages an assertive conclusion while supplying a ready-made commercial conclusion.

The inspected output starts “Operational throughput anchored by core volume” and repeatedly discusses margin optimization. Its source is `car-sales-extended.csv`. This is strong evidence of prompt anchoring and inadequate grounding. An exact model-call trace was not captured, so copying behavior is inferred from the prompt/output correspondence rather than asserted as a captured runtime event.

**Consequence:** the story can come from the example and generic business vocabulary instead of the source's actual findings.

### 2. The slide writer receives references without enough evidence content

`director/slide_planner.py:81` reduces the main information units to IDs, titles, evidence IDs, and source types. It does not include their complete statements, metric values, units, or comparisons in this summary.

At `slide_planner.py:119`, the JSON example explicitly suggests:

```text
[Evidence] Ground truth metric from data.
[Context] Comparative benchmark.
[Impact] Strategic implication.
```

The downloaded deck repeats these prefixes and references such as `DATASET_PROFILE`, `CURRENT_EVIDENCE`, and `EVID-KPI-01` in the body. A reference ID is a useful internal binding but is not a presenter-friendly statement of the underlying result.

**Consequence:** the writer generates descriptions of evidence instead of explaining the evidence to the audience.

### 3. Technical audit material is deliberately written into audience content

The deterministic path also contains the problem, so switching models alone will not fix it:

- `storyline_generator.py:123` always adds an audit-trail section with a focus on a cryptographic SHA-256 seal.
- `builders/governance_builder.py:263` constructs a slide about “100% Traceability Under Cryptographic Seal.” Its body names SHA-256, SQLite, tolerance thresholds, and record-level lineage.
- `builders/common.py:58` prepares presenter answers about deterministic SQL and snapshot hashes.
- `director/narrative_planner.py:88` treats HR as part of generic Operations/General, with default sections about throughput, dispersion, governance, and audited evidence.
- The fallback slide planner supplies similar technical sections and repetitive evidence/benchmark/action bullets.

**Consequence:** implementation details reach both slides and speaker material because the content builders put them there. This is not merely an exporter or theme problem.

### 4. The “language polish” phase does not perform audience editing

In `pipeline_orchestrator.py:363`, the executive-polish loop strips surrounding whitespace from titles and fills a missing subtitle from the key message. It does not rewrite jargon, check HR comprehension, or prepare a plain-language explanation.

**Consequence:** the displayed phase name promises more than the implementation does. Technical or vague content survives unchanged.

### 5. Validation can pass a slide whose business meaning is unsupported

`director/plan_validator.py:77` checks whether a slide has evidence references. Its `is_valid` expression at line 97 checks duplicate concepts and a minimum slide count, without making unsupported claims or unanswered questions blocking conditions.

`review_gates.py:174` primarily passes the storyline gate based on existing titles, title length, and at least three slides. `claim_verifier.py` focuses on numerical claims. These checks do not establish that a qualitative claim is supported by the cited evidence.

The inspected generated deck contains:

- “Unit sales correlate strongly with footfall in top performers”
- “Seasonal highs confirm operational resilience”
- “Implementing top-quartile standards projects immediate margin uplift”

The current source schema includes make, colour, odometer, doors, price, and derived interactions. It does not provide footfall, time-series dates, cost/margin inputs, or a measured ROI scenario supporting those statements.

Nevertheless, its saved numerical validation reports **24 checked items, 24 passed, zero discrepancies**. That is numerical-check coverage, not proof that the story is correct.

**Consequence:** adding an evidence ID can make a claim look grounded without proving the evidence supports its meaning.

### 6. Adaptation can attach an unrelated chart or unsupported default metric

`director/plan_adapter.py:188` attaches charts primarily by visual type and positional fallback. A generic bar-chart request can bind the available bar chart even when its measure does not support the proposed slide title.

In the actual PPTX, a slide about performance and margin opportunities displays an odometer-by-make chart. A slide discussing seasonal performance uses a colour distribution. The chart numbers may be real while the headline describes a different concept.

The adapter also contains hard-coded defaults such as “System Resilience: 100% / Zero service failures” at line 192, and proposed targets such as compressing dispersion by 15% within 90 days at line 85. These are not automatically measured facts. Proposed targets need explicit proposal status and appropriate user/domain context.

**Consequence:** correctly calculated charts can support incorrectly labelled stories, and generic targets can appear more authoritative than the data warrants.

### 7. HR analysis exists, but the presentation contract loses useful detail

`shared_evidence_package.py:121` already invokes `analyze_hr_attendance_sheet` when applicable. The existing engine includes attendance/leave reconciliation, cross-sheet checks, department metrics, and negative-final-attendance information. This capability should be reused.

The standard presentation path converts candidate findings into a generic ledger and a compact director context. The whole HR result is not exposed as a dedicated, audience-oriented reporting contract to the planner. Neither the generic outline nor the chart inventory guarantees slides for the HR questions demonstrated in the reference.

Further analysis would be necessary to match every reference slide. For example, calendar-versus-working-day leave checks require an explicit work-calendar definition, appropriate period parsing, and verified row-level evidence. The current HR policy note describes negative Final Attendance as net-balance accounting; it does not determine whether subtracting leave is appropriate for the intended WFO measure.

**Consequence:** useful HR checks may be flattened or missed, while generic executive sections dominate the output. The solution is to connect and extend existing analysis, not build another analytics pipeline from scratch.

## Recommended correction order

1. **Correct story grounding first.** Resolve scope and reporting period, select relevant verified findings, and supply actual values, units, populations, comparisons, limitations, and supporting rows before narrative planning. Encapsulate the commercial example and domain-irrelevant fallback assertions. Verify that source fields can support the requested subject.
2. **Separate internal evidence from presenter content.** Keep IDs, hashes, execution records, and verification internals in structured metadata and the existing evidence interface. Use business source labels and material caveats on slides. Include a technical appendix only when requested. Keep substantive data-quality findings visible in plain HR language.
3. **Make the story specific to the business question.** For a WFO review, choose summary, weekly pattern, department comparison, attendance distribution, formula/leave issues, exceptions, reconciled checks, and next steps when verified evidence exists. Do not force empty sections or invent findings to fill ten slides.
4. **Bind each visual to its actual claim.** Match measure, unit, period, grouping, denominator, filters, and source. An odometer chart cannot support a footfall or margin headline. Use charts because they answer the slide's question, not because an available chart needs a destination.
5. **Add a real presenter-language pass.** Produce clear titles, short factual explanations, and useful spoken notes while preserving all values and qualifications. Keep the existing theme and output-template controls. Use the reference's clarity, not its fixed palette or potentially weak contrast, as the communication target.
6. **Make semantic relevance and comprehension release criteria.** A slide must answer its intended question, say what its cited evidence establishes, and avoid unsupported causes, projections, policy conclusions, or “verified” labels. Numerical, visual, accessibility, and export checks remain necessary alongside these checks.

## HR rules that must remain explicit

- Attendance days, calendar-day leave, working-day leave, eligible WFO days, and compliance percentages are distinct measures.
- Three days per week is a policy input to confirm, not a policy the application can infer solely from a cluster of observed values. The reference itself recommends confirming it.
- A weekday count is not automatically the organization's working calendar. Holidays, schedules, and employee eligibility can change the denominator.
- A small worked example can explain a suspect Final Attendance formula. Whether it double-counts leave depends on what Total Attendance and Approved Leaves actually mean.
- Department comparisons should acknowledge relevant leave/population differences. Lower recorded office attendance is not automatically misconduct or poor performance.
- A finding of “no mismatch” supports the checks actually executed, not a blanket claim that the dataset or all business interpretations are correct.
- Employee identifiers and exception rows should remain exact and visible only within the application's existing authorized access.

## Acceptance examples for implementation

| Test | Required outcome |
|---|---|
| Car dataset without footfall or dates | No claims about footfall correlation, seasonality, or ROI without separately supplied, verified evidence |
| WFO weekly data with approved leave | Relevant HR summary, weekly pattern, departments, distribution, and verified exceptions |
| Unspecified WFO mandate/calendar | Policy/denominator limitation stated plainly, no invented compliance percentage |
| Affected employee/period example | Actual ID, dates, values, units, and explanation stay consistent |
| Real reconciliation result | Correct matched/mismatched counts and boundaries, no generic “100% integrity” substitution |
| Chart binding | Title and explanation match the chart's measure, unit, grouping, and period |
| Unsupported qualitative claim with a valid EVID ID | Validation rejects or revises the claim despite the reference existing |
| HR presenter language | No unexplained internal tokens, database names, hashes, or audit-mechanism prose in the ordinary deck or narration |
| Fallback/model failure | Still produces factual, understandable domain content without generic success claims |
| Export | Downloaded PPTX retains the same validated story, readable tables/charts, centralized slide theme, and AAA requirements |

The primary repair is a better content and evidence contract across analysis,
planning, adaptation, and QA. Changing colours or replacing one model will not
address the confirmed failures.
