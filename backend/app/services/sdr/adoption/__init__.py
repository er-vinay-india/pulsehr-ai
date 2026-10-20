"""
HighView Semantic Data Refinery — Phase SDR-9 Controlled Adoption Module
"""

from app.services.sdr.adoption.contracts import (
    SDRAdoptionRecord,
    SDRAdoptionState,
    SDREligibilityAssessment,
    SDRRouteDecision,
)
from app.services.sdr.adoption.eligibility import SDREligibilityEvaluator
from app.services.sdr.adoption.cache_safety import compute_sdr_cache_key
from app.services.sdr.adoption.telemetry import (
    SDRAdoptionTelemetryLedger,
    compute_latency_stats,
    get_adoption_telemetry,
)
from app.services.sdr.adoption.manager import (
    SDRAdoptionManager,
    get_sdr_adoption_manager,
)
from app.services.sdr.adoption.hriday_adoption import build_sdr_hriday_context
from app.services.sdr.adoption.dashboard_adoption import build_sdr_dashboard_response
from app.services.sdr.adoption.presentation_adoption import build_sdr_presentation_evidence

__all__ = [
    "SDRAdoptionRecord",
    "SDRAdoptionState",
    "SDREligibilityAssessment",
    "SDRRouteDecision",
    "SDREligibilityEvaluator",
    "compute_sdr_cache_key",
    "SDRAdoptionTelemetryLedger",
    "compute_latency_stats",
    "get_adoption_telemetry",
    "SDRAdoptionManager",
    "get_sdr_adoption_manager",
    "build_sdr_hriday_context",
    "build_sdr_dashboard_response",
    "build_sdr_presentation_evidence",
]
