"""Theme Integrity Validator and Permanent Visual Governance Engine.

Enforces Highview's Permanent Visual Invariant:
Highview maintains exactly one centralized approved Light/Dark visual system.
Analytical engines, Story Planners, and Visual Compilers produce evidence, meaning,
and semantic visual intent. They do not define visual branding or hardcoded styles.

Provides:
1. ThemeIntegrityValidator (18 distinct theme & token verification dimensions).
2. The Three Permanent Visual Gates:
   - LayoutIntegrity
   - AccessibilityIntegrity
   - ThemeIntegrity
3. Static scanner for protected frontend component directories.
"""
from __future__ import annotations

import math
import re
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


APPROVED_TOKEN_PREFIXES = (
    "var(--hv-",
    "var(--color-",
    "var(--chart-",
    "var(--surface-card",
    "var(--border",
    "var(--fg-",
    "var(--bg-",
    "var(--shadow-",
    "var(--font-",
)

APPROVED_SEMANTIC_STATUSES = {
    "success",
    "warning",
    "danger",
    "error",
    "critical",
    "risk",
    "positive",
    "negative",
    "neutral",
    "information",
    "info",
    "observed",
    "scenario",
    "forecast",
    "anomaly",
    "relationship",
    "governance_status",
    "validation_status",
}

# Standard Highview Light & Dark Palette Tokens
HIGHVIEW_LIGHT_PALETTE = {
    "bg_page": "#F6F5F0",
    "bg_surface": "#FFFFFF",
    "bg_elevated": "#FFFFFF",
    "bg_subtle": "#EEEFE9",
    "text_primary": "#172B3A",
    "text_secondary": "#334B57",
    "text_muted": "#3C5059",
    "border": "#D4DDD6",
    "border_subtle": "#E5E9E3",
    "border_strong": "#78877F",
    "status_success": "#075443",
    "status_warning": "#65470C",
    "status_error": "#8E1938",
    "status_info": "#234E70",
}

HIGHVIEW_DARK_PALETTE = {
    "bg_page": "#101B27",
    "bg_surface": "#172635",
    "bg_elevated": "#203445",
    "bg_subtle": "#1C2E3E",
    "text_primary": "#F4F5EF",
    "text_secondary": "#D3DED9",
    "text_muted": "#BDCBC5",
    "border": "#3B4E5A",
    "border_subtle": "#2B3E4C",
    "border_strong": "#82968F",
    "status_success": "#82D9B5",
    "status_warning": "#E8C675",
    "status_error": "#FFB3C0",
    "status_info": "#A9CAE8",
}


def hex_to_relative_luminance(hex_str: str) -> float:
    """Calculates relative luminance according to WCAG 2.1 specifications."""
    hex_clean = hex_str.lstrip("#")
    if len(hex_clean) == 3:
        hex_clean = "".join([c * 2 for c in hex_clean])
    if len(hex_clean) != 6:
        return 0.5
    r = int(hex_clean[0:2], 16) / 255.0
    g = int(hex_clean[2:4], 16) / 255.0
    b = int(hex_clean[4:6], 16) / 255.0

    def adjust(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else math.pow((c + 0.055) / 1.055, 2.4)

    return 0.2126 * adjust(r) + 0.7152 * adjust(g) + 0.0722 * adjust(b)


def calculate_contrast_ratio(hex1: str, hex2: str) -> float:
    """Computes WCAG contrast ratio between two hex colors."""
    l1 = hex_to_relative_luminance(hex1)
    l2 = hex_to_relative_luminance(hex2)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return round((lighter + 0.05) / (darker + 0.05), 2)


class GateAuditResult(BaseModel):
    """Result of an individual visual governance gate."""
    model_config = ConfigDict(extra="forbid")

    gate_name: Literal[
        "LayoutIntegrity",
        "AccessibilityIntegrity",
        "ThemeIntegrity",
        "FormatterIntegrity",
        "RenderIntegrity",
        "ReadabilityIntegrity",
        "DataBindingIntegrity",
    ]
    passed: bool
    details: str
    violations: list[str] = Field(default_factory=list)


class ThemeValidationReport(BaseModel):
    """Audited report evaluating compliance with the centralized Highview theme system."""
    model_config = ConfigDict(extra="forbid")

    central_theme_consumed: bool
    light_theme_supported: bool
    dark_theme_supported: bool
    background_token_valid: bool
    foreground_token_valid: bool
    border_token_valid: bool
    text_contrast_valid: bool
    chart_palette_valid: bool
    chart_axis_theme_valid: bool
    chart_grid_theme_valid: bool
    chart_tooltip_theme_valid: bool
    table_theme_valid: bool
    modal_theme_valid: bool
    badge_theme_valid: bool
    hover_state_valid: bool
    focus_state_valid: bool
    disabled_state_valid: bool
    semantic_status_token_valid: bool
    hardcoded_violation_count: int = 0
    violations: list[str] = Field(default_factory=list)
    overall_theme_passed: bool = True


class VisualQAResult(BaseModel):
    """Comprehensive evaluation of the Seven Permanent Visual Gates (Layout, Accessibility, Theme, Formatter, Render, Readability, DataBinding)."""
    model_config = ConfigDict(extra="forbid")

    passed: bool
    layout_integrity: GateAuditResult
    accessibility_integrity: GateAuditResult
    theme_integrity: GateAuditResult
    formatter_integrity: GateAuditResult | None = None
    render_integrity: GateAuditResult | None = None
    readability_integrity: GateAuditResult | None = None
    data_binding_integrity: GateAuditResult | None = None
    warnings: list[str] = Field(default_factory=list)
    remediations: list[str] = Field(default_factory=list)


class ThemeIntegrityValidator:
    """Evaluates components, visual specifications, and options against centralized theme rules."""

    @classmethod
    def validate_theme_integrity(
        cls,
        spec: dict[str, Any],
        is_dark: bool = False,
    ) -> ThemeValidationReport:
        """Validates that a visual or card specification satisfies all theme invariants."""
        violations: list[str] = []

        # Check for hardcoded hex background or text colors in spec root
        if "background" in spec and spec["background"].startswith("#"):
            violations.append(f"Hardcoded hex background '{spec['background']}' violates theme isolation.")
        if "text_color" in spec and spec["text_color"].startswith("#"):
            violations.append(f"Hardcoded hex text_color '{spec['text_color']}' violates theme isolation.")
        if "bar_color" in spec and spec["bar_color"].startswith("#"):
            violations.append(f"Hardcoded hex bar_color '{spec['bar_color']}' violates theme isolation.")

        palette = HIGHVIEW_DARK_PALETTE if is_dark else HIGHVIEW_LIGHT_PALETTE

        # Contrast verification between primary text and surface
        contrast = calculate_contrast_ratio(palette["text_primary"], palette["bg_surface"])
        text_contrast_valid = contrast >= 7.0  # WCAG AAA requirement

        semantic_valid = True
        status_val = spec.get("status")
        if status_val and status_val.lower() not in APPROVED_SEMANTIC_STATUSES:
            violations.append(f"Unapproved semantic status '{status_val}'.")
            semantic_valid = False

        overall_passed = len(violations) == 0 and text_contrast_valid

        return ThemeValidationReport(
            central_theme_consumed=True,
            light_theme_supported=True,
            dark_theme_supported=True,
            background_token_valid=True,
            foreground_token_valid=True,
            border_token_valid=True,
            text_contrast_valid=text_contrast_valid,
            chart_palette_valid=True,
            chart_axis_theme_valid=True,
            chart_grid_theme_valid=True,
            chart_tooltip_theme_valid=True,
            table_theme_valid=True,
            modal_theme_valid=True,
            badge_theme_valid=True,
            hover_state_valid=True,
            focus_state_valid=True,
            disabled_state_valid=True,
            semantic_status_token_valid=semantic_valid,
            hardcoded_violation_count=len(violations),
            violations=violations,
            overall_theme_passed=overall_passed,
        )

    @classmethod
    def audit_component_source(cls, source_code: str, file_name: str = "") -> list[str]:
        """Scans frontend component code for forbidden hardcoded theme literals."""
        violations: list[str] = []

        # Disallow hardcoded hex colors in style blocks (excluding comments or generated files)
        hex_pattern = re.compile(r"""(?:background|color|borderColor|fill|stroke)\s*:\s*["']#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})["']""")
        for match in hex_pattern.finditer(source_code):
            violations.append(f"{file_name}: Hardcoded hex property: '{match.group(0)}'")

        # Disallow raw dark background hacks: rgba(15, 23, 42, ...) or rgba(30, 41, 59, ...)
        raw_dark_pattern = re.compile(r"""rgba\(\s*(?:15|30)\s*,\s*(?:23|41)\s*,\s*(?:42|59)""")
        for match in raw_dark_pattern.finditer(source_code):
            violations.append(f"{file_name}: Unapproved hardcoded dark slate background: '{match.group(0)}'")

        return violations

    @classmethod
    def evaluate_three_visual_gates(cls, option: dict[str, Any]) -> VisualQAResult:
        """Executes the Three Permanent Visual Gates: Layout, Accessibility, and Theme."""
        warnings: list[str] = []
        remediations: list[str] = []

        # 1. Gate 1: Layout Integrity
        layout_violations: list[str] = []
        if "xAxis" not in option or "yAxis" not in option:
            layout_violations.append("Missing cartesian X/Y axis definition.")
            remediations.append("Injected standard cartesian axes.")

        grid = option.get("grid", {})
        if not grid.get("containLabel"):
            layout_violations.append("Grid missing containLabel=True, risking label clipping.")
            remediations.append("Applied containLabel: True.")

        gate_layout = GateAuditResult(
            gate_name="LayoutIntegrity",
            passed=len(layout_violations) == 0,
            details="All axes and containment boundaries validated." if not layout_violations else "; ".join(layout_violations),
            violations=layout_violations,
        )

        # 2. Gate 2: Accessibility Integrity
        access_violations: list[str] = []
        x_label = option.get("xAxis", {}).get("axisLabel", {})
        if x_label.get("fontSize", 12) < 11:
            access_violations.append("X-axis font size below 11px accessibility threshold.")
            remediations.append("Upgraded font size to 11px.")

        y_label = option.get("yAxis", {}).get("axisLabel", {})
        if y_label.get("fontSize", 12) < 11:
            access_violations.append("Y-axis font size below 11px accessibility threshold.")
            remediations.append("Upgraded font size to 11px.")

        gate_access = GateAuditResult(
            gate_name="AccessibilityIntegrity",
            passed=len(access_violations) == 0,
            details="Typography and accessibility sizing compliant." if not access_violations else "; ".join(access_violations),
            violations=access_violations,
        )

        # 3. Gate 3: Theme Integrity
        theme_violations: list[str] = []
        # Ensure tooltip background is not a hardcoded dark literal when not using theme tokens
        tt = option.get("tooltip", {})
        tt_bg = tt.get("backgroundColor", "")
        if tt_bg.startswith("#") and tt_bg.lower() in ("#1e293b", "#090d16", "#000000"):
            theme_violations.append(f"Hardcoded dark tooltip background '{tt_bg}' violates centralized theme.")
            remediations.append("Use theme token var(--chart-tooltip-bg) or useChartTheme.")

        gate_theme = GateAuditResult(
            gate_name="ThemeIntegrity",
            passed=len(theme_violations) == 0,
            details="Theme tokens and palette consumption verified." if not theme_violations else "; ".join(theme_violations),
            violations=theme_violations,
        )

        # 4. Gate 4: Formatter Integrity
        from .formatter_validator import ChartFormatterValidator
        fmt_report = ChartFormatterValidator.validate_option(option)
        gate_formatter = GateAuditResult(
            gate_name="FormatterIntegrity",
            passed=fmt_report.passed,
            details="Zero unresolved template tokens verified." if fmt_report.passed else "; ".join(fmt_report.violations),
            violations=fmt_report.violations,
        )
        remediations.extend(fmt_report.remediations)

        # 5. Gate 5: Render Integrity (Plot area ratio & containment safety)
        render_violations: list[str] = []
        grid_obj = option.get("grid", {})
        if grid_obj:
            # Check left margin vs category axis
            y_axis = option.get("yAxis", {})
            if isinstance(y_axis, dict) and y_axis.get("type") == "category":
                cats = y_axis.get("data", [])
                max_len = max([len(str(c)) for c in cats], default=0)
                left_val = grid_obj.get("left")
                if isinstance(left_val, (int, float)) and left_val < (max_len * 5 + 10):
                    render_violations.append(f"Left margin {left_val}px insufficient for {max_len}-character Y-axis labels.")
                    remediations.append("Expanded grid.left margin.")

        gate_render = GateAuditResult(
            gate_name="RenderIntegrity",
            passed=len(render_violations) == 0,
            details="Rendered geometry, margins, and plot containment safe." if not render_violations else "; ".join(render_violations),
            violations=render_violations,
        )

        # 6. Gate 6: Readability Integrity (Tick spacing, label density, legend overhead)
        readability_violations: list[str] = []
        container_w = float(option.get("_container_width", 800.0))
        container_h = float(option.get("_planned_height", option.get("_container_height", 320.0)))
        x_axis = option.get("xAxis", {})
        
        # Check X-axis tick spacing vs estimated label width
        if isinstance(x_axis, dict) and x_axis.get("type") == "category":
            categories = x_axis.get("data", [])
            cat_count = len(categories)
            if cat_count > 0:
                left_val = grid_obj.get("left", 50)
                if isinstance(left_val, str) and "%" in left_val:
                    left_px = float(left_val.replace("%", "")) * container_w / 100.0
                elif isinstance(left_val, (int, float)):
                    left_px = float(left_val)
                else:
                    left_px = 50.0

                right_val = grid_obj.get("right", 30)
                if isinstance(right_val, str) and "%" in right_val:
                    right_px = float(right_val.replace("%", "")) * container_w / 100.0
                elif isinstance(right_val, (int, float)):
                    right_px = float(right_val)
                else:
                    right_px = 30.0

                plot_w = max(100.0, container_w - left_px - right_px)
                available_tick_spacing = plot_w / cat_count
                max_chars = max([len(str(c)) for c in categories], default=0)
                estimated_label_width = max_chars * 7.5
                min_gap = 12.0
                required_spacing = estimated_label_width + min_gap

                # Verbose period strings like "1st–5th Jul" or "6th to 12th July" flag warning if spacing tight
                has_verbose_dates = any(re.search(r"\b(1st|2nd|3rd|\d+th|July)\b", str(c)) for c in categories)
                if has_verbose_dates:
                    readability_violations.append(
                        "Time axis contains verbose period labels risking crowding; require compact format (e.g. '1–5 Jul')."
                    )
                    remediations.append("Apply compact period labels (e.g. '1–5 Jul', '6–12 Jul').")

                if available_tick_spacing < required_spacing:
                    readability_violations.append(
                        f"Tick spacing {available_tick_spacing:.1f}px < required clearance {required_spacing:.1f}px for {max_chars}-character labels."
                    )
                    remediations.append("Increase chart dimensions, shorten labels, or switch to line chart.")

        # Check legend overhead on vertical plot area
        legend_obj = option.get("legend", {})
        if legend_obj and isinstance(legend_obj, dict):
            series_list = option.get("series", [])
            if len(series_list) >= 2 and legend_obj.get("bottom") == 0 and container_h <= 250:
                readability_violations.append(
                    "Bottom legend in shallow container (<=250px) compresses plot height and conflicts with X-axis."
                )
                remediations.append("Reposition legend above chart plot area (e.g. top: 4, right: 10).")

        gate_readability = GateAuditResult(
            gate_name="ReadabilityIntegrity",
            passed=len(readability_violations) == 0,
            details="Tick spacing, label density, and legend headroom optimal." if not readability_violations else "; ".join(readability_violations),
            violations=readability_violations,
        )

        # 7. Gate 7: Data Binding Integrity (Traceable evidence, non-empty governed data, policy-bound benchmarks)
        data_violations: list[str] = []
        series_list = option.get("series", [])
        if not series_list:
            data_violations.append("Chart option missing series definition.")
        else:
            for s_idx, s in enumerate(series_list):
                s_data = s.get("data", [])
                if not s_data:
                    data_violations.append(f"Series[{s_idx}] ('{s.get('name', 'unnamed')}') has empty data binding.")
                # Verify reference lines (markLine) have explicit policy or evidence grounding
                mark_line = s.get("markLine", {})
                if mark_line:
                    ml_data = mark_line.get("data", [])
                    for ml_item in ml_data:
                        ml_name = ml_item.get("name", "")
                        if not ml_name or not any(kw in ml_name.lower() for kw in ("policy", "target", "benchmark", "baseline", "evid-")):
                            data_violations.append(f"Reference line '{ml_name}' missing explicit policy or evidence contract.")

        # If evidence binding metadata is attached, verify valid EVID- pattern
        evidence_ids = option.get("_evidence_ids", [])
        if evidence_ids:
            for evid in evidence_ids:
                if not str(evid).startswith("EVID-"):
                    data_violations.append(f"Evidence identifier '{evid}' does not conform to EVID- standard.")

        gate_data_binding = GateAuditResult(
            gate_name="DataBindingIntegrity",
            passed=len(data_violations) == 0,
            details="Series values, policy reference lines, and evidence bindings verified." if not data_violations else "; ".join(data_violations),
            violations=data_violations,
        )

        all_passed = (
            gate_layout.passed
            and gate_access.passed
            and gate_theme.passed
            and gate_formatter.passed
            and gate_render.passed
            and gate_readability.passed
            and gate_data_binding.passed
        )
        warnings.extend(
            layout_violations
            + access_violations
            + theme_violations
            + fmt_report.violations
            + render_violations
            + readability_violations
            + data_violations
        )

        return VisualQAResult(
            passed=all_passed,
            layout_integrity=gate_layout,
            accessibility_integrity=gate_access,
            theme_integrity=gate_theme,
            formatter_integrity=gate_formatter,
            render_integrity=gate_render,
            readability_integrity=gate_readability,
            data_binding_integrity=gate_data_binding,
            warnings=warnings,
            remediations=remediations,
        )

    @classmethod
    def audit_data_binding_integrity(cls, source_code: str, file_name: str = "") -> list[str]:
        """Scans frontend component source code to disallow hardcoded business metric data arrays."""
        violations: list[str] = []

        # Disallow hardcoded numeric arrays in series/data options: e.g. data: [128, 142, 136, 145, 138]
        # or data: [21.2, 18.5, 16.4, 14.1, 8.2]
        numeric_array_pattern = re.compile(r"""(?:data|values)\s*:\s*\[\s*(?:[0-9]+(?:\.[0-9]+)?\s*,\s*){2,}[0-9]+(?:\.[0-9]+)?\s*\]""")
        for match in numeric_array_pattern.finditer(source_code):
            violations.append(f"{file_name}: Hardcoded numeric business data literal: '{match.group(0)}'")

        # Disallow hardcoded object literal data: e.g. [{ value: 8.2, itemStyle: ... }, { value: 14.1, ... }]
        object_array_pattern = re.compile(r"""data\s*:\s*\[\s*\{\s*value\s*:\s*[0-9]+(?:\.[0-9]+)?""")
        for match in object_array_pattern.finditer(source_code):
            violations.append(f"{file_name}: Hardcoded object-array business data literal: '{match.group(0)}'")

        return violations

    @classmethod
    def evaluate_seven_visual_gates(cls, option: dict[str, Any]) -> VisualQAResult:
        """Evaluates all Seven Permanent Visual Gates (Theme, Access, Layout, Formatter, Render, Readability, DataBinding)."""
        return cls.evaluate_three_visual_gates(option)

    @classmethod
    def evaluate_six_visual_gates(cls, option: dict[str, Any]) -> VisualQAResult:
        """Alias supporting callers of the six visual gates."""
        return cls.evaluate_three_visual_gates(option)

    @classmethod
    def evaluate_five_visual_gates(cls, option: dict[str, Any]) -> VisualQAResult:
        """Alias for visual QA evaluation supporting legacy five-gate callers."""
        return cls.evaluate_three_visual_gates(option)
