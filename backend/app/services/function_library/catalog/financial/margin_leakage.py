"""Margin Leakage & Commercial Concession Analytical Function.

Mathematical Formula: Margin_Leakage_$ = Δ_Rate × Segment_Revenue_Volume
Calculates direct dollar erosion from discount slippage, scrap, or return rates.
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
class MarginLeakageFunction(BaseAnalyticalFunction):
    metadata = AnalyticalFunctionMetadata(
        function_id="fn_margin_leakage",
        name="Commercial Margin Leakage & Concession Drift",
        category=FunctionCategory.FINANCIAL_IMPACT,
        version="1.0.0",
        mathematical_formula="Margin_Leakage_$ = (Rate_Segment - Rate_Baseline) × Segment_Volume",
        preconditions=FunctionPreconditions(
            required_roles=[SemanticRole.NUMERIC_MEASURE],
            metric_keywords=["discount", "scrap", "refund", "return", "rebate", "markdown", "defect"],
            min_sample_size=4
        ),
        jargon_mapping=JargonMapping(
            layman_definition="Calculates the exact unrecovered dollars leaking from gross profit due to off-guideline discounts, product defects, or scrap.",
            hr_takeaway="Highlights sales or operations teams needing pricing policy compliance and incentive realignment.",
            finance_takeaway="Pins down direct margin erosion that fails to convert into expected gross revenue.",
            pm_takeaway="Quantifies physical production defect waste and rework expenditure.",
            term_translations={
                "discount_rate": "concession percentage",
                "scrap_rate": "unrecoverable material waste percentage",
                "leakage": "unbudgeted dollar margin loss"
            }
        ),
        impact_rule=BusinessImpactRule(
            impact_type=ImpactType.MARGIN_LEAKAGE,
            primary_metric_name="Unrecovered Dollar Margin Leakage",
            unit="$",
            formula_description="Excess percentage rate × Segment financial volume",
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
        if not any(k in metric for k in ("discount", "scrap", "refund", "return", "rebate", "markdown", "defect")):
            return None

        val = getattr(fact, "value", None)
        base = getattr(fact, "baseline_value", None)
        n = getattr(fact, "sample_size", 0)

        if val is None or base is None or n < 3:
            return None

        diff = val - base
        if diff <= 0.05:
            return None

        rate_diff = (diff / 100.0) if val > 1.0 else diff

        # Estimate segment financial volume
        est_segment_volume = 100000.0  # Default $100K segment baseline
        if isinstance(df, pd.DataFrame):
            for col in df.columns:
                if any(w in col.lower() for w in ("sales", "revenue", "amount", "total", "spend", "cost")):
                    try:
                        numeric_s = pd.to_numeric(df[col].astype(str).str.replace(r'[\$,]', '', regex=True), errors='coerce')
                        avg_order = numeric_s.mean()
                        if avg_order > 0:
                            est_segment_volume = avg_order * n
                        break
                    except Exception:
                        pass

        dollar_leakage = round(rate_diff * est_segment_volume, 0)
        if dollar_leakage < 100:
            return None

        severity = ImpactSeverity.CRITICAL if dollar_leakage >= 50000 else ImpactSeverity.HIGH

        dims = getattr(fact, "dimensions", {}) or {}
        seg_str = " in " + ", ".join(f"{k}='{v}'" for k, v in dims.items()) if dims else ""

        formatted_impact = f"${dollar_leakage:,.0f} Margin Leakage"
        layman_takeaway = (
            f"Excess {metric} (+{diff:+.1f}% vs baseline){seg_str} eroded an estimated ${dollar_leakage:,.0f} "
            f"in gross margin across ${est_segment_volume:,.0f} in transaction volume."
        )

        return BusinessImpactAssessment(
            impact_type=ImpactType.MARGIN_LEAKAGE,
            impact_metric="Gross Margin Leakage",
            impact_value=dollar_leakage,
            formatted_impact=formatted_impact,
            unit="$",
            severity=severity,
            formula_explanation=f"{rate_diff:+.1%} excess rate × ${est_segment_volume:,.0f} segment volume = ${dollar_leakage:,.0f}",
            layman_takeaway=layman_takeaway
        )
