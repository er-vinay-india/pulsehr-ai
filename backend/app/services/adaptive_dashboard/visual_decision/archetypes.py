"""Governed Visual Archetypes Library.

Provides multi-level visual archetypes combining primary executive charts with
contextual drill-down views (e.g. 100% stacked bar with waterfall drill-down).
"""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict, Field

from .contracts import AnalyticalIntent, ChartType


class VisualArchetype(BaseModel):
    """Governed visual archetype with primary and drill-down specifications."""
    model_config = ConfigDict(extra="forbid")

    archetype_id: str
    archetype_name: str
    primary_intent: AnalyticalIntent
    preferred_chart: ChartType
    drill_down_chart: ChartType | None = None
    labeling_strategy: str
    takeaway_pattern: str
    mobile_behavior: str
    description: str


ARCHETYPE_LIBRARY: dict[str, VisualArchetype] = {
    "COMPOSITION_STORY": VisualArchetype(
        archetype_id="COMPOSITION_STORY",
        archetype_name="Workforce Capacity & Resource Composition",
        primary_intent=AnalyticalIntent.COMPOSITION,
        preferred_chart=ChartType.ONE_HUNDRED_PERCENT_STACKED_BAR,
        drill_down_chart=ChartType.WATERFALL,
        labeling_strategy="proportional_percentages_with_exact_units",
        takeaway_pattern="Proportional split across workforce disposition states",
        mobile_behavior="vertical_stacked_bars_with_toggle",
        description="Highlights resource allocation and capacity share without scale distortion.",
    ),
    "GAP_STORY": VisualArchetype(
        archetype_id="GAP_STORY",
        archetype_name="Reconciliation & Capacity Gap Analysis",
        primary_intent=AnalyticalIntent.GAP_EXPLANATION,
        preferred_chart=ChartType.WATERFALL,
        drill_down_chart=ChartType.ONE_HUNDRED_PERCENT_STACKED_BAR,
        labeling_strategy="delta_step_annotations",
        takeaway_pattern="Stepwise bridge from expected capacity to actual presence",
        mobile_behavior="horizontal_step_cards",
        description="Explains divergence between planned and realized operational metrics.",
    ),
    "RANKING_STORY": VisualArchetype(
        archetype_id="RANKING_STORY",
        archetype_name="Cohort Ranking & Segment Disparity",
        primary_intent=AnalyticalIntent.RANKING,
        preferred_chart=ChartType.HORIZONTAL_BAR,
        drill_down_chart=ChartType.BULLET_BAR,
        labeling_strategy="sorted_descending_with_benchmark_line",
        takeaway_pattern="Ranking highlighting top/bottom outliers and spread against policy",
        mobile_behavior="natural_vertical_scrolling_bars",
        description="Compares discrete organizational units against benchmarks.",
    ),
    "TREND_STORY": VisualArchetype(
        archetype_id="TREND_STORY",
        archetype_name="Operational Trajectory & Cadence",
        primary_intent=AnalyticalIntent.TREND,
        preferred_chart=ChartType.LINE,
        drill_down_chart=ChartType.CONTROL_CHART,
        labeling_strategy="temporal_chronological_with_trend_line",
        takeaway_pattern="Directional movement, volatility, and cycle stability over time",
        mobile_behavior="pinch_zoom_timeline_with_summary_endpoints",
        description="Shows continuous metric progression over time intervals.",
    ),
    "TARGET_STORY": VisualArchetype(
        archetype_id="TARGET_STORY",
        archetype_name="Policy Target & Compliance Adherence",
        primary_intent=AnalyticalIntent.TARGET_VS_ACTUAL,
        preferred_chart=ChartType.BULLET_BAR,
        drill_down_chart=ChartType.VARIANCE_BAR,
        labeling_strategy="actual_fill_with_target_marker",
        takeaway_pattern="Distance to compliance threshold and variance deficit",
        mobile_behavior="compact_bullet_tiles",
        description="Evaluates operational results against pre-set policies.",
    ),
    "RELATIONSHIP_STORY": VisualArchetype(
        archetype_id="RELATIONSHIP_STORY",
        archetype_name="Co-Movement & Covariance Explorer",
        primary_intent=AnalyticalIntent.RELATIONSHIP,
        preferred_chart=ChartType.SCATTER,
        drill_down_chart=ChartType.BUBBLE,
        labeling_strategy="bivariate_orthogonal_axes",
        takeaway_pattern="Statistical co-movement and clustering across entities",
        mobile_behavior="quadrant_summary_matrix",
        description="Examines statistical association between two continuous quantitative measures.",
    ),
    "CONTRIBUTION_STORY": VisualArchetype(
        archetype_id="CONTRIBUTION_STORY",
        archetype_name="Cumulative Factor Contribution Bridge",
        primary_intent=AnalyticalIntent.CONTRIBUTION,
        preferred_chart=ChartType.WATERFALL,
        drill_down_chart=ChartType.PARETO,
        labeling_strategy="signed_positive_negative_deltas",
        takeaway_pattern="Component contributions culminating in net variance",
        mobile_behavior="waterfall_summary_stack",
        description="Attributes top drivers contributing to an aggregated total.",
    ),
}
