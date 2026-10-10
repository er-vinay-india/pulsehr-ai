"""Visual Semantic Validator and Narrative Entitlement Integrity Guard.

Enforces pre-rendering visual invariants:
1. No chart generated with unresolved metric grain or ambiguous unit (VISUALIZATION_BLOCKED).
2. Measure unit fidelity: employee_day must never be displayed as plain "days".
3. Compared measures must have compatible units.
4. Narrative entitlement: correlation/observation cannot claim causal driver without statistical proof.
"""
from __future__ import annotations

import re
from typing import Any

from .contracts import (
    AnalyticalIntent,
    ChartType,
    VisualDecisionAudit,
    VisualQuestion,
)


class VisualSemanticValidator:
    """Validates structural and semantic soundness of visual specifications before compilation."""

    CAUSAL_FORBIDDEN_WORDS = [
        "caused", "causes", "causing",
        "drives the", "driving the", "driver of",
        "resulted in", "resulting in",
        "responsible for", "attributable entirely to",
    ]

    @classmethod
    def validate_visual_plan(
        cls,
        question: VisualQuestion,
        selected_chart: ChartType,
        title: str,
        takeaway: str,
    ) -> tuple[bool, str | None]:
        """Validates metric grain, unit consistency, scale compatibility, and claim entitlement.

        Returns (is_valid, blocking_reason).
        """
        # Invariant 1: Resolved Metric Unit & Grain (Hard Requirement)
        for ms in question.metric_semantics:
            if not ms.is_resolved or not ms.unit or not ms.grain or "unresolved" in ms.unit.lower() or "unresolved" in ms.grain.lower():
                return False, f"AMBIGUOUS_METRIC_GRAIN: Metric '{ms.metric_name}' grain or unit is unresolved."

        # Invariant 2: Unit Label Fidelity (employee_day cannot be plain 'days')
        for ms in question.metric_semantics:
            if ms.unit == "employee_day" and ms.display_unit.strip().lower() in ("days", "day"):
                return False, f"METRIC_UNIT_MISMATCH: Metric '{ms.metric_name}' is measured in employee-days, cannot be labeled as plain days."

        # Invariant 3: Incompatible Units on Single Axis
        distinct_units = {ms.unit.lower() for ms in question.metric_semantics if ms.unit}
        if len(distinct_units) > 1 and len(question.measures) > 1:
            if selected_chart in (ChartType.LINE, ChartType.STACKED_BAR, ChartType.ONE_HUNDRED_PERCENT_STACKED_BAR):
                return False, f"INCOMPATIBLE_UNITS: Cannot plot incompatible units ({list(distinct_units)}) on a single axis."

        # Invariant 4: Narrative Entitlement Integrity (No unentitled causal language)
        takeaway_lower = (takeaway or "").lower()
        if question.intent != AnalyticalIntent.CONTRIBUTION:  # Contribution may state additive delta
            for word in cls.CAUSAL_FORBIDDEN_WORDS:
                if re.search(r'\b' + re.escape(word) + r'\b', takeaway_lower):
                    return False, f"NARRATIVE_ENTITLEMENT_VIOLATION: Visual takeaway claims causality ('{word}') unsupported by observational evidence."

        # Invariant 5: Denominator Integrity & Composition Reconciliation (Hard Requirement)
        # For composition, part-to-whole, or 100% stacked visuals, Highview must verify that
        # displayed components reconcile to the expected denominator, and residual populations are not dropped.
        if selected_chart in (ChartType.ONE_HUNDRED_PERCENT_STACKED_BAR, ChartType.STACKED_BAR) or question.intent in (AnalyticalIntent.COMPOSITION, AnalyticalIntent.PART_TO_WHOLE):
            if question.denominator_semantics is not None:
                denom = question.denominator_semantics
                if not denom.is_reconciled:
                    return False, (
                        f"INCOMPLETE_COMPOSITION: Displayed components ({denom.numerator_components}) "
                        f"do not reconcile to denominator '{denom.denominator_metric}' (delta={denom.unreconciled_delta:.1f}). "
                        f"Missing components must not be silently normalized away."
                    )

        return True, None

    @classmethod
    def check_takeaway_entitlement(cls, text: str, is_causal_proven: bool = False) -> str:
        """Sanitizes or warns on over-entitled narrative conclusions."""
        if is_causal_proven or not text:
            return text

        sanitized = text
        for word in cls.CAUSAL_FORBIDDEN_WORDS:
            pattern = re.compile(r'\b' + re.escape(word) + r'\b', re.IGNORECASE)
            if pattern.search(sanitized):
                # Replace with observational phrasing
                sanitized = pattern.sub("co-occurs with the", sanitized)
        return sanitized
