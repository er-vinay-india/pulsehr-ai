"""McKinsey / GE 9-Box Matrix Talent Placement Analytical Function.

Mathematical Formula: 3×3 Grid mapping Performance (Low, Med, High) × Potential (Low, Med, High)
Surfaces Star Talent (Top Right) vs Talent Risk / Remediation (Bottom Left).
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
class Talent9BoxFunction(BaseAnalyticalFunction):
    metadata = AnalyticalFunctionMetadata(
        function_id="fn_talent_9box",
        name="McKinsey / GE 9-Box Talent Placement Matrix",
        category=FunctionCategory.WORKFORCE_DYNAMICS,
        version="1.0.0",
        mathematical_formula="Grid(Performance_Tier × Potential_Tier) → 9 Talent Quadrants",
        preconditions=FunctionPreconditions(
            required_roles=[SemanticRole.NUMERIC_MEASURE],
            metric_keywords=["performance", "potential", "rating", "evaluation", "score"],
            min_sample_size=9
        ),
        jargon_mapping=JargonMapping(
            layman_definition="Categorizes employees into 9 strategic talent quadrants based on demonstrated performance vs future leadership potential.",
            hr_takeaway="Identifies key succession candidates and flags misaligned underperformers needing coaching or exit plans.",
            finance_takeaway="Ensures merit budget and equity grants are directed toward high-value growth assets rather than stagnant personnel.",
            pm_takeaway="Highlights team lead succession bench strength and delivery execution risk.",
            term_translations={
                "9-box": "performance-potential talent grid",
                "star quadrant": "high-performance, high-potential future leaders",
                "risk quadrant": "underperforming personnel requiring remediation"
            }
        ),
        impact_rule=BusinessImpactRule(
            impact_type=ImpactType.HEADCOUNT_AT_RISK,
            primary_metric_name="Succession Bench & Talent Remediation Headcount",
            unit="headcount",
            formula_description="Count of personnel in Star Quadrant vs Remediation Quadrant",
            default_severity=ImpactSeverity.MODERATE
        ),
        visual_recommendation=VisualGrammarRecommendation(
            primary_visual="HEATMAP_GRID",
            secondary_visual="BREAKDOWN_TREE",
            highlight_rule="quadrant_color_coded"
        )
    )

    def evaluate_impact(
        self,
        fact: Any,
        df: Any,
        profile: SemanticDatasetProfile
    ) -> BusinessImpactAssessment | None:
        metric = getattr(fact, "metric", "").lower()
        if not any(k in metric for k in ("9box", "9_box", "talent_grid", "performance_tier")):
            return None

        val = getattr(fact, "value", 0.0)
        n = getattr(fact, "sample_size", 0)

        dims = getattr(fact, "dimensions", {}) or {}
        quadrant = dims.get("quadrant") or dims.get("box") or "Talent Segment"

        severity = ImpactSeverity.CRITICAL if "risk" in quadrant.lower() or "under" in quadrant.lower() else ImpactSeverity.OPPORTUNITY

        formatted_impact = f"{int(val)} Employees in {quadrant}"
        layman_takeaway = f"{int(val)} employees ({n} total assessed) are positioned in '{quadrant}', directing targeted succession or performance intervention."

        return BusinessImpactAssessment(
            impact_type=ImpactType.HEADCOUNT_AT_RISK,
            impact_metric="Talent Segment Headcount",
            impact_value=float(val),
            formatted_impact=formatted_impact,
            unit="headcount",
            severity=severity,
            formula_explanation=f"Evaluated 9-box performance vs potential distribution across {n} employees",
            layman_takeaway=layman_takeaway
        )
