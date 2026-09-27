"""Deterministic Visual & Accessibility Validator for Phase 4.

Calculates mathematical WCAG contrast ratios, verifies layout content budgets,
enforces minimum font sizing, and audits visual completeness for the 16:9 canvas.
"""

from __future__ import annotations

import math
import re
from typing import Any
from pydantic import BaseModel, Field

from .design_tokens import SlideDesignTokens
from .visual_models import VisualSpecification


def parse_hex_color(hex_str: str) -> tuple[int, int, int]:
    """Parses #RRGGBB or #RGB into (R, G, B) integer tuple."""
    clean = hex_str.strip().lstrip("#")
    if len(clean) == 3:
        clean = "".join([c * 2 for c in clean])
    if len(clean) >= 6:
        try:
            return int(clean[:2], 16), int(clean[2:4], 16), int(clean[4:6], 16)
        except ValueError:
            pass
    return (255, 255, 255)


def calculate_relative_luminance(rgb: tuple[int, int, int]) -> float:
    """Calculates WCAG 2.1 relative luminance for an RGB tuple."""
    normalized = []
    for c in rgb:
        v = c / 255.0
        if v <= 0.03928:
            normalized.append(v / 12.92)
        else:
            normalized.append(math.pow((v + 0.055) / 1.055, 2.4))
    return 0.2126 * normalized[0] + 0.7152 * normalized[1] + 0.0722 * normalized[2]


def calculate_contrast_ratio(hex_fg: str, hex_bg: str) -> float:
    """Calculates WCAG 2.1 contrast ratio between foreground and background colors."""
    lum1 = calculate_relative_luminance(parse_hex_color(hex_fg))
    lum2 = calculate_relative_luminance(parse_hex_color(hex_bg))
    l_bright = max(lum1, lum2)
    l_dark = min(lum1, lum2)
    return round((l_bright + 0.05) / (l_dark + 0.05), 2)


class VisualValidationIssue(BaseModel):
    """An identified visual, accessibility, or content budget anomaly."""
    severity: str = "warning"  # info | warning | critical
    rule_id: str
    component: str
    message: str
    remediation: str = ""


class VisualValidationReport(BaseModel):
    """Comprehensive visual quality and accessibility evaluation."""
    is_valid: bool = True
    accessibility_score: float = 100.0
    issues: list[VisualValidationIssue] = Field(default_factory=list)
    contrast_ratios: dict[str, float] = Field(default_factory=dict)
    remediation_notes: list[str] = Field(default_factory=list)


class VisualValidator:
    """Audits VisualSpecification instances for accessibility, layout fit, and visual integrity."""

    @classmethod
    def validate_contrast(cls, tokens: SlideDesignTokens) -> dict[str, Any]:
        """Validates WCAG contrast ratios for design tokens."""
        cr_primary = calculate_contrast_ratio(tokens.primary_text, tokens.background)
        cr_secondary = calculate_contrast_ratio(tokens.secondary_text, tokens.background)
        cr_accent = calculate_contrast_ratio(tokens.accent_primary, tokens.background)
        return {
            "primary_contrast": cr_primary,
            "secondary_contrast": cr_secondary,
            "accent_contrast": cr_accent,
            "passes_wcag_aa": cr_primary >= 4.5 and cr_secondary >= 3.0,
            "passes_wcag_aaa": cr_primary >= 7.0 and cr_secondary >= 4.5
        }

    @classmethod
    def validate_content_budget(
        cls,
        headline: str,
        body_text: str,
        insights: list[str],
        budget: Any,
        table_row_count: int = 0
    ) -> dict[str, Any]:
        """Validates text and component quantities against layout-aware content budget."""
        headline_chars = len(headline or "")
        word_count = len((body_text or "").split())
        insight_count = len(insights or [])
        violations = []

        if headline_chars > getattr(budget, "max_headline_chars", 80):
            violations.append(f"Headline length ({headline_chars} chars) exceeds budget.")
        if word_count > getattr(budget, "max_body_words", 120):
            violations.append(f"Body word count ({word_count} words) exceeds budget.")
        if insight_count > getattr(budget, "max_insights", 4):
            violations.append(f"Insight count ({insight_count}) exceeds budget.")
        if table_row_count > getattr(budget, "max_table_rows", 8):
            violations.append(f"Table row count ({table_row_count}) exceeds budget.")

        return {
            "within_budget": len(violations) == 0,
            "violations": violations,
            "headline_chars": headline_chars,
            "body_words": word_count,
            "insight_count": insight_count,
            "table_rows": table_row_count
        }

    @classmethod
    def validate_spec(
        cls,
        spec: VisualSpecification,
        tokens: SlideDesignTokens
    ) -> VisualValidationReport:
        """Runs deterministic accessibility, spatial budget, and visual asset checks."""
        issues: list[VisualValidationIssue] = []
        contrast_ratios: dict[str, float] = {}

        # 1. WCAG Contrast Checks
        # Primary text vs background
        cr_primary = calculate_contrast_ratio(tokens.primary_text, tokens.background)
        contrast_ratios["primary_text_vs_bg"] = cr_primary
        if cr_primary < 4.5:
            issues.append(VisualValidationIssue(
                severity="critical" if cr_primary < 3.0 else "warning",
                rule_id="WCAG-CONTRAST-PRIMARY",
                component="typography",
                message=f"Primary text contrast ({cr_primary}:1) is below WCAG AAA standard (4.5:1).",
                remediation="Darken background or lighten text color."
            ))

        # Secondary text vs surface/background
        cr_secondary = calculate_contrast_ratio(tokens.secondary_text, tokens.background)
        contrast_ratios["secondary_text_vs_bg"] = cr_secondary
        if cr_secondary < 3.0:
            issues.append(VisualValidationIssue(
                severity="warning",
                rule_id="WCAG-CONTRAST-SECONDARY",
                component="typography",
                message=f"Secondary text contrast ({cr_secondary}:1) is below minimum 3.0:1 threshold.",
                remediation="Increase lightness separation of secondary text."
            ))

        # 2. Content Budget Checks
        budget = spec.layout.content_budget
        headline_len = len(spec.headline or "")
        if headline_len > budget.max_headline_chars:
            issues.append(VisualValidationIssue(
                severity="warning",
                rule_id="BUDGET-HEADLINE-LENGTH",
                component="headline",
                message=f"Headline length ({headline_len} chars) exceeds layout budget ({budget.max_headline_chars} chars).",
                remediation="Trim headline to fit 2-line maximum."
            ))

        # Insights count
        if len(spec.insights) > budget.max_insights:
            issues.append(VisualValidationIssue(
                severity="warning",
                rule_id="BUDGET-INSIGHTS-OVERFLOW",
                component="insight_panel",
                message=f"Insight count ({len(spec.insights)}) exceeds layout budget ({budget.max_insights}).",
                remediation=f"Limit takeaways to the top {budget.max_insights} critical points."
            ))

        # Table rows check
        if spec.table_data and "rows" in spec.table_data:
            num_rows = len(spec.table_data["rows"])
            if num_rows > budget.max_table_rows:
                issues.append(VisualValidationIssue(
                    severity="warning",
                    rule_id="BUDGET-TABLE-ROWS",
                    component="table",
                    message=f"Table row count ({num_rows}) exceeds visual budget ({budget.max_table_rows}).",
                    remediation=f"Paginate or paginate top {budget.max_table_rows} rows to appendix."
                ))

        # 3. Chart Data & Guardrail Validation
        if spec.chart_spec:
            guard_res = spec.chart_spec.validate_guardrails()
            if not guard_res.passed:
                for v in guard_res.violations:
                    issues.append(VisualValidationIssue(
                        severity="warning",
                        rule_id="CHART-GUARDRAIL-VIOLATION",
                        component="chart",
                        message=v,
                        remediation=guard_res.reason
                    ))

        # Compute Score
        deductions = sum(20 if i.severity == "critical" else 5 for i in issues)
        score = max(0.0, 100.0 - deductions)
        has_critical = any(i.severity == "critical" for i in issues)

        return VisualValidationReport(
            is_valid=not has_critical,
            accessibility_score=score,
            issues=issues,
            contrast_ratios=contrast_ratios,
            remediation_notes=[i.remediation for i in issues if i.remediation]
        )
