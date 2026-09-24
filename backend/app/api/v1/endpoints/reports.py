"""V1 API Endpoints alias for reports router."""
from app.routers.reports import (
    router,
    PresentationRequest,
    WorkflowReportRequest,
    create_presentation,
    get_latest_presentation,
    get_executive_html_report,
    download_presentation,
    orchestrate_evidence_report,
)

__all__ = [
    "router",
    "PresentationRequest",
    "WorkflowReportRequest",
    "create_presentation",
    "get_latest_presentation",
    "get_executive_html_report",
    "download_presentation",
    "orchestrate_evidence_report",
]
