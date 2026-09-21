from __future__ import annotations

import datetime
import json
import logging
import re
from typing import Any, Literal
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..core import config
from ..db.database import get_connection
from ..services.presentation_service import (
    THEMES,
    job_manager,
    start_presentation_job,
    regenerate_single_slide,
    preview_presentation_scope,
    verify_presentation_claims,
)
from ..services.report_generator import export_spec_to_pptx

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/presentations", tags=["presentations"])


class GeneratePresentationRequest(BaseModel):
    deck_style: Literal["standard", "decision_brief"] = "standard"
    objective: str | None = "Executive Leadership Review"
    audience: str | None = "C-Suite & Operations Leadership"
    target_length: int | None = 6
    theme_id: str | None = "executive_dark"
    scope_type: str | None = "workspace"  # "workspace" | "connected_group" | "custom_sheets" | "single_sheet"
    sheet_id: int | None = None
    sheet_ids: list[int] | None = None
    group_id: str | None = None
    instructions: str | None = ""


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


@router.get("/themes")
def get_themes():
    """Returns available presentation visual themes."""
    return {"themes": list(THEMES.values())}


@router.post("/scope-preview")
def get_scope_preview(req: ScopePreviewRequest):
    """Preflights presentation scope, reporting periods, partial-year status, and relationship coverage."""
    with get_connection() as conn:
        res = preview_presentation_scope(conn, req.model_dump())
    return res


@router.post("/generate")
def start_presentation_generation(req: GeneratePresentationRequest):
    """Spawns an asynchronous 7-stage presentation generation job."""
    scope = {
        "deck_style": req.deck_style,
        "objective": req.objective or "Executive Leadership Review",
        "audience": req.audience or "C-Suite & Operations Leadership",
        "target_length": req.target_length or 6,
        "theme_id": req.theme_id or "executive_dark",
        "scope_type": req.scope_type or "workspace",
        "sheet_id": req.sheet_id,
        "sheet_ids": req.sheet_ids or [],
        "group_id": req.group_id,
        "instructions": req.instructions or "",
    }
    job_id = start_presentation_job(scope)

    return {
        "job_id": job_id,
        "status": "in_progress",
        "stage": "reviewing_coverage",
        "progress": 15,
        "message": "Initiating 7-stage analytical presentation pipeline...",
    }


@router.get("/decks/{deck_id}/evidence")
def get_deck_evidence(deck_id: str):
    """Returns the frozen evidence ledger, snapshot hash, and claim verification summary."""
    with get_connection() as conn:
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
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Presentation job not found")
    if job.get("status") == "ready" and job.get("deck_id"):
        try:
            with get_connection() as conn:
                row = conn.execute("SELECT spec_json FROM presentation_decks WHERE id = ?", (job["deck_id"],)).fetchone()
                if row and row["spec_json"]:
                    job["deck"] = json.loads(row["spec_json"])
        except Exception as exc:
            logger.warning(f"Could not attach deck spec to ready presentation job: {exc}")
    return job


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
    with get_connection() as conn:
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


@router.get("/decks/{deck_id}")
def get_presentation_deck(deck_id: str):
    """Retrieves full PresentationDeckSpec by deck_id."""
    with get_connection() as conn:
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


@router.put("/decks/{deck_id}")
def update_presentation_deck(deck_id: str, deck_spec: dict[str, Any]):
    """Saves updated PresentationDeckSpec after user inline edits or theme changes."""
    title = deck_spec.get("metadata", {}).get("title") or deck_spec.get("slides", [{}])[0].get("title", "Presentation")
    dataset_id = deck_spec.get("metadata", {}).get("dataset_id")
    sheet_id = deck_spec.get("metadata", {}).get("sheet_id")
    theme_id = deck_spec.get("metadata", {}).get("theme_id") or deck_spec.get("theme", {}).get("id", "executive_dark")
    pptx_filename = deck_spec.get("pptx_filename")
    spec_json = json.dumps(deck_spec)

    with get_connection() as conn:
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


@router.post("/export-pptx")
def export_presentation_to_pptx(req: ExportPptxRequest):
    """Builds and returns an editable PowerPoint file with native charts from deck spec."""
    try:
        deck_spec = req.deck_spec
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
    except Exception as exc:
        logger.error(f"Export PPTX error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate PowerPoint: {str(exc)}")


@router.get("/download/{deck_id}")
def download_deck_pptx(deck_id: str):
    """Exports or serves a PowerPoint presentation for a stored deck."""
    deck_spec = None
    with get_connection() as conn:
        row = conn.execute("SELECT spec_json FROM presentation_decks WHERE id = ?", (deck_id,)).fetchone()
    if row:
        deck_spec = json.loads(row["spec_json"])

    pptx_path = config.EXPORTS_DIR / f"presentation_{deck_id}.pptx"
    if not pptx_path.exists():
        if not deck_spec:
            raise HTTPException(status_code=404, detail="Presentation deck not found")
        pptx_path = export_spec_to_pptx(deck_spec)

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

