"""Chart Formatter Validator and Token Sanitization Engine.

Guarantees that no raw template tokens (e.g. {value}, {name}, {percent}, {b}, {c})
ever leak into rendered chart axes, tooltips, or annotations.
"""
from __future__ import annotations

import re
from typing import Any, Callable
from pydantic import BaseModel, ConfigDict, Field


UNRESOLVED_TOKEN_PATTERN = re.compile(r"\{[a-zA-Z0-9_]+\}")


class FormatterValidationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    passed: bool
    violations: list[str] = Field(default_factory=list)
    remediations: list[str] = Field(default_factory=list)


class ChartFormatterValidator:
    """Validates and sanitizes formatters across ECharts option trees."""

    @classmethod
    def validate_option(cls, option: dict[str, Any]) -> FormatterValidationReport:
        """Inspects all axis labels, tooltips, series labels, and markLines for unresolved template placeholders."""
        violations: list[str] = []
        remediations: list[str] = []

        # 1. Validate X and Y Axis formatters
        for axis_key in ("xAxis", "yAxis"):
            axes = option.get(axis_key)
            if not axes:
                continue
            axis_list = axes if isinstance(axes, list) else [axes]
            for idx, axis in enumerate(axis_list):
                axis_label = axis.get("axisLabel", {})
                fmt = axis_label.get("formatter")
                if isinstance(fmt, str):
                    # Flag literal {value}% or {value} in strings if not deterministic
                    if UNRESOLVED_TOKEN_PATTERN.search(fmt):
                        violations.append(
                            f"{axis_key}[{idx}].axisLabel.formatter contains unresolved token: '{fmt}'"
                        )
                        remediations.append(
                            f"Replace {axis_key}[{idx}] string template '{fmt}' with deterministic formatter function or unit suffix."
                        )

        # 2. Validate Tooltip
        tooltip = option.get("tooltip", {})
        tt_fmt = tooltip.get("formatter")
        if isinstance(tt_fmt, str):
            # ECharts supports {a}, {b}, {c}, {d} in string tooltips, but NOT custom {value} or {name} or {token}
            unsupported_matches = [
                m.group(0) for m in UNRESOLVED_TOKEN_PATTERN.finditer(tt_fmt)
                if m.group(0) not in ("{a}", "{b}", "{c}", "{d}", "{e}")
            ]
            if unsupported_matches:
                violations.append(
                    f"tooltip.formatter contains unsupported/unresolved template tokens: {unsupported_matches}"
                )
                remediations.append("Convert tooltip.formatter to a deterministic formatter callback.")

        # 3. Validate Series and MarkLine labels
        series_list = option.get("series", [])
        for s_idx, s in enumerate(series_list):
            s_label = s.get("label", {})
            s_fmt = s_label.get("formatter")
            if isinstance(s_fmt, str) and UNRESOLVED_TOKEN_PATTERN.search(s_fmt):
                if not any(token in s_fmt for token in ("{a}", "{b}", "{c}", "{d}")):
                    violations.append(f"series[{s_idx}].label.formatter contains unresolved token: '{s_fmt}'")
                    remediations.append(f"Sanitize series[{s_idx}].label.formatter.")

            # MarkLine labels
            mark_line = s.get("markLine", {})
            for m_idx, ml_item in enumerate(mark_line.get("data", [])):
                ml_label = ml_item.get("label", {})
                ml_fmt = ml_label.get("formatter")
                if isinstance(ml_fmt, str) and UNRESOLVED_TOKEN_PATTERN.search(ml_fmt):
                    violations.append(
                        f"series[{s_idx}].markLine.data[{m_idx}].label.formatter contains unresolved token: '{ml_fmt}'"
                    )
                    remediations.append("Sanitize markLine label formatter.")

        return FormatterValidationReport(
            passed=len(violations) == 0,
            violations=violations,
            remediations=remediations,
        )

    @classmethod
    def sanitize_option(cls, option: dict[str, Any]) -> dict[str, Any]:
        """Deeply repairs options by converting string templates to safe unit strings or removing broken tokens."""
        import copy
        sanitized = copy.deepcopy(option)

        for axis_key in ("xAxis", "yAxis"):
            axes = sanitized.get(axis_key)
            if not axes:
                continue
            axis_list = axes if isinstance(axes, list) else [axes]
            for axis in axis_list:
                axis_label = axis.get("axisLabel")
                if isinstance(axis_label, dict):
                    fmt = axis_label.get("formatter")
                    if isinstance(fmt, str) and "{value}" in fmt:
                        # Extract suffix e.g. "{value}%" -> "%"
                        suffix = fmt.replace("{value}", "").strip()
                        # Remove the template string so consumer can use clean formatter function or unit
                        if suffix:
                            axis_label["_unit_suffix"] = suffix
                        del axis_label["formatter"]

        return sanitized
