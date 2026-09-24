"""Copilot Data Models for Grounded Conversational Q&A (Phase 5)."""

from typing import Any
from pydantic import BaseModel, Field

from ..data_engine.candidate_fact import CandidateFact
from ..data_engine.visualization_models import VisualChartSpec


class GroundedAnswer(BaseModel):
    """Evidence-backed conversational answer to a user query."""
    query: str
    intent: str  # "SURPRISE_ME", "ENTITY_DRILLDOWN", "INTERPRETATION", "CALCULATION", "AMBIGUITY"
    answer_markdown: str
    cited_facts: list[CandidateFact] = Field(default_factory=list)
    recommended_chart: VisualChartSpec | None = None
    followup_questions: list[str] = Field(default_factory=list)
    audit_passed: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)
