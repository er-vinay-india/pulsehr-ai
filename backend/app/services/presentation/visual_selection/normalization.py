"""Visual Family Normalization Adapter.

Translates legacy ChartFamily enums, raw informal strings, and legacy visual hook
identifiers into canonical VisualFamily enums for the active layered pipeline.

CRITICAL INVARIANTS:
1. Normalizer ONLY handles syntax compatibility and known synonyms.
2. Normalizer NEVER makes semantic fallback decisions (e.g. unknown -> BAR).
3. If an input visual string is unrecognized, return None / unresolved so that
   DataShapeProfile and candidate generation can govern the semantic decision.
"""
from __future__ import annotations

import logging
from typing import Any, Optional
from ..presentation_visual_spec import VisualFamily

logger = logging.getLogger(__name__)

# Complete explicit mapping dictionary from historical, legacy, or raw strings to canonical VisualFamily
RAW_TO_VISUAL_FAMILY: dict[str, VisualFamily] = {
    # Ranking & Bar variants
    "ranked_bar": VisualFamily.RANKED_BAR,
    "ranked-bar": VisualFamily.RANKED_BAR,
    "ranking_bar": VisualFamily.RANKED_BAR,
    "ranking": VisualFamily.RANKED_BAR,
    "ranked": VisualFamily.RANKED_BAR,
    "horizontal_bar": VisualFamily.HORIZONTAL_BAR,
    "horizontal-bar": VisualFamily.HORIZONTAL_BAR,
    "bar_horizontal": VisualFamily.HORIZONTAL_BAR,
    "bar": VisualFamily.BAR,
    "bar_chart": VisualFamily.BAR,
    "bar-chart": VisualFamily.BAR,
    "column": VisualFamily.BAR,
    "column_chart": VisualFamily.BAR,
    "column-chart": VisualFamily.BAR,
    "bar_vertical": VisualFamily.BAR,
    "vertical_bar": VisualFamily.BAR,
    "grouped_bar": VisualFamily.GROUPED_BAR,
    "grouped-bar": VisualFamily.GROUPED_BAR,
    "bar_grouped": VisualFamily.GROUPED_BAR,
    "grouped_column": VisualFamily.GROUPED_BAR,
    "clustered_bar": VisualFamily.GROUPED_BAR,
    "clustered_column": VisualFamily.GROUPED_BAR,
    "stacked_bar": VisualFamily.STACKED_BAR,
    "stacked-bar": VisualFamily.STACKED_BAR,
    "bar_stacked": VisualFamily.STACKED_BAR,
    "stacked_column": VisualFamily.STACKED_BAR,

    # Temporal & Trends
    "line": VisualFamily.LINE,
    "line_chart": VisualFamily.LINE,
    "line-chart": VisualFamily.LINE,
    "line_multi": VisualFamily.LINE,
    "trend": VisualFamily.TREND,
    "timeseries": VisualFamily.LINE,
    "time_series": VisualFamily.LINE,
    "area": VisualFamily.LINE,
    "temporal": VisualFamily.LINE,

    # Correlation & Dispersion
    "scatter": VisualFamily.SCATTER,
    "scatter_plot": VisualFamily.SCATTER,
    "xy_scatter": VisualFamily.SCATTER,
    "bivariate": VisualFamily.SCATTER,
    "correlation": VisualFamily.CORRELATION,
    "box_plot": VisualFamily.BOX_PLOT,
    "box-plot": VisualFamily.BOX_PLOT,
    "boxplot": VisualFamily.BOX_PLOT,
    "box_whisker": VisualFamily.BOX_PLOT,
    "dispersion": VisualFamily.BOX_PLOT,

    # Part-to-whole
    "pie": VisualFamily.PIE,
    "pie_chart": VisualFamily.PIE,
    "donut": VisualFamily.DONUT,
    "doughnut": VisualFamily.DONUT,
    "donut_chart": VisualFamily.DONUT,
    "treemap": VisualFamily.TREEMAP,
    "tree_map": VisualFamily.TREEMAP,

    # Metrics & Cards
    "kpi": VisualFamily.KPI_CARD,
    "kpi_card": VisualFamily.KPI_CARD,
    "kpi-card": VisualFamily.KPI_CARD,
    "kpi_metric": VisualFamily.KPI_CARD,
    "metric": VisualFamily.KPI_CARD,
    "card": VisualFamily.KPI_CARD,
    "kpi_cards_grid": VisualFamily.KPI_CARD,
    "scenario_card": VisualFamily.SCENARIO_CARD,
    "scenario": VisualFamily.SCENARIO_CARD,
    "decision_simulator": VisualFamily.SCENARIO_CARD,
    "counterfactual": VisualFamily.SCENARIO_CARD,

    # Tabular
    "table": VisualFamily.DATA_TABLE,
    "data_table": VisualFamily.DATA_TABLE,
    "table_detail": VisualFamily.DATA_TABLE,
    "tabular": VisualFamily.DATA_TABLE,
    "matrix": VisualFamily.DATA_TABLE,

    # Geographic
    "choropleth": VisualFamily.CHOROPLETH,
    "choropleth_map": VisualFamily.CHOROPLETH,
    "map": VisualFamily.MAP,
    "geo_map": VisualFamily.MAP,
    "bubble_map": VisualFamily.MAP,
    "point_map": VisualFamily.MAP,
    "geographic": VisualFamily.MAP,

    # Specialized Analytical Visuals
    "variance_bar": VisualFamily.VARIANCE_BAR,
    "variance-bar": VisualFamily.VARIANCE_BAR,
    "waterfall": VisualFamily.VARIANCE_BAR,
    "variance_bridge": VisualFamily.VARIANCE_BAR,
    "outlier_summary": VisualFamily.VARIANCE_BAR,
    "bullet": VisualFamily.BULLET,
    "bullet_chart": VisualFamily.BULLET,
    "podium": VisualFamily.PODIUM_TOP_3,
    "podium_top_3": VisualFamily.PODIUM_TOP_3,
    "top_3_podium": VisualFamily.PODIUM_TOP_3,
    "dumbbell": VisualFamily.DUMBBELL,
    "dumbbell_plot": VisualFamily.DUMBBELL,
    "range_plot": VisualFamily.DUMBBELL,
}


def normalize_to_visual_family(raw_visual: Any, default: Optional[VisualFamily] = None) -> Optional[VisualFamily]:
    """Normalizes known legacy syntax, aliases, or synonyms into canonical VisualFamily.

    If the input is unrecognized or unsupported, returns default (None by default)
    so that semantic selection can be properly governed by DataShapeProfile and
    candidate generation, rather than prematurely defaulting to BAR.
    """
    if isinstance(raw_visual, VisualFamily):
        return raw_visual

    if raw_visual is None:
        return default

    # Handle legacy ChartFamily or other enums
    val_str = (raw_visual.value if hasattr(raw_visual, "value") else str(raw_visual)).strip().lower()

    if val_str in RAW_TO_VISUAL_FAMILY:
        return RAW_TO_VISUAL_FAMILY[val_str]

    # Clean whitespace and hyphens
    clean_val = val_str.replace("-", "_").replace(" ", "_")
    if clean_val in RAW_TO_VISUAL_FAMILY:
        return RAW_TO_VISUAL_FAMILY[clean_val]

    logger.debug("Unrecognized visual identifier '%s'; returning neutral unresolved %s", raw_visual, default)
    return default
