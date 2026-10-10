"""Adaptive Chart Layout Engine.

Calculates deterministic, presentation-safe geometry before rendering:
- Dynamic chart height based on category count and header/axis overhead
- Grid margins based on longest label length, title lines, and legend items
- Plot area ratio enforcement (>= 0.55)
- Collision-free annotation placement candidates
"""
from __future__ import annotations

import math
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class LayoutPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    grid_left: int
    grid_right: int
    grid_top: int
    grid_bottom: int
    chart_height: int
    label_rotation: int
    label_interval: int | str
    legend_position: Literal["top", "bottom", "none"]
    value_label_position: Literal["top", "right", "inside", "none"]
    annotation_position: Literal["top", "insideEndTop", "end", "none"]
    truncate_strategy: str
    plot_area_ratio: float
    safety_score: float = 1.0
    tick_spacing_px: float = 0.0
    tick_label_width_px: float = 0.0
    readability_passed: bool = True
    recommended_chart_type: str = ""


class AdaptiveChartLayoutEngine:
    """Plans optimal layout dimensions and collision-avoidance geometry."""

    MIN_HORIZONTAL_BAR_HEIGHT = 260
    ROW_HEIGHT_PX = 38
    HEADER_OVERHEAD_PX = 50
    AXIS_OVERHEAD_PX = 45
    MIN_PLOT_AREA_RATIO = 0.55

    @classmethod
    def plan(
        cls,
        chart_type: str,
        container_width: float = 800.0,
        container_height: float = 350.0,
        category_count: int = 5,
        longest_label_chars: int = 10,
        series_count: int = 1,
        title_lines: int = 1,
        legend_items: int = 0,
        annotations: list[dict[str, Any]] | None = None,
        is_mobile: bool = False,
    ) -> LayoutPlan:
        """Determines precise layout parameters ensuring presentation safety."""
        clean_type = chart_type.lower()
        annotations = annotations or []

        # 1. Dynamic Chart Height calculation
        if clean_type in ("bar", "horizontal_bar", "horizontalbar", "ranked_bar"):
            computed_height = (
                cls.HEADER_OVERHEAD_PX
                + (category_count * cls.ROW_HEIGHT_PX)
                + cls.AXIS_OVERHEAD_PX
            )
            # Enforce minimum height and scale dynamically
            chart_height = max(cls.MIN_HORIZONTAL_BAR_HEIGHT, computed_height)
            if category_count > 10:
                chart_height = min(chart_height, 650)
        elif clean_type in ("line", "area", "grouped_bar", "column"):
            chart_height = max(int(container_height), 280)
            if is_mobile:
                chart_height = max(chart_height, 300)
        else:
            chart_height = int(container_height)

        # 2. Reserve Left Margin (Y-axis label accommodation)
        if clean_type in ("bar", "horizontal_bar", "horizontalbar", "ranked_bar"):
            # ~8-9px per character for standard typography + 24px padding
            char_width_px = 7.5
            calc_left = int(math.ceil(longest_label_chars * char_width_px)) + 28
            grid_left = max(70, min(calc_left, 240))
            grid_right = 40 if not annotations else 55
        else:
            # Value axis on Y
            grid_left = 50 if container_width > 500 else 42
            grid_right = 24

        # 3. Top Margin (Title lines & Annotations)
        grid_top = 28 + (title_lines * 16)
        if annotations:
            grid_top += 12

        # 4. Bottom Margin (X-axis labels & Legend)
        grid_bottom = 36
        label_rotation = 0
        label_interval: int | str = 0

        if clean_type in ("column", "grouped_bar", "line"):
            # If categories are dense or on mobile, rotate labels
            available_cat_width = container_width / max(1, category_count)
            if is_mobile or available_cat_width < (longest_label_chars * 7):
                label_rotation = 35 if longest_label_chars <= 12 else 45
                grid_bottom += 28

        # 5. Legend Intelligence
        if series_count <= 1:
            legend_position = "none"  # Redundant for single-series
        elif is_mobile or (series_count >= 2 and (container_height <= 280 or chart_height <= 280)):
            # Shallow container with multi-series: move legend to top so bottom plot is not cramped
            legend_position = "top"
            grid_top += 18
            grid_bottom += 8
        else:
            legend_position = "bottom"
            grid_bottom += 24

        # 6. Annotation Collision Avoidance
        # If reference line exists, pick placement that avoids bar endpoints
        annotation_position: Literal["top", "insideEndTop", "end", "none"] = "none"
        if annotations:
            # Avoid placing directly on top of bar ends
            annotation_position = "insideEndTop"

        # 7. Value Label Position
        if clean_type in ("bar", "horizontal_bar", "ranked_bar"):
            value_label_position = "right"
        elif clean_type in ("column", "grouped_bar"):
            value_label_position = "top"
        else:
            value_label_position = "none"

        # 8. Plot Area Ratio verification
        plot_w = container_width - grid_left - grid_right
        plot_h = chart_height - grid_top - grid_bottom
        total_area = container_width * chart_height
        plot_area = max(0.0, plot_w * plot_h)
        ratio = round(plot_area / total_area, 3) if total_area > 0 else 0.0

        # If plot area ratio is below threshold, compact margins
        if ratio < cls.MIN_PLOT_AREA_RATIO:
            grid_top = max(24, grid_top - 10)
            grid_bottom = max(28, grid_bottom - 10)
            plot_h = chart_height - grid_top - grid_bottom
            plot_area = max(0.0, plot_w * plot_h)
            ratio = round(plot_area / total_area, 3)

        # 9. Readability Integrity Metrics
        tick_spacing = cls.estimate_tick_spacing(container_width, grid_left, grid_right, category_count)
        label_width = cls.estimate_label_width(longest_label_chars)
        readability_passed = tick_spacing >= (label_width + 12.0)

        should_switch = cls.should_switch_to_line_chart(
            clean_type, category_count, series_count, container_width, longest_label_chars
        )
        recommended_type = "line" if should_switch else clean_type

        return LayoutPlan(
            grid_left=grid_left,
            grid_right=grid_right,
            grid_top=grid_top,
            grid_bottom=grid_bottom,
            chart_height=chart_height,
            label_rotation=label_rotation,
            label_interval=label_interval,
            legend_position=legend_position,
            value_label_position=value_label_position,
            annotation_position=annotation_position,
            truncate_strategy="tooltip_preserved",
            plot_area_ratio=ratio,
            safety_score=1.0 if ratio >= cls.MIN_PLOT_AREA_RATIO else 0.85,
            tick_spacing_px=round(tick_spacing, 2),
            tick_label_width_px=round(label_width, 2),
            readability_passed=readability_passed,
            recommended_chart_type=recommended_type,
        )

    @classmethod
    def compact_period_label(cls, label: str) -> str:
        """Deterministically compacts verbose period labels into executive format."""
        import re
        clean = str(label).strip()
        m = re.search(r"(\d+)(?:st|nd|rd|th)?\s*(?:to|–|-)\s*(\d+)(?:st|nd|rd|th)?\s*(?:July|Jul)?", clean, re.I)
        if m:
            start_d, end_d = m.group(1), m.group(2)
            return f"{start_d}–{end_d} Jul"
        clean = re.sub(r"(\d+)(?:st|nd|rd|th)", r"\1", clean)
        clean = re.sub(r"\bJuly\b", "Jul", clean, flags=re.I)
        return clean

    @classmethod
    def compact_categories(cls, categories: list[str]) -> list[str]:
        """Maps an array of period category strings to compact form."""
        return [cls.compact_period_label(c) for c in categories]

    @classmethod
    def estimate_tick_spacing(
        cls, container_width: float, grid_left: float, grid_right: float, category_count: int
    ) -> float:
        """Computes horizontal space available per tick category."""
        plot_w = max(0.0, container_width - grid_left - grid_right)
        return plot_w / max(1, category_count)

    @classmethod
    def estimate_label_width(cls, longest_label_chars: int, font_size: float = 11.0) -> float:
        """Estimates pixel width occupied by category tick label text."""
        return longest_label_chars * (font_size * 0.68)

    @classmethod
    def should_switch_to_line_chart(
        cls,
        chart_type: str,
        category_count: int,
        series_count: int,
        container_width: float = 800.0,
        longest_label_chars: int = 10,
    ) -> bool:
        """Determines if a dense multi-series categorical chart should switch to a line chart."""
        clean = chart_type.lower()
        if clean in ("grouped_bar", "column", "bar") and series_count >= 2:
            tick_spacing = (container_width - 90) / max(1, category_count)
            req_clearance = (longest_label_chars * 7.5) + 16
            if tick_spacing < req_clearance or container_width < 500:
                return True
        return False
