"""API endpoints for the Adaptive Decision Dashboard (Revision 2)."""
from fastapi import APIRouter, HTTPException, Query
from ..services.adaptive_dashboard import AdaptiveDashboardResponse, run_adaptive_dashboard

router = APIRouter(prefix="/api/adaptive-dashboard", tags=["adaptive dashboard"])


@router.get("/primary-element", response_model=AdaptiveDashboardResponse)
def get_primary_element(sheet_id: int | None = Query(None, description="Target sheet ID")):
    """Returns exactly ONE verified primary metric tile or honest coverage card."""
    try:
        return run_adaptive_dashboard(sheet_id=sheet_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Adaptive analysis error: {exc}") from exc
