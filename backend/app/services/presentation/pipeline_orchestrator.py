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
        mgr.update_stage(job_id, "collecting_findings", "Freezing snapshot & gathering shared evidence package", 12)
        if mgr.is_cancelled(job_id):
            return

        with get_connection() as conn:
            preflight = preview_presentation_scope(conn, scope)
            if not preflight["eligible"]:
                raise ValueError("No uploaded datasets eligible for presentation generation.")
            workspace_evidence = collect_workspace_evidence(conn, scope)
            primary_ctx = workspace_evidence["primary_ctx"]

        # STAGE 2: Planning coverage & prioritizing material findings (25%)
        mgr.update_stage(job_id, "planning_coverage", "Planning coverage manifest & prioritizing material findings", 25)
        if mgr.is_cancelled(job_id):
            return

        # STAGE 3: Planning presentation narrative & visual layout selection (40%)
        mgr.update_stage(job_id, "planning_presentation", "Adapting presentation narrative & visual layout selection", 40)
        if mgr.is_cancelled(job_id):
            return

        # STAGE 4: Assembling slide layouts & design system (45% -> 68%)
        def _on_slide_progress(slide_num: int, total_slides: int, slide_title: str, category: str = "", **kwargs):
            import time
            clean_title = slide_title.split(":")[0].strip()[:35]
            pct = 45 + int((slide_num / max(1, total_slides)) * 22)
            label = f"Constructed slide {slide_num} of {total_slides}: {clean_title}"
            mgr.update_stage(
                job_id,
                "building_slides",
                label,
                pct,
                extra={
                    "current_slide": slide_num,
                    "total_slides": total_slides,
                    "current_slide_title": slide_title,
                    "current_slide_category": category,
                    "slide_status_list": [
                        {
                            "order": i + 1,
                            "status": "complete" if (i + 1) <= slide_num else ("building" if (i + 1) == slide_num + 1 else "pending")
                        }
                        for i in range(total_slides)
                    ]
                }
            )
            time.sleep(0.12)

        target_total_slides = int(scope.get("target_length") or 8)
        mgr.update_stage(
            job_id,
            "building_slides",
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
            on_slide_progress=_on_slide_progress
        )

        # STAGE 5: Auditing deterministic numbers & verifying claim ledger (±0.1%) (70%)
        mgr.update_stage(job_id, "checking_evidence", "Auditing deterministic numbers & verifying claim ledger (±0.1%)", 70)
        if mgr.is_cancelled(job_id):
            return

        verification_res = verify_presentation_claims(deck_spec, deck_spec["evidence_ledger"])
        deck_spec["metadata"]["validation_summary"] = verification_res

        # STAGE 6: Auditing spatial bounding boxes, text density & chart geometry (80%)
        mgr.update_stage(job_id, "checking_layout", "Auditing spatial bounding boxes, text density & chart geometry", 80)
        if mgr.is_cancelled(job_id):
            return

        audit_res = PresentationQualityAuditor.audit_deck_spec(deck_spec, deck_spec["evidence_ledger"])
        deck_spec["quality_audit"] = audit_res

        # STAGE 7: Executing bounded repairs (layout tuning, concise rewriting, table splitting) (90%)
        mgr.update_stage(job_id, "repairing_issues", "Executing bounded repairs (layout tuning, concise rewriting, table splitting)", 90)
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
        mgr.update_stage(job_id, "finalizing_presentation", "Generating verified native PPTX & persisting presentation deck", 95)
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
            logger.warning(f"Could not persist presentation deck to database: {exc}")

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
