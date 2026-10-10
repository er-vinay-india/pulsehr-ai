"""Visual Decision Intelligence Engine.

Executes the end-to-end Analytical Intent -> Visual Decision pipeline:
1. Resolves Metric Semantics & Grain
2. Classifies Analytical Intent
3. Builds machine-readable VisualQuestion
4. Ranks candidate chart types via Suitability Matrix & Scoring
5. Validates semantics & claim entitlement
6. Generates full VisualDecisionAudit and enriched VisualSpec
"""
from __future__ import annotations

import logging
from typing import Any

from .archetypes import ARCHETYPE_LIBRARY, VisualArchetype
from .contracts import (
    AnalyticalIntent,
    AudienceType,
    ChartSuitabilityScore,
    ChartType,
    MetricSemantics,
    VisualDecisionAudit,
    VisualQuestion,
)
from .intent_classifier import AnalyticalIntentClassifier
from .question_builder import VisualQuestionBuilder
from .semantic_validator import VisualSemanticValidator
from .suitability_ranker import ChartSuitabilityRanker

logger = logging.getLogger(__name__)


class VisualDecisionEngine:
    """Orchestrates governed visual decision intelligence prior to visual compilation."""

    @classmethod
    def decide_visual(
        cls,
        visual_id: str,
        question_text: str,
        primary_dimension: str,
        measures: list[str],
        dimension_cardinality: int = 1,
        is_temporal_dimension: bool = False,
        temporal_grain: str | None = None,
        series_data: dict[str, list[float]] | None = None,
        audience: AudienceType = AudienceType.LAYMAN_EXECUTIVE,
        finding_context: dict[str, Any] | None = None,
        title: str = "",
        takeaway: str = "",
        provided_units: dict[str, str] | None = None,
        denominator_metric: str | None = None,
        denominator_value: float | None = None,
        residual_component: str | None = None,
        excluded_population: list[str] | None = None,
    ) -> dict[str, Any]:
        """Evaluates intent, metrics, and scale to select the optimal chart with full audit trail."""
        # 1. Build VisualQuestion with MetricSemantics & DenominatorIntegrity
        v_question = VisualQuestionBuilder.build_question(
            question_text=question_text,
            primary_dimension=primary_dimension,
            measures=measures,
            dimension_cardinality=dimension_cardinality,
            is_temporal_dimension=is_temporal_dimension,
            temporal_grain=temporal_grain,
            finding_context=finding_context,
            provided_units=provided_units,
            denominator_metric=denominator_metric,
            denominator_value=denominator_value,
            residual_component=residual_component,
            excluded_population=excluded_population,
            series_data=series_data,
        )

        # 2. Calculate series magnitude ratio
        magnitude_ratio = 1.0
        if series_data and len(series_data) >= 2:
            means = []
            for s_name, s_vals in series_data.items():
                if s_vals:
                    valid = [v for v in s_vals if v is not None and not (isinstance(v, float) and (v != v))]
                    if valid:
                        means.append(sum(valid) / len(valid))
            if len(means) >= 2 and min(means) > 0:
                magnitude_ratio = round(max(means) / max(1e-6, min(means)), 2)

        # 3. Rank candidate chart types
        candidates = ChartSuitabilityRanker.rank_candidates(
            question=v_question,
            series_magnitude_ratio=magnitude_ratio,
            audience=audience,
        )
        selected_cand = candidates[0] if candidates else None
        selected_type = selected_cand.chart_type if selected_cand else ChartType.HORIZONTAL_BAR

        # 4. Semantic Validation & Claim Entitlement
        is_valid, block_reason = VisualSemanticValidator.validate_visual_plan(
            question=v_question,
            selected_chart=selected_type,
            title=title,
            takeaway=takeaway,
        )

        sanitized_takeaway = VisualSemanticValidator.check_takeaway_entitlement(takeaway)

        # 5. Determine Archetype & Drill-down
        archetype_match: VisualArchetype | None = None
        for arch in ARCHETYPE_LIBRARY.values():
            if arch.primary_intent == v_question.intent and arch.preferred_chart == selected_type:
                archetype_match = arch
                break
        if not archetype_match and v_question.intent == AnalyticalIntent.COMPOSITION:
            archetype_match = ARCHETYPE_LIBRARY.get("COMPOSITION_STORY")
        elif not archetype_match and v_question.intent == AnalyticalIntent.RANKING:
            archetype_match = ARCHETYPE_LIBRARY.get("RANKING_STORY")

        # 6. Build Audit Record
        audit = VisualDecisionAudit(
            visual_id=visual_id,
            business_question=question_text,
            analytical_intent=v_question.intent,
            audience=audience,
            candidate_charts=candidates,
            selected_chart=selected_type,
            selection_score=selected_cand.total_score if selected_cand else 0.5,
            selection_reason=selected_cand.rationale if selected_cand else "Default fallback",
            rejected_alternatives=[
                {"chart_type": c.chart_type.value, "score": c.total_score, "penalties": round(c.ambiguity_penalty + c.clutter_penalty, 2)}
                for c in candidates[1:]
            ],
            metric_units=[ms.unit for ms in v_question.metric_semantics],
            metric_grain=v_question.grain,
            validation_status="VALIDATED" if is_valid else "BLOCKED",
            blocking_reason=block_reason,
            denominator_integrity=v_question.denominator_semantics,
        )

        if not is_valid:
            logger.warning("Visual decision blocked for %s: %s", visual_id, block_reason)
            return {
                "status": "VISUALIZATION_BLOCKED",
                "blocking_reason": block_reason,
                "audit": audit.model_dump(),
                "chart_type": "blocked",
            }

        return {
            "status": "VALIDATED",
            "chart_type": selected_type.value,
            "analytical_intent": v_question.intent.value,
            "secondary_intent": v_question.secondary_intent.value if v_question.secondary_intent else None,
            "business_question": question_text,
            "audience": audience.value,
            "metric_semantics": [ms.model_dump() for ms in v_question.metric_semantics],
            "series_magnitude_ratio": magnitude_ratio,
            "selection_reason": selected_cand.rationale if selected_cand else "",
            "selection_score": selected_cand.total_score if selected_cand else 0.5,
            "audit": audit.model_dump(),
            "archetype_id": archetype_match.archetype_id if archetype_match else None,
            "drill_down_chart": archetype_match.drill_down_chart.value if archetype_match and archetype_match.drill_down_chart else None,
            "sanitized_takeaway": sanitized_takeaway,
        }
