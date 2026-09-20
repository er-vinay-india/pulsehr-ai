from __future__ import annotations

import json
import logging
from typing import Any
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
)
from ..services.report_generator import export_spec_to_pptx

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/presentations", tags=["presentations"])


class GeneratePresentationRequest(BaseModel):
    objective: str | None = "Executive Leadership Review"
    audience: str | None = "C-Suite & Operations Leadership"
    target_length: int | None = 6
    theme_id: str | None = "executive_dark"
    sheet_id: int | None = None
    instructions: str | None = ""


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


@router.post("/generate")
def start_presentation_generation(req: GeneratePresentationRequest):
    """Spawns an asynchronous 6-stage presentation generation job."""
    scope = {
        "objective": req.objective or "Executive Leadership Review",
        "audience": req.audience or "C-Suite & Operations Leadership",
        "target_length": req.target_length or 6,
        "theme_id": req.theme_id or "executive_dark",
        "sheet_id": req.sheet_id,
        "instructions": req.instructions or "",
    }
    job_id = start_presentation_job(scope)

    return {
        "job_id": job_id,
        "status": "in_progress",
        "stage": "collecting_findings",
        "progress": 5,
        "message": "Initiating analytical presentation pipeline...",
    }


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
        filename = f"{deck_spec.get('id', 'presentation')}.pptx"
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
    pptx_path = config.EXPORTS_DIR / f"presentation_{deck_id}.pptx"
    if not pptx_path.exists():
        # Load from DB and export
        with get_connection() as conn:
            row = conn.execute("SELECT spec_json FROM presentation_decks WHERE id = ?", (deck_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Presentation deck not found")
        deck_spec = json.loads(row["spec_json"])
        pptx_path = export_spec_to_pptx(deck_spec)

    filename = f"presentation_{deck_id}.pptx"
    return FileResponse(
        path=str(pptx_path),
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
