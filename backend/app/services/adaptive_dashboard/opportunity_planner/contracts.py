"""Contracts for the Analytical Opportunity Planner.

Defines typed schemas for candidate opportunities, multi-factor scoring,
combinatorial reduction tracking, and analytical role pairings.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class AnalyticalOpportunityType(str, Enum):
    """Canonical analytical pairings derived directly from ingestion semantic roles."""
    MEASURE_BY_DIMENSION = "MEASURE_BY_DIMENSION"           # Measure + Categorical Dimension (ranking, variance, spread)
    MEASURE_BY_TIME = "MEASURE_BY_TIME"                     # Measure + Temporal Dimension (trend, seasonality, change-point)
    DIMENSION_BY_DIMENSION = "DIMENSION_BY_DIMENSION"       # Categorical + Categorical (interaction, contingency, concentration)
    MEASURE_BY_MEASURE = "MEASURE_BY_MEASURE"               # Measure + Measure (scatter, correlation, lagged elasticity)
    CROSS_SHEET_RELATIONSHIP = "CROSS_SHEET_RELATIONSHIP"   # Validated Cross-Sheet Join (reconciliation, cross-table KPI)
    COMPOSITION_PART_TO_WHOLE = "COMPOSITION_PART_TO_WHOLE" # Multi-measure breakdown (reconciled capacity, share)


class AnalyticalOpportunityScore(BaseModel):
    """Multi-factor score prioritizing candidate analytical opportunities."""
    model_config = ConfigDict(extra="forbid")

    business_impact: float = 0.5
    statistical_strength: float = 0.5
    actionability: float = 0.5
    relationship_confidence: float = 0.5
    novelty: float = 0.5
    temporal_relevance: float = 0.5
    cross_sheet_value: float = 0.0
    visual_suitability: float = 0.5
    redundancy_penalty: float = 0.0
    uncertainty_penalty: float = 0.0
    total_score: float = 0.5

    @classmethod
    def compute(
        cls,
        business_impact: float = 0.5,
        statistical_strength: float = 0.5,
        actionability: float = 0.5,
        relationship_confidence: float = 0.5,
        novelty: float = 0.5,
        temporal_relevance: float = 0.5,
        cross_sheet_value: float = 0.0,
        visual_suitability: float = 0.5,
        redundancy_penalty: float = 0.0,
        uncertainty_penalty: float = 0.0,
    ) -> AnalyticalOpportunityScore:
        """Calculates governed merit score using weighted formula."""
        raw = (
            0.20 * business_impact
            + 0.18 * statistical_strength
            + 0.15 * actionability
            + 0.12 * relationship_confidence
            + 0.10 * novelty
            + 0.10 * temporal_relevance
            + 0.10 * cross_sheet_value
            + 0.05 * visual_suitability
            - 0.15 * redundancy_penalty
            - 0.10 * uncertainty_penalty
        )
        total = round(max(0.0, min(1.0, raw)), 4)
        return cls(
            business_impact=round(business_impact, 2),
            statistical_strength=round(statistical_strength, 2),
            actionability=round(actionability, 2),
            relationship_confidence=round(relationship_confidence, 2),
            novelty=round(novelty, 2),
            temporal_relevance=round(temporal_relevance, 2),
            cross_sheet_value=round(cross_sheet_value, 2),
            visual_suitability=round(visual_suitability, 2),
            redundancy_penalty=round(redundancy_penalty, 2),
            uncertainty_penalty=round(uncertainty_penalty, 2),
            total_score=total,
        )


class RelationshipReductionTracker(BaseModel):
    """Audits how semantic grouping eliminates brute-force cartesian explosion."""
    model_config = ConfigDict(extra="forbid")

    raw_possible_relationships: int = 0
    eligible_group_relationships: int = 0
    eligible_column_relationships: int = 0
    statistically_meaningful_relationships: int = 0
    selected_executive_relationships: int = 0
    reduction_ratio: float = 0.0  # Percentage of brute-force noise eliminated


class AnalyticalOpportunity(BaseModel):
    """Deterministic candidate opportunity generated from ingestion semantic metadata."""
    model_config = ConfigDict(extra="forbid")

    opportunity_id: str
    opportunity_type: AnalyticalOpportunityType
    title: str
    question: str
    sheet_id: int
    sheet_name: str
    primary_measure: str | None = None
    primary_dimension: str | None = None
    secondary_measure: str | None = None
    secondary_dimension: str | None = None
    semantic_group: str | None = None
    secondary_group: str | None = None
    measure_unit: str | None = None
    metric_grain: str | None = None
    temporal_grain: str | None = None
    cardinality: int = 0
    statistical_intent: str = "ranking"  # ranking, variance, trend, correlation, composition, anomaly
    target_visual_archetype: str = "RANKING_STORY"
    score: AnalyticalOpportunityScore
    is_cross_sheet: bool = False
    source_sheet_ids: list[int] = Field(default_factory=list)
    relationship_id: str | None = None
    join_confidence: float = 1.0
    effect_size: float = 0.5
    lag_periods: int = 0
    semantic_family: str | None = None
    periods: list[str] = Field(default_factory=list)
    underlying_columns: list[str] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)
