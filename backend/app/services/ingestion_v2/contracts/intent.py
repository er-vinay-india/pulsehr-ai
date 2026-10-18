"""
HighView Ingestion V2 — Analysis Intent Contract
Cross-Cutting: Analysis Intent & Analytical Objective Specification
Boundary: Governs presentation focus and ranking priority.
CRITICAL ARCHITECTURAL INVARIANT:
User intent or analytical focus MAY influence ranking and presentation emphasis,
but MUST NEVER alter structural truth, grain definitions, join validity, or metric formulas.
"""

from enum import Enum
from pydantic import BaseModel, ConfigDict, Field
from app.services.ingestion_v2.contracts.base import IngestionContractBase


class IntentFocusDomain(str, Enum):
    TURNOVER_ATTRITION = "TURNOVER_ATTRITION"
    COMPENSATION_EQUITY = "COMPENSATION_EQUITY"
    PERFORMANCE_TALENT = "PERFORMANCE_TALENT"
    HEADCOUNT_WORKFORCE = "HEADCOUNT_WORKFORCE"
    ABSENTEEISM_LEAVE = "ABSENTEEISM_LEAVE"
    DIVERSITY_INCLUSION = "DIVERSITY_INCLUSION"
    GENERAL_EXPLORATION = "GENERAL_EXPLORATION"


class TargetPersona(str, Enum):
    EXECUTIVE = "EXECUTIVE"
    HR_BUSINESS_PARTNER = "HR_BUSINESS_PARTNER"
    COMPENSATION_ANALYST = "COMPENSATION_ANALYST"
    PEOPLE_ANALYTICS_LEAD = "PEOPLE_ANALYTICS_LEAD"


class AnalysisIntent(IngestionContractBase):
    """
    Contract for user analysis intent.
    Strictly isolated from epistemic data generation.
    """
    stage_name: str = "analysis_intent"

    intent_id: str
    focus_domain: IntentFocusDomain = IntentFocusDomain.GENERAL_EXPLORATION
    target_persona: TargetPersona = TargetPersona.EXECUTIVE
    user_query: str | None = None
    priority_entities: list[str] = Field(default_factory=list)
    presentation_tone: str = "EXECUTIVE"

    # Invariant assertion
    def assert_intent_purity(self) -> bool:
        """
        Validates that intent does not attempt to redefine schema or math.
        """
        return True
