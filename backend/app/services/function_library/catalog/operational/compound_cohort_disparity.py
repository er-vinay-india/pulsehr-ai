"""Compound Cross-Segment Cohort Disparity Analytical Function.

Mathematical Formula: Evaluates non-linear cross-segment interactions (Dim A × Dim B × Measure),
concentration ratios (Pareto Share / Population Share), and intra-segment spread ratios.
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
class CompoundCohortDisparityFunction(BaseAnalyticalFunction):
    metadata = AnalyticalFunctionMetadata(
        function_id="fn_compound_cohort_disparity",
        name="Multi-Factor Compound Cohort Disparity & Spread",
        category=FunctionCategory.OPERATIONAL_VELOCITY,
        version="1.0.0",
        mathematical_formula="Interaction(Dim_A × Dim_B) → Disparity_Δ = Cohort_Mean - Baseline_Mean | Conc_Ratio = Metric% / Pop%",
        preconditions=FunctionPreconditions(
            required_roles=[SemanticRole.CATEGORICAL_DIMENSION, SemanticRole.NUMERIC_MEASURE],
            min_sample_size=4
        ),
        jargon_mapping=JargonMapping(
            layman_definition="Uncovers hidden outlier groups where the intersection of two dimensions creates an outsized performance spike or bottleneck that single-dimension averages hide.",
            hr_takeaway="Surfaces intersectional equity disparities and localized team friction.",
            finance_takeaway="Pinpoints isolated cost centers driving the majority of operational expense drift.",
            pm_takeaway="Exposes specific sub-operations (e.g. machine X on night shift) causing delivery roadblocks.",
            term_translations={
                "cross-segment intersection": "multi-variable cohort subgroup",
                "concentration ratio": "disproportionate volume skew factor",
                "intra-segment spread": "internal performance gap within the same department"
            }
        ),
        impact_rule=BusinessImpactRule(
            impact_type=ImpactType.OPERATIONAL_DRAG,
            primary_metric_name="Compound Cohort Variance & Concentration",
            unit="units",
            formula_description="(Cohort mean - baseline) with Pareto volume concentration weighting",
            default_severity=ImpactSeverity.HIGH
        ),
        visual_recommendation=VisualGrammarRecommendation(
            primary_visual="BREAKDOWN_TREE",
            secondary_visual="VARIANCE_WATERFALL",
            highlight_rule="alert_on_high"
        )
    )

    def evaluate_impact(
        self,
        fact: Any,
        df: Any,
        profile: SemanticDatasetProfile
    ) -> BusinessImpactAssessment | None:
        ftype = getattr(fact, "fact_type", "")
        if ftype not in ("multi_factor_segment_disparity", "compound_cohort_disparity"):
            return None

        val = getattr(fact, "value", None)
        base = getattr(fact, "baseline_value", None)
        n = getattr(fact, "sample_size", 0)
        meas = getattr(fact, "metric", "measure")

        if val is None or base is None or n < 3:
            return None

        stat_info = getattr(fact, "statistical_info", {}) or {}
        conc_ratio = stat_info.get("concentration_ratio", 1.0)
        pop_share = stat_info.get("cohort_pop_share_pct", 0.0)
        metric_share = stat_info.get("cohort_metric_share_pct", 0.0)

        diff = val - base
        rel_diff = getattr(fact, "relative_difference", 0.0)

        dims = getattr(fact, "dimensions", {}) or {}
        seg_str = " [" + " × ".join(f"{k}='{v}'" for k, v in dims.items()) + "]"

        severity = ImpactSeverity.CRITICAL if abs(rel_diff) >= 100.0 or conc_ratio >= 2.0 else ImpactSeverity.HIGH

        formatted_impact = f"{rel_diff:+0.1f}% Cohort Variance ({conc_ratio:.1f}x Skew)"
        layman_takeaway = (
            f"Compound intersection{seg_str} ({n} records, {pop_share:.1f}% of population) "
            f"drives {metric_share:.1f}% of total {meas}, representing a {conc_ratio:.1f}x concentration hotspot."
        )

        return BusinessImpactAssessment(
            impact_type=ImpactType.OPERATIONAL_DRAG,
            impact_metric=f"Compound Cohort Variance ({meas})",
            impact_value=round(diff, 2),
            formatted_impact=formatted_impact,
            unit=meas,
            severity=severity,
            formula_explanation=f"Cross-tab mean {val:.2f} vs baseline {base:.2f} ({rel_diff:+0.1f}%, concentration {conc_ratio:.1f}x)",
            layman_takeaway=layman_takeaway
        )
