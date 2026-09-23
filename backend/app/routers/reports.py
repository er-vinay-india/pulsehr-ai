from pathlib import Path
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from ..core import config
from ..services.report_generator import generate_pptx_presentation, generate_html_executive_report

router = APIRouter(prefix="/api/reports", tags=["reports"])

@router.post("/presentation")
def create_presentation():
    try:
        pptx_path = generate_pptx_presentation()
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return FileResponse(
        path=str(pptx_path),
        filename=pptx_path.name,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation"
    )

@router.get("/presentation/latest")
def get_latest_presentation():
    # Always build from active sources; never serve a deleted dataset's old report.
    try:
        path = generate_pptx_presentation()
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    return FileResponse(
        path=str(path),
        filename=path.name,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation"
    )

@router.get("/executive-html", response_class=HTMLResponse)
def get_executive_html_report():
    return generate_html_executive_report()


@router.get("/presentation/files/{filename}")
def download_presentation(filename: str):
    import re
    if not re.fullmatch(r"pulsehr_presentation_[0-9a-f]{32}\.pptx", filename):
        raise HTTPException(status_code=404, detail="Presentation not found")
    path = config.EXPORTS_DIR / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Presentation not found")
    return FileResponse(path, filename=filename,
                        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation")


class WorkflowReportRequest(BaseModel):
    sheet_id: int | None = None
    objective: str = "Quarterly Operational Review & Performance Architecture"


@router.post("/orchestrate")
def orchestrate_evidence_report(req: WorkflowReportRequest):
    """Executes the full 7-stage role-based deterministic AI reporting workflow."""
    import json
    import pandas as pd
    from ..db.database import get_connection
    from ..services.reporting.workflow_orchestrator import WorkflowOrchestrator

    with get_connection() as conn:
        if req.sheet_id is not None:
            sheet = conn.execute(
                'SELECT s.*, d.original_name FROM sheets s JOIN dataset_uploads d ON d.id=s.dataset_id WHERE s.id=?',
                (req.sheet_id,)
            ).fetchone()
            if not sheet:
                raise HTTPException(404, "Requested sheet not found")
            rows = conn.execute('SELECT data_json FROM sheet_rows WHERE sheet_id=? ORDER BY row_index', (req.sheet_id,)).fetchall()
            records = [json.loads(r['data_json']) for r in rows]
            dataset_name = sheet['display_name'] or sheet['name']
        else:
            # Workspace global view: load first active sheet
            sheet = conn.execute(
                'SELECT s.*, d.original_name FROM sheets s JOIN dataset_uploads d ON d.id=s.dataset_id ORDER BY s.id ASC LIMIT 1'
            ).fetchone()
            if not sheet:
                raise HTTPException(400, "No active datasets available in workspace")
            rows = conn.execute('SELECT data_json FROM sheet_rows WHERE sheet_id=? ORDER BY row_index', (sheet['id'],)).fetchall()
            records = [json.loads(r['data_json']) for r in rows]
            dataset_name = sheet['display_name'] or sheet['name']

    df = pd.DataFrame(records)
    result = WorkflowOrchestrator.execute(
        df=df,
        dataset_name=dataset_name,
        objective=req.objective
    )
    return result.model_dump()
