"""Chart Suitability Matrix and Decision Taxonomy.

Governs baseline preferred, alternative, and avoided chart forms across all analytical intents.
"""
from __future__ import annotations

from .contracts import AnalyticalIntent, ChartType


CHART_SUITABILITY_MATRIX: dict[AnalyticalIntent, dict[str, list[ChartType]]] = {
    AnalyticalIntent.TREND: {
        "preferred": [ChartType.LINE],
        "alternative": [ChartType.AREA, ChartType.CONTROL_CHART],
        "avoid": [ChartType.PIE, ChartType.DONUT, ChartType.HORIZONTAL_BAR],
    },
    AnalyticalIntent.RANKING: {
        "preferred": [ChartType.HORIZONTAL_BAR],
        "alternative": [ChartType.LOLLIPOP],
        "avoid": [ChartType.LINE, ChartType.PIE, ChartType.DONUT],
    },
    AnalyticalIntent.COMPOSITION: {
        "preferred": [ChartType.ONE_HUNDRED_PERCENT_STACKED_BAR],
        "alternative": [ChartType.STACKED_BAR, ChartType.STACKED_AREA, ChartType.DONUT],
        "avoid": [ChartType.LINE, ChartType.PIE, ChartType.SCATTER],
    },
    AnalyticalIntent.GAP_EXPLANATION: {
        "preferred": [ChartType.WATERFALL],
        "alternative": [ChartType.ONE_HUNDRED_PERCENT_STACKED_BAR, ChartType.STACKED_BAR, ChartType.VARIANCE_BAR],
        "avoid": [ChartType.LINE, ChartType.PIE, ChartType.AREA],
    },
    AnalyticalIntent.TARGET_VS_ACTUAL: {
        "preferred": [ChartType.BULLET_BAR],
        "alternative": [ChartType.HORIZONTAL_BAR, ChartType.VARIANCE_BAR],
        "avoid": [ChartType.PIE, ChartType.LINE, ChartType.AREA],
    },
    AnalyticalIntent.RELATIONSHIP: {
        "preferred": [ChartType.SCATTER],
        "alternative": [ChartType.BUBBLE],
        "avoid": [ChartType.LINE, ChartType.PIE, ChartType.STACKED_BAR],
    },
    AnalyticalIntent.DISTRIBUTION: {
        "preferred": [ChartType.HISTOGRAM, ChartType.BOX_PLOT],
        "alternative": [ChartType.VIOLIN],
        "avoid": [ChartType.PIE, ChartType.LINE],
    },
    AnalyticalIntent.CONTRIBUTION: {
        "preferred": [ChartType.WATERFALL],
        "alternative": [ChartType.PARETO, ChartType.STACKED_BAR],
        "avoid": [ChartType.LINE, ChartType.PIE],
    },
    AnalyticalIntent.PART_TO_WHOLE: {
        "preferred": [ChartType.STACKED_BAR, ChartType.ONE_HUNDRED_PERCENT_STACKED_BAR],
        "alternative": [ChartType.DONUT],
        "avoid": [ChartType.LINE, ChartType.PIE],
    },
    AnalyticalIntent.CHANGE: {
        "preferred": [ChartType.SLOPE, ChartType.DUMBBELL],
        "alternative": [ChartType.HORIZONTAL_BAR, ChartType.LINE],
        "avoid": [ChartType.PIE, ChartType.DONUT],
    },
    AnalyticalIntent.ANOMALY: {
        "preferred": [ChartType.CONTROL_CHART],
        "alternative": [ChartType.LINE],
        "avoid": [ChartType.PIE, ChartType.DONUT, ChartType.STACKED_BAR],
    },
    AnalyticalIntent.VARIANCE: {
        "preferred": [ChartType.VARIANCE_BAR],
        "alternative": [ChartType.WATERFALL, ChartType.BULLET_BAR],
        "avoid": [ChartType.PIE, ChartType.LINE],
    },
    AnalyticalIntent.FLOW: {
        "preferred": [ChartType.WATERFALL],
        "alternative": [ChartType.STACKED_BAR],
        "avoid": [ChartType.PIE, ChartType.LINE],
    },
    AnalyticalIntent.COMPARISON: {
        "preferred": [ChartType.HORIZONTAL_BAR],
        "alternative": [ChartType.BULLET_BAR, ChartType.ONE_HUNDRED_PERCENT_STACKED_BAR],
        "avoid": [ChartType.PIE, ChartType.LINE],
    },
}
