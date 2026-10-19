"""
HighView Semantic Data Refinery — Phase SDR-4
Enrichment Module
"""

from app.services.sdr.enrichment.hard_gates import HardGovernanceGateEvaluator
from app.services.sdr.enrichment.mock_providers import (
    CodeLabelProvider,
    DatePartProvider,
    MockAmbiguousProvider,
    MockFailingProvider,
    MockLowUtilityProvider,
    MockSensitiveInferenceProvider,
)
from app.services.sdr.enrichment.provider import (
    EnrichmentProvider,
    EnrichmentProviderRegistry,
)
from app.services.sdr.enrichment.utility_evaluator import InformationGainEvaluator
from app.services.sdr.enrichment.enrichment_engine import (
    SDREnrichmentEngine,
    SDREnrichmentResult,
)

__all__ = [
    "HardGovernanceGateEvaluator",
    "CodeLabelProvider",
    "DatePartProvider",
    "MockAmbiguousProvider",
    "MockFailingProvider",
    "MockLowUtilityProvider",
    "MockSensitiveInferenceProvider",
    "EnrichmentProvider",
    "EnrichmentProviderRegistry",
    "InformationGainEvaluator",
    "SDREnrichmentEngine",
    "SDREnrichmentResult",
]
