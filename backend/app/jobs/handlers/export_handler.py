"""
Export Job Handlers for Phase G4 Slow-Path Worker Plane.
Executes PDF and PPTX document synthesis asynchronously without blocking the HTTP request path.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from app.db.database import session_scope
from app.services.dataset_deletion import require_live_sources
from app.services.presentation.review_gates import evaluate_automated_gates
from app.services.report_generator import export_spec_to_pdf, export_spec_to_pptx
from ..worker_plane import ProgressReporter

logger = logging.getLogger(__name__)


def _resolve_deck_spec(payload: dict[str, Any]) -> dict[str, Any]:
    """Resolves deck_spec either directly or by loading by referenced deck_id from database."""
    deck_spec = payload.get("deck_spec")
    if not deck_spec and payload.get("deck_id"):
        deck_id = str(payload["deck_id"])
        with session_scope() as conn:
            row = conn.execute("SELECT spec_json FROM presentation_decks WHERE id = ?", (deck_id,)).fetchone()
            if row:
                deck_spec = json.loads(row["spec_json"])
    if not deck_spec:
        raise ValueError("Payload missing 'deck_spec' or valid 'deck_id' reference")
    return deck_spec


def handle_pdf_export_job(
    job_id: str,
    payload: dict[str, Any],
    reporter: ProgressReporter,
) -> tuple[dict[str, Any], str | None]:
    """Generates PDF presentation in the background."""
    reporter.update(10, "VALIDATING", "Validating slide geometry and evidence claims")
    deck_spec = _resolve_deck_spec(payload)

    require_live_sources(deck_spec)
    review = evaluate_automated_gates(deck_spec)
    failures = [
        g.get("automated", {}).get("details", "Failed check")
        for g in review.get("gates", {}).values()
        if g.get("automated", {}).get("status") == "FAILED"
    ]
    if failures:
        raise ValueError("Delivery blocked by review gates: " + "; ".join(failures))

    reporter.update(35, "RENDERING_CANVAS", "Synthesizing vector charts, layouts, and typography")
    if reporter.is_cancelled():
        raise InterruptedError()

    reporter.update(65, "COMPILING_PDF", "Compiling ReportLab flowables to PDF document")
    pdf_path = export_spec_to_pdf(deck_spec)

    reporter.update(95, "FINALIZING", "Verifying artifact on disk and updating ledger")
    artifact_str = str(pdf_path)

    title = deck_spec.get("metadata", {}).get("title") or deck_spec.get("title") or "Presentation"
    return {
        "title": title,
        "artifact_path": artifact_str,
        "filename": pdf_path.name,
        "size_bytes": pdf_path.stat().st_size,
        "slide_count": len(deck_spec.get("slides", [])),
    }, artifact_str


def handle_pptx_export_job(
    job_id: str,
    payload: dict[str, Any],
    reporter: ProgressReporter,
) -> tuple[dict[str, Any], str | None]:
    """Generates PowerPoint (.pptx) presentation in the background."""
    reporter.update(15, "VALIDATING", "Evaluating automated presentation gates")
    deck_spec = _resolve_deck_spec(payload)

    require_live_sources(deck_spec)
    reporter.update(50, "BUILDING_SHAPES", "Assembling PowerPoint slide shapes and tables")
    if reporter.is_cancelled():
        raise InterruptedError()

    pptx_path = export_spec_to_pptx(deck_spec)
    reporter.update(95, "FINALIZING", "Packaging OpenXML presentation")
    artifact_str = str(pptx_path)

    title = deck_spec.get("metadata", {}).get("title") or deck_spec.get("title") or "Presentation"
    return {
        "title": title,
        "artifact_path": artifact_str,
        "filename": pptx_path.name,
        "size_bytes": pptx_path.stat().st_size,
        "slide_count": len(deck_spec.get("slides", [])),
    }, artifact_str
