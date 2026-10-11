"""API endpoints for AI Observability & Runtime Intelligence (Phase D).

Exposes:
- GET /api/observability/runtime-intelligence: Technical Explorer KPIs & health summary.
- GET /api/observability/traces/{trace_id}: Complete execution drilldown.
- POST /api/observability/benchmark/run: Run benchmark evaluations.
"""
from __future__ import annotations

import logging
from typing import Any
from fastapi import APIRouter, HTTPException, Query
from ..observability import ai_observability_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/observability", tags=["AI Observability"])


@router.get("/runtime-intelligence")
def get_runtime_intelligence(
    dataset_id: int | str | None = Query(default=None),
) -> dict[str, Any]:
    """Surfaces telemetry KPIs, recent trace summaries, and anomalies for Technical Explorer."""
    return ai_observability_service.get_technical_explorer_summary(dataset_id=dataset_id)


@router.get("/traces/{trace_id}")
def get_trace_details(trace_id: str) -> dict[str, Any]:
    """Retrieves sentence-level attribution, node execution metrics, and provenance for a trace."""
    details = ai_observability_service.get_trace_details(trace_id)
    if not details:
        raise HTTPException(status_code=404, detail=f"Trace '{trace_id}' not found.")
    return details


@router.post("/benchmark/run")
def run_benchmark_evaluations(
    limit: int | None = Query(default=None, description="Optional limit of test cases to run"),
) -> dict[str, Any]:
    """Executes benchmark test cases and aggregates evaluation metrics."""
    report = ai_observability_service.run_benchmark_evaluations(limit=limit)
    return report.model_dump()
