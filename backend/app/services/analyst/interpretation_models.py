"""Pydantic schemas for Phase 3A: Evidence-Grounded AI Interpretation."""

from pydantic import BaseModel, Field


class InterpretationInsight(BaseModel):
    """A structured, evidence-grounded analytical insight synthesized by the Analyst model."""
    insight_id: str = Field(description="Unique insight identifier (e.g. INSIGHT-001)")
    title: str = Field(description="Concise analytical title summarizing the cross-fact theme")
    observation: str = Field(
        description="Strictly what the cited facts show. Every factual statement MUST cite [FACT-XXX]."
    )
    interpretation: str = Field(
        description="What the combination of facts suggests or why it matters operationally, citing [FACT-XXX]."
    )
    questions_to_investigate: list[str] = Field(
        default_factory=list,
        description="Hypotheses or specific questions for human analysts to investigate next."
    )
    supporting_fact_ids: list[str] = Field(
        default_factory=list,
        description="All fact IDs directly referenced in this insight."
    )
    confidence: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Confidence score from 0.0 to 1.0 reflecting analytical certainty."
    )
    caveats: list[str] = Field(
        default_factory=list,
        description="Data limitations, non-causality boundaries, or sample size constraints."
    )


class InterpretationResponse(BaseModel):
    """Overall interpretation payload produced by the Analyst model."""
    executive_synthesis: str = Field(
        description="High-level narrative connecting the key insights across the dataset."
    )
    insights: list[InterpretationInsight] = Field(
        default_factory=list,
        description="List of structured interpretation insights."
    )
