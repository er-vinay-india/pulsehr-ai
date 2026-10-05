"""Declarative Visualization Compiler and Visual QA Guard.

Transforms high-level analytical intents into accessible, overflow-safe
Apache ECharts options:
1. Translates VisualIntent (e.g. compare_ranked_categories, trend_forecast_cone)
   into hardened ECharts options.
2. Implements deterministic Visual QA checks:
   - Mandatory X/Y axis presence
   - Minimum font size guards (>= 11px)
   - Safe grid margins to prevent label truncation
   - Contrast-compliant WCAG palettes
   - Reference benchmark line injection
"""
from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class VisualIntent(BaseModel):
    """High-level visual goal selected by the AI story planner or engine."""
    model_config = ConfigDict(extra="forbid")

    intent: Literal[
        "compare_ranked_categories",
        "trend_forecast_cone",
        "disparity_matrix",
        "distribution_spread",
        "composition_donut",
    ]
    metric_name: str
    dimension_name: str | None = None
    unit: str = ""
    priority: Literal["hero", "secondary", "tertiary"] = "secondary"
    purpose: str = ""
    benchmark_value: float | None = None
    highlight_categories: list[str] = Field(default_factory=list)


from .theme_validator import (
    GateAuditResult,
    ThemeIntegrityValidator,
    VisualQAResult,
)


class VisualCompiler:
    """Compiles declarative visual intents into safe ECharts options."""

    PALETTE = [
        "var(--color-brand-primary, #183B56)",
        "var(--color-brand-secondary, #075443)",
        "var(--color-brand-blue, #234E70)",
        "var(--color-gold, #65470C)",
        "var(--color-error, #8E1938)",
        "var(--color-violet, #513B72)",
    ]

    @classmethod
    def compile_ranked_categories(
        cls,
        categories: list[str],
        values: list[float],
        intent: VisualIntent,
    ) -> dict[str, Any]:
        """Compiles a clean horizontal ranked bar chart with optional benchmark line."""
        # Pair and sort descending
        pairs = sorted(zip(categories, values), key=lambda x: x[1], reverse=False)  # Ascending for horizontal Y-axis
        sorted_cats = [p[0] for p in pairs]
        sorted_vals = [round(p[1], 2) for p in pairs]

        series_data = []
        for cat, val in zip(sorted_cats, sorted_vals):
            is_highlight = cat in intent.highlight_categories
            item: dict[str, Any] = {"value": val}
            if is_highlight:
                item["itemStyle"] = {"color": "var(--color-error, #8E1938)"}
            series_data.append(item)

        option: dict[str, Any] = {
            "color": cls.PALETTE,
            "tooltip": {
                "trigger": "axis",
                "axisPointer": {"type": "shadow"},
                "backgroundColor": "var(--chart-tooltip-bg, #FFFFFF)",
                "textStyle": {"color": "var(--chart-tooltip-text, #172B3A)", "fontSize": 12},
                "formatter": f"{{b}}: {{c}} {intent.unit}".strip(),
            },
            "grid": {
                "left": "15%",
                "right": "8%",
                "top": "12%",
                "bottom": "10%",
                "containLabel": True,
            },
            "xAxis": {
                "type": "value",
                "name": intent.unit,
                "nameTextStyle": {"fontSize": 11, "color": "var(--chart-title, #172B3A)"},
                "axisLabel": {"fontSize": 11, "color": "var(--chart-text, #334B57)"},
                "splitLine": {"lineStyle": {"type": "dashed", "color": "var(--chart-split-line, rgba(23, 43, 58, 0.1))"}},
            },
            "yAxis": {
                "type": "category",
                "data": sorted_cats,
                "axisLabel": {
                    "fontSize": 11,
                    "color": "var(--chart-text, #334B57)",
                    "formatter": "{value}",
                },
                "axisTick": {"alignWithLabel": True},
            },
            "series": [
                {
                    "name": intent.metric_name,
                    "type": "bar",
                    "data": series_data,
                    "barMaxWidth": 24,
                    "itemStyle": {"borderRadius": [0, 4, 4, 0], "color": "var(--color-brand-primary, #183B56)"},
                    "label": {
                        "show": True,
                        "position": "right",
                        "fontSize": 11,
                        "color": "var(--chart-text, #334B57)",
                    },
                }
            ],
        }

        # Add benchmark reference line if present
        if intent.benchmark_value is not None:
            option["series"][0]["markLine"] = {
                "symbol": ["none", "none"],
                "data": [
                    {
                        "xAxis": intent.benchmark_value,
                        "name": "Benchmark",
                        "label": {
                            "formatter": f"Benchmark: {intent.benchmark_value:.1f}",
                            "color": "var(--color-success, #075443)",
                            "fontSize": 11,
                        },
                        "lineStyle": {"color": "var(--color-success, #075443)", "type": "dashed", "width": 2},
                    }
                ],
            }

        return option

    @classmethod
    def compile_trend_forecast_cone(
        cls,
        history_x: list[str],
        history_y: list[float],
        forecast_x: list[str],
        forecast_y: list[float],
        lower_bounds: list[float],
        upper_bounds: list[float],
        intent: VisualIntent,
    ) -> dict[str, Any]:
        """Compiles a time series line chart with a shaded prediction interval cone."""
        all_x = list(history_x) + list(forecast_x)
        hist_series = [round(y, 2) for y in history_y] + [None] * len(forecast_x)
        
        # Connect last historical point to first forecast point
        last_hist = history_y[-1] if history_y else 0.0
        fc_series = [None] * (len(history_x) - 1) + [round(last_hist, 2)] + [round(y, 2) for y in forecast_y]
        
        # Upper and lower cone series (relative band)
        band_base = [None] * (len(history_x) - 1) + [round(last_hist, 2)] + [round(lb, 2) for lb in lower_bounds]
        band_diff = [None] * (len(history_x) - 1) + [0.0] + [round(ub - lb, 2) for ub, lb in zip(upper_bounds, lower_bounds)]

        option: dict[str, Any] = {
            "tooltip": {
                "trigger": "axis",
                "backgroundColor": "var(--chart-tooltip-bg, #FFFFFF)",
                "textStyle": {"color": "var(--chart-tooltip-text, #172B3A)", "fontSize": 12},
            },
            "legend": {
                "data": ["Observed History", "Projected Trend", "80% Confidence Cone"],
                "textStyle": {"color": "var(--chart-text, #334B57)", "fontSize": 11},
                "top": "2%",
            },
            "grid": {
                "left": "10%",
                "right": "8%",
                "top": "16%",
                "bottom": "12%",
                "containLabel": True,
            },
            "xAxis": {
                "type": "category",
                "data": all_x,
                "axisLabel": {"fontSize": 11, "color": "var(--chart-text, #334B57)"},
            },
            "yAxis": {
                "type": "value",
                "name": intent.unit,
                "axisLabel": {"fontSize": 11, "color": "var(--chart-text, #334B57)"},
                "splitLine": {"lineStyle": {"type": "dashed", "color": "var(--chart-split-line, rgba(23, 43, 58, 0.1))"}},
            },
            "series": [
                {
                    "name": "Observed History",
                    "type": "line",
                    "data": hist_series,
                    "itemStyle": {"color": "var(--color-brand-primary, #183B56)"},
                    "lineStyle": {"width": 2.5},
                    "symbol": "circle",
                    "symbolSize": 6,
                },
                {
                    "name": "Projected Trend",
                    "type": "line",
                    "data": fc_series,
                    "itemStyle": {"color": "var(--color-info, #234E70)"},
                    "lineStyle": {"width": 2, "type": "dashed"},
                    "symbol": "emptyCircle",
                    "symbolSize": 5,
                },
                {
                    "name": "Confidence Lower",
                    "type": "line",
                    "data": band_base,
                    "lineStyle": {"opacity": 0},
                    "stack": "confidence-band",
                    "symbol": "none",
                },
                {
                    "name": "80% Confidence Cone",
                    "type": "line",
                    "data": band_diff,
                    "lineStyle": {"opacity": 0},
                    "areaStyle": {"color": "var(--color-bg-soft-blue, rgba(35, 78, 112, 0.18))"},
                    "stack": "confidence-band",
                    "symbol": "none",
                },
            ],
        }
        return option

    @staticmethod
    def audit_visual_qa(option: dict[str, Any]) -> VisualQAResult:
        """Audits an ECharts option dictionary against the Three Permanent Visual Gates."""
        return ThemeIntegrityValidator.evaluate_three_visual_gates(option)
