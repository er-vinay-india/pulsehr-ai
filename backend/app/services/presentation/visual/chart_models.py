"""Canonical Chart Specification and Guardrail Contracts for Phase 4.

Defines a renderer-neutral chart model independent of Apache ECharts or PPTX shapes,
with explicit family enumerations, series definitions, and guardrail validations.
"""

from __future__ import annotations

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class ChartFamily(str, Enum):
    """Canonical chart families supported across the presentation rendering engine."""
    BAR_VERTICAL = "bar_vertical"
    BAR_HORIZONTAL = "bar_horizontal"
    BAR_GROUPED = "bar_grouped"
    BAR_STACKED = "bar_stacked"
    LINE = "line"
    LINE_MULTI = "line_multi"
    AREA = "area"
    PIE = "pie"
    DONUT = "donut"
    SCATTER = "scatter"
    BUBBLE = "bubble"
    HEATMAP = "heatmap"
    RADAR = "radar"
    WATERFALL = "waterfall"
    FUNNEL = "funnel"
    GAUGE = "gauge"
    TREEMAP = "treemap"
    SUNBURST = "sunburst"
    SANKEY = "sankey"
    CANDLESTICK = "candlestick"
    BOXPLOT = "boxplot"
    HISTOGRAM = "histogram"
    GRAPH_NETWORK = "graph_network"
    MIXED_BAR_LINE = "mixed_bar_line"


class ChartSeries(BaseModel):
    """An individual series of data within a ChartSpec."""
    name: str
    data: list[Any] = Field(default_factory=list)
    type: str | None = None
    color: str | None = None
    stack: str | None = None
    smooth: bool = True
    area_style: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChartAnnotation(BaseModel):
    """Visual benchmark, reference target, or alert annotation on a chart."""
    type: str = "line"  # line | point | band
    label: str
    value: float | None = None
    y_value: float | None = None
    color: str | None = None


class ChartFormatting(BaseModel):
    """Display rules, unit indicators, and formatting for values and axes."""
    value_format: str = "standard"  # standard | percentage | currency | compact | integer
    sort: str = "none"              # none | ascending | descending
    unit: str = ""
    prefix: str = ""
    suffix: str = ""
    show_legend: bool = True
    show_data_labels: bool = True
    axis_label_rotation: int = 0


class ChartGuardrailCheck(BaseModel):
    """Validation report detailing whether a chart configuration obeys statistical and visual best practices."""
    passed: bool = True
    violations: list[str] = Field(default_factory=list)
    fallback_family: ChartFamily | None = None
    reason: str = ""


class ChartSpec(BaseModel):
    """The canonical, renderer-neutral chart specification contract."""
    chart_id: str = ""
    family: ChartFamily
    variant: str = "standard"
    purpose: str = "comparison"
    title: str = ""
    subtitle: str = ""
    categories: list[str] = Field(default_factory=list)
    series: list[ChartSeries] = Field(default_factory=list)
    annotations: list[ChartAnnotation] = Field(default_factory=list)
    formatting: ChartFormatting = Field(default_factory=ChartFormatting)
    source_refs: list[str] = Field(default_factory=list)
    selection_reason: str = ""
    extra_options: dict[str, Any] = Field(default_factory=dict)

    def validate_guardrails(self) -> ChartGuardrailCheck:
        """Evaluates strict guardrails ensuring semantic and statistical appropriateness."""
        violations = []
        fallback = None
        reason = ""

        # 1. Donut / Pie guardrails: part-to-whole only, max 5 major categories
        if self.family in (ChartFamily.DONUT, ChartFamily.PIE):
            num_cats = len(self.categories) if self.categories else (len(self.series[0].data) if self.series else 0)
            if num_cats > 5:
                violations.append(f"Donut chart has {num_cats} categories (exceeds maximum recommendation of 5).")
                fallback = ChartFamily.BAR_HORIZONTAL
                reason = f"Replaced {self.family.value} with horizontal bar because {num_cats} categories exceeds readable radial slice threshold."

        # 2. Heatmap guardrails: requires two dimensions + values
        elif self.family == ChartFamily.HEATMAP:
            x_dim = self.extra_options.get("x_categories") or self.categories
            y_dim = self.extra_options.get("y_categories")
            if not x_dim or not y_dim or len(x_dim) < 2 or len(y_dim) < 2:
                violations.append("Heatmap requires at least two distinct categorical dimensions (X and Y axes).")
                fallback = ChartFamily.BAR_GROUPED
                reason = "Heatmap downgraded to grouped bar due to insufficient orthogonal category dimensions."

        # 3. Candlestick guardrails: requires 4-tuple [open, close, low, high] (OHLC)
        elif self.family == ChartFamily.CANDLESTICK:
            has_ohlc = False
            if self.series and self.series[0].data:
                first_item = self.series[0].data[0]
                if isinstance(first_item, (list, tuple)) and len(first_item) >= 4:
                    has_ohlc = True
            if not has_ohlc:
                violations.append("Candlestick chart requires structured OHLC 4-tuple values [open, close, low, high].")
                fallback = ChartFamily.LINE
                reason = "Candlestick downgraded to line chart due to absence of OHLC multi-point structure."

        # 4. Sankey guardrails: requires nodes (sources/targets) and weighted links
        elif self.family == ChartFamily.SANKEY:
            nodes = self.extra_options.get("nodes") or []
            links = self.extra_options.get("links") or []
            if not nodes or not links or not any(l.get("value", 0) > 0 for l in links if isinstance(l, dict)):
                violations.append("Sankey diagram requires structured nodes and positive weighted links.")
                fallback = ChartFamily.BAR_HORIZONTAL
                reason = "Sankey downgraded to horizontal bar due to unweighted or missing directed flow links."

        # 5. Scatter guardrails: requires 2 numerical dimensions [x, y]
        elif self.family == ChartFamily.SCATTER:
            has_xy = False
            if self.series and self.series[0].data:
                first_item = self.series[0].data[0]
                if isinstance(first_item, (list, tuple)) and len(first_item) >= 2:
                    has_xy = True
                elif isinstance(first_item, dict) and "x" in first_item and "y" in first_item:
                    has_xy = True
            if not has_xy and len(self.series) < 2:
                violations.append("Scatter plot requires paired numerical [X, Y] coordinates.")
                fallback = ChartFamily.BAR_VERTICAL
                reason = "Scatter plot downgraded to vertical bar due to lack of bivariate coordinates."

        # 6. Bubble guardrails: requires 3 numerical dimensions [x, y, size]
        elif self.family == ChartFamily.BUBBLE:
            has_xyz = False
            if self.series and self.series[0].data:
                first_item = self.series[0].data[0]
                if isinstance(first_item, (list, tuple)) and len(first_item) >= 3:
                    has_xyz = True
                elif isinstance(first_item, dict) and "x" in first_item and "y" in first_item and "size" in first_item:
                    has_xyz = True
            if not has_xyz:
                violations.append("Bubble chart requires 3 numerical variables [X, Y, size].")
                fallback = ChartFamily.SCATTER
                reason = "Bubble chart downgraded to scatter plot because third magnitude variable is missing."

        # 7. Radar guardrails: requires 3 to 8 metrics
        elif self.family == ChartFamily.RADAR:
            num_indicators = len(self.categories)
            if num_indicators < 3 or num_indicators > 8:
                violations.append(f"Radar chart has {num_indicators} dimensions (recommended range is 3 to 8).")
                fallback = ChartFamily.BAR_GROUPED
                reason = f"Radar chart downgraded to grouped bar because {num_indicators} dimensions causes angular clutter."

        # 8. Waterfall guardrails: requires delta/step decomposition
        elif self.family == ChartFamily.WATERFALL:
            if not self.series or len(self.series[0].data) < 2:
                violations.append("Waterfall chart requires multiple sequential step contributions.")
                fallback = ChartFamily.BAR_VERTICAL
                reason = "Waterfall chart downgraded to vertical bar due to insufficient delta step data."

        is_passed = len(violations) == 0
        return ChartGuardrailCheck(
            passed=is_passed,
            violations=violations,
            fallback_family=fallback,
            reason=reason or ("All guardrails satisfied." if is_passed else "Guardrail violations detected.")
        )
