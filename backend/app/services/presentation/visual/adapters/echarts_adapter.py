"""ECharts Adapter for Phase 4.

Translates canonical ChartSpec models into production-ready Apache ECharts configuration objects.
Applies presentation slide design tokens, axis typography, and accessibility tooltip configs.
"""

from __future__ import annotations

from typing import Any
from ..chart_models import ChartFamily, ChartSpec
from ..design_tokens import SlideDesignTokens


class EChartsAdapter:
    """Transforms a canonical ChartSpec into an Apache ECharts options dictionary."""

    @classmethod
    def to_echarts_option(
        cls,
        spec: ChartSpec,
        tokens: SlideDesignTokens
    ) -> dict[str, Any]:
        """Maps renderer-neutral ChartSpec and slide tokens into an ECharts options payload."""
        palette = tokens.chart_palette
        font_family = tokens.font_body

        option: dict[str, Any] = {
            "backgroundColor": "transparent",
            "color": palette,
            "textStyle": {
                "fontFamily": font_family,
                "color": tokens.secondary_text
            },
            "animation": True,
            "animationDuration": 750,
            "tooltip": {
                "trigger": "item" if spec.family in (ChartFamily.DONUT, ChartFamily.PIE, ChartFamily.SANKEY) else "axis",
                "backgroundColor": tokens.surface,
                "borderColor": tokens.border,
                "textStyle": {"color": tokens.primary_text, "fontFamily": font_family, "fontSize": 13},
                "extraCssText": "box-shadow: 0 10px 25px rgba(0, 0, 0, 0.4); border-radius: 8px;"
            }
        }

        if spec.formatting.show_legend and len(spec.series) > 1:
            option["legend"] = {
                "bottom": "0%",
                "textStyle": {"color": tokens.secondary_text, "fontSize": 12},
                "icon": "circle"
            }

        # 1. PIE / DONUT
        if spec.family in (ChartFamily.DONUT, ChartFamily.PIE):
            is_donut = spec.family == ChartFamily.DONUT
            radius_cfg = ["50%", "75%"] if is_donut else ["0%", "75%"]
            pie_data = []
            if spec.series:
                s_data = spec.series[0].data
                for idx, val in enumerate(s_data):
                    cat_name = spec.categories[idx] if idx < len(spec.categories) else f"Cat {idx + 1}"
                    pie_data.append({"name": str(cat_name), "value": val})

            option["series"] = [{
                "type": "pie",
                "radius": radius_cfg,
                "center": ["50%", "50%"],
                "avoidLabelOverlap": True,
                "itemStyle": {"borderRadius": 6, "borderColor": tokens.background, "borderWidth": 2},
                "label": {
                    "show": True,
                    "color": tokens.primary_text,
                    "formatter": "{b}: {d}%"
                },
                "data": pie_data
            }]
            return option

        # 2. RADAR
        elif spec.family == ChartFamily.RADAR:
            indicators = [{"name": str(c), "max": 100} for c in spec.categories]
            option["radar"] = {
                "indicator": indicators,
                "splitArea": {"show": False},
                "splitLine": {"lineStyle": {"color": tokens.grid}},
                "axisLine": {"lineStyle": {"color": tokens.grid}},
                "axisName": {"color": tokens.secondary_text}
            }
            option["series"] = [{
                "type": "radar",
                "data": [
                    {"value": s.data, "name": s.name}
                    for s in spec.series
                ]
            }]
            return option

        # 3. SANKEY
        elif spec.family == ChartFamily.SANKEY:
            option["series"] = [{
                "type": "sankey",
                "layout": "none",
                "data": spec.extra_options.get("nodes", []),
                "links": spec.extra_options.get("links", []),
                "lineStyle": {"color": "gradient", "curveness": 0.5},
                "label": {"color": tokens.primary_text}
            }]
            return option

        # 4. TREEMAP
        elif spec.family == ChartFamily.TREEMAP:
            treemap_data = []
            if spec.series:
                for idx, val in enumerate(spec.series[0].data):
                    cat_name = spec.categories[idx] if idx < len(spec.categories) else f"Item {idx + 1}"
                    treemap_data.append({"name": str(cat_name), "value": val})
            option["series"] = [{
                "type": "treemap",
                "data": treemap_data,
                "breadcrumb": {"show": False},
                "label": {"color": "#FFFFFF", "fontSize": 14}
            }]
            return option

        # 5. CARTESIAN (Bar, Line, Area, Scatter, Waterfall)
        is_horizontal = spec.family == ChartFamily.BAR_HORIZONTAL
        is_stacked = spec.family in (ChartFamily.BAR_STACKED,)

        grid_cfg = {"left": "3%", "right": "4%", "bottom": "10%", "top": "12%", "containLabel": True}
        option["grid"] = grid_cfg

        category_axis = {
            "type": "category",
            "data": [str(c) for c in spec.categories],
            "axisLine": {"lineStyle": {"color": tokens.border}},
            "axisLabel": {"color": tokens.secondary_text, "fontSize": 12},
            "axisTick": {"show": False}
        }
        value_axis = {
            "type": "value",
            "splitLine": {"lineStyle": {"color": tokens.grid}},
            "axisLabel": {"color": tokens.muted_text, "fontSize": 11}
        }

        if is_horizontal:
            option["xAxis"] = value_axis
            option["yAxis"] = category_axis
        else:
            option["xAxis"] = category_axis
            option["yAxis"] = value_axis

        # Map Series
        series_configs = []
        for idx, s in enumerate(spec.series):
            s_type = "line" if "line" in spec.family.value or "area" in spec.family.value else "bar"
            if spec.family == ChartFamily.SCATTER:
                s_type = "scatter"

            s_cfg: dict[str, Any] = {
                "name": s.name,
                "type": s_type,
                "data": s.data,
            }
            if is_stacked or s.stack:
                s_cfg["stack"] = s.stack or "total"

            if s_type == "bar":
                s_cfg["itemStyle"] = {"borderRadius": [4, 4, 0, 0] if not is_horizontal else [0, 4, 4, 0]}
            elif s_type == "line":
                s_cfg["smooth"] = s.smooth
                s_cfg["lineStyle"] = {"width": 3}
                if spec.family == ChartFamily.AREA or s.area_style:
                    s_cfg["areaStyle"] = {"opacity": 0.25}

            series_configs.append(s_cfg)

        option["series"] = series_configs
        return option
