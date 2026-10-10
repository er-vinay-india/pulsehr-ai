"""Contracts for Visual Decision Intelligence layer.

Defines:
- AnalyticalIntent: Business questions answered by visuals
- MetricSemantics: Unit, grain, aggregation, denominator
- VisualQuestion: Concise machine-readable question
- AudienceType: Target viewer persona
- ChartType: Governed catalog of chart forms
- ChartSuitabilityScore: Multi-signal suitability evaluation
- VisualDecisionAudit: Audit trail for why a chart was chosen or rejected
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class AnalyticalIntent(str, Enum):
    """Business question intent that a visualization must answer."""
    TREND = "TREND"
    COMPOSITION = "COMPOSITION"
    RANKING = "RANKING"
    COMPARISON = "COMPARISON"
    GAP_EXPLANATION = "GAP_EXPLANATION"
    CONTRIBUTION = "CONTRIBUTION"
    RELATIONSHIP = "RELATIONSHIP"
    DISTRIBUTION = "DISTRIBUTION"
    VARIANCE = "VARIANCE"
    CHANGE = "CHANGE"
    ANOMALY = "ANOMALY"
    FLOW = "FLOW"
    PART_TO_WHOLE = "PART_TO_WHOLE"
    TARGET_VS_ACTUAL = "TARGET_VS_ACTUAL"


class AudienceType(str, Enum):
    """Target viewer audience persona governing chart complexity and density."""
    LAYMAN_EXECUTIVE = "LAYMAN_EXECUTIVE"
    ANALYST = "ANALYST"
    DATA_SCIENTIST = "DATA_SCIENTIST"


class ChartType(str, Enum):
    """Governed chart taxonomy."""
    LINE = "line"
    AREA = "area"
    HORIZONTAL_BAR = "horizontal_bar"
    LOLLIPOP = "lollipop"
    ONE_HUNDRED_PERCENT_STACKED_BAR = "100_percent_stacked_bar"
    STACKED_BAR = "stacked_bar"
    STACKED_AREA = "stacked_area"
    WATERFALL = "waterfall"
    PARETO = "pareto"
    BULLET_BAR = "bullet_bar"
    VARIANCE_BAR = "variance_bar"
    SCATTER = "scatter"
    BUBBLE = "bubble"
    HISTOGRAM = "histogram"
    BOX_PLOT = "box_plot"
    VIOLIN = "violin"
    DONUT = "donut"
    SLOPE = "slope"
    DUMBBELL = "dumbbell"
    CONTROL_CHART = "control_chart"
    PIE = "pie"


class MetricSemantics(BaseModel):
    """Semantic grain, units, and aggregation metadata for a quantitative measure."""
    model_config = ConfigDict(extra="forbid")

    metric_name: str
    semantic_role: str = "MEASURE"               # MEASURE, COUNT, RATIO, RATE, AMOUNT
    unit: str                                     # employee_day, usd, percent, count, hours
    display_unit: str                             # employee-days, $, %, headcount, hrs
    aggregation: str = "SUM"                      # SUM, AVG, COUNT_DISTINCT, RATIO, NONE
    grain: str                                    # employee × working_day, order, transaction
    denominator: str | None = None                # For ratios and rates
    time_grain: str | None = None                 # week, month, day, quarter, year
    is_resolved: bool = True                      # False if grain or unit could not be verified


class DenominatorIntegrityContract(BaseModel):
    """Governance contract ensuring composition charts do not silently drop residual populations."""
    model_config = ConfigDict(extra="forbid")

    metric_name: str
    numerator_components: list[str]
    denominator_metric: str
    denominator_value: float | None = None
    expected_total: float | None = None
    excluded_population: list[str] = Field(default_factory=list)
    residual_component: str | None = None
    is_reconciled: bool = True
    unreconciled_delta: float = 0.0


class VisualQuestion(BaseModel):
    """Machine-readable analytical question that the chart is explicitly chosen to answer."""
    model_config = ConfigDict(extra="forbid")

    question: str
    intent: AnalyticalIntent
    secondary_intent: AnalyticalIntent | None = None
    primary_dimension: str
    dimension_cardinality: int = 1
    is_temporal_dimension: bool = False
    measures: list[str]
    metric_semantics: list[MetricSemantics] = Field(default_factory=list)
    grain: str = ""
    temporal_grain: str | None = None
    denominator_semantics: DenominatorIntegrityContract | None = None


class ChartSuitabilityScore(BaseModel):
    """Scored evaluation of a candidate chart type against the visual question."""
    model_config = ConfigDict(extra="forbid")

    chart_type: ChartType
    total_score: float
    intent_match: float
    semantic_fit: float
    unit_compatibility: float
    scale_compatibility: float
    audience_readability: float
    comparison_efficiency: float
    density_fit: float
    mobile_fit: float
    ambiguity_penalty: float = 0.0
    clutter_penalty: float = 0.0
    rationale: str = ""


class VisualDecisionAudit(BaseModel):
    """Immutable audit trail explaining why Highview chose or rejected specific chart types."""
    model_config = ConfigDict(extra="forbid")

    visual_id: str
    business_question: str
    analytical_intent: AnalyticalIntent
    audience: AudienceType
    candidate_charts: list[ChartSuitabilityScore]
    selected_chart: ChartType
    selection_score: float
    selection_reason: str
    rejected_alternatives: list[dict[str, Any]]
    metric_units: list[str]
    metric_grain: str
    validation_status: Literal["VALIDATED", "BLOCKED", "DEGRADED"] = "VALIDATED"
    blocking_reason: str | None = None
    denominator_integrity: DenominatorIntegrityContract | None = None
