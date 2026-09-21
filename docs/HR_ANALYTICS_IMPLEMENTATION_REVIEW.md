# Implementation review and refinement request

Reviewed 21 September 2026 against HR_EXECUTIVE_ANALYTICS_ROOT_CAUSE_AND_FIX_PROMPT.md.

## Verdict

Partially implemented; not ready for HR acceptance. New modules provide useful scaffolding and a July-specific happy path, but they do not yet implement the general semantic, temporal, query, and executive-report contract. This review changed documentation only. The live database was read-only; test databases were isolated. No rendered deck or browser acceptance review was performed.

## Implemented improvements

- New semantic_mapping.py excludes identity headers from arithmetic; the profiler no longer averages Full Name in the regression fixture.
- New hr_period_analytics.py parses wide July period headers, reconciles weekly/source totals, computes department averages, and supplies weekly drilldowns.
- New copilot_query_planner.py routes the original attendance-ranking phrases to deterministic analysis with sheet/dataset parameters.
- Backend API accepts prior_context, although frontend wiring and full-context preservation remain missing.
- Evidence packaging includes an HR analysis and department finding; snapshot hashing now includes source cell contents.
- The row-count-as-mean fallback was removed. Unmatched metric cards are now marked unverified instead of automatically passed.

## Verification results

Command from backend: `PYTHONPATH=. .venv/bin/pytest tests/test_hr_executive_analytics.py tests/test_copilot_tools.py tests/test_executive_story.py tests/test_presentation_pipeline.py -q`

Result: **60 passed, 6 failed**. All nine new HR tests pass, but their coverage is insufficient. Four existing copilot tests fail (changed routing and over-capture of individual, definition, and filtered-comparison questions); two presentation tests fail revalidation. Some old routing assertions may legitimately require migration, but silently changing the meaning of questions does not.

The new rate-versus-total test calculates pandas results locally without invoking production analytics. The snapshot test defines its own hash helper rather than calling the production evidence package. Neither proves the corresponding feature works end to end. The suite description promises scope isolation without an executable test for it.

## Blocking findings and reproductions

### P0 — Requested period is ignored

`plan_analytical_query("Which department has the lowest attendance in August?", sheet_id=33)` records August, but `execute_analytical_plan` returns July results from the current database. No execution filter uses time_window. The analytics service defaults to July if no period is detected and always claims the workbook contains July only. Period keys omit year: headers for 1–5 July 2025 and 1–5 July 2026 collapse into one period. Monthly measures are aggregated across the entire frame, not grouped by month/year.

Fix: preserve and execute month/year constraints, group facts by period, validate chronology and reject unavailable periods explicitly. Never substitute July for August. Test multiple months and years, month-only ambiguity, invalid ranges, and no date metadata.

### P0 — Default source selection still breaks the original question

Running the original worst-attendance question without sheet_id selects the latest sheet, Leave Calculation Check, and fails: “Could not identify Department groupings.” Selecting dataset_id simply chooses its first sheet. When both scope IDs are supplied, only sheet_id is checked.

Fix: resolve compatible fact and dimension sources inside the authorized scope. Enforce dataset/sheet consistency; clarify only genuinely ambiguous compatible sources. Test the public query endpoint with the two-sheet workbook and no manually selected sheet.

### P0 — Planner substitutes different questions and metrics

The planner interprets absent/absence as approved leave, infers attendance for unspecified worst performance, defaults ordinary metric mentions to a lowest-department ranking, and never executes requested Team/Division dimensions or filters. It captures definition and individual questions before appropriate handling. Explicit lowest/highest and business worst/best need distinct metric-aware handling. Ranking ties are not represented; all-department output is capped at 25.

Final-attendance rankings sort departmental totals (`net_attendance_days`), label them days/employee, and compare them to the gross attendance average. This mixes aggregation, units, and metric definitions.

Fix: validated metric registry and strict supported-intent contract; preserve aggregation, filter, dimension, denominator, direction, ties, and scope. Ask for the metric when worst is ambiguous. Never equate approved leave to absence. Use the same defined metric for ranked values and benchmarks. Test rates versus totals through the real executor/API.

### P0 — Invalid and missing inputs can produce confident false rankings

The service uses numeric coercion followed by fillna(0), silently converting unknown attendance to zero. A synthetic row with missing attendance becomes the lowest department at 0. Duplicate employee rows are summed while the denominator uses distinct IDs: two duplicate 10-day rows become 20 days per employee. Reconciliation reports mismatches but does not establish which total is valid before ranking. Comparison-sheet joins lack cardinality validation and can multiply matches.

Fix: preserve unknowns; report used, excluded, missing, and conflicting records. Validate entity-period uniqueness and joins before aggregation. Block or qualify affected metrics, without arbitrary deduplication. Test missing IDs/departments, duplicate/conflicting records, leading-zero IDs, negative values, and mismatching totals.

### P0 — Semantic metadata is not an enforced business contract

Low-cardinality detection runs before explicit HR measure mapping: in a three-row fixture, Total Attendance and Approved Leaves are classified as dimensions. The analytics module imports semantic inference but does not use it to govern calculations. Final Attendance is declared resolved, and negative values are explained as leave-balance accounting without established business policy. Approved leaves are assigned higher-is-worse by default.

Fix: explicit known measure semantics before cardinality heuristics; enforce the catalogue in analysis. Keep final-attendance definition unresolved until validated. Separate descriptive leave usage from policy or performance judgments. Add versioned mapping/definition resolution rather than undocumented assumptions.

### P1 — The original executive-summary problem remains

The deterministic summary builder still leads with “Records Audited,” “Baseline Mean,” and completeness. The overview story still calls generate_ai_narrative with scalar ground_truth, without the new structured department analysis. Adding a department finding to presentation evidence is useful but does not establish shared findings across chat, overview, and deck. Existing AI planning remains chart/template oriented.

Fix: build a single typed finding contract and feed all three outputs. First page: 3–5 supported department/monthly pointers, each with observation, comparator, implication, limitation, and proposed action. Keep methodological inventory in the appendix. Inspect both AI and fallback outputs.

### P0 — Evidence scope and verification are incomplete

Shared evidence still calls workspace-wide industrial and relational services; multi-sheet visuals/stories use unscoped None. HR analysis is attempted even for non-HR primary sheets and can return zero attendance benchmarks rather than “not applicable.” Hashing now includes cells but lacks an explicit semantic-definition/version contract. Claim verification still focuses on metric cards, not headline, narrative, chart, and table claims. Stricter unmatched-claim detection has exposed deck/evidence integration failures; do not restore automatic passing to make tests green.

Fix: enforce exact scoped sources throughout; gate analytics by resolved domain/metrics; bind all claims to typed evidence; test actual production snapshot invalidation and out-of-scope contamination. Verify signed/scaled numbers and period/entity/units, not number presence alone.

## Copy-ready refinement prompt

Continue the existing PulseHR implementation; do not mark the repair complete or replace the current work with another superficial rewrite. Read this review and the original root-cause plan. Preserve unrelated changes.

First, turn each P0 reproduction above into a failing production-path regression test. Repair semantics, missing-data handling, entity-period uniqueness, source selection, and month/year filtering before changing narrative wording. Then fix planner intent/metric preservation, genuine ambiguity handling, ranking ties, all-department coverage, and frontend follow-up scope/context. Retain deterministic operation when the model is unavailable.

Use the same validated scoped monthly metrics and structured findings in chat, executive overview, and presentation. Replace the record-count-led executive summary in both AI and fallback paths. Every key pointer must identify the department and period, state a validated measure and comparator, explain its business implication without asserting unsupported cause, and offer an evidence-linked proposed action or precise missing-information request.

Resolve the six current test failures without weakening verification. Migrate old routing assertions only when the intended answer semantics are covered by stronger end-to-end tests. Replace the locally reimplemented hash/rate tests with tests calling production services. Add API coverage for: August requested on July-only data; two-sheet automatic resolution; duplicate and missing attendance; same period in different years; rate versus total ranking; ambiguous worst performance; individual and definition questions; Team/Division filters; dataset/sheet mismatch; explicit scope with unrelated high-risk data; ties and >25 departments; model outage; and edited-cell snapshot invalidation.

Finish with the relevant backend suite and frontend build, plus an inspected sample overview and exported deck. Provide a requirement-by-requirement completion matrix with passing test names, supported scenarios, and unresolved business definitions. Do not invent denominators, prior months, leave policy, or negative-attendance explanations to satisfy the acceptance criteria. Do not claim HR acceptance solely because the new happy-path tests pass.
