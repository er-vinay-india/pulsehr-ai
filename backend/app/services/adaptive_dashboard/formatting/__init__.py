"""
Formatting and Presentation Utilities Package (Phase G5.1).
"""
from __future__ import annotations

from .metric_formatter import (
    MetricFormatter,
    calendar_month_range,
    compute_focused_duration_scale,
    compute_numeric_focused_scale,
    compute_source_snapshot,
    format_compact_number,
    format_currency_short,
    format_duration_short,
    format_month_label,
    format_month_tick,
    format_percentage,
    linear_quantile,
    parse_clock_interval,
    parse_date_range,
    parse_date_safe,
    parse_iso_date,
)
from .presentation_labels import (
    clean_metric_name,
    safe_title,
    sanitize_axis_label,
)

__all__ = [
    "MetricFormatter",
    "compute_source_snapshot",
    "parse_date_safe",
    "parse_iso_date",
    "parse_date_range",
    "format_currency_short",
    "format_percentage",
    "format_compact_number",
    "format_duration_short",
    "format_month_label",
    "format_month_tick",
    "calendar_month_range",
    "parse_clock_interval",
    "linear_quantile",
    "compute_focused_duration_scale",
    "compute_numeric_focused_scale",
    "clean_metric_name",
    "safe_title",
    "sanitize_axis_label",
]
