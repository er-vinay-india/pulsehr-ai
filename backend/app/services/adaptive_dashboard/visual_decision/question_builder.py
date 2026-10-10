"""Visual Question Builder.

Assembles concise, machine-readable VisualQuestion specifications with explicit
metric semantics, grain, and analytical intent before any chart is chosen.
"""
from __future__ import annotations

import re
from typing import Any

from .contracts import (
    AnalyticalIntent,
    DenominatorIntegrityContract,
    MetricSemantics,
    VisualQuestion,
)
from .intent_classifier import AnalyticalIntentClassifier


class VisualQuestionBuilder:
    """Builds machine-readable VisualQuestions from business findings and data profiles."""

    STANDARD_METRIC_GRAINS: dict[str, dict[str, str]] = {
        "attendance": {
            "unit": "employee_day",
            "display_unit": "employee-days",
            "grain": "employee × working_day",
            "aggregation": "SUM",
            "semantic_role": "MEASURE",
        },
        "leave": {
            "unit": "employee_day",
            "display_unit": "employee-days",
            "grain": "employee × working_day",
            "aggregation": "SUM",
            "semantic_role": "MEASURE",
        },
        "absence": {
            "unit": "employee_day",
            "display_unit": "employee-days",
            "grain": "employee × working_day",
            "aggregation": "SUM",
            "semantic_role": "MEASURE",
        },
        "gap": {
            "unit": "employee_day",
            "display_unit": "employee-days",
            "grain": "employee × working_day",
            "aggregation": "SUM",
            "semantic_role": "MEASURE",
        },
        "unclassified": {
            "unit": "employee_day",
            "display_unit": "employee-days",
            "grain": "employee × working_day",
            "aggregation": "SUM",
            "semantic_role": "MEASURE",
        },
        "capacity": {
            "unit": "employee_day",
            "display_unit": "employee-days",
            "grain": "employee × working_day",
            "aggregation": "SUM",
            "semantic_role": "MEASURE",
        },
        "headcount": {
            "unit": "headcount",
            "display_unit": "employees",
            "grain": "employee",
            "aggregation": "COUNT_DISTINCT",
            "semantic_role": "COUNT",
        },
        "sales": {
            "unit": "usd",
            "display_unit": "$",
            "grain": "transaction",
            "aggregation": "SUM",
            "semantic_role": "AMOUNT",
        },
        "revenue": {
            "unit": "usd",
            "display_unit": "$",
            "grain": "period",
            "aggregation": "SUM",
            "semantic_role": "AMOUNT",
        },
        "budget": {
            "unit": "usd",
            "display_unit": "$",
            "grain": "period",
            "aggregation": "SUM",
            "semantic_role": "AMOUNT",
        },
        "rate": {
            "unit": "percent",
            "display_unit": "%",
            "grain": "ratio",
            "aggregation": "RATE",
            "semantic_role": "RATIO",
        },
    }

    DEFAULT_UNIT_GRAINS: dict[str, tuple[str, str, str]] = {
        "employee_day": ("employee × working_day", "employee-days", "SUM"),
        "employee-day": ("employee × working_day", "employee-days", "SUM"),
        "employee_days": ("employee × working_day", "employee-days", "SUM"),
        "usd": ("financial_transaction", "$", "SUM"),
        "dollar": ("financial_transaction", "$", "SUM"),
        "dollars": ("financial_transaction", "$", "SUM"),
        "$": ("financial_transaction", "$", "SUM"),
        "percent": ("ratio", "%", "RATE"),
        "%": ("ratio", "%", "RATE"),
        "count": ("record", "units", "COUNT"),
        "headcount": ("employee", "employees", "COUNT_DISTINCT"),
        "hours": ("work_hour", "hrs", "SUM"),
        "days": ("calendar_day", "days", "SUM"),
        "units": ("unit_record", "units", "SUM"),
        "unit": ("unit_record", "units", "SUM"),
        "score": ("student_record", "pts", "MEAN"),
        "points": ("score_record", "pts", "MEAN"),
        "µg/m³": ("air_sample", "µg/m³", "MEAN"),
        "ug/m3": ("air_sample", "µg/m³", "MEAN"),
        "ppm": ("air_sample", "ppm", "MEAN"),
    }

    @classmethod
    def resolve_metric_semantics(
        cls,
        metric_name: str,
        provided_unit: str = "",
        provided_grain: str = "",
    ) -> MetricSemantics:
        """Resolves precise metric unit, grain, and aggregation. Flags unresolved metrics."""
        m_lower = metric_name.lower()
        p_unit = (provided_unit or "").strip().lower()
        
        # 1. Look for standard catalog entries by metric name
        matched_info = None
        for key, info in cls.STANDARD_METRIC_GRAINS.items():
            if key in m_lower:
                matched_info = info
                break

        if matched_info:
            unit = provided_unit or matched_info["unit"]
            display_unit = matched_info["display_unit"]
            # Correct "days" to "employee-days" if it's workforce presence
            if unit in ("days", "day") and any(k in m_lower for k in ("attendance", "leave", "absence")):
                unit = "employee_day"
                display_unit = "employee-days"

            return MetricSemantics(
                metric_name=metric_name,
                semantic_role=matched_info["semantic_role"],
                unit=unit,
                display_unit=display_unit,
                aggregation=matched_info["aggregation"],
                grain=provided_grain or matched_info["grain"],
                is_resolved=True,
            )

        # 2. Look for default grain by provided unit
        if p_unit in cls.DEFAULT_UNIT_GRAINS:
            std_grain, std_display, std_agg = cls.DEFAULT_UNIT_GRAINS[p_unit]
            return MetricSemantics(
                metric_name=metric_name,
                semantic_role="AMOUNT" if p_unit in ("usd", "$", "dollar", "dollars") else ("RATIO" if p_unit in ("percent", "%") else "MEASURE"),
                unit=p_unit,
                display_unit=std_display,
                aggregation=std_agg,
                grain=provided_grain or std_grain,
                is_resolved=True,
            )

        # 3. Generic resolution for currencies and percentages
        is_percent = "%" in p_unit or "percent" in m_lower or "rate" in m_lower or "ratio" in m_lower
        is_currency = "$" in p_unit or any(c in m_lower for c in ("usd", "cost", "salary", "expense", "revenue", "price"))
        
        if is_percent:
            return MetricSemantics(
                metric_name=metric_name,
                semantic_role="RATIO",
                unit="percent",
                display_unit="%",
                aggregation="RATE",
                grain=provided_grain or "cohort_ratio",
                is_resolved=True,
            )
        if is_currency:
            return MetricSemantics(
                metric_name=metric_name,
                semantic_role="AMOUNT",
                unit="usd",
                display_unit="$",
                aggregation="SUM",
                grain=provided_grain or "financial_record",
                is_resolved=True,
            )

        if provided_unit and (provided_grain or provided_unit not in ("unresolved", "unknown", "")):
            resolved_grain = provided_grain or f"{provided_unit}_record"
            return MetricSemantics(
                metric_name=metric_name,
                semantic_role="MEASURE",
                unit=provided_unit,
                display_unit=provided_unit,
                aggregation="SUM",
                grain=resolved_grain,
                is_resolved=True,
            )

        # Ambiguous / unresolved
        return MetricSemantics(
            metric_name=metric_name,
            semantic_role="MEASURE",
            unit=provided_unit or "unresolved_unit",
            display_unit=provided_unit or "unresolved",
            aggregation="SUM",
            grain=provided_grain or "unresolved_grain",
            is_resolved=bool(provided_unit and provided_grain),
        )

    @classmethod
    def build_question(
        cls,
        question_text: str,
        primary_dimension: str,
        measures: list[str],
        dimension_cardinality: int = 1,
        is_temporal_dimension: bool = False,
        temporal_grain: str | None = None,
        finding_context: dict[str, Any] | None = None,
        provided_units: dict[str, str] | None = None,
        denominator_metric: str | None = None,
        denominator_value: float | None = None,
        residual_component: str | None = None,
        excluded_population: list[str] | None = None,
        series_data: dict[str, list[float]] | None = None,
    ) -> VisualQuestion:
        """Constructs a complete VisualQuestion instance."""
        intent, sec_intent = AnalyticalIntentClassifier.classify(
            question=question_text,
            finding_context=finding_context,
        )

        units_map = provided_units or {}
        resolved_semantics = [
            cls.resolve_metric_semantics(m, units_map.get(m, ""))
            for m in measures
        ]

        primary_grain = resolved_semantics[0].grain if resolved_semantics else "record"

        # Denominator Integrity Contract derivation
        denom_semantics: DenominatorIntegrityContract | None = None
        if denominator_metric or denominator_value is not None:
            expected_denom = denominator_value
            is_reconciled = True
            delta = 0.0

            if expected_denom is not None and series_data:
                # Sum component series values across available slices
                # Check reconciliation for the latest cycle / period or total
                slice_count = max((len(vals) for vals in series_data.values()), default=0)
                for idx in range(slice_count):
                    slice_sum = sum(
                        (series_data[m][idx] for m in measures if m in series_data and idx < len(series_data[m])),
                        0.0,
                    )
                    slice_delta = abs(slice_sum - expected_denom)
                    if slice_delta > 0.05:
                        # Check if residual is accounted for
                        if not residual_component or residual_component not in measures:
                            is_reconciled = False
                            delta = max(delta, slice_delta)

            elif expected_denom is not None and not series_data:
                # If series_data not supplied but finding_context has expected_total
                fc_total = finding_context.get("expected_total") if finding_context else None
                if fc_total is not None and abs(fc_total - expected_denom) > 0.05:
                    if not residual_component or residual_component not in measures:
                        is_reconciled = False
                        delta = abs(fc_total - expected_denom)

            denom_semantics = DenominatorIntegrityContract(
                metric_name=measures[0] if measures else "composition",
                numerator_components=measures,
                denominator_metric=denominator_metric or "total_capacity",
                denominator_value=expected_denom,
                expected_total=expected_denom,
                excluded_population=excluded_population or [],
                residual_component=residual_component,
                is_reconciled=is_reconciled,
                unreconciled_delta=round(delta, 2),
            )

        return VisualQuestion(
            question=question_text,
            intent=intent,
            secondary_intent=sec_intent,
            primary_dimension=primary_dimension,
            dimension_cardinality=dimension_cardinality,
            is_temporal_dimension=is_temporal_dimension,
            measures=measures,
            metric_semantics=resolved_semantics,
            grain=primary_grain,
            temporal_grain=temporal_grain,
            denominator_semantics=denom_semantics,
        )
