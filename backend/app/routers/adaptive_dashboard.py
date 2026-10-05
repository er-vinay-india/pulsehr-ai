"""API endpoints for the Adaptive Decision Dashboard (Revision 2)."""
from fastapi import APIRouter, HTTPException, Query
from ..db.database import get_connection
from ..services.adaptive_dashboard import AdaptiveDashboardResponse, run_adaptive_dashboard
from ..services.adaptive_dashboard.dataset_orchestrator import DatasetIntelligenceResponse, run_dataset_intelligence
from ..services.adaptive_dashboard.findings import UnifiedFinding, get_shared_findings_for_sheet

router = APIRouter(prefix="/api/adaptive-dashboard", tags=["adaptive dashboard"])


@router.get("/primary-element", response_model=AdaptiveDashboardResponse)
def get_primary_element(
    sheet_id: int | None = Query(None, description="Target sheet ID (resolves to parent dataset)"),
    dataset_id: int | None = Query(None, description="Target dataset ID"),
):
    """Returns verified dataset-level adaptive dashboard intelligence (WP-9.6)."""
    try:
        target_dataset_id = dataset_id
        if target_dataset_id is None and sheet_id is not None:
            conn = get_connection()
            try:
                row = conn.execute("SELECT dataset_id FROM sheets WHERE id = ?", (sheet_id,)).fetchone()
                if row and row[0]:
                    target_dataset_id = row[0]
            finally:
                conn.close()

        return run_adaptive_dashboard(
            sheet_id=sheet_id,
            dataset_id=target_dataset_id,
            include_dataset_intelligence=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Adaptive analysis error: {exc}") from exc


@router.get("/dataset/{dataset_id}", response_model=DatasetIntelligenceResponse)
def get_dataset_dashboard(dataset_id: int):
    """Returns authoritative dataset-wide intelligence, relationships, and globally ranked insights (WP-9.6)."""
    try:
        return run_dataset_intelligence(dataset_id=dataset_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Dataset intelligence error: {exc}") from exc


@router.get("/findings", response_model=list[UnifiedFinding])
def get_dashboard_findings(sheet_id: int = Query(..., description="Target sheet ID")):
    """Returns authoritative, immutable, deduplicated findings from the Shared Findings Store (T31, T33)."""
    try:
        return get_shared_findings_for_sheet(sheet_id=sheet_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Findings store error: {exc}") from exc

