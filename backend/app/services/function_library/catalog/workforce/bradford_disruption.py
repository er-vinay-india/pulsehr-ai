"""Bradford Absence Disruption Index Analytical Function.

Mathematical Formula: B = S^2 * D
Where S = number of distinct absence spells, D = total days absent.
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
class BradfordDisruptionFunction(BaseAnalyticalFunction):
    metadata = AnalyticalFunctionMetadata(
        function_id="fn_bradford_disruption",
        name="Bradford Absence Disruption Index",
        category=FunctionCategory.WORKFORCE_DYNAMICS,
        version="1.0.0",
        mathematical_formula="B = S² × D (S = absence spells, D = total days absent)",
        preconditions=FunctionPreconditions(
            required_roles=[SemanticRole.NUMERIC_MEASURE],
            metric_keywords=["absence", "leave", "sick", "spells", "attendance"],
            min_sample_size=5
        ),
        jargon_mapping=JargonMapping(
            layman_definition="Measures how frequent short unplanned absences create compounding operational disruption compared to single planned leaves.",
            hr_takeaway="Persistent short-term absences signal localized burnout, team friction, or disengagement.",
            finance_takeaway="Quantifies hidden overtime and temporary staff replacement payroll expenses.",
            pm_takeaway="Flags unpredictable sprint velocity drag and milestone delivery risk.",
            term_translations={
                "spells": "unplanned absence occurrences",
                "compounding disruption": "exponential workflow friction",
                "bradford score": "operational absence impact index"
            }
        ),
        impact_rule=BusinessImpactRule(
            impact_type=ImpactType.LOST_CAPACITY_HOURS,
            primary_metric_name="Excess Absence Disruption Hours",
            unit="hours",
            formula_description="(Excess absence days × 8.0 hrs/day) with 1.5x overtime replacement multiplier",
            default_severity=ImpactSeverity.HIGH
        ),
        visual_recommendation=VisualGrammarRecommendation(
            primary_visual="BREAKDOWN_TREE",
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
        if not any(k in metric for k in ("absence", "leave", "sick", "attendance", "bradford")):
            return None

        val = getattr(fact, "value", None)
        baseline = getattr(fact, "baseline_value", None)
        n = getattr(fact, "sample_size", 0)

        if val is None or baseline is None or n < 3:
            return None

        diff = val - baseline
        if diff <= 0:
            return None

        # Calculate excess lost productive days and hours
        excess_days = diff * n
        lost_hours = round(excess_days * 8.0, 1)
        fte_months = round(lost_hours / 160.0, 1)

        # Estimate replacement / overtime cost ($35/hr default or wage column)
        hourly_rate = 35.0
        if isinstance(df, pd.DataFrame):
            for col in df.columns:
                if any(w in col.lower() for w in ("salary", "wage", "pay", "rate", "cost")):
                    try:
                        numeric_s = pd.to_numeric(df[col].astype(str).str.replace(r'[\$,]', '', regex=True), errors='coerce')
                        avg_val = numeric_s.mean()
                        if avg_val > 1000:
                            hourly_rate = avg_val / 2080.0
                        elif avg_val > 10:
                            hourly_rate = avg_val
                        break
                    except Exception:
                        pass

        replacement_cost = round(lost_hours * hourly_rate * 1.5, 0)

        severity = ImpactSeverity.CRITICAL if lost_hours >= 200 or replacement_cost >= 15000 else ImpactSeverity.HIGH

        segment_name = ""
        dims = getattr(fact, "dimensions", {}) or {}
        if dims:
            segment_name = " in " + ", ".join(f"{k}='{v}'" for k, v in dims.items())

        formatted_impact = f"{lost_hours:,.0f} Lost Hours (~${replacement_cost:,.0f} Cost)"
        layman_takeaway = (
            f"Excess absences{segment_name} created {lost_hours:,.0f} lost productive hours "
            f"(~{fte_months} FTE-months capacity drain), costing an estimated ${replacement_cost:,.0f} in overtime replacement."
        )

        return BusinessImpactAssessment(
            impact_type=ImpactType.LOST_CAPACITY_HOURS,
            impact_metric="Lost Productive Hours & Overtime Cost",
            impact_value=lost_hours,
            formatted_impact=formatted_impact,
            unit="hours",
            severity=severity,
            formula_explanation=f"({diff:+.2f} excess days/person × {n} people × 8 hrs) × ${hourly_rate:.0f}/hr × 1.5x replacement multiplier",
            layman_takeaway=layman_takeaway
        )
