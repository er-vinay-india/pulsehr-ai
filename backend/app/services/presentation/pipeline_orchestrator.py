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
        # STAGE 1: Reviewing coverage & collecting findings (12%)
        mgr.update_stage(job_id, "layout", "Freezing snapshot & gathering shared evidence package", 12)
        if mgr.is_cancelled(job_id):
            return

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

        # STAGE 2: Planning coverage & prioritizing material findings (25%)
        mgr.update_stage(job_id, "layout", "Planning coverage manifest & prioritizing material findings", 25)
        if mgr.is_cancelled(job_id):
            return

        # STAGE 3: Planning presentation narrative & visual layout selection (40%)
        mgr.update_stage(job_id, "headings", "Adapting presentation narrative & visual layout selection", 40)
        if mgr.is_cancelled(job_id):
            return

        # STAGE 4: Assembling slide layouts & design system (45% -> 68%)
        def _on_slide_progress(slide_num: int, total_slides: int, slide_title: str, category: str = "", **kwargs):
            import time
            clean_title = slide_title.split(":")[0].strip()[:35]
            effective_total = max(total_slides, slide_num, 1)
            pct = 45 + int((slide_num / effective_total) * 22)
            label = f"Constructed slide {slide_num} of {effective_total}: {clean_title}"
            mgr.update_stage(
                job_id,
                "headings",
                label,
                pct,
                extra={
                    "current_slide": slide_num,
                    "total_slides": effective_total,
                    "current_slide_title": slide_title,
                    "current_slide_category": category,
                    "slide_status_list": [
                        {
                            "order": i + 1,
                            "status": "complete" if (i + 1) <= slide_num else ("building" if (i + 1) == slide_num + 1 else "pending")
                        }
                        for i in range(effective_total)
                    ]
                }
            )
            time.sleep(0.12)

        target_total_slides = int(scope.get("target_length") or 0)
        mgr.update_stage(
            job_id,
            "headings",
            "Planning slide blueprints & assembling layout components...",
            46,
            extra={
                "current_slide": 1,
                "total_slides": target_total_slides,
                "current_slide_title": "Slide 1: Executive Architecture",
                "current_slide_category": "Executive",
                "slide_status_list": [
                    {"order": i + 1, "status": "building" if i == 0 else "pending"}
                    for i in range(target_total_slides)
                ]
            }
        )
        if mgr.is_cancelled(job_id):
            return

        deck_spec = generate_presentation_deck_spec(
            scope,
            primary_ctx,
            workspace_evidence=workspace_evidence,
            on_slide_progress=_on_slide_progress,
            on_phase_progress=lambda phase, label, pct: mgr.update_stage(job_id, phase, label, pct)
        )

        # STAGE 5: Auditing deterministic numbers & verifying claim ledger (±0.1%) (70%)
        mgr.update_stage(job_id, "text", "Auditing deterministic numbers & verifying claim ledger (±0.1%)", 70)
        if mgr.is_cancelled(job_id):
            return

        verification_res = verify_presentation_claims(deck_spec, deck_spec["evidence_ledger"])
        deck_spec["metadata"]["validation_summary"] = verification_res

        mgr.update_stage(job_id, "animation", "Applying content animation preferences", 73)
        for slide in deck_spec["slides"]:
            slide["animation"] = scope.get("animation", "none")
            if scope.get("background_image"):
                slide["background_image"] = scope["background_image"]
                slide["scrim_opacity"] = scope.get("scrim_opacity", 70)
        if mgr.is_cancelled(job_id):
            return
        mgr.update_stage(job_id, "transitions", "Applying slide transitions", 75)
        deck_spec["metadata"]["transition"] = scope.get("transition", "none")
        for slide in deck_spec["slides"]:
            slide["transition"] = scope.get("transition", "none")
        if mgr.is_cancelled(job_id):
            return
        mgr.update_stage(job_id, "transcript", "Preparing HRIDAY speaker transcripts from slide content", 78)
        for slide in deck_spec["slides"]:
            if not slide.get("speaker_notes"):
                bullets = [item if isinstance(item, str) else item.get("text", "") for item in slide.get("bullets", [])]
                slide["speaker_notes"] = "\n".join(filter(None, [slide.get("title"), slide.get("narrative"), *bullets]))
        if mgr.is_cancelled(job_id):
            return

        # STAGE 6: Auditing spatial bounding boxes, text density & chart geometry (80%)
        mgr.update_stage(job_id, "formatting", "Auditing spatial bounding boxes, text density & chart geometry", 80)
        if mgr.is_cancelled(job_id):
            return

        audit_res = PresentationQualityAuditor.audit_deck_spec(deck_spec, deck_spec["evidence_ledger"])
        deck_spec["quality_audit"] = audit_res

        # STAGE 7: Executing bounded repairs (layout tuning, concise rewriting, table splitting) (90%)
        mgr.update_stage(job_id, "formatting", "Executing bounded repairs (layout tuning, concise rewriting, table splitting)", 90)
        if mgr.is_cancelled(job_id):
            return

        if audit_res.get("issues"):
            if audit_res.get("can_repair", True):
                deck_spec = PresentationQualityAuditor.execute_bounded_repair(deck_spec, audit_res)
                # Re-audit post-repair
                audit_res_2 = PresentationQualityAuditor.audit_deck_spec(deck_spec, deck_spec["evidence_ledger"])
                deck_spec["quality_audit"] = audit_res_2
                if audit_res_2.get("critical_count", 0) > 0:
                    critical_msgs = [i["message"] for i in audit_res_2["issues"] if i["severity"] == "critical"]
                    raise ValueError(f"Presentation audit failed with critical issue(s) after bounded repair: {'; '.join(critical_msgs)}")
            else:
                critical_msgs = [i["message"] for i in audit_res["issues"] if i["severity"] == "critical"]
                raise ValueError(f"Presentation quality audit failed: {'; '.join(critical_msgs)}")

        # Revalidate after any bounded layout repairs; never publish changed claims.
        if scope.get("deck_style") == "decision_brief":
            verified = verify_presentation_claims(deck_spec, deck_spec["evidence_ledger"])
            deck_spec["metadata"]["validation_summary"] = verified
            if verified["status"] != "PASSED":
                raise ValueError("Decision slide claims differ from the frozen overview evidence.")

        # STAGE 8: Generating verified native PPTX & persisting presentation deck (95% -> 100%)
        mgr.update_stage(job_id, "formatting", "Generating verified native PPTX & persisting presentation deck", 95)
        if mgr.is_cancelled(job_id):
            return

        from ..report_generator import export_spec_to_pptx
        pptx_path = export_spec_to_pptx(deck_spec)
        deck_spec["pptx_filename"] = pptx_path.name

        # Persist deck specification to database
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

        mgr.update_stage(job_id, "ready", "Presentation ready to review", 100, deck_id=deck_id)

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
