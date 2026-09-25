# Gemini execution prompt — first-tile refinement

Act as the implementation lead combining data science, UX research, visual/content design, software architecture, and delivery management.

Project: `/Users/vinayksharma/Developer/pulsehr-ai`

Read `docs/adaptive-dashboard-design.md`, Revision 4, before editing. Pay particular attention to the review findings, business vocabulary policy, three disclosure layers, notice materiality, and first-element review gate. These replace the earlier instructions that produced a verbose audit card. Read the integrated UX/visual-design decisions and scope/loading/recovery rules as implementation requirements. Do not execute the entire roadmap.

## Authorized scope

Refine the EXISTING first element on the separate Adaptive Dashboard page. Do not start another dashboard, add a second tile, introduce a chart or narration feature, or alter the existing Leadership Report and Reference Overview. Supporting disclosure belongs to this same element.

Inspect git status and applicable instructions first. Other work is in progress: preserve unrelated changes; do not reset, restore deleted files, broadly refactor, commit, push, or deploy.

## Problem to solve

The client wants a prominent number with a familiar business label, not scientific explanation on the card face. The previous plan itself taught “Employees represented” and required qualifications without defining their display location. The current implementation hardcodes “Workforce members represented” and renders all qualifiers as prominent limitations.

Fix the reusable naming/disclosure policy, not one literal string. Do not replace every count with “headcount,” hide incorrect results in a tooltip, or shrink the current audit card's text.

## Inspect the current implementation

Start with:
- `backend/app/services/adaptive_dashboard/contracts.py`
- `backend/app/services/adaptive_dashboard/engine.py`
- `frontend/src/pages/AdaptiveDashboardPage.jsx`
- `frontend/src/styles/adaptive-dashboard.scss`
- `backend/tests/test_adaptive_dashboard.py`

Verify the current state; changes may have occurred since the review. Findings to check include hardcoded `100`/`712` explanatory text, a manufactured `value/value` “100% complete” display, HR-specific definition text embedded in the generic renderer, and a required free-text coverage warning. Correct confirmed defects within this element instead of concealing them behind the new design.

## 1. Separate metric meaning, business name, and disclosure

Preserve the verified calculation, entity, grain, population, period, unit, exclusions, and source identity. Introduce or adapt a reusable business-concept naming policy and typed presentation fields.

Use a familiar concise label, generally two to four words when accurate. For known concepts, select from approved terminology; unfamiliar concepts can use validated model proposals. Do not invoke a model merely to rename a known metric.

Examples are conditional, not defaults:
- Defined workforce snapshot with appropriate population and reference date → “Employee headcount.”
- Distinct employee IDs observed in attendance data, without proof of complete workforce coverage → “Employee count,” visibly scoped to “In attendance data.”
- Verified employees plus contractors → “Workforce count,” with inclusion rules in details.
- Verified distinct placed orders → “Orders.”
- Pending orders without deadline evidence → “Pending orders,” never “Overdue orders.”
- Returned-order numerator over eligible delivered orders → “Order return rate,” never an ambiguous “Return performance.”

Do not infer employees from arbitrary Person_* columns without a supported entity mapping. Preserve meaning-changing words such as active, net, overdue, order/unit, or paid only when their definitions are verified. Original column display labels and business metric names are separate concepts.

## 2. Implement three disclosure layers

GLANCE — default tile:
- Familiar business label.
- Large, visually dominant verified number.
- Meaningful unit only when not already implicit in the label.
- At most one short necessary context line.
- One labeled information button.

No paragraph, audit heading, formula, file name, technical ID, “AI verified” badge, selection rationale, or warning about an unrelated unavailable metric. Keep common source/period controls at page level. Remove internal “Gate 1,” revision numbers, and pipeline terminology from ordinary page copy.

EXPLAIN — hover/focus preview:
- One or two brief plain-language sentences defining the metric.
- Exact value where the displayed value is abbreviated.
- No long formula or interactive links.

INSPECT — persistent details on activation:
- Definition, applicable population, source/period, calculation, actual coverage/missingness, exclusions, and selection reason.
- Technical identifiers can be nested further.
- Every number and factual assertion must come from the same evidence revision as the headline value.

Use a real accessible information button. Hover and keyboard focus reveal the preview; click, Enter/Space, and touch open persistent details. Support Escape, appropriate focus handling, viewport containment, and touch access without hover. Do not rely only on HTML title attributes. Opening details must not add another dashboard component.

## 3. Apply the agreed visual and interaction specification

Quiet the local page header as well as the tile. Use “Dashboard,” the source control, actual period, and Refresh. Remove the process hero and repeated file/sheet badges. Keep global navigation and other pages intact.

Build one left-aligned card with a preferred desktop max-width near 24rem and full available width on small screens. Start with 24px desktop/20px mobile padding and 12px radius. Use approximately 16px medium label, 56px desktop/48px mobile semibold number with tabular numerals, and 13px context. These are design starting points: allow necessary labels and enlarged text to wrap naturally. No fixed height that clips content.

Use shared application theme tokens and verify resolved contrast. Do not introduce a separate visual theme, decorative gradients, strong shadows, unexplained deltas, status colors or confidence badges. The number should dominate the entire local page hierarchy.

Use an approximately 18px info glyph inside a 44px button target. The preview is noninteractive and disappears while persistent details are open. Use one accessible modal details component styled as a compact dialog on desktop and a sheet on narrow screens. Support focus placement/containment/restoration and Escape. Do not make the number a separate unexplained interactive control.

Follow the interaction and contrast references in Revision 4; inspect the actual rendered states rather than claiming accessibility from CSS values alone.

## 4. Resolve source and loading UX

Do not send an unscoped request while sources are loading. Reuse valid existing selection; visibly select the sole source when only one exists; otherwise require a source choice without silently picking the first.

Keep source selection usable while calculating. On source change or refresh, close source-bound disclosures and replace old content with a stable tile-sized “Calculating…” state; never display zero while loading. Cancel/discard obsolete results. Publish source, period, value and disclosure content together.

Handle source loading, no uploads, unavailable source, failed calculation and undefined metric separately, each with one relevant recovery. Source-list failures must appear in the UI, not only console logs. Preserve the chosen source on retry and never broaden scope implicitly.

## 5. Classify limitations instead of warning about everything

- Routine method and provenance → details.
- Helpful nonessential explanation → preview.
- Material population/period restriction → short visible qualifier plus details.
- Invalid or undefined metric → compact unavailable/definition-needed state; no misleading number.

Do not generate a caveat merely because a schema requires a string. Use optional typed notices with evidence-backed conditions. The absence of scheduled days for an attendance rate is not automatically a warning on a valid employee-count tile.

Record completeness and workforce/population coverage are different. Neither can be established by dividing a displayed count by itself. If the eligible denominator is unknown, say it is unknown in the appropriate disclosure layer. Do not display an invented 100%.

## 6. Validate the first element

Test meaning, data binding, and presentation separately:
- Repeated employee observations do not inflate the value.
- Attendance-only counts do not become active workforce headcount.
- Changing the fixture from 100 people to 37 and changing its dates updates every label-dependent explanation; no copied constants remain.
- Unknown coverage does not become 100%.
- Familiar naming survives equivalent column renaming without inventing semantics.
- One element only is rendered.
- The closed tile is readable at a glance, with the number dominant and no routine warning paragraph.
- The preview/details work with mouse, keyboard, touch, 320px/390px widths, and enlarged text. Inspect the whole viewport, not only the card.
- Source loading/failure and fast source changes follow the specified UX without stale labels or tooltip content.
- Full values and meaningful units remain accessible.
- Source changes cannot mix old values with new labels or tooltip content.
- Existing report routes remain intact.

Run focused tests and the frontend build, then inspect the rendered result. Present the actual closed, preview and expanded states on desktop and a narrow screen for review; a static mockup does not verify interaction. Do not certify accessibility or usefulness solely from a build. Do not make tests assert the rejected wording as the only valid label.

## Delivery and mandatory stop

Provide the page link, a concise account of the root cause and changes, the selected business label and its semantic justification, verification results, and any concrete limitation.

Ask the client to confirm what the number counts and its scope, then ask: “Is this first tile clear and useful now—both the business wording and the number-first design?”

Stop for explicit user approval before adding any second element. Do not treat silence as approval. Proceed with authorized implementation and verification; do not respond with another plan alone.
