"""
HighView Ingestion V2 — Gateway Adapters Package
Stage: Consumer Cutover Infrastructure
Exports consumer adapters for HRIDAY, Dashboard, and Presentation.
"""

from app.services.ingestion_v2.gateway.adapters.hriday_adapter import (
    HridayIntelligenceAdapter,
    get_hriday_adapter,
    set_hriday_adapter,
)
from app.services.ingestion_v2.gateway.adapters.dashboard_adapter import (
    DashboardIntelligenceAdapter,
    compute_semantic_render_hash,
    get_dashboard_adapter,
    set_dashboard_adapter,
)
from app.services.ingestion_v2.gateway.adapters.presentation_adapter import (
    PresentationIntelligenceAdapter,
    get_presentation_adapter,
    set_presentation_adapter,
    map_presentation_diagnostic_to_fallback_reason,
)

__all__ = [
    "HridayIntelligenceAdapter",
    "get_hriday_adapter",
    "set_hriday_adapter",
    "DashboardIntelligenceAdapter",
    "get_dashboard_adapter",
    "set_dashboard_adapter",
    "compute_semantic_render_hash",
    "PresentationIntelligenceAdapter",
    "get_presentation_adapter",
    "set_presentation_adapter",
    "map_presentation_diagnostic_to_fallback_reason",
]
