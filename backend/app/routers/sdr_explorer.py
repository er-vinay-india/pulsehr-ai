"""
HighView Semantic Data Refinery — Phase SDR-7
Data Explorer Semantic Experience API Router

Endpoints for inspecting SDR refinery artifacts across:
- /summary
- /semantics
- /relationships
- /analytical-views
- /analytical-facts
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.services.sdr.explorer_service import SDRExplorerService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/datasets", tags=["sdr-explorer"])
_explorer_service = SDRExplorerService()


@router.get("/{dataset_id}/explorer/summary")
def get_explorer_summary(dataset_id: str) -> dict[str, Any]:
    """Returns high-level dataset summary and refinery stage status."""
    try:
        return _explorer_service.get_explorer_summary(dataset_id)
    except Exception as e:
        logger.error(f"Error fetching explorer summary for dataset {dataset_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to load semantic summary: {str(e)}")


@router.get("/{dataset_id}/explorer/source-rows")
def get_explorer_source_rows(
    dataset_id: str,
    sheet_id: str = Query(..., description="Sheet identifier or name"),
    page: int = Query(default=1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(default=50, ge=1, le=500, description="Rows per page"),
    search: str | None = Query(default=None, description="Optional search term"),
    sort_by: str | None = Query(default=None, description="Optional column to sort by"),
    sort_direction: str | None = Query(default=None, description="Sort direction: 'asc' or 'desc'"),
) -> dict[str, Any]:
    """Returns exact raw source rows without derived column additions or type distortions."""
    try:
        return _explorer_service.get_source_rows(
            dataset_id=dataset_id,
            sheet_id=sheet_id,
            page=page,
            page_size=page_size,
            search=search,
            sort_by=sort_by,
            sort_direction=sort_direction,
        )
    except Exception as e:
        logger.error(f"Error fetching source rows for dataset {dataset_id} sheet {sheet_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to load source rows: {str(e)}")


@router.get("/{dataset_id}/explorer/semantics")
def get_explorer_semantics(
    dataset_id: str,
    sheet_id: str | None = Query(default=None, description="Optional sheet filter"),
) -> dict[str, Any]:
    """Returns semantic column profiles, entity hypotheses, row grain, candidate keys, and enrichments."""
    try:
        return _explorer_service.get_semantics_data(dataset_id, sheet_id=sheet_id)
    except Exception as e:
        logger.error(f"Error fetching explorer semantics for dataset {dataset_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to load semantics: {str(e)}")


@router.get("/{dataset_id}/explorer/relationships")
def get_explorer_relationships(dataset_id: str) -> dict[str, Any]:
    """Returns validated relationships, join plans, safety status, and topology graph."""
    try:
        return _explorer_service.get_relationships_data(dataset_id)
    except Exception as e:
        logger.error(f"Error fetching explorer relationships for dataset {dataset_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to load relationships: {str(e)}")


@router.get("/{dataset_id}/explorer/analytical-views")
def get_explorer_analytical_views(dataset_id: str) -> dict[str, Any]:
    """Returns SDR-6 analytical views, freshness status, and execution metadata."""
    try:
        return _explorer_service.get_analytical_views_data(dataset_id)
    except Exception as e:
        logger.error(f"Error fetching explorer analytical views for dataset {dataset_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to load analytical views: {str(e)}")


@router.get("/{dataset_id}/explorer/analytical-facts")
def get_explorer_analytical_facts(
    dataset_id: str,
    view_id: str | None = Query(default=None, description="Optional view filter"),
) -> dict[str, Any]:
    """Returns analytical facts with exact values, units, denominators, and lineage paths."""
    try:
        data = _explorer_service.get_analytical_views_data(dataset_id)
        facts = data.get("facts", [])
        if view_id:
            facts = [f for f in facts if f.get("analytical_view_id") == view_id]
        return {
            "dataset_id": dataset_id,
            "facts": facts,
            "total_count": len(facts),
        }
    except Exception as e:
        logger.error(f"Error fetching explorer analytical facts for dataset {dataset_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to load analytical facts: {str(e)}")
