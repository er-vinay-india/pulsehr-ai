# Gemini Lead Developer Prompt — Adaptive Dashboard Element 7: Executive Briefing with Voice Orb

You are the lead developer working with a senior data scientist, software architect, product manager, executive communications specialist, accessibility specialist, and top-tier UX designer.

Repository:

`/Users/vinayksharma/Developer/pulsehr-ai`

Implement **only Element 7** on the existing Adaptive Dashboard at `#adaptive`.

Element 6 is complete. Preserve Elements 1–6 and every other application page. Present Element 7 for client review and stop. Do not implement Element 8, commit, push, merge, restore deleted files, or clean unrelated work.

## 1. Element 7 purpose

Elements 1–6 provide the analytical content and the decision priority. The missing capability is rapid executive consumption through readable and audible narration.

Element 7 must answer:

> **Can a business leader understand the current state, the most meaningful pattern, and the next check in a short, evidence-grounded briefing without reading every chart?**

Build one compact **Executive briefing** element with:

- A concise written briefing.
- An explicit Listen control.
- The existing animated acoustic orb, retained as a meaningful playback indicator.
- A transcript available at all times.
- Every factual claim bound to existing verified evidence from Elements 1–6.

This element is a new consumption mode, not a new analytical calculation. It must not introduce new metrics, recompute values in React, invent causal explanations, or repeat every dashboard component.

## 2. Inspect and preserve current work

Before editing:

```bash
git status --short --branch
git diff --stat
git diff --check
```

Read:

- `docs/adaptive-dashboard-design.md`
- `docs/gemini-sixth-element-prompt.md`
- `backend/app/services/adaptive_dashboard/contracts.py`
- `backend/app/services/adaptive_dashboard/engine.py`
- `backend/tests/test_adaptive_dashboard.py`
- `backend/app/routers/decision_brief.py`
- `backend/app/services/local_voiceover.py`
- `frontend/src/pages/AdaptiveDashboardPage.jsx`
- `frontend/src/components/VoiceoverPlayer.jsx`
- `frontend/src/components/presentation/AnimatedAcousticOrb.jsx`
- `frontend/src/components/presentation/AcousticOrbPresenter.jsx`
- `frontend/src/styles/acoustic-orb.scss`
- `frontend/src/styles/adaptive-dashboard.scss`

The branch contains completed Element 6 changes that may still be uncommitted. Do not discard, restore, rewrite, or stage them. Do not run `git reset`, `git restore`, `git checkout --`, `git clean`, or bulk replacement commands.

Preserve:

- Employee count and all approved dashboard elements.
- Element 6 Decision focus calculations, wording, and interactions.
- The original orb animation. The client explicitly requires it.
- Leadership Report voiceover.
- Presentation voiceover/orb behavior.
- Copilot, presentation creation, EDA Explorer, Reference Overview, and responsive navigation.
- The local speech endpoint and its privacy-preserving behavior unless a small backward-compatible change is required.

## 3. Product definition

Use this stable user-facing title:

**Executive briefing**

The default closed/readable state should contain:

1. A compact animated orb or orb mark.
2. `Executive briefing` title.
3. A short context line such as the selected source and reporting period.
4. A briefing of approximately 55–100 spoken words, normally three parts:
   - **Current state** — the most useful headline fact.
   - **What stands out** — one verified trend, comparison, or disparity.
   - **Decision focus** — the Element 6 priority and safe next check.
5. `Listen to briefing` and `Stop` controls using the existing voice infrastructure.
6. An accessible transcript control. The written summary must remain available when audio fails.
7. A small information control for source scope, snapshot, included claims, exclusions, and narration policy.

Do not add:

- Autoplay.
- A floating panel that competes with Copilot or covers bottom navigation.
- A large presentation-style HUD on the dashboard.
- A second voice engine.
- A chatbot response inside the element.
- A typewriter effect or continuously moving text.
- A long report, top-five list, or repeat of all chart labels.
- Background music, sound effects, or automatic volume changes.
- Fake live-waveform claims. The current orb animation indicates playback state; it does not analyze real audio frequency unless actual Web Audio analysis is implemented and tested.
- Model names, prompt versions, “AI generated,” confidence percentages, or technical IDs in the default view.

## 4. Briefing content policy

### 4.1 Claim order

Compose at most four short claim segments:

1. **Scope**: selected source and reporting period when known.
2. **State**: Element 1 primary metric or another more decision-relevant verified headline.
3. **Pattern**: one eligible fact from Elements 2–5.
4. **Action**: Element 6 Decision focus and its `next_step`.

The spoken briefing should sound natural, but its meaning must remain identical to the structured evidence.

### 4.2 Pattern selection

Select one pattern, not all patterns. Use this auditable order:

1. A valid Element 6 supporting component when it contributes a distinct explanatory fact.
2. A material comparator from Element 4.
3. A meaningful segment disparity from Element 5.
4. A genuine temporal movement from Element 2.
5. A categorical concentration from Element 3.

Skip a candidate when it would merely repeat the same number already spoken, its sample is inadequate, its meaning is unresolved, or its direction cannot be described safely.

Do not describe a nearly flat time series as a trend. Use movement language only when the backend has a defined comparison, adequate periods, complete/qualified periods, and a meaningful change in the metric’s natural unit. Do not invent a materiality threshold during narration.

### 4.3 Wording strength

Use structured claim types:

- `scope`
- `observation`
- `comparison`
- `association`
- `decision_focus`
- `next_check`
- `limitation`

Allowed patterns:

- `The uploaded attendance data represents 100 employees.`
- `Corporate Functions records 70.0% attendance reliability, 11.7 percentage points below the workforce benchmark.`
- `The next check is to review scheduling coverage and approved-leave patterns before changing policy.`
- `Weekly sales density differs across stores; Store 33 is 63% below the network median across 143 observed store-weeks.`
- `A positive association is present across 45 paired records. This does not establish a cause.`

Prohibited patterns unless directly supported by explicit source definitions:

- `Corporate Functions is performing badly.`
- `Leave caused low attendance.`
- `Store 33 will recover if assortment changes.`
- `The business is healthy.`
- `Sales will increase next month.`
- `This is a critical risk.`
- `AI discovered with 97% confidence...`

Use “percentage points” for differences between percentages. Use percent for relative change. Keep currencies, durations, dates, and denominator/grain audible and unambiguous.

### 4.4 Domain examples

These are templates for behavior, not hard-coded live copy.

#### Workforce

`The attendance data represents 100 employees. Corporate Functions has the largest verified attendance-reliability gap among adequately represented departments, at 70.0%, 11.7 percentage points below the workforce benchmark. Review scheduling coverage and approved-leave patterns before changing policy.`

#### Retail

`The selected source covers 45 stores across the observed retail weeks. Store 33 records the lowest eligible weekly sales density, 63% below the network median across 143 store-weeks. Compare trading days, stock availability, assortment, and traffic before setting a recovery target.`

#### Ecommerce

`The reconciled checkout population contains 12,400 sessions. Of these, 18.4% did not reach a verified order. Break the gap down by payment status, device, and error code before attributing a cause.`

Do not speak funnel abandonment when sessions and orders cannot be linked at a compatible grain.

#### Sales or marketing

`Enterprise qualified-lead conversion is 8.2%, 4.1 percentage points below the eligible benchmark across 317 qualified leads. Compare stage ageing, source mix, and recorded loss reasons before changing campaign or sales policy.`

#### Support

`There are 46 unresolved tickets older than seven days, representing 31% of the open backlog. Review severity, blocked status, and ownership before changing staffing. No SLA breach is claimed because the required target is not defined.`

#### General tabular data

Use neutral words such as `differs`, `diverges`, `highest observed`, or `lowest observed`. Do not say `best`, `worst`, `healthy`, `poor`, or `underperforming` when polarity is unknown.

## 5. Backend architecture

The current adaptive engine is already large. Do not add another long narration builder directly to `engine.py`.

Create a focused module such as:

`backend/app/services/adaptive_dashboard/briefing.py`

It should own:

- Briefing candidate selection.
- Deterministic claim construction.
- Claim/evidence binding validation.
- Spoken-text composition.
- Word-count and privacy checks.
- Graceful abstention.

The existing engine should only pass validated Elements 1–6 and the manifest into the briefing builder, catch Element 7 failure independently, and attach the result to the response.

### 5.1 Typed contracts

Add strict Pydantic contracts with `extra="forbid"`. Prefer business-purpose names:

```text
BriefingClaim
  claim_id
  claim_type
  text
  source_component_id
  calculation_ids
  numeric_values
  unit
  is_material_qualifier

ExecutiveBriefingSpec
  component_id = "briefing_element"
  kind: executive_briefing | briefing_unavailable
  business_concept
  title
  context_line
  spoken_text
  transcript_text
  claims
  source_component_ids
  calculation_ids
  estimated_word_count
  estimated_duration_seconds
  snapshot
  glance
  explain
  inspect
  caption
```

Add `briefing_element: ExecutiveBriefingSpec | None` to `AdaptiveDashboardResponse` and update the response version to `adaptive-v7`.

If a cleaner contract fits the existing architecture, adapt the names while retaining strict binding, snapshot, and claim provenance.

Element 7 does not create a new business EvidenceResult merely for having narration. Each factual `BriefingClaim` must reference the existing calculation IDs that support it. Do not create fake numerator/denominator values for narrative text.

### 5.2 Claim binding

Every factual sentence must bind to:

- A current response component.
- One or more current-snapshot calculation IDs.
- The exact raw numeric values and unit used in the sentence.
- Any material qualifier, such as partial period, unknown direction, sample limitation, or correlation-not-causation.

Validate before publication:

- All referenced components exist in the same response.
- All referenced calculations use `manifest.snapshot`.
- No number appears in the transcript unless it is a bound value, a formatted date, a sample size, or a harmless structural phrase.
- Display rounding never changes the claim direction or comparator.
- The transcript and spoken text convey the same facts.
- No raw employee/customer name, email, phone, address, free-text note, or record-level identifier is narrated.
- Segment names may be spoken only when they are business categories already displayed safely in Elements 3–6.

Implement deterministic text first. An LLM may optionally improve sentence flow only through a strict schema and only if the post-generation validator proves that every claim, number, direction, unit, and qualifier is unchanged. On timeout, malformed output, extra claim, or validation failure, use the deterministic briefing. Audio availability must never depend on an LLM.

### 5.3 Duration and content limits

- Target 55–100 words.
- Hard maximum 130 words and 1,200 characters for the adaptive briefing.
- Estimate duration using a documented speaking-rate assumption, e.g. 145–165 words per minute. Label it as an estimate only in details when shown.
- Do not pad a short briefing. Two correct sentences are better than four repetitive sentences.
- If only one supported fact exists, narrate that fact and the analysis limitation honestly.

### 5.4 Failure isolation

- Element 7 failure must preserve Elements 1–6.
- If no valid claim exists, return `None` or a typed unavailable state with a readable explanation; do not send empty text to speech.
- A voice-service failure must leave the transcript and dashboard usable.
- A stale response, changed source, aborted request, or superseded selection must stop audio preparation and prevent old audio from being presented as current.

## 6. Voice and orb implementation

Reuse:

- `frontend/src/components/VoiceoverPlayer.jsx`
- `frontend/src/components/presentation/AnimatedAcousticOrb.jsx`
- `/api/analytics/decision-brief/voiceover`
- `backend/app/services/local_voiceover.py`

Do not embed `AcousticOrbPresenter` directly because it is a fixed, slide-specific HUD. Create a small reusable component such as:

`frontend/src/components/adaptive/ExecutiveBriefingCard.jsx`

The new component should compose the existing orb and voice player in an inline dashboard card.

Required behavior:

- Orb remains visible and animated in its calm idle state.
- Playback state visibly changes the orb animation.
- `prefers-reduced-motion: reduce` produces a calm static orb without losing status information.
- Audio starts only after an explicit user action.
- Loading state says `Preparing voiceover…` and is announced politely.
- Stop immediately stops playback and aborts preparation.
- Changing sheet, snapshot, or briefing identity aborts the old request, releases its object URL, clears ready state, and stops the orb.
- Playback end returns the orb to idle.
- Audio failure shows concise retry guidance while leaving the transcript readable.
- Controls expose correct disabled, loading, playing, stopped, and error states.
- Do not create two overlapping audio controls with unclear ownership. If native controls remain, make the custom controls and labels coherent.

Keep the speech privacy statement accurate. The current macOS `say` implementation is local. Do not call it a cloud neural voice or promise studio quality.

## 7. Minimal UX specification

Place Element 7 after Element 6 during this approval stage.

### Desktop

- One full-width inline card using the Adaptive Dashboard’s warm minimal theme.
- Compact orb area on the left, briefing content on the right.
- Title, context, short written briefing, and controls.
- No fixed positioning and no overlap with Copilot.
- Maximum readable text width approximately 65–75 characters per line.

### Mobile

- Stack orb/title, briefing, and controls naturally.
- Keep the orb compact; it must not consume most of the viewport.
- Controls wrap without horizontal scrolling.
- Transcript is readable without relying on hover.
- Minimum 44×44 CSS pixel touch targets.
- Card and controls remain above the bottom navigation and clear of the Copilot trigger.

### Visual language

- Reuse Adaptive Dashboard color tokens, border, typography, radius, and focus treatment.
- Preserve the orb’s recognizable gyroscopic animation, shaded core, and playback response.
- Adapt its surrounding colors to the page if necessary without removing or flattening the animation.
- Avoid the dark floating presentation-HUD treatment inside the warm dashboard.
- Do not use the orb as a decorative background watermark.
- Do not show playback state through color alone; pair it with text such as `Ready`, `Preparing`, `Speaking`, `Stopped`, or `Unavailable`.

### Accessibility

- Canvas remains `aria-hidden`; accessible text communicates state.
- The card has a meaningful region label.
- Transcript is keyboard and screen-reader accessible.
- Focus order is title/context → listen → stop/native playback if used → transcript → details.
- If transcript uses `<details>`, ensure its summary is clear and the same content is not duplicated confusingly for screen readers.
- Errors use `role="status"` or `role="alert"` according to urgency.
- Do not automatically move focus when playback starts.
- At 200% zoom, no control or transcript is clipped.

## 8. Frontend integration

- Read `data.briefing_element`.
- Render it through the new focused component rather than adding another large block to `AdaptiveDashboardPage.jsx`.
- Use `identity={`${snapshot}:${briefing calculation/content identity}`}` so existing audio is invalidated on any relevant content change.
- Do not compose the briefing by concatenating frontend labels. Use the backend-validated `spoken_text` and claims.
- Integrate `briefing` into the existing glance/explain/inspect system without duplicating modal code.
- Inspection should list included claims with their supporting component names, calculation IDs, source scope, and material qualifiers.
- Do not expose raw JSON in the default UI.
- If the element is unavailable, keep Elements 1–6 intact and show no broken orb/player.

Any backward-compatible improvement to `VoiceoverPlayer` must be tested on Leadership Report and presentation usage. Do not make adaptive-specific styling leak into those pages.

## 9. Tests

### Backend tests

Add tests for:

1. Workforce briefing binds primary state, department disparity, Decision focus, and next check.
2. Retail briefing preserves currency and store-week grain.
3. Ecommerce briefing speaks drop-off only when funnel populations reconcile.
4. Unknown-polarity general data uses neutral language.
5. Nearly flat time series is not narrated as increasing/decreasing.
6. Missing secondary/tertiary/quaternary/quinary elements are skipped without broken punctuation.
7. Missing Decision focus produces a shorter honest briefing or an unavailable result.
8. Partial period qualifier is retained in the transcript.
9. Correlation narration includes association/non-causation wording.
10. Stale component snapshot or calculation ID is rejected.
11. An unbound number or altered unit causes validation failure.
12. Rounding cannot reverse or exaggerate direction.
13. Record-level PII and free-text fields are not narrated.
14. Word and character limits are enforced.
15. Element 7 failure preserves Elements 1–6.
16. `AdaptiveDashboardResponse.version == "adaptive-v7"` and extra fields remain forbidden.

Where an LLM wording path exists, test malformed JSON, inserted numbers, changed direction, causal language, timeout, and fallback to deterministic copy.

### Frontend/component tests or meaningful verification

Verify:

- Listen triggers one request with the exact validated briefing text.
- Loading text appears immediately.
- Stop aborts the request and playback.
- Snapshot/text changes abort and revoke old audio.
- Playback events update orb state.
- Audio failure leaves transcript available and retry possible.
- No autoplay occurs.
- Reduced motion retains a visible static orb and textual state.
- Leadership Report voiceover still works.
- Presentation orb still works.

Run:

```bash
backend/.venv/bin/python -m pytest backend/tests/test_adaptive_dashboard.py
backend/.venv/bin/python -m pytest backend/tests
cd frontend && npm test && npm run build
```

## 10. Rendered acceptance

Inspect the real `#adaptive` page with an actual selected dataset at:

- 320 px
- 390 px
- 768 px
- Normal desktop width
- Desktop at 200% zoom

Verify:

- The written briefing can be understood in under one minute.
- It contains no unsupported number, cause, target, forecast, or performance label.
- The orb animation remains present.
- Idle, preparing, speaking, stopped, ended, and error states are distinguishable.
- Audio plays only after user action.
- Stop works during preparation and playback.
- Source changes cannot leave stale audio active.
- Transcript remains usable if local speech is unavailable.
- No overlap with Copilot, mobile navigation, card content, or viewport edge.
- Elements 1–6 remain unchanged and usable.
- Leadership Report and presentation audio have not regressed.

A successful build is not visual or audio acceptance. Actually play and stop the voiceover. If local speech cannot run in the environment, report that verification as unavailable rather than claiming success, and fully verify the failure/transcript path.

## 11. Update the design contract

Append **Revision 9: Element 7 — Executive Briefing with Voice Orb** to `docs/adaptive-dashboard-design.md` covering:

- The executive question answered.
- Evidence-bound claim selection.
- Narration strength and non-causal wording.
- Typed claim provenance.
- Duration/privacy requirements.
- Voice failure isolation.
- Orb preservation, reduced motion, accessibility, and responsive behavior.
- Status: awaiting client approval.

Do not rewrite prior revision history or mark Element 7 approved.

## 12. Handoff and stop condition

Report:

1. The exact written/spoken briefing generated for the currently loaded dataset.
2. Each claim and its supporting component/calculation ID.
3. Word count and estimated duration.
4. Why any candidate fact was omitted.
5. Files changed.
6. Focused and full backend test results.
7. Frontend test/build results.
8. Browser widths and audio states actually verified.
9. Whether local audio playback was personally tested.
10. Any limitation or abstention.

Then ask:

> Is this briefing useful, factually faithful, and comfortable to read and listen to?

Stop after presenting Element 7. Do not implement Element 8, commit, push, merge, or clean unrelated files.
