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

__all__ = [
    "HridayIntelligenceAdapter",
    "get_hriday_adapter",
    "set_hriday_adapter",
]
