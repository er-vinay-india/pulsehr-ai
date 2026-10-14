"""Narrative and Briefing Typed Contracts (Phase G5.3).

Defines:
- NarrativeInput: Typed, verified input for business interpretation and wording (zero raw dataframes/DB connections).
- NarrativeResult: Typed, evidence-bound business wording (title, finding, takeaway, summary fragment, and cited evidence IDs).
- Re-exports of BriefingClaim and ExecutiveBriefingSpec for legacy briefing consumers.
"""
from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

from ..contracts import (
    BriefingClaim,
    ExecutiveBriefingSpec,
    GlanceSpec,
    ExplainSpec,
    InspectSpec,
)
from ..evidence.contracts import BoundFact, BoundEvidence


class NarrativeInput(BaseModel):
    """Verified analytical facts and evidence passed into the narrative layer.
    
    Strictly decoupled from raw dataframes, SQLite connections, DuckDB sessions, and filesystem paths.
    """
    model_config = ConfigDict(extra="ignore")

    dataset_id: int
    dataset_version: int | None = None
    domain: str = "general"
    topic_id: str | None = None
    subject: str = ""
    metric: str = ""
    bound_facts: list[BoundFact] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    context_refs: list[str] = Field(default_factory=list)
    scenario_refs: list[str] = Field(default_factory=list)
    analytical_intent: str = "RANKING"  # RANKING, TREND, SEGMENTATION, COMPOSITION, RELATIONSHIP, ANOMALY, etc.
    entity_grain: str = "aggregate"  # PERSON, DEPARTMENT, STORE, LOCATION, aggregate
    tokens: dict[str, Any] = Field(default_factory=dict)


class NarrativeResult(BaseModel):
    """Business interpretation and executive wording bound to verified evidence nodes."""
    model_config = ConfigDict(extra="ignore")

    topic_id: str | None = None
    title: str
    finding: str
    takeaway: str = ""
    business_question: str = ""
    executive_summary_fragment: str = ""
    recommended_action: str = ""
    claim_refs: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    context_ids: list[str] = Field(default_factory=list)
    scenario_ids: list[str] = Field(default_factory=list)
    entity_grain: str = "aggregate"
    domain: str = "general"


__all__ = [
    "NarrativeInput",
    "NarrativeResult",
    "BriefingClaim",
    "ExecutiveBriefingSpec",
    "GlanceSpec",
    "ExplainSpec",
    "InspectSpec",
]
