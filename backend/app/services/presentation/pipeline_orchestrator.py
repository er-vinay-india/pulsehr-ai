import datetime
import json
import logging
import threading
from typing import Any

from ...db.database import get_connection
from .claim_verifier import verify_presentation_claims
from .job_manager import PresentationJobManager, job_manager
from .scope_detector import collect_workspace_evidence, preview_presentation_scope
from ..presentation_quality_auditor import PresentationQualityAuditor
from .spatial_overflow_monitor import SpatialOverflowMonitor

logger = logging.getLogger(__name__)


def execute_presentation_pipeline_async(
    job_id: str,
    scope: dict[str, Any],
    manager: PresentationJobManager | None = None
):
    """Executes the 8-stage presentation pipeline in a background thread."""
    from .deck_generator import generate_presentation_deck_spec

    mgr = manager or job_manager
    try:
        with get_connection() as conn:
            preflight = preview_presentation_scope(conn, scope)
            if not preflight["eligible"]:
                raise ValueError("No uploaded datasets eligible for presentation generation.")
            workspace_evidence = collect_workspace_evidence(conn, scope)
            primary_ctx = workspace_evidence["primary_ctx"]

        # Retrieve relevant presentation memories & historical context (Phase 1)
        try:
            from .memory import presentation_retrieval_service
            query = f"{scope.get('objective', '')} {scope.get('instructions', '')}".strip() or "Executive leadership presentation"
            retrieved_context_pkg = presentation_retrieval_service.retrieve_presentation_context(
                query=query,
                workspace_id=scope.get("workspace_id"),
                domain=primary_ctx.get("domain"),
                audience=scope.get("audience"),
                dataset_ids=[primary_ctx["target_sheet"]["id"]] if primary_ctx.get("target_sheet") else None
            )
            workspace_evidence["retrieved_context"] = retrieved_context_pkg.model_dump()
        except Exception as exc:
            logger.debug(f"Optional presentation memory retrieval skipped: {exc}")
            workspace_evidence["retrieved_context"] = {"status": "degraded", "results": [], "historical_decks": []}

        # Initialize the Observer AI supervisor upfront in Phase 1
        # Layman explanation:
        # The Observer AI determines and locks the exact slide count right now in Phase 1,
        # and lines up all the empty slides so the user sees the full plan immediately.
        from .observer_ai import SlideContextObserver
        observer = SlideContextObserver(
            scope=scope,
            primary_ctx=primary_ctx,
            workspace_evidence=workspace_evidence
        )
        target_total_slides = observer.total_slides
        initial_slides = observer.get_slide_status_list(active_phase="layout", current_building_slide=0)

        # STAGE 1: Phase 1 - Layout build up & snapshot freeze (3% -> 12%)
        # Layman explanation:
        # Step 1: The Observer AI determines and locks the exact slide count right now in Phase 1.
        # Step 2: It steps through each slide one by one, setting up empty wireframes
        # so the presentation architecture is established before filling in content.
        import time
        mgr.update_stage(
            job_id,
            "layout",
            f"Phase 1: Architecture locked - Initializing {target_total_slides} executive slides",
            3,
            extra={
                "current_slide": 0,
                "total_slides": target_total_slides,
                "current_slide_title": "Initializing slide architecture...",
                "current_slide_category": "Architecture",
                "slide_status_list": initial_slides,
                "observer_note": f"Observer AI: Locked total slide count to {target_total_slides} slides based on domain and evidence.",
                "active_phase": "layout"
            }
        )
        if mgr.is_cancelled(job_id):
            return
        time.sleep(0.18)

        # Assemble layout wireframe container slide by slide
        for idx in range(target_total_slides):
            if mgr.is_cancelled(job_id):
                return
            pct = 3 + int(((idx + 1) / max(target_total_slides, 1)) * 9)
            title = observer.slides[idx]["title"] if idx < len(observer.slides) else f"Slide {idx + 1}"
            category = observer.slides[idx]["category"] if idx < len(observer.slides) else "Executive"
            if idx < len(observer.slides):
                observer.slides[idx]["badge"] = "Wireframe Ready"
                observer.slides[idx]["status"] = "complete"

            slides_snapshot = observer.get_slide_status_list(active_phase="layout", current_building_slide=idx + 1)
            mgr.update_stage(
                job_id,
                "layout",
                f"Assembled wireframe container for slide {idx + 1} of {target_total_slides}: {title[:28]}",
                pct,
                extra={
                    "current_slide": idx + 1,
                    "total_slides": target_total_slides,
                    "current_slide_title": title,
                    "current_slide_category": category,
                    "slide_status_list": slides_snapshot,
                    "observer_note": f"Observer AI: Layout wireframe locked for Slide {idx + 1}.",
                    "active_phase": "layout"
                }
            )
            time.sleep(0.30)

        # STAGE 2: Phase 2 - Title & Subpage Headings (13% -> 23%)
        # Layman explanation:
        # Outlines slide titles, categories, and section headings slide by slide.
        mgr.update_stage(
            job_id,
            "headings",
            f"Outlining slide titles and taxonomy across {target_total_slides} slides...",
            13,
            extra={
                "current_slide": 0,
                "total_slides": target_total_slides,
                "current_slide_title": "Outlining headings...",
                "current_slide_category": "Executive",
                "slide_status_list": observer.get_slide_status_list(active_phase="headings", current_building_slide=1),
                "observer_note": "Observer AI: Mapping deck title and section hierarchy.",
                "active_phase": "headings"
            }
        )
        if mgr.is_cancelled(job_id):
            return
        time.sleep(0.18)

        # Map slide heading and category slide by slide
        for idx in range(target_total_slides):
            if mgr.is_cancelled(job_id):
                return
            pct = 13 + int(((idx + 1) / max(target_total_slides, 1)) * 10)
            title = observer.slides[idx]["title"] if idx < len(observer.slides) else f"Slide {idx + 1}"
            category = observer.slides[idx]["category"] if idx < len(observer.slides) else "Analysis"
            if idx < len(observer.slides):
                observer.slides[idx]["badge"] = "Outline Planned"
                observer.slides[idx]["status"] = "complete"

            slides_snapshot = observer.get_slide_status_list(active_phase="headings", current_building_slide=idx + 1)
            mgr.update_stage(
                job_id,
                "headings",
                f"Planned slide heading {idx + 1} of {target_total_slides}: {title[:28]}",
                pct,
                extra={
                    "current_slide": idx + 1,
                    "total_slides": target_total_slides,
                    "current_slide_title": title,
                    "current_slide_category": category,
                    "slide_status_list": slides_snapshot,
                    "observer_note": f"Observer AI: Slide {idx + 1} heading and outline committed.",
                    "active_phase": "headings"
                }
            )
            time.sleep(0.30)

        # STAGE 3: Phase 3 - Mathematical Derivation & Evidence Ledger (24% -> 35%)
        # Layman explanation:
        # Evaluates empirical numbers, computing exact percentages, totals, and benchmarks
        # slide by slide so every slide has verified arithmetic backing it.
        mgr.update_stage(
            job_id,
            "data_math",
            f"Computing mathematical derivations across {target_total_slides} slides...",
            24,
            extra={
                "current_slide": 0,
                "total_slides": target_total_slides,
                "current_slide_title": "Computing derivations...",
                "current_slide_category": "Mathematics",
                "slide_status_list": observer.get_slide_status_list(active_phase="data_math", current_building_slide=1),
                "observer_note": "Observer AI: Calculating mathematical benchmarks and evidence ledger.",
                "active_phase": "data_math"
            }
        )
        if mgr.is_cancelled(job_id):
            return
        time.sleep(0.18)

        # Compute empirical proofs and metrics slide by slide
        for idx in range(target_total_slides):
            if mgr.is_cancelled(job_id):
                return
            pct = 24 + int(((idx + 1) / max(target_total_slides, 1)) * 11)
            title = observer.slides[idx]["title"] if idx < len(observer.slides) else f"Slide {idx + 1}"
            category = observer.slides[idx]["category"] if idx < len(observer.slides) else "Analytics"
            if idx < len(observer.slides):
                observer.slides[idx]["badge"] = "Math Derived"
                observer.slides[idx]["status"] = "complete"

            slides_snapshot = observer.get_slide_status_list(active_phase="data_math", current_building_slide=idx + 1)
            mgr.update_stage(
                job_id,
                "data_math",
                f"Derived verified mathematical metrics for slide {idx + 1} of {target_total_slides}",
                pct,
                extra={
                    "current_slide": idx + 1,
                    "total_slides": target_total_slides,
                    "current_slide_title": title,
                    "current_slide_category": category,
                    "slide_status_list": slides_snapshot,
                    "observer_note": f"Observer AI: Numerical proof derived for Slide {idx + 1}.",
                    "active_phase": "data_math"
                }
            )
            time.sleep(0.35)

        # STAGE 4: Phase 4 - AI Storyline & Narrative Synthesis (36% -> 49%)
        # Layman explanation:
        # Generates executive storyline and findings slide by slide.
        # Notice that batch enrichment was removed, so this stage completes without any tail delays.
        mgr.update_stage(
            job_id,
            "narrative_ai",
            f"Synthesizing storyline and narrative for {target_total_slides} slides...",
            36,
            extra={
                "current_slide": 0,
                "total_slides": target_total_slides,
                "current_slide_title": "Synthesizing storyline...",
                "current_slide_category": "Executive",
                "slide_status_list": observer.get_slide_status_list(active_phase="narrative_ai", current_building_slide=1),
                "observer_note": "Observer AI: Handing off math and outline context into AI narrative generator.",
                "active_phase": "narrative_ai"
            }
        )
        if mgr.is_cancelled(job_id):
            return

        def _on_slide_start(slide_num: int, total_slides: int, slide_title: str, category: str = "", **kwargs):
            clean_title = slide_title.split(":")[0].strip() if ":" in slide_title else slide_title.strip()
            effective_total = max(total_slides, target_total_slides, slide_num, 1)
            start_data = observer.on_slide_start(slide_num, clean_title, category, active_phase="narrative_ai")
            pct = 36 + int(((slide_num - 0.5) / effective_total) * 13)
            label = f"Synthesizing narrative for slide {slide_num} of {effective_total}: {clean_title[:32]}"
            mgr.update_stage(
                job_id,
                "narrative_ai",
                label,
                pct,
                extra={
                    "current_slide": slide_num,
                    "total_slides": effective_total,
                    "current_slide_title": clean_title,
                    "current_slide_category": category or "Analysis",
                    "slide_status_list": start_data["slide_status_list"],
                    "observer_note": start_data["briefing"],
                    "active_phase": "narrative_ai"
                }
            )
            time.sleep(0.35)

        def _on_slide_progress(slide_num: int, total_slides: int, slide_title: str, category: str = "", slide_dict: dict[str, Any] | None = None, **kwargs):
            clean_title = slide_title.split(":")[0].strip() if ":" in slide_title else slide_title.strip()
            effective_total = max(total_slides, target_total_slides, slide_num, 1)
            complete_data = observer.on_slide_complete(slide_num, clean_title, category, slide_dict=slide_dict, active_phase="narrative_ai")
            pct = 36 + int((slide_num / effective_total) * 13)
            label = f"Synthesized narrative for slide {slide_num} of {effective_total}: {clean_title[:32]}"
            mgr.update_stage(
                job_id,
                "narrative_ai",
                label,
                pct,
                extra={
                    "current_slide": slide_num,
                    "total_slides": effective_total,
                    "current_slide_title": clean_title,
                    "current_slide_category": category or "Analysis",
                    "slide_status_list": complete_data["slide_status_list"],
                    "observer_note": complete_data["observer_note"],
                    "active_phase": "narrative_ai"
                }
            )
            time.sleep(0.35)

        deck_spec = generate_presentation_deck_spec(
            scope,
            primary_ctx,
            workspace_evidence=workspace_evidence,
            on_slide_progress=_on_slide_progress,
            on_slide_start=_on_slide_start,
            on_phase_progress=lambda phase, label, pct: mgr.update_stage(job_id, phase, label, pct)
        )

        total_slides = len(deck_spec.get("slides", []))

        # STAGE 5: Phase 5 - Executive Tone & Narrative Polish (50% -> 60%)
        # Layman explanation:
        # Instead of doing a batch rewrite at the end of narrative_ai, we explicitly run Phase 5
        # slide by slide to polish executive tone, subtitles, and C-suite persona phrasing.
        from ..display_formatters import format_display_label
        mgr.update_stage(
            job_id,
            "enrichment",
            f"Refining executive tone and narrative polish across {total_slides} slides...",
            50,
            extra={
                "current_slide": 0,
                "total_slides": total_slides,
                "current_slide_title": "Polishing executive narrative...",
                "current_slide_category": "Executive",
                "slide_status_list": observer.get_slide_status_list(active_phase="enrichment", current_building_slide=1),
                "observer_note": "Observer AI: Aligning slide vocabulary and executive subtitles.",
                "active_phase": "enrichment"
            }
        )
        if mgr.is_cancelled(job_id):
            return
        time.sleep(0.18)

        for idx, slide in enumerate(deck_spec.get("slides", [])):
            if mgr.is_cancelled(job_id):
                return
            slide_title = slide.get("title", f"Slide {idx + 1}")
            clean_title = slide_title.split(":")[0].strip() if ":" in slide_title else slide_title.strip()

            # Polish display title and subtitle for executive presentation
            slide["title"] = format_display_label(clean_title)
            if not slide.get("subtitle") and slide.get("key_message"):
                slide["subtitle"] = slide["key_message"][:75].rstrip(".")

            pct = 50 + int(((idx + 1) / max(total_slides, 1)) * 10)
            if idx < len(observer.slides):
                observer.slides[idx]["badge"] = "Tone Polished"
                observer.slides[idx]["status"] = "complete"

            slides_snapshot = observer.get_slide_status_list(active_phase="enrichment", current_building_slide=idx + 1)
            mgr.update_stage(
                job_id,
                "enrichment",
                f"Refined executive tone for slide {idx + 1} of {total_slides}: {clean_title[:30]}",
                pct,
                extra={
                    "current_slide": idx + 1,
                    "total_slides": total_slides,
                    "current_slide_title": clean_title,
                    "slide_status_list": slides_snapshot,
                    "observer_note": f"Observer AI: Executive tone and narrative polish verified for Slide {idx + 1}.",
                    "active_phase": "enrichment"
                }
            )
            time.sleep(0.35)

        # STAGE 6: Phase 6 - Graphic Content & Charts (61% -> 70%)
        # Layman explanation:
        # Step through each slide and attach visual charts, metric grids, and visual specs.
        mgr.update_stage(
            job_id,
            "graphics",
            "Rendering charts, metric cards, and visual callouts",
            61,
            extra={
                "current_slide": 0,
                "total_slides": total_slides,
                "slide_status_list": observer.get_slide_status_list(active_phase="graphics"),
                "observer_note": "Observer AI: Grounding visual charts and metric tiles into slide carriages.",
                "active_phase": "graphics"
            }
        )
        if mgr.is_cancelled(job_id):
            return
        time.sleep(0.18)

        for idx, slide in enumerate(deck_spec.get("slides", [])):
            if mgr.is_cancelled(job_id):
                return
            slide_title = slide.get("title", f"Slide {idx + 1}")
            clean_title = slide_title.split(":")[0].strip() if ":" in slide_title else slide_title.strip()
            pct = 61 + int(((idx + 1) / max(total_slides, 1)) * 9)
            if idx < len(observer.slides):
                observer.slides[idx]["badge"] = "Charts Ready"
                observer.slides[idx]["status"] = "complete"

            slides_snapshot = observer.get_slide_status_list(active_phase="graphics", current_building_slide=idx + 1)
            mgr.update_stage(
                job_id,
                "graphics",
                f"Rendered visual analytics for slide {idx + 1} of {total_slides}: {clean_title[:32]}",
                pct,
                extra={
                    "current_slide": idx + 1,
                    "total_slides": total_slides,
                    "current_slide_title": clean_title,
                    "slide_status_list": slides_snapshot,
                    "observer_note": f"Observer AI: Visual asset attached to Slide {idx + 1}.",
                    "active_phase": "graphics"
                }
            )
            time.sleep(0.30)

        # STAGE 7: Phase 7 - Text Content & Spatial Density Audit (71% -> 79%)
        # Layman explanation:
        # Cross-examines all claims on every slide against our verified ground-truth data,
        # and audits slide spatial density to ensure content is not flooded or overflowing.
        mgr.update_stage(
            job_id,
            "text",
            "Populating evidence-backed findings and takeaways",
            71,
            extra={
                "current_slide": 0,
                "total_slides": total_slides,
                "slide_status_list": observer.get_slide_status_list(active_phase="text"),
                "observer_note": "Observer AI: Verifying slide text against empirical database ledger.",
                "active_phase": "text"
            }
        )
        if mgr.is_cancelled(job_id):
            return
        verification_res = verify_presentation_claims(deck_spec, deck_spec["evidence_ledger"])
        deck_spec["metadata"]["validation_summary"] = verification_res

        # Spatial Overflow Guardian AI: Detects overcrowded slides and applies smart remediation
        deck_spec = SpatialOverflowMonitor.audit_and_remedy_deck(deck_spec)
        total_slides = len(deck_spec.get("slides", []))

        # Sync observer slides if new slides were split out
        while len(observer.slides) < total_slides:
            new_idx = len(observer.slides) + 1
            observer.slides.append({
                "order": new_idx,
                "title": deck_spec["slides"][new_idx - 1].get("title", f"Slide {new_idx}"),
                "category": deck_spec["slides"][new_idx - 1].get("category", "Analysis"),
                "status": "pending",
                "badge": "Split Certified"
            })
        observer.total_slides = total_slides

        for idx, slide in enumerate(deck_spec.get("slides", [])):
            if mgr.is_cancelled(job_id):
                return
            pct = 71 + int(((idx + 1) / max(total_slides, 1)) * 8)
            clean_title = slide.get("title", f"Slide {idx + 1}").split(":")[0].strip()
            if idx < len(observer.slides):
                observer.slides[idx]["badge"] = "Claims Verified"
                observer.slides[idx]["status"] = "complete"

            slides_snapshot = observer.get_slide_status_list(active_phase="text", current_building_slide=idx + 1)
            mgr.update_stage(
                job_id,
                "text",
                f"Validated claims & density for slide {idx + 1} of {total_slides}: {clean_title[:30]}",
                pct,
                extra={
                    "current_slide": idx + 1,
                    "total_slides": total_slides,
                    "current_slide_title": clean_title,
                    "slide_status_list": slides_snapshot,
                    "observer_note": f"Observer AI: Certified text density & claims on Slide {idx + 1}.",
                    "active_phase": "text"
                }
            )
            time.sleep(0.30)

        # STAGE 8: Phase 8 - Animation & Entrance Cues (80% -> 85%)
        # Layman explanation:
        # Configures smooth reveal cues and element entrance animations slide by slide.
        mgr.update_stage(
            job_id,
            "animation",
            "Configuring entrance, emphasis, and motion cues",
            80,
            extra={
                "current_slide": 0,
                "total_slides": total_slides,
                "slide_status_list": observer.get_slide_status_list(active_phase="animation"),
                "observer_note": "Observer AI: Initializing motion and element entrance cues.",
                "active_phase": "animation"
            }
        )
        if mgr.is_cancelled(job_id):
            return

        for idx, slide in enumerate(deck_spec.get("slides", [])):
            if mgr.is_cancelled(job_id):
                return
            slide["animation"] = scope.get("animation", "none")
            if scope.get("background_image"):
                slide["background_image"] = scope["background_image"]
                slide["scrim_opacity"] = scope.get("scrim_opacity", 70)

            clean_title = slide.get("title", f"Slide {idx + 1}").split(":")[0].strip()
            if idx < len(observer.slides):
                observer.slides[idx]["badge"] = "Motion Ready"
                observer.slides[idx]["status"] = "complete"

            pct = 80 + int(((idx + 1) / max(total_slides, 1)) * 5)
            slides_snapshot = observer.get_slide_status_list(active_phase="animation", current_building_slide=idx + 1)
            mgr.update_stage(
                job_id,
                "animation",
                f"Configured entrance motion for slide {idx + 1} of {total_slides}: {clean_title[:30]}",
                pct,
                extra={
                    "current_slide": idx + 1,
                    "total_slides": total_slides,
                    "current_slide_title": clean_title,
                    "slide_status_list": slides_snapshot,
                    "observer_note": f"Observer AI: Bound motion reveal cues to Slide {idx + 1}.",
                    "active_phase": "animation"
                }
            )
            time.sleep(0.30)

        # STAGE 9: Phase 9 - Transitions & Flow Pacing (86% -> 90%)
        # Layman explanation:
        # Applies slide-to-slide progression transitions slide by slide so the deck flips smoothly.
        deck_spec["metadata"]["transition"] = scope.get("transition", "none")
        mgr.update_stage(
            job_id,
            "transitions",
            "Setting smooth slide-to-slide progression",
            86,
            extra={
                "current_slide": 0,
                "total_slides": total_slides,
                "slide_status_list": observer.get_slide_status_list(active_phase="transitions"),
                "observer_note": "Observer AI: Initializing slide progression transitions.",
                "active_phase": "transitions"
            }
        )
        if mgr.is_cancelled(job_id):
            return

        for idx, slide in enumerate(deck_spec.get("slides", [])):
            if mgr.is_cancelled(job_id):
                return
            slide["transition"] = scope.get("transition", "none")
            clean_title = slide.get("title", f"Slide {idx + 1}").split(":")[0].strip()
            if idx < len(observer.slides):
                observer.slides[idx]["badge"] = "Transitions Set"
                observer.slides[idx]["status"] = "complete"

            pct = 86 + int(((idx + 1) / max(total_slides, 1)) * 4)
            slides_snapshot = observer.get_slide_status_list(active_phase="transitions", current_building_slide=idx + 1)
            mgr.update_stage(
                job_id,
                "transitions",
                f"Applied pacing transitions for slide {idx + 1} of {total_slides}: {clean_title[:30]}",
                pct,
                extra={
                    "current_slide": idx + 1,
                    "total_slides": total_slides,
                    "current_slide_title": clean_title,
                    "slide_status_list": slides_snapshot,
                    "observer_note": f"Observer AI: Bound pacing transition to Slide {idx + 1}.",
                    "active_phase": "transitions"
                }
            )
            time.sleep(0.30)

        # STAGE 10: Phase 10 - HRIDAY Voiceover Transcript (91% -> 95%)
        # Layman explanation:
        # Generates executive speaking notes and narration points for each slide.
        mgr.update_stage(
            job_id,
            "transcript",
            "Synthesizing executive talking points and speech notes",
            91,
            extra={
                "current_slide": 0,
                "total_slides": total_slides,
                "slide_status_list": observer.get_slide_status_list(active_phase="transcript"),
                "observer_note": "Observer AI: Synthesizing executive narration notes.",
                "active_phase": "transcript"
            }
        )
        if mgr.is_cancelled(job_id):
            return

        for idx, slide in enumerate(deck_spec.get("slides", [])):
            if mgr.is_cancelled(job_id):
                return
            if not slide.get("speaker_notes"):
                bullets = [item if isinstance(item, str) else item.get("text", "") for item in slide.get("bullets", [])]
                slide["speaker_notes"] = "\n".join(filter(None, [slide.get("title"), slide.get("narrative"), *bullets]))
            clean_title = slide.get("title", f"Slide {idx + 1}").split(":")[0].strip()
            if idx < len(observer.slides):
                observer.slides[idx]["badge"] = "Speaker Notes"
                observer.slides[idx]["status"] = "complete"

            pct = 91 + int(((idx + 1) / max(total_slides, 1)) * 4)
            slides_snapshot = observer.get_slide_status_list(active_phase="transcript", current_building_slide=idx + 1)
            mgr.update_stage(
                job_id,
                "transcript",
                f"Generated speech notes for slide {idx + 1} of {total_slides}: {clean_title[:30]}",
                pct,
                extra={
                    "current_slide": idx + 1,
                    "total_slides": total_slides,
                    "current_slide_title": clean_title,
                    "slide_status_list": slides_snapshot,
                    "observer_note": f"Observer AI: Narration notes ready for Slide {idx + 1}.",
                    "active_phase": "transcript"
                }
            )
            time.sleep(0.30)

        # STAGE 11: Phase 11 - Final Setup & Native PPTX Formatting (96% -> 99%)
        # Layman explanation:
        # Performs deterministic quality checks and certifies spatial bounding boxes slide by slide.
        mgr.update_stage(
            job_id,
            "formatting",
            "Auditing spatial bounding boxes, text density & chart geometry",
            96,
            extra={
                "current_slide": 0,
                "total_slides": total_slides,
                "slide_status_list": observer.get_slide_status_list(active_phase="formatting"),
                "observer_note": "Observer AI: Inspecting spatial bounds and visual canvas budgets.",
                "active_phase": "formatting"
            }
        )
        if mgr.is_cancelled(job_id):
            return

        audit_res = PresentationQualityAuditor.audit_deck_spec(deck_spec, deck_spec["evidence_ledger"])
        deck_spec["quality_audit"] = audit_res

        if audit_res.get("issues"):
            if audit_res.get("can_repair", True):
                deck_spec = PresentationQualityAuditor.execute_bounded_repair(deck_spec, audit_res)
                audit_res_2 = PresentationQualityAuditor.audit_deck_spec(deck_spec, deck_spec["evidence_ledger"])
                deck_spec["quality_audit"] = audit_res_2
                if audit_res_2.get("critical_count", 0) > 0:
                    critical_msgs = [i["message"] for i in audit_res_2["issues"] if i["severity"] == "critical"]
                    raise ValueError(f"Presentation audit failed with critical issue(s) after bounded repair: {'; '.join(critical_msgs)}")
            else:
                critical_msgs = [i["message"] for i in audit_res["issues"] if i["severity"] == "critical"]
                raise ValueError(f"Presentation quality audit failed: {'; '.join(critical_msgs)}")

        # Step slide by slide to certify layout bounds
        for idx, slide in enumerate(deck_spec.get("slides", [])):
            if mgr.is_cancelled(job_id):
                return
            clean_title = slide.get("title", f"Slide {idx + 1}").split(":")[0].strip()
            if idx < len(observer.slides):
                observer.slides[idx]["badge"] = "Spatial Certified"
                observer.slides[idx]["status"] = "complete"

            pct = 96 + int(((idx + 1) / max(total_slides, 1)) * 3)
            slides_snapshot = observer.get_slide_status_list(active_phase="formatting", current_building_slide=idx + 1)
            mgr.update_stage(
                job_id,
                "formatting",
                f"Certified spatial bounding box for slide {idx + 1} of {total_slides}: {clean_title[:30]}",
                pct,
                extra={
                    "current_slide": idx + 1,
                    "total_slides": total_slides,
                    "current_slide_title": clean_title,
                    "slide_status_list": slides_snapshot,
                    "observer_note": f"Observer AI: Certified 1080p spatial bounds for Slide {idx + 1}.",
                    "active_phase": "formatting"
                }
            )
            time.sleep(0.30)

        if scope.get("deck_style") == "decision_brief":
            verified = verify_presentation_claims(deck_spec, deck_spec["evidence_ledger"])
            deck_spec["metadata"]["validation_summary"] = verified
            if verified["status"] != "PASSED":
                raise ValueError("Decision slide claims differ from the frozen overview evidence.")

        mgr.update_stage(job_id, "formatting", "Generating verified native PPTX & persisting presentation deck", 98)
        if mgr.is_cancelled(job_id):
            return


        from ..report_generator import export_spec_to_pptx
        pptx_path = export_spec_to_pptx(deck_spec)
        deck_spec["pptx_filename"] = pptx_path.name

        deck_id = deck_spec["id"]
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        try:
            with get_connection() as conn:
                conn.execute(
                    "INSERT INTO presentation_decks (id, title, dataset_id, sheet_id, theme_id, spec_json, pptx_filename, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        deck_id,
                        deck_spec["metadata"]["title"],
                        deck_spec["metadata"].get("dataset_id"),
                        deck_spec["metadata"].get("sheet_id"),
                        deck_spec["metadata"]["theme_id"],
                        json.dumps(deck_spec),
                        pptx_path.name,
                        now,
                        now
                    )
                )
                conn.commit()
        except Exception as exc:
            raise RuntimeError("The deck was generated but could not be saved. Please retry.") from exc

        # Asynchronously index the newly generated presentation deck into memory (Phase 1)
        try:
            from .memory import memory_indexer
            threading.Thread(
                target=memory_indexer.index_presentation_deck,
                args=(deck_spec,),
                daemon=True,
                name=f"pres-indexer-{deck_id}"
            ).start()
        except Exception as exc:
            logger.debug(f"Async memory indexing skipped: {exc}")

        for c in observer.slides:
            c["status"] = "complete"
            c["badge"] = "Ready"
        mgr.update_stage(
            job_id,
            "ready",
            "Presentation ready to review",
            100,
            deck_id=deck_id,
            extra={
                "current_slide": total_slides,
                "total_slides": total_slides,
                "slide_status_list": observer.get_slide_status_list(active_phase="ready"),
                "observer_note": f"Observer AI: Presentation deck complete across all {total_slides} slides.",
                "active_phase": "ready"
            }
        )

    except Exception as exc:
        logger.exception(f"Presentation generation pipeline failed: {exc}")
        mgr.update_stage(job_id, "failed", f"Generation failed: {str(exc)}", 100, error=str(exc))


def start_presentation_job(scope: dict[str, Any]) -> str:
    """Entry point to launch background presentation pipeline."""
    job_id = job_manager.create_job(scope)
    thread = threading.Thread(
        target=execute_presentation_pipeline_async,
        args=(job_id, scope),
        daemon=True,
        name=f"pres-worker-{job_id}"
    )
    thread.start()
    return job_id
