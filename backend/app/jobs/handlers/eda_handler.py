"""
EDA Job Handler for Phase G4 Slow-Path Worker Plane.
Executes statistical profiling and anomaly analysis outside the HTTP request path.
"""
from __future__ import annotations

import logging
from typing import Any

from app.services.eda import run_eda_pipeline
from ..worker_plane import ProgressReporter

logger = logging.getLogger(__name__)


def handle_eda_job(
    job_id: str,
    payload: dict[str, Any],
    reporter: ProgressReporter,
) -> tuple[dict[str, Any], str | None]:
    """Executes heavy Exploratory Data Analysis in background."""
    reporter.update(10, "INITIALIZING", "Initializing statistical distributions and IQR fences")
    sheet_ids = payload.get("sheet_ids")

    reporter.update(40, "PROFILING_COLUMNS", "Calculating quantiles, skewness, and cardinality")
    if reporter.is_cancelled():
        raise InterruptedError()

    result = run_eda_pipeline(sheet_ids=sheet_ids)
    reporter.update(90, "COMPILING_REPORTS", "Synthesizing Data Health Score and anomaly flags")

    return {
        "status": "COMPLETED",
        "sheets_analyzed": len(sheet_ids) if sheet_ids else "all",
        "eda_summary": result.get("summary", {}) if isinstance(result, dict) else {},
    }, None
