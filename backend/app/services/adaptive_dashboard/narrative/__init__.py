"""Executive Narrative, Briefing, and Wording Domain (Phase G5.3).

Provides typed contracts, builders, and integrity guards for:
- Executive titles (zero underscores, zero machine taxonomy, grain-aware).
- Evidence-grounded findings and takeaways (zero number invention, zero causal claims).
- Narrative deduplication and executive summary synthesis.
- Audible executive briefings and claim validation.
"""
from __future__ import annotations

from .contracts import (
    BriefingClaim,
    ExecutiveBriefingSpec,
    NarrativeInput,
    NarrativeResult,
)
from .integrity import (
    NarrativeEntitlementIntegrity,
    NarrativeGrainIntegrity,
    NarrativeSemanticAlignmentIntegrity,
    NarrativeViolationError,
    PROHIBITED_MACHINE_TAXONOMY,
    PROHIBITED_WORDS,
)
from .title_builder import TitleBuilder
from .finding_builder import FindingBuilder
from .deduplication import NarrativeDeduplicationIntegrity
from .briefing_service import (
    ExecutiveBriefingService,
    count_words,
    format_pp_for_speech,
    validate_briefing_claims,
)

__all__ = [
    "BriefingClaim",
    "ExecutiveBriefingSpec",
    "ExecutiveBriefingService",
    "FindingBuilder",
    "NarrativeDeduplicationIntegrity",
    "NarrativeEntitlementIntegrity",
    "NarrativeGrainIntegrity",
    "NarrativeInput",
    "NarrativeResult",
    "NarrativeSemanticAlignmentIntegrity",
    "NarrativeViolationError",
    "PROHIBITED_MACHINE_TAXONOMY",
    "PROHIBITED_WORDS",
    "TitleBuilder",
    "count_words",
    "format_pp_for_speech",
    "validate_briefing_claims",
]
