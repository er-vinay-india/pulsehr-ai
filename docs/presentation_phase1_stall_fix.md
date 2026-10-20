# HIGHVIEW — PRESENTATION PHASE-1 STALL FIX

## Root cause and reproduction

The UI's first phase maps to `brief_setup` (backend phase index 0). It remained at 3% while `collect_workspace_evidence` prepared the entire evidence package and optional historical memories. On a cold narrative cache, the exact blocking call was:

`execute_presentation_pipeline_async → collect_workspace_evidence → PresentationIntelligenceAdapter → _legacy_collect_workspace_evidence → build_shared_evidence_package → get_or_generate_executive_story → generate_ai_narrative → ModelGateway.generate`.

The writer role calls Ollama `/api/chat`, initially `gemma4:12b`, with a 45-second HTTP inactivity timeout and governed model fallback. The prompt requests a short executive narrative grounded in computed facts; no raw prompt/data is included here. One request timing out did not bound the total multi-model operation or update the presentation phase. The cold-cache reproduction spent 79.372 seconds in ModelGateway, 79.424 seconds in the executive-story call, and 79.739 seconds in evidence collection. Warm evidence collection took 0.310 seconds, plus 0.312 seconds for memory retrieval. No deadlock or lost frontend event was observed.

Reproduction used the current source, real local models, and an isolated copy of existing data at localhost:8011, to avoid certifying by modifying the live database. Request: `POST /api/presentations/generate`. Dataset 99795, sheet 9967451. Baseline job `pres_job_4453c8f001a2` started 2026-10-20 05:03:28.618603 UTC; first phase started 05:03:28.620623; completion 05:04:48.560885. Job was genuinely busy, but its phase label/state incorrectly kept saying brief setup.

## Internal trace

| Step/function | Expected state | Observed before fix | Dependency/event/next state |
|---|---|---|---|
| UI/API client → POST generate | New independent job | New job ID and worker | No SSE: polling architecture |
| create_job → background thread | Brief setup | Persisted initial state could disagree with API | Initial state now brief_setup/3% |
| preview_presentation_scope | Validate sources then complete brief | Completed quickly | Scope bounded at 120s total wall time |
| collect_workspace_evidence | Evidence audit active | Still brief_setup/3% | Evidence phase now persisted before loading |
| get_or_generate_executive_story | Await bounded writer/fallback | 79.4s cold-cache delay | Existing writer timeout; total evidence budget now 600s |
| retrieve_presentation_context | Optional memory | Also inside first phase | Existing degraded fallback retained; 35s total budget |
| update_stage | Atomic phase/status/progress write | Persistence failures logged only at debug | Exceptions surfaced; ordered phase history persisted; terminal writes repaired on next successful poll |
| GET jobs/{id} → frontend | Current persisted job | Accurately showed incorrectly persisted phase | Existing polling retained; no SSE implementation to repair |
| Later phases → exports → deck insert | Real artifacts then ready | Existing pipeline | Watchdog at 900s per phase; no renderer/truth/routing changes |

## Runtime policy

All timeouts are configurable environment variables: `PRESENTATION_SCOPE_TIMEOUT_SECONDS=120`, `PRESENTATION_EVIDENCE_TIMEOUT_SECONDS=600`, `PRESENTATION_MEMORY_TIMEOUT_SECONDS=35`, `PRESENTATION_PHASE_TIMEOUT_SECONDS=900`, `PRESENTATION_HEARTBEAT_SECONDS=15`. The generous evidence deadline allows multiple 45-second writer/fallback/identity attempts and existing 60-second SQLite busy waits. Heartbeats do not invent progress or reset the absolute phase deadline. A watchdog runs independently of frontend polling. Timed-out dependency results cannot revive failed jobs or publish presentation records; Python cannot forcibly terminate the abandoned daemon dependency itself. Existing HTTP/SQLite dependency limits remain in place.

Fatal exceptions produce a persisted error code and retryable failure. Unexpected worker exit is caught. Progress-write failure is no longer silently logged; a terminal state whose write failed is repaired on the next successful poll. Retry creates a new job ID. Existing owner-death recovery remains covered by tests.

## Real generation certification

Fixed cold-cache job: `pres_job_ed4f9bdc97d7`, dataset 99795, sheet 9967451, deliverable both, theme Amber Brush. Started 2026-10-20 05:05:34.822091 UTC. Brief setup started 05:05:34.833339; ended 05:05:34.880206 (47ms); evidence phase started in the same persisted transition (0ms gap). Polling while the model was active returned evidence_audit/10%, refreshed heartbeat_at, dependency workspace_evidence. No return to the first phase.

Evidence loading: 91.455s; model generation: 90.656s; memory retrieval: 5.080s. Evidence phase completed 05:07:11.428514. Narrative started then; headlines first started 05:07:11.436306; layout 05:07:11.437443; reconciliation 05:07:11.452478; graphics 05:07:11.454121; polish 05:07:11.455746; visual QA 05:07:11.458144; animation 05:07:11.459984; speaker notes 05:07:11.461856; export QA 05:07:11.463393; ready 05:07:12.127204. Completion persisted 05:07:12.127327 (97.305s total). The existing per-slide headlines/layout callbacks repeat those phases; this behavior was not redesigned.

Deck record `deck_9dafe5f66a1a`: five slides, three chart specifications. PPTX ZIP integrity passed: five slide XML parts and three native chart parts, 1,150,177 bytes. PDF passed pdfinfo: five pages, 960×540pt, 1,442,333 bytes. Export/rendering code and slide architecture were not changed.

## Validation and release gates

The final focused pipeline/runtime/recovery run is recorded separately below; the broader Track3 run passed all 61 Track3 checks. The first focused run had one new-test import error, corrected and verified by the subsequent runtime/recovery rerun. An initial-stage assertion in the existing cancellation test was updated to require brief_setup/3% instead of legacy pre-pipeline states.

The required full backend run completed once: 2,240 passed / 2,247 total; seven failures. The cancellation assertion above was one failure and is covered by the final focused rerun. The other six were outside this fix's scope:

- tests/sdr/test_sdr2_certification_corpus.py::test_sdr2_certification_corpus_benchmark
- tests/sdr/test_sdr7_explorer_api.py::test_sdr7_p0_database_invariant
- tests/sdr/test_sdr_certification_corpus.py::test_sdr1_certification_corpus_benchmark
- tests/test_evidence_fast_retrieval.py::test_paginated_related_evidence_service
- tests/test_ingestion_v2_hriday_cutover.py::test_p0_database_invariant
- tests/test_ingestion_v2_production_certification.py::test_p0_database_invariant

A targeted recheck of those six failures passed 4/6: all three P0 invariants and Evidence retrieval now pass. Only the SDR1 and SDR2 certification benchmark failures remain unresolved. Those systems were not changed by this task. The final friendly timeout-message paths also passed 7/7.

The full suite regenerated a timing baseline and four workbook metadata timestamps; only those confirmed test-generated changes were restored. No frontend code changed in this task, so no frontend rebuild was required. Recent phase history is retained for 80 events; all phase transitions are also logged.

Final pipeline/runtime/recovery: **47/47 PASS**. Track3: **61/61 PASS**. Combined unique presentation/runtime/recovery/Track3 checks: **108/108 PASS** across those runs.

P0 was already different before implementation: SHA256 `57e407aff4a59f6af8205cb3269e40a079f43bc30877a35c4d231ac65d79ad05`, size 70,385,664. Requested SHA256 was `1561d64eeae26f4d30926371740d6ca9dc41eb6ea7c537281763b7d5aabd9496`. A later read during concurrent application work returned `98a979466977d59d117e441a191276ce78ec45064a5e108edd273abc126945ab`, same size. This task did not restore, replace, or intentionally edit the live database; reproduction and tests used isolated databases. Final verification returned the required SHA256 `1561d64eeae26f4d30926371740d6ca9dc41eb6ea7c537281763b7d5aabd9496` and size 70,385,664. P0 is EXACT at final verification; the earlier mismatches explain the checksum failures in the full run.

Other ongoing work left the shared checkout dirty. Those edits were not staged or modified by this task. Remote publication requires approval of the exact configured destination after the earlier automatic push rejection; no push was attempted in this task.


## Requested certification summary

| Check | Result |
|---|---|
| Root cause | Slow cold-cache evidence/model work incorrectly persisted as brief setup; no total dependency/phase deadline |
| Backend actually stuck | NO deadlock observed; synchronous model/fallback wait reproduced |
| Frontend stale | NO; it faithfully displayed the incorrectly persisted phase |
| Blocking function | get_or_generate_executive_story → ModelGateway.generate |
| Dependency | Ollama writer /api/chat, gemma4:12b then governed fallback |
| Timeout previously present | YES per HTTP attempt; NO total presentation dependency/phase limit |
| Timeout now present | YES; configurable wall budgets plus independent phase watchdog |
| Phase transition persistence fixed | PASS |
| SSE/progress fixed | PASS for persisted polling state; SSE N/A (not used) |
| Exception propagation fixed | PASS |
| Watchdog | PASS |
| Stale-job handling | EXISTING policy, recovery regression PASS |
| Focused Phase 1→2 test | PASS |
| Dependency failure test | PASS |
| Never-return timeout test | PASS |
| Event-order test | PASS |
| Real presentation run | PASS, real models and existing data on isolated localhost clone |
| Phase 1 duration | 47ms |
| Phase 2 started | YES |
| Presentation completed | YES, 97.305s total |
| PPTX | PASS, 5 slides / 3 native charts |
| PDF | PASS, 5 pages |
| Track3 | PASS, 61/61 |
| Presentation regression | 108/108 PASS across focused runs |
| Full backend | 2240/2247 passed in full run; cancellation assertion subsequently corrected; 4/6 other failures now pass on recheck; 2 SDR certification benchmark failures unresolved |
| P0 | EXACT at final verification; pre-existing/intermediate mismatches recorded above |
| Working tree | Dirty with unrelated ongoing work, preserved |
| HEAD == origin/main | NO after local task commit; push pending destination approval |
| READY FOR PRESENTATION STALL FIX FREEZE | NO — full-suite/working-tree/publication gates are not green |
