from pathlib import Path
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
