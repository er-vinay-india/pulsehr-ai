# Gemini implementation prompt: HRIDAY analytical queries and follow-ups

You are working in the existing **HighView** repository. Implement the fix described below. First inspect the current checkout and applicable repository instructions; the observations below describe the checkout inspected on 2 October 2026 and must be checked against any subsequent changes.

## Objective and boundaries

HRIDAY must retrieve verified insights when retrieval answers the question, execute deterministic calculations when calculations are needed, and preserve analytical intent across follow-ups. An employee-level question must produce employee-level evidence. A department insight cannot substitute for employee IDs.

Preserve HRIDAY's existing identity layer, model orchestration, original heart artwork, centralized theme tokens, global light/dark preference, AAA contrast requirements, accessible controls, and real backend activity indicators. Encapsulate internal models, council roles, votes, and technical routing. Do not introduce a source selector, expose internal query plans in ordinary chat, redesign the chat, or change presentation generation. Do not rewrite working backend capabilities.

**Important baseline correction:** do not assume greeting continuity, dataset binding, or DatasetContext integration is complete simply because a previous prompt said so. At inspection, these three files were untracked drafts:

```text
backend/app/services/copilot/conversation_context.py
backend/app/services/copilot/dataset_context.py
backend/app/services/copilot/dataset_query.py
```

They were not connected to the request path or verified. Inspect their current status. Reuse useful parts only after validation; do not ship them by assumption, build duplicate services around them, or discard unrelated work. Scope changes to dependencies necessary for this analytical fix. Identity branding is already implemented and does not need another identity system.

## Code-based RCA supplied by Codex

These are confirmed static findings, including an independently reproduced string-matching defect. A live trace against the user's active dataset was not captured. Confirm runtime branches and actual output before claiming end-to-end reproduction.

### 1. The exact word “coming” triggers the department shortcut

In `backend/app/routers/copilot.py`, `_answer_from_shared_findings` contains:

```python
is_lowest = any(w in q_low for w in [
    "lowest", "worst", "bottom", "least", "min", "minimum",
    "deficit", "lagging", "friction"
])
```

This is substring matching: **`"min" in "coming"` is True**. The following queries both match `min`:

```text
who is not coming regularly
calculate and then tell who is coming very less (employee id)
```

The subsequent lowest branch checks `is_lowest` without requiring an attendance metric or department grain. When shared findings and quinary items exist, it sorts those department items and returns the literal heading **“Lowest Recorded Attendance Department.”** This directly explains a code path capable of producing the reported response for the exact query. Its runtime prerequisites still need verification.

Both `/query` and `/query/stream` consult this shortcut before analytical routing. Fixing only the substring match is insufficient: valid “least attendance” employee questions can still be intercepted by the same department branch.

Use token/phrase-aware matching, then enforce requested metric, grain, period, and filters before considering any shared finding an answer. A direction word alone does not authorize a department-attendance answer. Audit other short substring terms such as `max`, `top`, and `present` for similar collisions.

### 2. Client routing bypasses the existing planner

`frontend/src/components/hriday/presentation.js::inferHRIDAYTool` recognizes a limited arithmetic/calculation grammar. Employee ranking questions and “i need employee id” do not match it.

`frontend/src/api/client.js::streamCopilotQuery` sends:

```javascript
engine: tool ? "auto" : "war_room"
```

In `/query/stream`, the `war_room` branch—and `auto` without a tool—dispatches to `UnionWarRoomEngine` before reaching the legacy stream path that performs server-side tool inference. Consequently, an obvious analytical question can skip the planner solely because the frontend did not recognize it.

The council's `_extract_dataset_summary` supplies limited descriptive context, rather than an employee-level executed analytical result. Selecting a council answer does not validate its analytical grain or prove the requested calculation ran.

**Required fix:** server-side analytical classification and validated execution must take precedence over these conversational engine defaults. Client heuristics may be hints; they cannot be the gatekeeper for correct calculations. Preserve the existing council for appropriate conversational tasks.

### 3. A planner already exists, but its attendance execution is department-specific

`backend/app/services/copilot_query_planner.py` already defines a **dataclass** `AnalyticalQueryPlan`, `plan_analytical_query`, and `execute_analytical_plan`. `backend/app/services/copilot_tools.py` already supports `ToolRequest(name='analytical_plan')`, `infer_tool`, and `execute_tool`.

Do not create a second planner/executor architecture. Extend these contracts or introduce a thin adapter if necessary.

The existing plan defaults `entity_dimension` to `Department`; grouping resolution can otherwise choose the first available dimension. Neither is adequate for an explicit employee request. Additionally, `_execute_hr_period_attendance_query` consumes `res['departments']`, sorts department metrics, and constructs department responses regardless of the requested employee grain. Merely setting `entity_dimension='employee_id'` does not fix this executor.

The general tabular executor computes group means; it is not a generic implementation of requested sums, attendance-day counts, or weighted rates. `filter_col` and `filter_val` are declared in the plan, but no execution references were found in this file. Verify these gaps and implement real semantics, not just additional plan fields.

### 4. Follow-up state is insufficient and can lose scope

`frontend/src/components/hriday/conversation.js` sends `prior_context` and updates it only when a response contains one. “i need employee id” has no dedicated refinement route. An early department shortcut can therefore fail to provide a reusable analytical plan for the next turn.

`frontend/src/App.jsx` initializes `activeScope` with null IDs; no call to `setActiveScope` was found. The global widget has a URL `sheet_id` fallback, which does not establish that every page's selected dataset/snapshot is correctly bound. `_load_active_sheet_dataframe` also resolves an explicit sheet without jointly checking a supplied dataset ID.

Validate scope continuity only as required for this fix. Do not assume the latest sheet or stale URL represents the user's active data. Revalidate client-supplied prior context on the server.

### 5. Adjacent retrieval paths need compatibility checks

The generic copilot's ranking path can select segment facts without checking employee grain, and its metric resolver can fall back to the first numeric column. That is unsafe for an unresolved, explicitly requested attendance metric. Its insight-summary path selects three facts rather than honoring every requested count; the shared shortcut also does not recognize “5 key points.”

The shared findings provider can run dashboard analysis on demand; do not describe it as necessarily a persisted, precomputed fact database. Retrieval may involve existing calculations, but that does not prove the requested employee calculation executed.

## Required implementation

### A. Trace and establish regression fixtures first

Trace the production HRIDAY transport, not only a helper call, using this sequence:

```text
who is not coming regularly
i need employee id
i need employee who came very less
calculate and then tell who is coming very less (employee id)
only top 3
show department also
```

Record resolved scope, classifier result, shortcut/engine selected, prior analytical context, requested and actual grain, resolved metric/identifier/period, executor invocation, validation outcome, and response. Check streaming and non-streaming route consistency. If local services/data are unavailable, reproduce with realistic fixtures and explicitly report the live validation gap.

Do not log full prompts, employee rows, or employee identifiers by default. Use request IDs, a query hash, scope/snapshot IDs, schema field names, operation, aggregate counts, and validation outcomes. A local diagnostic trace may capture redacted query/evidence under explicit debug configuration. Do not put production personal data into committed fixtures or the report.

### B. Resolve request type before choosing an answer path

Extend existing classification to distinguish:

```text
FACT_RETRIEVAL
ANALYTICAL_CALCULATION
FOLLOW_UP_REFINEMENT
GENERAL_CHAT
```

Resolve executable calculations and analytical refinements before shared-findings shortcuts and before default council dispatch. Honor explicit tools through the same validation. Keep domain explanations and ordinary greetings on their appropriate conversational paths.

Examples:

| Request | Required behavior |
|---|---|
| “which employee came least?” | Employee attendance ranking, ascending |
| “who is not coming regularly” | Infer employee attendance ranking when the dataset supports that interpretation |
| “i need employee id” after attendance ranking | Retain metric, period, filters, direction; change grain/output to employee and recalculate |
| “only top 3” after lowest ranking | Change limit to 3; preserve ascending direction |
| “show department also” after employee ranking | Add a descriptive field; retain employee grain |
| “who came less than 10 days?” | Execute an attendance-days threshold, not merely rank |
| “5 key points” | Return up to five distinct, verified, utility-ranked facts |
| “what is attendance compliance?” | Explain the concept; do not manufacture a compliance calculation |

“Who” is a person signal in people data, not a universal employee rule for every domain. Use existing semantic metadata. Ask one narrow clarification only when executable meaning genuinely remains ambiguous. “Very less” does not require inventing a threshold.

### C. Extend the existing plan and analytical state

The current plan includes intent, metric, secondary metric, entity dimension, direction, time window, ranking limit, filter fields, dataset/sheet/snapshot IDs, and prior context. Extend it with validated fields as needed:

- Requested entity grain and resolved identifier/grouping columns.
- Metric definition, unit, supported aggregation, and period/date boundaries.
- Typed filters with allowlisted operators and distinct pre-aggregation versus post-aggregation semantics.
- Requested output fields, deterministic ordering, and bounded result limit.
- Evidence scope and validation/execution status.

Use schema validation at the API/execution boundary. Client text and prior-context objects cannot authorize arbitrary column names, SQL, Python, expressions, file paths, or data access. Reuse current access controls and parameterized queries. Never execute LLM-generated code.

Preserve the last validated analytical intent/plan in the existing conversation context, including grain, identifier, metric definition, aggregation, direction, limit, filters, period, return fields, and dataset/sheet/snapshot provenance. Update it atomically with the completed response. Preserve meaningful intent through a supported refinement, including an explicit validation failure where appropriate; do not claim a failed execution produced a valid result.

Explicit new instructions override inherited fields. Grain changes require recalculation. A smaller limit may slice a validated result only if scope, snapshot, filters, metric, and ordering are unchanged and sufficient rows were materialized. Increasing a limit or changing filters/period/grain must execute again. New chat and source changes must invalidate incompatible state. An identifier-only request with no prior analytical question needs a narrow clarification, not an invented metric.

### D. Validate active scope and schema

Resolve actual dataset/sheet/snapshot IDs using existing application contracts. Never pass a literal `dataset_id='current'`, invent an analysis-run table, silently switch datasets, or select an unrelated sheet because its schema looks convenient. Validate dataset and sheet ownership jointly. Stale snapshot behavior must be explicit and consistent with existing refresh rules.

Use existing semantic profiles and prepared/derived data when they have verified lineage, scope, freshness, and requested grain. Otherwise use the appropriate persisted records through trusted loaders. Vector search can locate relevant evidence or fields; it cannot substitute for an aggregate over the eligible population.

Resolve aliases such as `employee_id`, `emp_id`, and `employee_number` only when semantically unambiguous. Preserve identifiers as strings, including leading zeros. Never synthesize employee IDs from row indexes or substitute employee names for requested IDs without explanation. Do not blindly treat office days, recorded attendance days, attendance rates, and obligation compliance as interchangeable metrics.

If an identifier or metric is missing, return that specific limitation. Do not use the first numeric column or a department fact as a fallback. If multiple plausible attendance fields exist, use explicit wording, validated prior intent, and semantic definitions; clarify only what cannot be resolved.

### E. Execute with correct attendance semantics

Reuse the trusted pandas/analytics/tool infrastructure. Ensure the HR-specific path honors employee grain or explicitly dispatches to a correct employee executor within the existing architecture. Keep department queries working.

Choose aggregation from the actual record grain and measure definition:

- One employee record with a recorded days value: use that value; do not invent another aggregation.
- Daily/event rows: count qualifying days/events using the existing attendance definition. Handle duplicate employee/date records explicitly; do not silently double-count days.
- Disjoint period totals: sum only the requested, non-overlapping periods. Do not sum cumulative totals or mix them with their components.
- Wide monthly headers: resolve the requested month/year and metric component, rather than using all months or leave columns.
- Rates/percentages: do not sum rates. Use a documented compatible average or a denominator-weighted calculation when denominators exist. Do not call percentages days.

Apply period and population filters before aggregation and aggregate thresholds afterward. “July 2025” must not include July 2024. Use the established reporting period when available; otherwise label the actual covered period or clarify a genuinely ambiguous choice.

Zero attendance is a valid observation and belongs at the low end. Missing/non-numeric attendance is not zero; exclude or handle it according to an explicit policy and report relevant counts. Exclude records without usable identifiers from employee-ID output with a concise coverage caveat. A dataset with one eligible employee must not fail merely because a statistical comparison helper requires two observations.

For “show department also,” do not split one employee into multiple ranked employees. Attach an unambiguous department, or represent multiple memberships honestly. Define tie handling and a deterministic identifier tiebreaker. “Only top 3” means at most three rows; note a boundary tie when material, rather than unexpectedly returning every tied row.

Rank recorded attendance, not alleged misconduct or obligation coverage. Without schedules/eligible-day denominators, do not infer compliance or invent causes for low attendance.

### F. Validate results and produce faithful HRIDAY responses

The structured result should carry actual scope/snapshot, validated metric definition/unit/aggregation, requested and result grain, ordered bounded rows, eligible/used/excluded counts, and execution provenance. Reuse existing evidence/calculation IDs where valid. Any new execution ID must represent a real invocation, never a decorative claim of proof.

Validate field presence, grain, metric, filters, period, finite values, ordering, limits, identifier uniqueness at the requested grain, and consistency with the executed plan. Do not simply copy the requested grain into metadata and call it validation; verify actual grouping/result structure.

Distinguish missing context, missing identifier, missing metric, unsupported operation, ambiguity, unavailable period, no eligible results, execution failure, and grain mismatch. An empty filtered population is a valid empty result. No failure path may substitute an unrelated insight.

Return compact employee-ID tables with accurate measure labels and only material caveats. Do not force rankings into executive insight cards or append unrequested recommendations. HRIDAY remains the single user-facing assistant.

Deterministic formatting is acceptable and preferable for exact identifiers/numbers/order. If an LLM explains the result, supply bounded validated evidence and ensure it cannot replace IDs, change values/order, invent missing rows, or claim an unexecuted calculation. A deterministic table with optional separately validated explanation is acceptable. Preserve evidence through existing model fallbacks and identity corrective retries; do not expose internal model identities or votes.

Default ranking limit: 10; maximum rows supplied to a model: 50, using existing configuration conventions. Bounds apply to displayed/model evidence, **not to the population being calculated**. Do not silently calculate over a truncated subset of employees. If an existing loader cap prevents complete execution, use a trusted full-population path or report the limit explicitly. Do not imply a truncated result is complete.

For “5 key points,” use the existing verified fact discovery/shared-findings infrastructure with matching scope and requested count. If fewer than five meaningful facts exist, return fewer and explain briefly; never pad with invented insights.

Emit loader updates from actual backend transitions—resolving the question, calculating, validating, preparing the response—as those transitions occur. Do not send a timer-driven performance, fake percentages, or pretend intermediate replies. Preserve cancellation, stale-request protection, existing SSE event contracts, and one assistant bubble.

### G. Keep the operation scope realistic

The essential deliverable is employee/department ranking, supported aggregate semantics, filters/thresholds, periods, and conversational refinements. Reuse existing sum/mean/min/max/count capabilities where correct. Support distinct counts, comparisons, percentages/ratios, and trends through existing trusted definitions where available. If additional operations need new semantics, document and return an explicit unsupported result; do not silently downgrade them to a nearby insight. Do not build a general query language as a prerequisite for this fix.

## Required tests and acceptance evidence

Use deterministic fixtures with known expected IDs/values and integration tests that prove the real route reaches the executor. Test behavior, not just attractive final text.

1. Reproduce `min` matching `coming`; prove the corrected matcher does not mistake “coming” for the token “min.” Then prove the full query still resolves low-attendance intent through intentional phrase handling.
2. The exact failed calculation query produces employee grain, a resolved identifier, ascending order, and verified numeric results.
3. An available “Lowest Attendance Department” finding cannot intercept an employee calculation; the appropriate executor is invoked once per new execution, excluding legitimate existing internal operations. A model retry must not repeat the calculation unnecessarily.
4. A department-ranking conversation followed by “i need employee id” retains metric, period, filters, and direction and recalculates at employee grain.
5. The golden conversation above works through the production streaming route. “Only top 3” preserves ascending order; “show department also” preserves employee grain.
6. “Less than 10 days” applies the actual threshold to the correct aggregated measure; inherited department/date filters remain active and explicit new filters override correctly.
7. “5 key points” returns five distinct verified facts when available and handles fewer available facts honestly.
8. Missing employee IDs, ambiguous attendance metrics, missing periods, stale scope, and execution errors never yield department or unrelated-metric substitutes.
9. A mocked department-grain executor result for an employee request is rejected before final answer/stream publication.
10. Leading-zero IDs, zero attendance, missing values, one eligible employee, duplicate daily events, wide monthly data, overlapping/cumulative totals, weighted percentages, and multi-department employees have explicit expected results.
11. Identical schema across two datasets cannot contaminate scope, cached results, or prior context; dataset/sheet mismatch is rejected. Month/year filters do not merge years.
12. A model attempting to alter a known employee ID/value cannot change the validated table; fallback and identity retries retain the same evidence.
13. General chat and legitimate department analytics retain existing behavior. Streaming/non-streaming classification agrees. Cancellation or a source change cannot publish a stale result or overwrite current analytical context.
14. Calculation uses the eligible population even when the response limit is 3/10/50; loader caps cannot silently produce partial rankings.

Run focused planner/executor/router tests, relevant existing copilot/identity tests, and frontend conversation tests if state/transport changes. Run the production frontend build if frontend code changes. Do not claim unavailable live checks passed. Do not add unrelated test rewrites or broaden this into a theme redesign.

## Implementation sequence and report

1. Verify the supplied RCA and capture the failed route; establish failing tests.
2. Extend existing request classification and analytical plan/state contracts.
3. Validate scope, identifier, metric, aggregation, filters, and reporting period.
4. Fix routing precedence and connect employee-grain execution through the existing executor architecture.
5. Enforce result compatibility and faithful output; connect real activity signals.
6. Verify golden conversations and regressions, then report the outcome.

Deliver:

- Confirmed RCA, including the substring collision and exact preemption/bypass points; distinguish live evidence from static findings.
- Before/after request flow and files changed.
- Actual extended plan/state schema, metric/grain validation, and executor used.
- A redacted real trace, or a clearly labeled fixture trace if live data is unavailable, showing scope → intent → plan → executor → validation → HRIDAY answer.
- Expected versus actual IDs/values for representative fixtures, test/build results, and remaining limitations.
- Status of any reused draft files: integrated and verified, or still unintegrated.

Complete implementation and validation without stopping at a plan. Preserve unrelated working-tree changes. Do not commit or push unless the user explicitly requests it for this implementation.

**Acceptance principle:** retrieving a nearby department insight is never proof of an employee calculation. Preserve the user's analytical intent, execute at the requested grain, and return only validated results.
