from __future__ import annotations

import datetime
import json
import logging
import re
from functools import wraps
from typing import Any, Literal
from contextlib import contextmanager
from fastapi import APIRouter, HTTPException, Query, status, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel
import sqlite3

from ..core import config
from ..db.database import get_connection
from ..services.data_lifecycle import data_lifecycle_lock


@contextmanager
def session_scope(db_path: Any = None):
    """Module-level session scope delegating to get_connection, respecting test monkeypatching."""
    conn_obj = get_connection(db_path) if db_path else get_connection()
    if hasattr(conn_obj, "__enter__") and hasattr(conn_obj, "__exit__") and not isinstance(conn_obj, sqlite3.Connection):
        with conn_obj as c:
            yield c
    else:
        try:
            yield conn_obj
            if hasattr(conn_obj, "commit"):
                conn_obj.commit()
        except Exception:
            if hasattr(conn_obj, "rollback"):
                conn_obj.rollback()
            raise
        finally:
            if hasattr(conn_obj, "close"):
                conn_obj.close()

from ..services.dataset_deletion import require_live_sources
from ..services.presentation_service import (
    THEMES,
    job_manager,
    start_presentation_job,
    regenerate_single_slide,
    preview_presentation_scope,
    verify_presentation_claims,
)
from ..services.presentation.pipeline_orchestrator import recover_presentation_jobs
from ..services.report_generator import export_spec_to_pptx

from ..services.presentation.slide_mutator import (
    SlideMutator,
    SlideMutationRequest,
    SlideMutationResult,
    SlideMutationAction,
)
from ..services.presentation.studio_models import (
    StudioStage,
    STUDIO_STAGE_LABELS,
    SlideThumbnailState,
    StudioSlideStatus,
    StudioPresentationStatus,
    TargetedRegenerationRequest,
    TargetedRegenerationResult,
)
from pathlib import Path

logger = logging.getLogger(__name__)

from ..services.presentation.image_provider import search_free_images

router = APIRouter(prefix="/api/presentations", tags=["presentations"])


def _serialize_deck_write(function):
    @wraps(function)
    def guarded(*args, **kwargs):
        with data_lifecycle_lock:
            return function(*args, **kwargs)
    return guarded


@router.post("/layout-preview")
def preview_slide_layout(slide: dict[str, Any], theme_id: str | None = None):
    """Resolve one slide locally using the same geometry as PPTX/PDF exports."""
    from ..services.presentation.slide_layout import resolve_slide, SlideLayoutError
    try:
        clean_slide = dict(slide)
        if clean_slide.get("zones") and not clean_slide.get("chart") and clean_slide.get("layout") in ("chart_narrative", "full_chart_takeaway", "two_charts"):
            clean_slide["layout"] = "comparison_split"
        return {"plan": resolve_slide(clean_slide, theme_id)}
    except SlideLayoutError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/theme-assets/{theme_id}/background")
def presentation_theme_background(theme_id: str):
    from ..services.presentation.theme_background import theme_background_path
    if theme_id not in THEMES:
        raise HTTPException(status_code=404, detail="Unknown presentation theme.")
    path = theme_background_path(theme_id)
    if not path or not path.is_file():
        raise HTTPException(status_code=404, detail="This theme has no background artwork.")
    return FileResponse(path, media_type="image/png")


@router.get("/theme-assets/{theme_id}/font")
def presentation_theme_font(theme_id: str):
    from ..services.presentation.theme_background import theme_font_path
    if theme_id not in THEMES:
        raise HTTPException(status_code=404, detail="Unknown presentation theme.")
    path = theme_font_path(theme_id)
    if not path or not path.is_file():
        raise HTTPException(status_code=404, detail="This theme has no bundled title font.")
    return FileResponse(path, media_type="font/ttf")


class GeneratePresentationRequest(BaseModel):
    deck_style: Literal["standard", "decision_brief"] = "standard"
    objective: str | None = None
    audience: str | None = None
    decision_requested: str | None = None
    main_takeaway: str | None = None
    presentation_time_minutes: int | None = 15
    deliverable: Literal["pptx", "pdf", "both"] = "pptx"
    content_preferences: dict[str, list[str]] | None = None
    citation_requirement: Literal["standard", "strict", "footnote_only", "none"] = "standard"
    motion_preference: Literal["none", "subtle", "full"] = "none"
    target_length: int | None = None
    theme_id: str | None = "executive_dark"
    scope_type: str | None = "workspace"  # "workspace" | "connected_group" | "custom_sheets" | "single_sheet"
    sheet_id: int | None = None
    sheet_ids: list[int] | None = None
    group_id: str | None = None
    instructions: str | None = ""
    source_mode: str = "dashboard_truth"
    background_image: str | None = None
    scrim_opacity: int = 70
    transition: Literal["none", "fade", "slide", "scale", "reveal"] = "none"
    animation: Literal["none", "fade"] = "none"
    enable_ai_planner: bool = True
    pipeline_mode: str | None = None
    use_layered_pipeline: bool | None = None


class ReviewGateSignoffRequest(BaseModel):
    approved: bool = True
    user_name: str = "User"
    notes: str | None = None
    expected_revision: int | None = None


class ScopePreviewRequest(BaseModel):
    scope_type: str | None = "workspace"
    sheet_id: int | None = None
    sheet_ids: list[int] | None = None
    group_id: str | None = None


class RevalidateRequest(BaseModel):
    deck_spec: dict[str, Any]


class RegenerateSlideRequest(BaseModel):
    deck_spec: dict[str, Any]
    slide_id: str
    prompt: str


class ExportPptxRequest(BaseModel):
    deck_spec: dict[str, Any]


@router.get("/images/search")
def get_free_images(
    query: str = Query("workplace", description="Search keyword for free royalty-free images"),
    category: str | None = Query(None, description="Category filter (executive, operations, team, analytics)"),
    page_size: int = Query(12, ge=1, le=30),
):
    """Searches commercial royalty-free workplace and enterprise photography with zero API key required."""
    images = search_free_images(query=query, category=category, page_size=page_size)
    return {"images": images, "total": len(images), "query": query}


@router.get("/themes")
def get_themes():
    """Returns available presentation visual themes."""
    return {"themes": list(THEMES.values())}


@router.get("/memory/stats")
def get_presentation_memory_stats():
    """Returns total indexed presentation memories and store health."""
    from ..services.presentation.memory import memory_store
    count = memory_store.count()
    return {
        "status": "healthy",
        "total_memories": count,
        "embedding_model": config.PRESENTATION_EMBEDDING_MODEL,
        "memory_enabled": config.PRESENTATION_MEMORY_ENABLED
    }


@router.get("/memory/search")
def search_presentation_memory(
    query: str = Query(..., description="Semantic search query"),
    domain: str | None = Query(None, description="Optional domain filter"),
    audience: str | None = Query(None, description="Optional audience filter"),
    top_k: int = Query(6, ge=1, le=20)
):
    """Performs semantic search across historical decks, slides, and dataset profiles."""
    from ..services.presentation.memory import presentation_retrieval_service
    res = presentation_retrieval_service.retrieve_presentation_context(
        query=query,
        domain=domain,
        audience=audience,
        top_k=top_k
    )
    return res.model_dump()


@router.get("/memory/similar-decks")
def get_similar_presentation_decks(
    query: str = Query(..., description="Query describing presentation topic or title"),
    domain: str | None = Query(None, description="Optional domain filter"),
    audience: str | None = Query(None, description="Optional audience filter"),
    top_k: int = Query(4, ge=1, le=10)
):
    """Retrieves similar past presentation decks for planning reference."""
    from ..services.presentation.memory import presentation_retrieval_service
    decks = presentation_retrieval_service.find_similar_presentations(
        query=query,
        domain=domain,
        audience=audience,
        top_k=top_k
    )
    return {"query": query, "similar_decks": [d.model_dump() for d in decks]}


@router.post("/scope-preview")
def get_scope_preview(req: ScopePreviewRequest):
    """Preflights presentation scope, reporting periods, partial-year status, and relationship coverage."""
    with session_scope() as conn:
        res = preview_presentation_scope(conn, req.model_dump())
    return res


@router.post("/generate")
def start_presentation_generation(req: GeneratePresentationRequest):
    """Spawns an asynchronous 13-phase presentation generation job."""
    scope = {
        "deck_style": req.deck_style,
        "objective": req.objective or "",
        "audience": req.audience or "",
        "decision_requested": req.decision_requested,
        "main_takeaway": req.main_takeaway,
        "presentation_time_minutes": req.presentation_time_minutes or 15,
        "deliverable": req.deliverable,
        "content_preferences": req.content_preferences or {},
        "citation_requirement": req.citation_requirement,
        "motion_preference": req.motion_preference,
        "target_length": req.target_length,
        "theme_id": req.theme_id or "executive_dark",
        "scope_type": req.scope_type or "workspace",
        "sheet_id": req.sheet_id,
        "sheet_ids": req.sheet_ids or [],
        "group_id": req.group_id,
        "instructions": req.instructions or "",
        "source_mode": req.source_mode,
        "background_image": req.background_image,
        "scrim_opacity": max(0, min(90, req.scrim_opacity)),
        "transition": req.transition,
        "animation": req.animation,
        "enable_ai_planner": req.enable_ai_planner,
        "pipeline_mode": req.pipeline_mode,
        "use_layered_pipeline": req.use_layered_pipeline,
    }
    job_id = start_presentation_job(scope)

    return {
        "job_id": job_id,
        "status": "in_progress",
        "stage": "brief_setup",
        "progress": 3,
        "message": "Initiating 13-phase evidence-based presentation pipeline...",
    }


@router.get("/decks/{deck_id}/evidence")
def get_deck_evidence(deck_id: str):
    """Returns the frozen evidence ledger, snapshot hash, and claim verification summary."""
    with session_scope() as conn:
        row = conn.execute("SELECT spec_json FROM presentation_decks WHERE id = ?", (deck_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Presentation deck not found")
    spec = json.loads(row["spec_json"])
    return {
        "deck_id": deck_id,
        "snapshot_hash": spec.get("metadata", {}).get("data_snapshot_hash"),
        "validation_summary": spec.get("metadata", {}).get("validation_summary"),
        "evidence_ledger": spec.get("evidence_ledger", [])
    }


@router.post("/revalidate")
def revalidate_deck_claims(req: RevalidateRequest):
    """Deterministically re-verifies all slide numerical claims against the evidence ledger within +/- 0.1%."""
    deck_spec = req.deck_spec
    ledger = deck_spec.get("evidence_ledger", [])
    res = verify_presentation_claims(deck_spec, ledger)
    return res


@router.get("/jobs/{job_id}")
def get_presentation_job_status(job_id: str):
    """Polls progress for a background presentation generation job."""
    recover_presentation_jobs(job_id)
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Presentation job not found")
    if job.get("status") == "ready" and job.get("deck_id"):
        try:
            with session_scope() as conn:
                row = conn.execute("SELECT spec_json FROM presentation_decks WHERE id = ?", (job["deck_id"],)).fetchone()
                if row and row["spec_json"]:
                    job["deck"] = json.loads(row["spec_json"])
        except Exception as exc:
            logger.warning(f"Could not attach deck spec to ready presentation job: {exc}")
    
    # Synthesize studio_status for clients consuming unified job payload
    extra = job.get("extra") or {}
    stage = extra.get("studio_stage") or job.get("studio_stage") or job.get("stage", "understanding_data")
    manifest_locked = bool(extra.get("manifest_locked") or job.get("manifest_locked") or job.get("status") == "ready")
    slides_data = extra.get("slides") or job.get("slides") or []
    total_slides = extra.get("total_slides") or job.get("total_slides") or len(slides_data) or 0
    job["studio_status"] = {
        "deck_id": job.get("deck_id"),
        "job_id": job_id,
        "current_stage": stage,
        "stage_label": STUDIO_STAGE_LABELS.get(stage) or job.get("stage_label") or "Processing...",
        "progress_percent": job.get("progress_pct", 0),
        "message": job.get("stage_label") or STUDIO_STAGE_LABELS.get(stage, "Processing..."),
        "manifest_locked": manifest_locked,
        "total_slides": total_slides,
        "rendered_slides": extra.get("rendered_slides") or job.get("rendered_slides") or (len(slides_data) if job.get("status") == "ready" else 0),
        "validated_slides": extra.get("validated_slides") or job.get("validated_slides") or (len(slides_data) if job.get("status") == "ready" else 0),
        "visually_certified_slides": extra.get("visually_certified_slides") or job.get("visually_certified_slides") or (len(slides_data) if job.get("status") == "ready" else 0),
        "failed_slides": 1 if job.get("status") == "failed" else 0,
        "recoverable": job.get("status") != "failed",
        "error": job.get("error"),
        "slides": slides_data,
    }
    return job


@router.get("/jobs/{job_id}/studio-status", response_model=StudioPresentationStatus)
def get_job_studio_status(job_id: str):
    """Returns typed progressive StudioPresentationStatus reflecting real backend state without fake timers."""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Presentation job not found")

    deck_id = job.get("deck_id")
    extra = job.get("extra") or {}
    stage = extra.get("studio_stage") or job.get("studio_stage") or job.get("stage", "understanding_data")
    pct = job.get("progress_pct", 0)
    manifest_locked = bool(extra.get("manifest_locked") or job.get("manifest_locked") or job.get("status") == "ready")
    slides_data = extra.get("slides") or job.get("slides") or []
    total_slides = extra.get("total_slides") or job.get("total_slides") or len(slides_data) or 0
    rendered_slides = extra.get("rendered_slides") or job.get("rendered_slides") or (total_slides if job.get("status") == "ready" else 0)
    validated_slides = extra.get("validated_slides") or job.get("validated_slides") or (total_slides if job.get("status") == "ready" else 0)
    visually_certified = extra.get("visually_certified_slides") or job.get("visually_certified_slides") or (total_slides if job.get("status") == "ready" else 0)

    stage_label = STUDIO_STAGE_LABELS.get(stage) or job.get("stage_label") or "Processing..."

    typed_slides = []
    for i, s in enumerate(slides_data):
        phys_id = s.get("physical_slide_id") or f"SLD-{s.get('order', i + 1)}"
        slide_order = s.get("slide_order") or s.get("order") or i + 1
        slide_title = s.get("title") or f"Slide {i + 1}"
        slide_layout = s.get("layout") or "chart_narrative"
        thumb_url = s.get("thumbnail_url")
        slide_html_url = s.get("html_url") or (f"/api/presentations/decks/{deck_id}/slides/{phys_id}/html" if deck_id else None)
        typed_slides.append(
            StudioSlideStatus(
                physical_slide_id=phys_id,
                slide_order=slide_order,
                title=slide_title,
                layout=slide_layout,
                status=SlideThumbnailState(s.get("status", "PREPARING")),
                thumbnail_url=thumb_url,
                html_url=slide_html_url,
                render_fingerprint=s.get("render_fingerprint"),
                zones=s.get("zones") or [],
                error=s.get("error"),
            )
        )

    return StudioPresentationStatus(
        deck_id=deck_id,
        html_url=f"/api/presentations/decks/{deck_id}/html" if deck_id else None,
        job_id=job_id,
        current_stage=stage,
        stage_label=stage_label,
        progress_percent=pct,
        message=job.get("stage_label") or stage_label,
        manifest_locked=manifest_locked,
        total_slides=total_slides,
        rendered_slides=rendered_slides,
        validated_slides=validated_slides,
        visually_certified_slides=visually_certified,
        failed_slides=1 if job.get("status") == "failed" else 0,
        recoverable=job.get("status") != "failed",
        error=job.get("error"),
        slides=typed_slides,
    )


@router.get("/decks/{deck_id}/slides/{slide_id}/thumbnail")
def get_slide_thumbnail(deck_id: str, slide_id: str):
    """Streams the rendered PNG thumbnail for a specific physical slide."""
    rendered_dir = Path(config.PRESENTATION_VISUAL_QA_DIR) / "rendered_slides" / deck_id

    # 1. Resolve slide index and target slide from spec
    target_idx = None
    target_slide = None
    with session_scope() as conn:
        row = conn.execute("SELECT spec_json FROM presentation_decks WHERE id = ?", (deck_id,)).fetchone()
        if row:
            spec = json.loads(row["spec_json"])
            slides = spec.get("slides", [])

            # Check direct match by physical_slide_id or id (non-empty string)
            for idx, s in enumerate(slides):
                if s.get("physical_slide_id") and str(s.get("physical_slide_id")) == str(slide_id):
                    target_idx = idx
                    target_slide = s
                    break
                if s.get("id") and str(s.get("id")) == str(slide_id):
                    target_idx = idx
                    target_slide = s
                    break

            # Check match by slide-{N} or numeric index
            if target_idx is None:
                if str(slide_id).startswith("slide-"):
                    try:
                        n = int(str(slide_id).split("-")[1])
                        if 1 <= n <= len(slides):
                            target_idx = n - 1
                            target_slide = slides[target_idx]
                    except (ValueError, IndexError):
                        pass
                elif str(slide_id).isdigit():
                    n = int(str(slide_id))
                    if 1 <= n <= len(slides):
                        target_idx = n - 1
                        target_slide = slides[target_idx]
                    elif n == 0 and len(slides) > 0:
                        target_idx = 0
                        target_slide = slides[0]

            # Check artifacts in spec metadata
            if target_slide:
                eff_id = target_slide.get("physical_slide_id") or target_slide.get("id")
                artifacts = spec.get("metadata", {}).get("slide_artifacts", [])
                for art in artifacts:
                    if (art.get("slide_id") == eff_id or art.get("physical_slide_id") == eff_id) and art.get("image_path"):
                        p = Path(art["image_path"])
                        if p.exists():
                            return FileResponse(
                                path=str(p),
                                media_type="image/png",
                                headers={"Cache-Control": "public, max-age=3600"},
                            )

    # 2. Look in rendered_dir using deterministic naming
    if rendered_dir.exists():
        files = sorted(rendered_dir.glob("*.png"))

        # Priority A: If target_idx resolved, match exact slide_{target_idx+1:03d}_*.png
        if target_idx is not None:
            order_prefix = f"slide_{target_idx + 1:03d}_"
            for f in files:
                if f.name.startswith(order_prefix):
                    return FileResponse(
                        path=str(f),
                        media_type="image/png",
                        headers={"Cache-Control": "public, max-age=3600"},
                    )

        # Priority B: Exact physical_slide_id or slide_id word match (not loose substring)
        if slide_id and str(slide_id).lower() != "none":
            for f in files:
                stem = f.stem
                parts = stem.split("_", 2)
                if len(parts) >= 3 and parts[2] == str(slide_id):
                    return FileResponse(
                        path=str(f),
                        media_type="image/png",
                        headers={"Cache-Control": "public, max-age=3600"},
                    )
                if stem.endswith(f"_{slide_id}") or stem == str(slide_id):
                    return FileResponse(
                        path=str(f),
                        media_type="image/png",
                        headers={"Cache-Control": "public, max-age=3600"},
                    )

    raise HTTPException(status_code=404, detail=f"Thumbnail for slide {slide_id} in deck {deck_id} not found.")


@router.get("/jobs/{job_id}/slides/{slide_id}/thumbnail")
def get_job_slide_thumbnail(job_id: str, slide_id: str):
    """Streams the rendered PNG thumbnail for a slide from an in-progress or ready job."""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    deck_id = job.get("deck_id")
    if not deck_id:
        raise HTTPException(status_code=404, detail="Deck not yet established for job")
    return get_slide_thumbnail(deck_id, slide_id)


@router.post("/decks/{deck_id}/regenerate-target", response_model=TargetedRegenerationResult)
def regenerate_presentation_target(deck_id: str, req: TargetedRegenerationRequest):
    """Executes genuine targeted regeneration for a physical slide, zone, or object."""
    from ..services.presentation.targeted_regenerator import TargetedRegenerationService
    if req.deck_id != deck_id:
        req.deck_id = deck_id
    service = TargetedRegenerationService()
    with session_scope() as conn:
        try:
            result = service.regenerate_target(req, conn=conn)
            return result
        except ValueError as exc:
            if "Stale" in str(exc) or "superseded" in str(exc):
                raise HTTPException(status_code=409, detail=str(exc))
            raise HTTPException(status_code=404, detail=str(exc))
        except Exception as exc:
            logger.error(f"Targeted regeneration error: {exc}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(exc))


@router.post("/jobs/{job_id}/cancel")
def cancel_presentation_job(job_id: str):
    """Gracefully cancels a running presentation generation job."""
    cancelled = job_manager.cancel_job(job_id)
    if not cancelled:
        raise HTTPException(status_code=404, detail="Active presentation job not found to cancel")
    return {"job_id": job_id, "status": "cancelled", "message": "Presentation generation cancelled"}


@router.get("/decks")
def list_presentation_decks(limit: int = Query(20, ge=1, le=100)):
    """Lists saved presentation decks from persistent storage."""
    with session_scope() as conn:
        rows = conn.execute(
            """
            SELECT id, title, dataset_id, sheet_id, theme_id, pptx_filename, created_at, updated_at
            FROM presentation_decks
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,)
        ).fetchall()

    decks = []
    for r in rows:
        decks.append({
            "id": r["id"],
            "title": r["title"],
            "dataset_id": r["dataset_id"],
            "sheet_id": r["sheet_id"],
            "theme_id": r["theme_id"],
            "pptx_filename": r["pptx_filename"],
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
        })
    return {"decks": decks}


@router.get("/personas")
def get_dataset_personas(sheet_id: int | None = Query(None)):
    """Returns detected persona and relevant industry-standard personas for the active dataset."""
    from ..services.presentation.persona_router import detect_dataset_persona, get_relevant_personas_for_dataset
    from ..services.presentation.scope_detector import capture_dataset_context

    with session_scope() as conn:
        ctx = capture_dataset_context(conn, sheet_id)
        detected = detect_dataset_persona(ctx, conn)
        relevant = get_relevant_personas_for_dataset(ctx, conn)

    return {
        "detected_persona": detected,
        "relevant_personas": relevant
    }


@router.get("/decks/latest")
def get_latest_presentation_deck():
    """Retrieves the most recently generated PresentationDeckSpec."""
    with session_scope() as conn:
        row = conn.execute(
            """
            SELECT id, title, dataset_id, sheet_id, theme_id, spec_json, pptx_filename, created_at, updated_at
            FROM presentation_decks
            ORDER BY created_at DESC
            LIMIT 1
            """
        ).fetchone()

    if not row:
        return {"deck": None, "exists": False}

    try:
        spec = json.loads(row["spec_json"])
        return {
            "deck": spec,
            "exists": True,
            "id": row["id"],
            "title": row["title"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        }
    except Exception as exc:
        logger.error(f"Error parsing latest deck spec: {exc}")
        return {"deck": None, "exists": False}


@router.delete("/decks/{deck_id}")
def delete_presentation_deck(deck_id: str):
    """Permanently deletes a saved presentation deck and cleans up export artifacts."""
    with session_scope() as conn:
        row = conn.execute("SELECT id, pptx_filename FROM presentation_decks WHERE id = ?", (deck_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Presentation deck not found")

        conn.execute("DELETE FROM presentation_decks WHERE id = ?", (deck_id,))
        conn.execute("UPDATE presentation_jobs SET deck_id = NULL WHERE deck_id = ?", (deck_id,))
        conn.commit()

    try:
        pptx_path = config.EXPORTS_DIR / f"presentation_{deck_id}.pptx"
        if pptx_path.exists():
            pptx_path.unlink()
    except Exception as exc:
        logger.warning(f"Could not delete export file for deck {deck_id}: {exc}")

    return {"status": "success", "id": deck_id, "deleted": True}


@router.get("/decks/{deck_id}")
def get_presentation_deck(deck_id: str):
    """Retrieves full PresentationDeckSpec by deck_id."""
    with session_scope() as conn:
        row = conn.execute(
            "SELECT spec_json FROM presentation_decks WHERE id = ?",
            (deck_id,)
        ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Presentation deck not found")

    try:
        spec = json.loads(row["spec_json"])
        return spec
    except Exception as exc:
        logger.error(f"Error parsing deck spec: {exc}")
        raise HTTPException(status_code=500, detail="Corrupted presentation deck specification")


@router.get("/decks/{deck_id}/review-gates")
def get_deck_review_gates(deck_id: str):
    """Returns the five review gates evaluation and human approval status."""
    with session_scope() as conn:
        row = conn.execute("SELECT spec_json FROM presentation_decks WHERE id = ?", (deck_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Presentation deck not found")
    spec = json.loads(row["spec_json"])
    rg = spec.get("metadata", {}).get("review_gates")
    if not rg:
        from ..services.presentation.review_gates import initialize_review_gates, evaluate_automated_gates
        rg = evaluate_automated_gates(spec)
        spec.setdefault("metadata", {})["review_gates"] = rg
        with session_scope() as conn:
            conn.execute("UPDATE presentation_decks SET spec_json = ? WHERE id = ?", (json.dumps(spec), deck_id))
            conn.commit()
    return rg


@router.post("/decks/{deck_id}/review-gates/{gate_id}/approve")
def approve_review_gate(deck_id: str, gate_id: str, req: ReviewGateSignoffRequest):
    """Records an explicit human approval or rejection for one of the five review gates."""
    with session_scope() as conn:
        row = conn.execute("SELECT spec_json FROM presentation_decks WHERE id = ?", (deck_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Presentation deck not found")
    spec = json.loads(row["spec_json"])
    from ..services.presentation.review_gates import record_human_signoff, initialize_review_gates
    rg = spec.get("metadata", {}).get("review_gates") or initialize_review_gates()
    stored_revision = rg.get("revision", 1)
    if req.expected_revision is not None and req.expected_revision != stored_revision:
        raise HTTPException(
            status_code=409,
            detail=f"Revision mismatch: approval requested for revision {req.expected_revision}, but current deck revision is {stored_revision}."
        )
    try:
        updated_rg = record_human_signoff(
            review_gates=rg,
            gate_id=gate_id,
            approved=req.approved,
            user_name=req.user_name,
            notes=req.notes
        )
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    spec.setdefault("metadata", {})["review_gates"] = updated_rg
    with session_scope() as conn:
        conn.execute("UPDATE presentation_decks SET spec_json = ? WHERE id = ?", (json.dumps(spec), deck_id))
        conn.commit()
    return updated_rg


@router.put("/decks/{deck_id}")
@_serialize_deck_write
def update_presentation_deck(deck_id: str, deck_spec: dict[str, Any]):
    """Saves updated PresentationDeckSpec after user inline edits or theme changes, invalidating relevant review gates."""
    from ..services.presentation.review_gates import invalidate_review_gates_on_edit

    require_live_sources(deck_spec)

    # Retrieve current stored revision from database to guarantee monotonic revision increment
    stored_rev = 0
    with session_scope() as conn:
        row = conn.execute("SELECT spec_json FROM presentation_decks WHERE id = ?", (deck_id,)).fetchone()
        if row:
            try:
                stored_spec = json.loads(row["spec_json"])
                stored_rev = stored_spec.get("metadata", {}).get("review_gates", {}).get("revision", 0)
            except Exception:
                pass

    client_rev = deck_spec.get("metadata", {}).get("review_gates", {}).get("revision", 0)
    base_rev = max(stored_rev, client_rev)
    deck_spec = invalidate_review_gates_on_edit(deck_spec, edited_scope="content", base_revision=base_rev)

    title = deck_spec.get("metadata", {}).get("title") or deck_spec.get("slides", [{}])[0].get("title", "Presentation")
    dataset_id = deck_spec.get("metadata", {}).get("dataset_id")
    sheet_id = deck_spec.get("metadata", {}).get("sheet_id")
    theme_id = deck_spec.get("metadata", {}).get("theme_id") or deck_spec.get("theme", {}).get("id", "executive_dark")
    pptx_filename = deck_spec.get("pptx_filename")
    spec_json = json.dumps(deck_spec)

    with session_scope() as conn:
        conn.execute(
            """
            INSERT INTO presentation_decks (id, title, dataset_id, sheet_id, theme_id, spec_json, pptx_filename, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET
                title = excluded.title,
                dataset_id = excluded.dataset_id,
                sheet_id = excluded.sheet_id,
                theme_id = excluded.theme_id,
                spec_json = excluded.spec_json,
                pptx_filename = excluded.pptx_filename,
                updated_at = CURRENT_TIMESTAMP
            """,
            (deck_id, title, dataset_id, sheet_id, theme_id, spec_json, pptx_filename)
        )
        conn.commit()

    return {"status": "success", "id": deck_id, "updated": True}


@router.post("/regenerate-slide")
def handle_regenerate_slide(req: RegenerateSlideRequest):
    """Regenerates a single slide's narrative and bullet points using targeted AI."""
    try:
        updated_deck = regenerate_single_slide(req.deck_spec, req.slide_id, req.prompt)
        return updated_deck
    except Exception as exc:
        logger.error(f"Slide regeneration error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/mutate-slide", response_model=SlideMutationResult)
def handle_mutate_slide(req: SlideMutationRequest):
    """Deterministically mutates a presentation slide (reslice, retype chart, filter, change theme)."""
    res = SlideMutator.mutate_slide(
        deck_spec=req.deck_spec,
        action=req.action,
        params=req.params,
        slide_index=req.slide_index,
        slide_id=req.slide_id,
        prompt=req.prompt
    )
    if not res.success:
        raise HTTPException(status_code=400, detail=res.error or res.diff_summary)

    # Persist updated deck if persisted deck_id is provided
    if req.deck_id:
        try:
            conn = get_connection()
            conn.execute(
                "UPDATE presentation_decks SET spec_json = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (json.dumps(res.updated_deck_spec), req.deck_id)
            )
            conn.commit()
            conn.close()
        except Exception as exc:
            logger.warning(f"Could not persist mutated deck {req.deck_id}: {exc}")

    return res


@router.post("/export-pptx")
@_serialize_deck_write
def export_presentation_to_pptx(req: ExportPptxRequest):
    """Builds and returns an editable PowerPoint file with native charts from deck spec."""
    deck_spec = req.deck_spec
    require_live_sources(deck_spec)
    from ..services.presentation.review_gates import evaluate_automated_gates
    rg = evaluate_automated_gates(deck_spec)
    deck_spec.setdefault("metadata", {})["review_gates"] = rg

    failed_gates = [
        f"{gid}: {g.get('automated', {}).get('details', 'Failed check')}"
        for gid, g in rg.get("gates", {}).items()
        if g.get("automated", {}).get("status") == "FAILED"
    ]
    if failed_gates:
        raise HTTPException(
            status_code=422,
            detail=f"Delivery blocked: Automated review gate check(s) failed: {'; '.join(failed_gates)}"
        )

    try:
        is_layered = (deck_spec.get("metadata", {}).get("pipeline_mode") == "LAYERED") or bool(deck_spec.get("metadata", {}).get("styled_pptx_path"))

        if deck_spec.get("metadata", {}).get("styled_pptx_path"):
            styled_path = Path(deck_spec["metadata"]["styled_pptx_path"])
            if styled_path.exists():
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                title_raw = deck_spec.get("metadata", {}).get("title") or deck_spec.get("title") or "Executive_Presentation"
                clean_title = re.sub(r'[^a-zA-Z0-9_-]', '_', title_raw)[:40].strip('_') or "Presentation"
                filename = f"{clean_title}_{timestamp}.pptx"
                return FileResponse(
                    path=str(styled_path),
                    filename=filename,
                    media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'}
                )

        if is_layered:
            if deck_spec.get("metadata", {}).get("pptx_path"):
                pptx_p = Path(deck_spec["metadata"]["pptx_path"])
                if pptx_p.exists():
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    title_raw = deck_spec.get("metadata", {}).get("title") or deck_spec.get("title") or "Executive_Presentation"
                    clean_title = re.sub(r'[^a-zA-Z0-9_-]', '_', title_raw)[:40].strip('_') or "Presentation"
                    filename = f"{clean_title}_{timestamp}.pptx"
                    return FileResponse(
                        path=str(pptx_p),
                        filename=filename,
                        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
                    )
            deck_id = deck_spec.get("id") or deck_spec.get("deck_id")
            if deck_id:
                std_path = config.EXPORTS_DIR / f"presentation_{deck_id}.pptx"
                if std_path.exists():
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    title_raw = deck_spec.get("metadata", {}).get("title") or deck_spec.get("title") or "Executive_Presentation"
                    clean_title = re.sub(r'[^a-zA-Z0-9_-]', '_', title_raw)[:40].strip('_') or "Presentation"
                    filename = f"{clean_title}_{timestamp}.pptx"
                    return FileResponse(
                        path=str(std_path),
                        filename=filename,
                        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
                    )

        pptx_path = export_spec_to_pptx(deck_spec)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        title_raw = deck_spec.get("metadata", {}).get("title") or deck_spec.get("title") or "Executive_Presentation"
        clean_title = re.sub(r'[^a-zA-Z0-9_-]', '_', title_raw)[:40].strip('_') or "Presentation"
        filename = f"{clean_title}_{timestamp}.pptx"
        return FileResponse(
            path=str(pptx_path),
            filename=filename,
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.error(f"Export PPTX error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate PowerPoint: {str(exc)}")


@router.post("/export-pdf")
@_serialize_deck_write
def export_presentation_to_pdf(req: ExportPptxRequest):
    """Export the current editor spec, including edits not yet saved to a deck."""
    from ..services.presentation.review_gates import evaluate_automated_gates
    from ..services.report_generator import export_spec_to_pdf
    deck = req.deck_spec
    require_live_sources(deck)
    review = evaluate_automated_gates(deck)
    failures = [g.get('automated', {}).get('details', 'Failed check') for g in review.get('gates', {}).values()
                if g.get('automated', {}).get('status') == 'FAILED']
    if failures:
        raise HTTPException(status_code=422, detail='Delivery blocked: ' + '; '.join(failures))

    if deck.get("metadata", {}).get("styled_pptx_path"):
        styled_path = Path(deck["metadata"]["styled_pptx_path"])
        import shutil
        import subprocess
        soffice = shutil.which("soffice") or shutil.which("libreoffice")
        if soffice and styled_path.exists():
            try:
                subprocess.run(
                    [soffice, "--headless", "--convert-to", "pdf", str(styled_path), "--outdir", str(config.EXPORTS_DIR)],
                    check=True,
                    timeout=30,
                    capture_output=True,
                )
                converted_pdf = config.EXPORTS_DIR / f"{styled_path.stem}.pdf"
                if converted_pdf.exists():
                    title = re.sub(r'[^a-zA-Z0-9_-]', '_', deck.get('metadata', {}).get('title') or deck.get('title') or 'Presentation')[:40]
                    return FileResponse(path=str(converted_pdf), filename=f'{title}.pdf', media_type='application/pdf')
            except Exception as conv_err:
                logger.warning(f"LibreOffice PDF conversion failed: {conv_err}")
        else:
            raise HTTPException(
                status_code=501,
                detail="PDF export requires headless LibreOffice or browser print. Please download the native PowerPoint PPTX or use browser print.",
            )

    try:
        path = export_spec_to_pdf(deck)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    title = re.sub(r'[^a-zA-Z0-9_-]', '_', deck.get('metadata', {}).get('title') or deck.get('title') or 'Presentation')[:40]
    return FileResponse(path=str(path), filename=f'{title}.pdf', media_type='application/pdf')


@router.post("/export-pdf/async", status_code=status.HTTP_202_ACCEPTED)
def export_presentation_to_pdf_async(req: ExportPptxRequest):
    """Phase G4: Enqueues PDF generation in background worker plane and returns HTTP 202 immediately."""
    from ..jobs import worker_plane, JobType
    payload: dict[str, Any] = {"deck_spec": req.deck_spec}
    deck_id = req.deck_spec.get("metadata", {}).get("deck_id") or req.deck_spec.get("id")
    if deck_id:
        payload["deck_id"] = str(deck_id)
    job = worker_plane.submit_job(
        job_type=JobType.PDF_EXPORT,
        payload=payload,
    )
    return {
        "job_id": job.id,
        "job_type": job.job_type.value,
        "status": job.status.value,
        "stage": job.stage,
        "progress_pct": job.progress_pct,
        "poll_url": f"/api/jobs/{job.id}",
        "message": "PDF export job submitted to background worker plane",
    }


@router.post("/export-pptx/async", status_code=status.HTTP_202_ACCEPTED)
def export_presentation_to_pptx_async(req: ExportPptxRequest):
    """Phase G4: Enqueues PowerPoint generation in background worker plane and returns HTTP 202 immediately."""
    from ..jobs import worker_plane, JobType
    payload: dict[str, Any] = {"deck_spec": req.deck_spec}
    deck_id = req.deck_spec.get("metadata", {}).get("deck_id") or req.deck_spec.get("id")
    if deck_id:
        payload["deck_id"] = str(deck_id)
    job = worker_plane.submit_job(
        job_type=JobType.PPTX_EXPORT,
        payload=payload,
    )
    return {
        "job_id": job.id,
        "job_type": job.job_type.value,
        "status": job.status.value,
        "stage": job.stage,
        "progress_pct": job.progress_pct,
        "poll_url": f"/api/jobs/{job.id}",
        "message": "PowerPoint export job submitted to background worker plane",
    }


@router.get("/download/{deck_id}")
@_serialize_deck_write
def download_deck_pptx(deck_id: str):
    """Exports or serves a PowerPoint presentation for a stored deck."""
    deck_spec = None
    with session_scope() as conn:
        row = conn.execute("SELECT spec_json FROM presentation_decks WHERE id = ?", (deck_id,)).fetchone()
    if row:
        deck_spec = json.loads(row["spec_json"])
    elif not (config.EXPORTS_DIR / f"presentation_{deck_id}.pptx").exists():
        raise HTTPException(status_code=404, detail="Presentation deck not found")

    # For layered presentation pipeline decks, prefer the certified styled PPTX artifact directly
    is_layered = (deck_spec and deck_spec.get("metadata", {}).get("pipeline_mode") == "LAYERED") or bool(deck_spec and deck_spec.get("metadata", {}).get("styled_pptx_path"))

    if deck_spec and deck_spec.get("metadata", {}).get("styled_pptx_path"):
        styled_path = Path(deck_spec["metadata"]["styled_pptx_path"])
        if styled_path.exists():
            clean_title = re.sub(r'[^a-zA-Z0-9_-]', '_', deck_spec.get("title") or f"presentation_{deck_id}")[:40].strip('_') or "Presentation"
            filename = f"{clean_title}.pptx"
            return FileResponse(
                path=str(styled_path),
                filename=filename,
                media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'}
            )

    if is_layered:
        if deck_spec and deck_spec.get("metadata", {}).get("pptx_path"):
            pptx_p = Path(deck_spec["metadata"]["pptx_path"])
            if pptx_p.exists():
                clean_title = re.sub(r'[^a-zA-Z0-9_-]', '_', deck_spec.get("title") or f"presentation_{deck_id}")[:40].strip('_') or "Presentation"
                filename = f"{clean_title}.pptx"
                return FileResponse(
                    path=str(pptx_p),
                    filename=filename,
                    media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'}
                )
        std_p = config.EXPORTS_DIR / f"presentation_{deck_id}.pptx"
        if std_p.exists():
            clean_title = re.sub(r'[^a-zA-Z0-9_-]', '_', (deck_spec.get("title") if deck_spec else None) or f"presentation_{deck_id}")[:40].strip('_') or "Presentation"
            filename = f"{clean_title}.pptx"
            return FileResponse(
                path=str(std_p),
                filename=filename,
                media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'}
            )

    if deck_spec and deck_spec.get("slides"):
        require_live_sources(deck_spec)
        from ..services.presentation.review_gates import evaluate_automated_gates
        rg = evaluate_automated_gates(deck_spec)
        deck_spec.setdefault("metadata", {})["review_gates"] = rg

        failed_gates = [
            f"{gid}: {g.get('automated', {}).get('details', 'Failed check')}"
            for gid, g in rg.get("gates", {}).items()
            if g.get("automated", {}).get("status") == "FAILED"
        ]
        if failed_gates:
            raise HTTPException(
                status_code=422,
                detail=f"Delivery blocked: Automated review gate check(s) failed: {'; '.join(failed_gates)}"
            )

    pptx_path = config.EXPORTS_DIR / f"presentation_{deck_id}.pptx"
    # Prefer existing validated styled PPTX if present; otherwise compile fresh
    if deck_spec and deck_spec.get("metadata", {}).get("styled_pptx_path") and Path(deck_spec["metadata"]["styled_pptx_path"]).exists():
        pptx_path = Path(deck_spec["metadata"]["styled_pptx_path"])
    elif deck_spec:
        try:
            pptx_path = export_spec_to_pptx(deck_spec)
        except Exception as exc:
            if not pptx_path.exists():
                raise HTTPException(status_code=422, detail=str(exc)) from exc
    elif not pptx_path.exists():
        raise HTTPException(status_code=404, detail="Presentation deck not found")

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    title_raw = (deck_spec.get("metadata", {}).get("title") if deck_spec else None) or f"presentation_{deck_id}"
    clean_title = re.sub(r'[^a-zA-Z0-9_-]', '_', title_raw)[:40].strip('_') or "Presentation"
    filename = f"{clean_title}_{timestamp}.pptx"
    return FileResponse(
        path=str(pptx_path),
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.get("/download/{deck_id}/pdf")
@_serialize_deck_write
def download_deck_pdf(deck_id: str):
    """Exports or serves a PDF document for a stored deck."""
    from ..services.report_generator import export_spec_to_pdf
    deck_spec = None
    with session_scope() as conn:
        row = conn.execute("SELECT spec_json FROM presentation_decks WHERE id = ?", (deck_id,)).fetchone()
    if row:
        deck_spec = json.loads(row["spec_json"])
    elif not (config.EXPORTS_DIR / f"presentation_{deck_id}.pdf").exists():
        raise HTTPException(status_code=404, detail="Presentation deck not found")

    pdf_path = config.EXPORTS_DIR / f"presentation_{deck_id}.pdf"
    if deck_spec and deck_spec.get("metadata", {}).get("styled_pptx_path"):
        styled_path = Path(deck_spec["metadata"]["styled_pptx_path"])
        import shutil
        import subprocess
        soffice = shutil.which("soffice") or shutil.which("libreoffice")
        if soffice and styled_path.exists():
            try:
                subprocess.run(
                    [soffice, "--headless", "--convert-to", "pdf", str(styled_path), "--outdir", str(config.EXPORTS_DIR)],
                    check=True,
                    timeout=30,
                    capture_output=True,
                )
                converted_pdf = config.EXPORTS_DIR / f"{styled_path.stem}.pdf"
                if converted_pdf.exists():
                    clean_title = re.sub(r'[^a-zA-Z0-9_-]', '_', deck_spec.get("title") or f"presentation_{deck_id}")[:40].strip('_') or "Presentation"
                    filename = f"{clean_title}.pdf"
                    return FileResponse(
                        path=str(converted_pdf),
                        filename=filename,
                        media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
                    )
            except Exception as conv_err:
                logger.warning(f"LibreOffice PDF conversion failed for deck {deck_id}: {conv_err}")
        elif not pdf_path.exists():
            # Gracefully handle bounded PDF export limitation without crashing
            raise HTTPException(
                status_code=501,
                detail="PDF export requires headless LibreOffice or browser print. Please download the native PowerPoint PPTX or use browser print.",
            )

    if deck_spec:
        require_live_sources(deck_spec)
        from ..services.presentation.review_gates import evaluate_automated_gates
        rg = evaluate_automated_gates(deck_spec)
        failed_gates = [
            f"{gid}: {g.get('automated', {}).get('details', 'Failed check')}"
            for gid, g in rg.get("gates", {}).items()
            if g.get("automated", {}).get("status") == "FAILED"
        ]
        if failed_gates:
            raise HTTPException(
                status_code=422,
                detail=f"Delivery blocked: Automated review gate check(s) failed: {'; '.join(failed_gates)}"
            )

    if deck_spec and not (deck_spec.get("metadata", {}).get("styled_pptx_path") and pdf_path.exists()):
        try:
            pdf_path = export_spec_to_pdf(deck_spec)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    elif not pdf_path.exists():
        raise HTTPException(status_code=404, detail="Presentation PDF not found")

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    title_raw = (deck_spec.get("metadata", {}).get("title") if deck_spec else None) or f"presentation_{deck_id}"
    clean_title = re.sub(r'[^a-zA-Z0-9_-]', '_', title_raw)[:40].strip('_') or "Presentation"
    filename = f"{clean_title}_{timestamp}.pdf"
    return FileResponse(
        path=str(pdf_path),
        filename=filename,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


def _deck_spec_to_visual_specs(deck_spec: dict[str, Any], requested_theme_id: str | None = None, target_idx: int | None = None):
    """Synthesizes canonical VisualSpecifications and tokens from a deck spec."""
    from ..services.presentation.visual import VisualIntelligenceEngine, normalize_slide_theme
    slides_data = deck_spec.get("slides", [])
    theme_id = requested_theme_id or deck_spec.get("metadata", {}).get("theme_id") or deck_spec.get("theme_id") or "executive_dark"
    tokens = normalize_slide_theme(theme_id)
    engine = VisualIntelligenceEngine()
    total_slides = len(slides_data)
    visual_specs = []

    content_pkg = deck_spec.get("metadata", {}).get("content_package", {})
    all_items = {it.get("content_id"): it for it in content_pkg.get("items", []) if isinstance(it, dict)}
    for kpi in content_pkg.get("global_kpis", []):
        if isinstance(kpi, dict) and kpi.get("content_id"):
            all_items[kpi["content_id"]] = kpi
    for exp in content_pkg.get("exploratory_items", []):
        if isinstance(exp, dict) and exp.get("content_id"):
            all_items[exp["content_id"]] = exp

    items_to_process = [(target_idx, slides_data[target_idx])] if (target_idx is not None and 0 <= target_idx < len(slides_data)) else list(enumerate(slides_data))

    for idx, s in items_to_process:
        if s.get("visual_spec") and isinstance(s["visual_spec"], dict):
            try:
                from ..services.presentation.visual.visual_models import VisualSpecification
                v_spec = VisualSpecification.model_validate(s["visual_spec"])
                visual_specs.append(v_spec)
                continue
            except Exception:
                pass

        s_clean = dict(s)
        if not s_clean.get("bullets"):
            raw_meta_bullets = (s.get("metadata") or {}).get("bullets")
            if raw_meta_bullets and isinstance(raw_meta_bullets, list):
                s_clean["bullets"] = raw_meta_bullets
            else:
                for z in s_clean.get("zones", []):
                    for obj in z.get("objects", []):
                        cid = obj.get("content_id")
                        if cid and cid in all_items:
                            b_list = all_items[cid].get("supporting_bullets")
                            if b_list and isinstance(b_list, list) and b_list:
                                s_clean["bullets"] = b_list
                                break

        if "metrics" not in s_clean or not s_clean["metrics"]:
            extracted_kpis = []
            for z in s_clean.get("zones", []):
                for obj in z.get("objects", []):
                    cid = obj.get("content_id")
                    if cid and cid in all_items and all_items[cid].get("kind") in ("kpi_metric", "KPI_METRIC"):
                        it = all_items[cid]
                        raw_lbl = it.get("metric_label") or it.get("title") or it.get("metric_name", "Metric")
                        from ..services.presentation.content_hub import compress_kpi_label
                        clean_lbl = compress_kpi_label(raw_lbl)
                        extracted_kpis.append({
                            "label": clean_lbl,
                            "value": str(it.get("metric_value", "0")),
                            "subtext": it.get("topic_category", "")
                        })
            if extracted_kpis:
                s_clean["metrics"] = extracted_kpis

        if "chart" not in s_clean or not s_clean["chart"]:
            for z in s_clean.get("zones", []):
                for obj in z.get("objects", []):
                    cid = obj.get("content_id")
                    if cid and cid in all_items:
                        it = all_items[cid]
                        if it.get("kind") in ("chart", "CHART", "map", "MAP"):
                            s_clean["chart"] = {
                                "chart_type": it.get("visual_type") or "bar",
                                "title": it.get("title", s_clean.get("title", "Chart")),
                                "categories": ["Category A", "Category B", "Category C", "Category D"],
                                "series": [{"name": "Value", "values": [120, 150, 180, 140]}]
                            }
                        elif it.get("kind") in ("table", "TABLE"):
                            raw_t = it.get("table_data")
                            if isinstance(raw_t, list) and raw_t:
                                s_clean["table"] = {
                                    "headers": list(raw_t[0].keys()),
                                    "rows": [[str(r.get(k, "")) for k in raw_t[0].keys()] for r in raw_t]
                                }
                            elif isinstance(raw_t, dict):
                                s_clean["table"] = raw_t

        v_spec = engine.process_slide(
            s_clean,
            theme_id=theme_id,
            sequence_number=s_clean.get("order") or s_clean.get("sequence_number") or idx + 1,
            total_slides=total_slides
        )
        try:
            s["visual_spec"] = v_spec.model_dump(mode="json")
        except Exception:
            pass
        visual_specs.append(v_spec)

    return visual_specs, tokens, theme_id


@router.get("/decks/{deck_id}/html")
@router.get("/download/{deck_id}/html")
@_serialize_deck_write
def download_deck_html(deck_id: str, download: bool = False, theme_id: str | None = None):
    """Exports or serves a standalone HTML presentation for a stored deck."""
    from ..services.presentation.visual.adapters.html_adapter import HTMLAdapter

    deck_spec = None
    with session_scope() as conn:
        row = conn.execute("SELECT spec_json FROM presentation_decks WHERE id = ?", (deck_id,)).fetchone()
    if row:
        deck_spec = json.loads(row["spec_json"])
    else:
        raise HTTPException(status_code=404, detail="Presentation deck not found")

    visual_specs, tokens, resolved_theme_id = _deck_spec_to_visual_specs(deck_spec, theme_id)
    title = deck_spec.get("title") or f"presentation_{deck_id}"
    html_content = HTMLAdapter.to_standalone_presentation_html(
        specs=visual_specs,
        tokens=tokens,
        title=title,
        deck_id=deck_id
    )

    clean_title = re.sub(r'[^a-zA-Z0-9_-]', '_', title)[:40].strip('_') or "presentation"
    headers = {"Cache-Control": "no-cache"}
    if download:
        headers["Content-Disposition"] = f'attachment; filename="{clean_title}.html"'

    return Response(content=html_content, media_type="text/html; charset=utf-8", headers=headers)


@router.get("/decks/{deck_id}/slides/{slide_id}/html")
def get_slide_html(deck_id: str, slide_id: str, theme_id: str | None = None):
    """Streams the rendered HTML for a specific physical slide in an isolated container."""
    from ..services.presentation.visual.adapters.html_adapter import HTMLAdapter

    deck_spec = None
    with session_scope() as conn:
        row = conn.execute("SELECT spec_json FROM presentation_decks WHERE id = ?", (deck_id,)).fetchone()
    if row:
        deck_spec = json.loads(row["spec_json"])
    else:
        raise HTTPException(status_code=404, detail="Presentation deck not found")

    slides_data = deck_spec.get("slides", [])
    target_idx = None
    target_slide = None

    # Check match by physical_slide_id or id (non-empty string)
    for i, s in enumerate(slides_data):
        if s.get("physical_slide_id") and str(s.get("physical_slide_id")) == str(slide_id):
            target_idx = i
            target_slide = s
            break
        if s.get("id") and str(s.get("id")) == str(slide_id):
            target_idx = i
            target_slide = s
            break

    # Match by slide-{N} or numeric index
    if target_idx is None:
        if str(slide_id).startswith("slide-"):
            try:
                n = int(str(slide_id).split("-")[1])
                if 1 <= n <= len(slides_data):
                    target_idx = n - 1
                    target_slide = slides_data[target_idx]
            except (ValueError, IndexError):
                pass
        elif str(slide_id).isdigit():
            n = int(str(slide_id))
            if 1 <= n <= len(slides_data):
                target_idx = n - 1
                target_slide = slides_data[target_idx]
            elif n == 0 and len(slides_data) > 0:
                target_idx = 0
                target_slide = slides_data[0]
        else:
            for i, s in enumerate(slides_data):
                if s.get("order") is not None and str(s.get("order")) == str(slide_id):
                    target_idx = i
                    target_slide = s
                    break

    if target_slide is None:
        raise HTTPException(status_code=404, detail=f"Slide {slide_id} not found in deck {deck_id}")

    visual_specs, tokens, resolved_theme_id = _deck_spec_to_visual_specs(deck_spec, theme_id, target_idx=target_idx)
    v_spec = visual_specs[0] if visual_specs else None
    if v_spec is None:
        raise HTTPException(status_code=404, detail=f"Visual specification could not be generated for slide {slide_id}")

    try:
        with session_scope() as conn:
            conn.execute("UPDATE presentation_decks SET spec_json = ? WHERE id = ?", (json.dumps(deck_spec), deck_id))
    except Exception:
        pass

    slide_html = HTMLAdapter.to_html_slide(
        spec=v_spec,
        tokens=tokens,
        slide_width=1920,
        slide_height=1080,
        use_ai=False
    )

    theme_vars = tokens.to_scoped_css_variables()
    var_styles = "; ".join(f"{k}: {v}" for k, v in theme_vars.items())

    isolated_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Plus+Jakarta+Sans:wght@500;600;700;800&display=swap" rel="stylesheet">
  <style>
    :root {{ {var_styles}; }}
    * {{ box-sizing: border-box; }}
    html, body {{
      margin: 0;
      padding: 0;
      width: 100%;
      height: 100%;
      overflow: hidden;
      background: {tokens.background};
      font-family: {tokens.font_body};
      -webkit-font-smoothing: antialiased;
      user-select: text;
    }}
    .presentation-runtime {{
      width: 100% !important;
      height: 100% !important;
      border: none !important;
    }}
  </style>
</head>
<body>
  {slide_html}
</body>
</html>"""

    return Response(
        content=isolated_html,
        media_type="text/html; charset=utf-8",
        headers={"Cache-Control": "public, max-age=60"}
    )


class ExportHtmlRequest(BaseModel):
    deck_spec: dict[str, Any] | None = None
    deck_id: str | None = None
    theme_id: str | None = "executive_dark"
    download: bool = False


@router.post("/export-html")
def export_presentation_to_html(req: ExportHtmlRequest):
    """Compiles and returns a standalone HTML presentation from a deck spec or deck ID."""
    from ..services.presentation.visual.adapters.html_adapter import HTMLAdapter

    deck_spec = req.deck_spec
    if not deck_spec and req.deck_id:
        with session_scope() as conn:
            row = conn.execute("SELECT spec_json FROM presentation_decks WHERE id = ?", (req.deck_id,)).fetchone()
        if row:
            deck_spec = json.loads(row["spec_json"])

    if not deck_spec:
        raise HTTPException(status_code=400, detail="Either deck_spec or valid deck_id must be provided.")

    visual_specs, tokens, resolved_theme_id = _deck_spec_to_visual_specs(deck_spec, req.theme_id)
    title = deck_spec.get("title") or "Executive Presentation"
    html_content = HTMLAdapter.to_standalone_presentation_html(
        specs=visual_specs,
        tokens=tokens,
        title=title,
        deck_id=req.deck_id
    )

    clean_title = re.sub(r'[^a-zA-Z0-9_-]', '_', title)[:40].strip('_') or "presentation"
    headers = {"Cache-Control": "no-cache"}
    if req.download:
        headers["Content-Disposition"] = f'attachment; filename="{clean_title}.html"'

    return Response(content=html_content, media_type="text/html; charset=utf-8", headers=headers)


class GenerateNarrationRequest(BaseModel):
    voice: str = "andrew"


@router.post("/{deck_id}/narration")
async def generate_narration(deck_id: str, req: GenerateNarrationRequest = GenerateNarrationRequest()):
    """Generates studio-quality neural voiceover audio for every slide in a presentation deck."""
    from ..services.presentation.narration_service import generate_deck_narration_async, EXECUTIVE_VOICES
    try:
        manifest = await generate_deck_narration_async(deck_id, voice_key=req.voice)
        return manifest
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.error(f"Narration generation failed for deck {deck_id}: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate narration: {str(exc)}")


@router.get("/{deck_id}/narration")
def get_narration(deck_id: str):
    """Returns the narration manifest and audio file links for a presentation deck."""
    from ..services.presentation.narration_service import get_deck_narration_manifest, EXECUTIVE_VOICES
    manifest = get_deck_narration_manifest(deck_id)
    if not manifest:
        return {
            "status": "not_generated",
            "deck_id": deck_id,
            "available_voices": list(EXECUTIVE_VOICES.values()),
            "slides": []
        }
    manifest["available_voices"] = list(EXECUTIVE_VOICES.values())
    return manifest


@router.get("/{deck_id}/narration/slide/{slide_order}")
def stream_slide_narration(deck_id: str, slide_order: int):
    """Streams the MP3 audio narration file for a specific slide."""
    from ..services.presentation.narration_service import get_narration_dir
    mp3_path = get_narration_dir(deck_id) / f"slide_{slide_order}.mp3"
    if not mp3_path.exists():
        raise HTTPException(status_code=404, detail=f"Audio for slide {slide_order} not found.")
    return FileResponse(
        path=str(mp3_path),
        media_type="audio/mpeg",
        filename=f"slide_{slide_order}.mp3"
    )
