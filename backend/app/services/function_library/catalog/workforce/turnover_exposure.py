"""Turnover Headcount & Financial Replacement Exposure Analytical Function.

Mathematical Formula: Headcount_At_Risk = N_cohort × Attrition_Rate
Turnover_Financial_Exposure = Headcount_At_Risk × Average_Annual_Salary × 1.5
(SHRM Benchmark: 1.5x annual salary to recruit, onboard, and ramp replacement talent).
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
class TurnoverExposureFunction(BaseAnalyticalFunction):
    metadata = AnalyticalFunctionMetadata(
        function_id="fn_turnover_exposure",
        name="Turnover Headcount & Financial Replacement Exposure",
        category=FunctionCategory.WORKFORCE_DYNAMICS,
        version="1.0.0",
        mathematical_formula="Headcount_At_Risk = N × Rate | Exposure_$ = Headcount × AvgSalary × 1.5",
        preconditions=FunctionPreconditions(
            required_roles=[SemanticRole.NUMERIC_MEASURE],
            metric_keywords=["attrition", "turnover", "churn", "exit", "resignation", "flight_risk"],
            min_sample_size=5
        ),
        jargon_mapping=JargonMapping(
            layman_definition="Translates abstract attrition percentages into the exact number of employees at risk and the true dollars required to replace them.",
            hr_takeaway="Surfaces flight-risk talent pools requiring immediate retention intervention.",
            finance_takeaway="Quantifies unbudgeted recruiting, severance, and productivity ramp costs (1.5x salary benchmark).",
            pm_takeaway="Highlights team domain knowledge loss and delivery vulnerability.",
            term_translations={
                "attrition_flag": "voluntary/involuntary exit indicator",
                "churn_rate": "turnover velocity percentage",
                "replacement cost": "recruiting, onboarding, and ramp overhead"
            }
        ),
        impact_rule=BusinessImpactRule(
            impact_type=ImpactType.HEADCOUNT_AT_RISK,
            primary_metric_name="Turnover Headcount & Financial Exposure",
            unit="$",
            formula_description="Headcount at risk × Average annual compensation × 1.5 replacement factor",
            default_severity=ImpactSeverity.CRITICAL
        ),
        visual_recommendation=VisualGrammarRecommendation(
            primary_visual="IMPACT_METRIC_CARD",
            secondary_visual="BREAKDOWN_TREE",
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
        if not any(k in metric for k in ("attrition", "turnover", "churn", "exit", "resignation", "flight")):
            return None

        val = getattr(fact, "value", None)
        n = getattr(fact, "sample_size", 0)

        if val is None or n < 3:
            return None

        # Rate can be percentage (0..100) or fraction (0..1)
        rate = val / 100.0 if val > 1.0 else val
        headcount_at_risk = round(rate * n)

        # Baseline comparison
        baseline_val = getattr(fact, "baseline_value", None)
        base_rate = (baseline_val / 100.0 if baseline_val > 1.0 else baseline_val) if baseline_val is not None else 0.0
        excess_rate = max(0.0, rate - base_rate)
        excess_headcount = round(excess_rate * n)

        # Determine average compensation
        avg_salary = 75000.0  # Industry standard default
        if isinstance(df, pd.DataFrame):
            for col in df.columns:
                if any(w in col.lower() for w in ("salary", "comp", "wage", "pay")):
                    try:
                        numeric_s = pd.to_numeric(df[col].astype(str).str.replace(r'[\$,]', '', regex=True), errors='coerce')
                        mean_val = float(numeric_s.mean())
                        if mean_val > 10000:
                            avg_salary = mean_val
                        break
                    except Exception:
                        pass

        total_financial_exposure = round(headcount_at_risk * avg_salary * 1.5, 0)
        excess_exposure = round(excess_headcount * avg_salary * 1.5, 0)

        severity = ImpactSeverity.CRITICAL if headcount_at_risk >= 5 or total_financial_exposure >= 100000 else ImpactSeverity.HIGH

        dims = getattr(fact, "dimensions", {}) or {}
        seg_str = " in " + ", ".join(f"{k}='{v}'" for k, v in dims.items()) if dims else ""

        formatted_impact = f"{headcount_at_risk} At Risk (~${total_financial_exposure:,.0f} Exposure)"
        layman_takeaway = (
            f"An estimated {headcount_at_risk} employees are at risk of leaving{seg_str} "
            f"({excess_headcount} above baseline), representing an annualized replacement exposure of ${total_financial_exposure:,.0f}."
        )

        return BusinessImpactAssessment(
            impact_type=ImpactType.HEADCOUNT_AT_RISK,
            impact_metric="Headcount at Risk & Replacement Cost",
            impact_value=float(headcount_at_risk),
            formatted_impact=formatted_impact,
            unit="headcount",
            severity=severity,
            formula_explanation=f"{headcount_at_risk} employees at risk × ${avg_salary:,.0f} avg salary × 1.5x SHRM replacement multiplier",
            layman_takeaway=layman_takeaway
        )
