"""Lost Productive Capacity & Overtime Drain Analytical Function.

Mathematical Formula: Lost_Hours = (Cohort_Mean - Baseline_Mean) × N_cohort × 8.0 hrs
Capacity_FTE_Drag = Lost_Hours / 160.0 (standard monthly working hours per FTE)
"""

from typing import Any
import pandas as pd

from ...base import (
    BaseAnalyticalFunction,
    AnalyticalFunctionMetadata,
    FunctionCategory,
    ImpactType,
    ImpactSeverity,
    JargonMapping,
    BusinessImpactRule,
    BusinessImpactAssessment,
    FunctionPreconditions,
    VisualGrammarRecommendation,
)
from ...registry import register_function
from ....data_engine.semantic_classifier import SemanticDatasetProfile, SemanticRole


@register_function
class LostCapacityHoursFunction(BaseAnalyticalFunction):
    metadata = AnalyticalFunctionMetadata(
        function_id="fn_lost_capacity_hours",
        name="Lost Productive Labor Hours & Capacity Drag",
        category=FunctionCategory.WORKFORCE_DYNAMICS,
        version="1.0.0",
        mathematical_formula="Lost_Hours = Δ_Days × N × 8 | FTE_Drag = Lost_Hours / 160",
        preconditions=FunctionPreconditions(
            required_roles=[SemanticRole.NUMERIC_MEASURE],
            metric_keywords=["absence", "overtime", "hours", "downtime", "sick", "days"],
            min_sample_size=4
        ),
        jargon_mapping=JargonMapping(
            layman_definition="Converts individual employee absence or overtime days into total aggregate lost working hours and equivalent lost full-time employee (FTE) capacity.",
            hr_takeaway="Identifies teams experiencing chronic labor shortages and unsustainable strain.",
            finance_takeaway="Quantifies unbudgeted overtime pay and loss of return on payroll investment.",
            pm_takeaway="Provides exact FTE capacity deductions needed for realistic sprint planning and milestone dates.",
            term_translations={
                "mean delta": "excess lost days per employee",
                "FTE drag": "equivalent full-time employee capacity shortfall",
                "productive hours": "actual labor hours delivered"
            }
        ),
        impact_rule=BusinessImpactRule(
            impact_type=ImpactType.LOST_CAPACITY_HOURS,
            primary_metric_name="Aggregate Lost Labor Hours",
            unit="hours",
            formula_description="(Cohort mean - baseline mean) × Cohort headcount × 8.0 hours/day",
            default_severity=ImpactSeverity.HIGH
        ),
        visual_recommendation=VisualGrammarRecommendation(
            primary_visual="VARIANCE_WATERFALL",
            secondary_visual="IMPACT_METRIC_CARD",
            highlight_rule="alert_on_high"
        )
    )

    def evaluate_impact(
        self,
        fact: Any,
        df: Any,
        profile: SemanticDatasetProfile
    ) -> BusinessImpactAssessment | None:
        metric = getattr(fact, "metric", "").lower()
        if not any(k in metric for k in ("absence", "overtime", "sick", "downtime", "hours", "days")):
            return None

        val = getattr(fact, "value", None)
        base = getattr(fact, "baseline_value", None)
        n = getattr(fact, "sample_size", 0)

        if val is None or base is None or n < 3:
            return None

        diff = val - base
        if abs(diff) < 0.2:
            return None

        # Convert to hours: if unit is already hours vs days
        is_already_hours = "hour" in metric or getattr(fact, "unit", "") == "hours"
        multiplier = 1.0 if is_already_hours else 8.0

        lost_hours = round(diff * n * multiplier, 1)
        fte_drag = round(abs(lost_hours) / 160.0, 1)

        direction = "deficit" if lost_hours > 0 else "efficiency gain"
        severity = ImpactSeverity.CRITICAL if abs(lost_hours) >= 300 else (ImpactSeverity.HIGH if abs(lost_hours) >= 80 else ImpactSeverity.MODERATE)

        dims = getattr(fact, "dimensions", {}) or {}
        seg_str = " in " + ", ".join(f"{k}='{v}'" for k, v in dims.items()) if dims else ""

        formatted_impact = f"{abs(lost_hours):,.0f} Hours ({fte_drag} FTE-mo {direction})"
        layman_takeaway = (
            f"Variance{seg_str} equates to {abs(lost_hours):,.0f} net {direction} hours "
            f"(~{fte_drag} FTE-months), directly impacting operational delivery velocity."
        )

        return BusinessImpactAssessment(
            impact_type=ImpactType.LOST_CAPACITY_HOURS,
            impact_metric="Lost Productive Hours",
            impact_value=lost_hours,
            formatted_impact=formatted_impact,
            unit="hours",
            severity=severity,
            formula_explanation=f"({diff:+.2f} {metric}/person × {n} people) × {multiplier:.0f} hrs = {lost_hours:+.1f} net hours",
            layman_takeaway=layman_takeaway
        )
