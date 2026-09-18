from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import FileResponse, HTMLResponse
from ..core import config
from ..services.report_generator import generate_pptx_presentation, generate_html_executive_report

router = APIRouter(prefix="/api/reports", tags=["reports"])

@router.post("/presentation")
def create_presentation():
    pptx_path = generate_pptx_presentation()
    return FileResponse(
        path=str(pptx_path),
        filename=pptx_path.name,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation"
    )

@router.get("/presentation/latest")
def get_latest_presentation():
    files = list(config.EXPORTS_DIR.glob("*.pptx"))
    if not files:
        # Generate on the fly
        path = generate_pptx_presentation()
    else:
        path = max(files, key=lambda f: f.stat().st_mtime)

    return FileResponse(
        path=str(path),
        filename=path.name,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation"
    )

@router.get("/executive-html", response_class=HTMLResponse)
def get_executive_html_report():
    return generate_html_executive_report()
