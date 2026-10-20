"""
HighView Semantic Data Refinery — Phase SDR-8
Shadow Consumer Integration Package
"""

from app.services.sdr.shadow.contracts import (
    ComparisonClass,
    DisagreementType,
    FactComparison,
    FactIdentity,
    SDRShadowEvaluation,
    SemanticComparison,
    Severity,
    ShadowConsumerType,
    ShadowTelemetrySummary,
)
from app.services.sdr.shadow.cross_consumer import CrossConsumerFactAuditor
from app.services.sdr.shadow.dashboard_shadow import evaluate_dashboard_shadow
from app.services.sdr.shadow.fact_comparator import (
    FactComparator,
    normalize_grain,
    normalize_unit,
    parse_numeric_value,
)
from app.services.sdr.shadow.hriday_shadow import evaluate_hriday_shadow
from app.services.sdr.shadow.presentation_shadow import evaluate_presentation_shadow
from app.services.sdr.shadow.shadow_evaluator import SDRShadowArtifactLoader
from app.services.sdr.shadow.telemetry import (
    ShadowTelemetryLedger,
    get_shadow_telemetry_ledger,
)

__all__ = [
    "ComparisonClass",
    "DisagreementType",
    "FactComparison",
    "FactIdentity",
    "SDRShadowEvaluation",
    "SemanticComparison",
    "Severity",
    "ShadowConsumerType",
    "ShadowTelemetrySummary",
    "CrossConsumerFactAuditor",
    "evaluate_dashboard_shadow",
    "FactComparator",
    "normalize_grain",
    "normalize_unit",
    "parse_numeric_value",
    "evaluate_hriday_shadow",
    "evaluate_presentation_shadow",
    "SDRShadowArtifactLoader",
    "ShadowTelemetryLedger",
    "get_shadow_telemetry_ledger",
]
