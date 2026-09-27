"""Data-Driven Chart Selector with Guardrails and Explainability for Phase 4.

Maps empirical data relationships and business questions directly to canonical ChartFamily
specifications. Enforces strict visual guardrails, provides human-readable explainability,
and tracks deck rhythm to maintain visual diversity without randomness.
"""

from __future__ import annotations

import logging
from typing import Any
from .chart_models import (
    ChartAnnotation,
    ChartFamily,
    ChartFormatting,
    ChartSeries,
    ChartSpec,
)

logger = logging.getLogger(__name__)


class ChartSelector:
    """Intelligent, data-driven chart selector enforcing semantic suitability and guardrails."""

    def __init__(self):
        self._recent_families: list[ChartFamily] = []

    def reset_rhythm(self):
        """Clears recent family history for a new presentation run."""
        self._recent_families.clear()

    @classmethod
    def select_chart(
        cls,
        data_relationship: str,
        num_categories: int = 5,
        num_series: int = 1,
        categories: list[str] | None = None,
        extra_options: dict[str, Any] | None = None
    ) -> tuple[ChartFamily, str]:
        cats = categories or [f"Cat {i+1}" for i in range(num_categories)]
        rel_up = (data_relationship or "").upper()
        if "SCATTER" in rel_up or "CORRELATION" in rel_up:
            mock_series = [{"name": f"Series {i+1}", "data": [[idx, idx * 2.5] for idx in range(len(cats))]} for i in range(num_series)]
        elif "BUBBLE" in rel_up:
            mock_series = [{"name": f"Series {i+1}", "data": [[idx, idx * 2, idx * 5] for idx in range(len(cats))]} for i in range(num_series)]
        else:
            mock_series = [{"name": f"Series {i+1}", "data": [10] * len(cats)} for i in range(num_series)]
        selector = cls()
        spec = selector.select_and_build_chart(
            chart_id="tmp",
            data_relationship=data_relationship,
            categories=cats,
            series_data=mock_series,
            extra_options=extra_options
        )
        return spec.family, spec.selection_reason

    def select_and_build_chart(
        self,
        chart_id: str,
        data_relationship: str,
        categories: list[str],
        series_data: list[dict[str, Any]],
        title: str = "",
        subtitle: str = "",
        purpose: str = "comparison",
        source_refs: list[str] | None = None,
        extra_options: dict[str, Any] | None = None
    ) -> ChartSpec:
        """Selects the optimal canonical ChartFamily based on data relationships and builds a validated ChartSpec."""
        extras = extra_options or {}
        num_categories = len(categories)
        num_series = len(series_data)
        rel_upper = (data_relationship or "").strip().upper()

        family: ChartFamily
        reason: str

        # 1. TIME + NUMERIC -> LINE / AREA
        if "TIME" in rel_upper or "TEMPORAL" in rel_upper or "TREND" in rel_upper:
            if num_series > 1:
                family = ChartFamily.LINE_MULTI
                reason = f"Multi-line chart selected to track {num_series} distinct metric trajectories over {num_categories} time periods."
            elif extras.get("is_cumulative") or "AREA" in rel_upper:
                family = ChartFamily.AREA
                reason = "Area chart selected to highlight cumulative volume and temporal magnitude."
            else:
                family = ChartFamily.LINE
                reason = f"Line chart selected to illustrate directional momentum across {num_categories} chronological points."

        # 2. RANKING -> HORIZONTAL BAR
        elif "RANK" in rel_upper or (extras.get("is_ranking") and num_categories > 4):
            family = ChartFamily.BAR_HORIZONTAL
            max_label_len = max([len(str(c)) for c in categories]) if categories else 0
            reason = f"Horizontal bar selected because {num_categories} entities are ranked and labels (up to {max_label_len} chars) require horizontal scanning space."

        # 3. PART TO WHOLE -> DONUT or STACKED BAR / TREEMAP
        elif "PART_TO_WHOLE" in rel_upper or "SHARE" in rel_upper or "COMPOSITION" in rel_upper:
            if num_categories <= 5:
                family = ChartFamily.DONUT
                reason = f"Donut chart selected because {num_categories} categories represent a clear part-to-whole share (<= 5 slices)."
            else:
                family = ChartFamily.BAR_HORIZONTAL
                reason = f"Horizontal bar selected instead of donut because {num_categories} categories exceeds the 5-category radial slice threshold."

        # 4. TWO NUMERICAL VARIABLES -> SCATTER
        elif "SCATTER" in rel_upper or "CORRELATION" in rel_upper or "BIVARIATE" in rel_upper:
            family = ChartFamily.SCATTER
            reason = "Scatter plot selected to evaluate mathematical correlation and clustering between two continuous numeric variables."

        # 5. THREE NUMERICAL VARIABLES -> BUBBLE
        elif "BUBBLE" in rel_upper or "TRIVARIATE" in rel_upper:
            family = ChartFamily.BUBBLE
            reason = "Bubble chart selected to communicate tri-variate relationship [X-axis, Y-axis, bubble magnitude]."

        # 6. CATEGORY x CATEGORY + VALUE -> HEATMAP
        elif "HEATMAP" in rel_upper or "MATRIX_2D" in rel_upper or ("x_categories" in extras and "y_categories" in extras):
            family = ChartFamily.HEATMAP
            reason = "Heatmap selected to visualize intensity distribution across intersecting categorical dimensions."

        # 7. FLOW / MIGRATION -> SANKEY
        elif "FLOW" in rel_upper or "SANKEY" in rel_upper or "FUNNEL_FLOW" in rel_upper:
            family = ChartFamily.SANKEY
            reason = "Sankey flow diagram selected to illustrate quantitative transition volume between origin and destination stages."

        # 8. HIERARCHY -> TREEMAP / SUNBURST
        elif "HIERARCHY" in rel_upper or "TREEMAP" in rel_upper:
            family = ChartFamily.TREEMAP
            reason = "Treemap selected to present nested hierarchical proportions with spatial area encoding."

        # 9. PIPELINE / CONVERSION -> FUNNEL
        elif "PIPELINE" in rel_upper or "FUNNEL" in rel_upper or "CONVERSION" in rel_upper:
            family = ChartFamily.FUNNEL
            reason = "Funnel chart selected to display attrition and conversion velocity through ordered stages."

        # 10. OHLC -> CANDLESTICK
        elif "OHLC" in rel_upper or "CANDLESTICK" in rel_upper or "STOCK" in rel_upper:
            family = ChartFamily.CANDLESTICK
            reason = "Candlestick chart selected to portray intra-period trading volatility [Open, Close, Low, High]."

        # 11. CUMULATIVE CONTRIBUTION -> WATERFALL
        elif "WATERFALL" in rel_upper or "VARIANCE_BRIDGE" in rel_upper or "CONTRIBUTION" in rel_upper:
            family = ChartFamily.WATERFALL
            reason = "Waterfall bridge chart selected to decompose sequential positive and negative variance drivers."

        # 12. MULTI-DIMENSIONAL PROFILE -> RADAR
        elif "RADAR" in rel_upper or "SPIDER" in rel_upper or (3 <= num_categories <= 8 and "PROFILE" in rel_upper):
            family = ChartFamily.RADAR
            reason = f"Radar chart selected to map multi-competency performance balance across {num_categories} normalized dimensions."

        # 13. DISTRIBUTION -> HISTOGRAM / BOXPLOT
        elif "DISTRIBUTION" in rel_upper or "HISTOGRAM" in rel_upper:
            family = ChartFamily.HISTOGRAM
            reason = "Histogram selected to display frequency density across continuous numeric bins."
        elif "BOXPLOT" in rel_upper or "SPREAD" in rel_upper:
            family = ChartFamily.BOXPLOT
            reason = "Boxplot selected to summarize 5-point quartile dispersion, median, and outlier tails."

        # 14. DEFAULT CATEGORY + NUMERIC -> BAR (Vertical or Horizontal)
        else:
            if num_series > 1:
                family = ChartFamily.BAR_GROUPED
                reason = f"Grouped bar chart selected to compare {num_series} metrics across {num_categories} categories."
            elif num_categories > 6:
                family = ChartFamily.BAR_HORIZONTAL
                reason = f"Horizontal bar selected to cleanly format {num_categories} categorical records."
            else:
                family = ChartFamily.BAR_VERTICAL
                reason = f"Vertical column chart selected for clear visual magnitude comparison across {num_categories} categories."

        # Visual rhythm adjustment: CLARITY > DIVERSITY
        if self._recent_families and family == self._recent_families[-1]:
            # If the exact same family was used on immediately prior slide, consider clean variant
            if family == ChartFamily.BAR_VERTICAL and num_categories > 4:
                family = ChartFamily.BAR_HORIZONTAL
                reason += " (Shifted to horizontal orientation to vary presentation rhythm while preserving readability)."

        # Construct ChartSeries objects
        built_series: list[ChartSeries] = []
        for idx, s in enumerate(series_data):
            name = s.get("name") or f"Series {idx + 1}"
            data_points = s.get("data") or s.get("values") or []
            s_type = s.get("type")
            color = s.get("color")
            built_series.append(ChartSeries(
                name=name,
                data=data_points,
                type=s_type,
                color=color,
                stack=s.get("stack"),
                smooth=s.get("smooth", True),
                area_style=s.get("area_style", False)
            ))

        # Build initial spec
        spec = ChartSpec(
            chart_id=chart_id,
            family=family,
            variant=extras.get("variant", "standard"),
            purpose=purpose,
            title=title,
            subtitle=subtitle,
            categories=categories,
            series=built_series,
            formatting=ChartFormatting(
                value_format=extras.get("value_format", "standard"),
                sort=extras.get("sort", "none"),
                unit=extras.get("unit", "")
            ),
            source_refs=source_refs or [],
            selection_reason=reason,
            extra_options=extras
        )

        # Enforce Guardrails
        guard_res = spec.validate_guardrails()
        if not guard_res.passed and guard_res.fallback_family:
            logger.warning(
                f"Chart '{chart_id}' violated guardrails: {guard_res.violations}. "
                f"Applying fallback {guard_res.fallback_family.value}: {guard_res.reason}"
            )
            spec.family = guard_res.fallback_family
            spec.selection_reason = f"{reason} [Fallback: {guard_res.reason}]"

        self._recent_families.append(spec.family)
        return spec


# Global singleton selector
chart_selector = ChartSelector()
