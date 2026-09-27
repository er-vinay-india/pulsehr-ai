"""Workspace Context & User Control API Router.

Exposes REST endpoints for:
- Fetching canonical WorkspaceContext (<200ms)
- Incremental partial PATCH overrides for domain, column roles, primary dataset, intent (<100ms)
- Question alignment audit
- EDAContextAdapter & DashboardContextAdapter delivery
- Join override evaluation with safety guarantees
"""

from __future__ import annotations

import json
import logging
from typing import Any
from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel, Field

from ..db.database import get_connection
from ..services.input_intelligence import (
    DashboardContextAdapter,
    DashboardPlanningContext,
    EDAAnalysisContext,
    EDAContextAdapter,
    InputIntelligenceService,
    SnapshotManager,
    WorkspaceContext,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/workspace", tags=["workspace-context"])


class PatchContextRequest(BaseModel):
    """Partial override payload for user corrections."""
    domain: str | None = None
    primary_dataset_id: str | None = None
    column_roles: dict[str, str] | None = None
    user_objective: str | None = None
    explicit_questions: list[str] | None = None
    audience: str | None = None
    expected_output: str | None = None
    reporting_period: str | None = None
    join_decisions: dict[str, bool] | None = None


class JoinDecisionRequest(BaseModel):
    """Specific override for candidate relationship join."""
    relationship_id: str
    accept: bool


def _resolve_workspace_context(workspace_id: str) -> WorkspaceContext:
    """Helper to retrieve cached context or reconstruct from sqlite dataset_uploads."""
    cached = SnapshotManager.get_cached_context(workspace_id)
    if cached:
        return cached

    # Try numeric dataset_id resolution
    ds_num = None
    if workspace_id.isdigit():
        ds_num = int(workspace_id)
    elif workspace_id.startswith("ws_") and workspace_id[3:].isdigit():
        ds_num = int(workspace_id[3:])

    if ds_num is not None:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT id, filename, original_name, columns_json, sample_preview_json, analysis_context_json FROM dataset_uploads WHERE id=?",
                (ds_num,)
            ).fetchone()
            if row:
                if row["analysis_context_json"]:
                    try:
                        ctx_dict = json.loads(row["analysis_context_json"])
                        ctx = WorkspaceContext.model_validate(ctx_dict)
                        SnapshotManager.cache_context(ctx)
                        return ctx
                    except Exception as exc:
                        logger.warning(f"Failed to parse stored context JSON: {exc}")

                # Synthesize fresh if records exist
                sheet_rows = conn.execute(
                    "SELECT id, name, display_name, columns_json, row_count FROM sheets WHERE dataset_id=?",
                    (ds_num,)
                ).fetchall()
                if sheet_rows:
                    files_or_data = []
                    for s in sheet_rows:
                        raw_rows = conn.execute(
                            "SELECT data_json FROM sheet_rows WHERE sheet_id=? LIMIT 100",
                            (s["id"],)
                        ).fetchall()
                        records = [json.loads(r["data_json"]) for r in raw_rows]
                        files_or_data.append({
                            "id": str(s["id"]),
                            "filename": s["display_name"] or s["name"],
                            "original_name": s["display_name"] or s["name"],
                            "records": records,
                            "columns": json.loads(s["columns_json"])
                        })
                    ctx = InputIntelligenceService.process_workspace_input(
                        workspace_id=workspace_id,
                        files_or_data=files_or_data
                    )
                    return ctx

    raise HTTPException(status_code=404, detail=f"WorkspaceContext for '{workspace_id}' not found.")


def _persist_context_if_applicable(workspace_id: str, context: WorkspaceContext) -> None:
    """Optionally stores updated context JSON in database."""
    ds_num = None
    if workspace_id.isdigit():
        ds_num = int(workspace_id)
    elif workspace_id.startswith("ws_") and workspace_id[3:].isdigit():
        ds_num = int(workspace_id[3:])

    if ds_num is not None:
        try:
            with get_connection() as conn:
                ctx_json = context.model_dump_json()
                conn.execute(
                    "UPDATE dataset_uploads SET analysis_context_json=? WHERE id=?",
                    (ctx_json, ds_num)
                )
                conn.commit()
        except Exception as exc:
            logger.debug(f"Optional DB context sync skipped: {exc}")


@router.get("/{workspace_id}/context")
def get_workspace_context(workspace_id: str) -> dict[str, Any]:
    """Retrieves authoritative canonical WorkspaceContext in <200ms."""
    ctx = _resolve_workspace_context(workspace_id)
    return ctx.model_dump()


@router.patch("/{workspace_id}/context")
def patch_workspace_context(workspace_id: str, patch: PatchContextRequest) -> dict[str, Any]:
    """Applies partial overrides incrementally in <100ms without physical data re-ingestion."""
    current = _resolve_workspace_context(workspace_id)
    overrides_dict = {k: v for k, v in patch.model_dump().items() if v is not None}

    updated = SnapshotManager.apply_user_overrides(current, overrides_dict)
    _persist_context_if_applicable(workspace_id, updated)
    return updated.model_dump()


@router.post("/{workspace_id}/context/revalidate")
def revalidate_workspace_context(workspace_id: str) -> dict[str, Any]:
    """Forces re-evaluation of question-to-data mapping and analysis readiness."""
    current = _resolve_workspace_context(workspace_id)
    updated = SnapshotManager.apply_user_overrides(current, {})
    _persist_context_if_applicable(workspace_id, updated)
    return updated.model_dump()


@router.get("/{workspace_id}/context/questions")
def get_workspace_questions(workspace_id: str) -> dict[str, Any]:
    """Returns explicit user questions and their data alignment status."""
    ctx = _resolve_workspace_context(workspace_id)
    return {
        "workspace_id": workspace_id,
        "questions": [qm.model_dump() for qm in ctx.question_mappings],
        "readiness": ctx.readiness.model_dump(),
        "objective": ctx.user_request.normalized_objective
    }


@router.get("/{workspace_id}/context/eda", response_model=EDAAnalysisContext)
def get_workspace_eda_context(workspace_id: str) -> EDAAnalysisContext:
    """Returns canonical EDAAnalysisContext via EDAContextAdapter."""
    ctx = _resolve_workspace_context(workspace_id)
    return EDAContextAdapter.adapt(ctx)


@router.get("/{workspace_id}/context/dashboard", response_model=DashboardPlanningContext)
def get_workspace_dashboard_context(workspace_id: str) -> DashboardPlanningContext:
    """Returns question-driven DashboardPlanningContext via DashboardContextAdapter."""
    ctx = _resolve_workspace_context(workspace_id)
    return DashboardContextAdapter.adapt(ctx)


@router.post("/{workspace_id}/context/join-override")
def override_candidate_join(workspace_id: str, req: JoinDecisionRequest) -> dict[str, Any]:
    """Explicitly accepts or blocks a join candidate, enforcing safety against many-to-many joins."""
    current = _resolve_workspace_context(workspace_id)
    patch_dict = {"join_decisions": {req.relationship_id: req.accept}}
    updated = SnapshotManager.apply_user_overrides(current, patch_dict)
    _persist_context_if_applicable(workspace_id, updated)
    return updated.model_dump()
