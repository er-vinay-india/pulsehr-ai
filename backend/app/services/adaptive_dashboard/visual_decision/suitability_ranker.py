"""Chart Suitability Ranker.

Scores, penalizes, and ranks candidate chart forms for a machine-readable VisualQuestion
respecting intent, scale compatibility, metric units, grain, and audience readability.
"""
from __future__ import annotations

import logging
from typing import Any

from .contracts import (
    AnalyticalIntent,
    AudienceType,
    ChartSuitabilityScore,
    ChartType,
    VisualQuestion,
)
from .suitability_matrix import CHART_SUITABILITY_MATRIX

logger = logging.getLogger(__name__)


class ChartSuitabilityRanker:
    """Ranks governed chart types using multi-factor fitness and penalty scoring."""

    @classmethod
    def rank_candidates(
        cls,
        question: VisualQuestion,
        series_magnitude_ratio: float = 1.0,
        audience: AudienceType = AudienceType.LAYMAN_EXECUTIVE,
        candidate_pool: list[ChartType] | None = None,
    ) -> list[ChartSuitabilityScore]:
        """Calculates suitability scores across candidate chart types and returns descending ranking."""
        primary_intent = question.intent
        secondary_intent = question.secondary_intent
        matrix_entry = CHART_SUITABILITY_MATRIX.get(primary_intent, {})
        preferred = set(matrix_entry.get("preferred", []))
        alternatives = set(matrix_entry.get("alternative", []))
        avoided = set(matrix_entry.get("avoid", []))

        # Secondary intent lookup for hybrid questions (e.g. COMPOSITION + GAP_EXPLANATION)
        sec_preferred: set[ChartType] = set()
        sec_alternatives: set[ChartType] = set()
        if secondary_intent:
            sec_entry = CHART_SUITABILITY_MATRIX.get(secondary_intent, {})
            sec_preferred = set(sec_entry.get("preferred", []))
            sec_alternatives = set(sec_entry.get("alternative", []))

        pool = candidate_pool or list(ChartType)
        candidates: list[ChartSuitabilityScore] = []

        # Check unit compatibility among measures
        measure_units = [ms.unit.lower() for ms in question.metric_semantics if ms.unit]
        distinct_units = set(measure_units)
        has_incompatible_units = len(distinct_units) > 1 and len(question.measures) > 1

        for c_type in pool:
            # 1. Intent Match
            intent_match = 0.50
            if c_type in preferred:
                intent_match = 0.95
            elif c_type in sec_preferred:
                intent_match = 0.90
            elif c_type in alternatives or c_type in sec_alternatives:
                intent_match = 0.75
            elif c_type in avoided:
                intent_match = 0.20

            # 2. Semantic Fit
            semantic_fit = 0.70
            if question.is_temporal_dimension:
                if c_type in (ChartType.LINE, ChartType.AREA, ChartType.ONE_HUNDRED_PERCENT_STACKED_BAR, ChartType.STACKED_BAR):
                    semantic_fit = 0.90
                elif c_type == ChartType.HORIZONTAL_BAR:
                    semantic_fit = 0.60
            else:
                if c_type == ChartType.HORIZONTAL_BAR:
                    semantic_fit = 0.95
                elif c_type == ChartType.LINE:
                    # Line chart on non-temporal dimension is heavily un-semantic
                    semantic_fit = 0.15

            # 3. Unit Compatibility
            unit_compatibility = 1.0
            if has_incompatible_units:
                if c_type in (ChartType.LINE, ChartType.STACKED_BAR, ChartType.ONE_HUNDRED_PERCENT_STACKED_BAR):
                    # Stacking or co-plotting distinct units (e.g. $ and %) on a single axis is invalid
                    unit_compatibility = 0.10

            # 4. Scale Compatibility
            scale_compatibility = 0.85
            if series_magnitude_ratio >= 3.0:
                if c_type == ChartType.ONE_HUNDRED_PERCENT_STACKED_BAR:
                    # Normalizing to percentages resolves scale disparity
                    scale_compatibility = 0.98
                elif c_type == ChartType.WATERFALL:
                    scale_compatibility = 0.90
                elif c_type in (ChartType.LINE, ChartType.STACKED_BAR):
                    # Unscaled multi-series flattens smaller measure (e.g. 135 vs 15)
                    scale_compatibility = 0.30
                else:
                    scale_compatibility = 0.50

            # 5. Audience Readability
            audience_readability = 0.80
            if audience == AudienceType.LAYMAN_EXECUTIVE:
                if c_type in (ChartType.HORIZONTAL_BAR, ChartType.ONE_HUNDRED_PERCENT_STACKED_BAR, ChartType.BULLET_BAR, ChartType.LINE):
                    audience_readability = 0.95
                elif c_type == ChartType.WATERFALL:
                    audience_readability = 0.88
                elif c_type in (ChartType.BOX_PLOT, ChartType.VIOLIN, ChartType.SCATTER):
                    audience_readability = 0.40
            elif audience == AudienceType.ANALYST:
                audience_readability = 0.90
            elif audience == AudienceType.DATA_SCIENTIST:
                if c_type in (ChartType.BOX_PLOT, ChartType.VIOLIN, ChartType.SCATTER):
                    audience_readability = 0.95

            # 6. Comparison Efficiency
            comparison_efficiency = 0.80
            if primary_intent == AnalyticalIntent.RANKING and c_type == ChartType.HORIZONTAL_BAR:
                comparison_efficiency = 0.98
            elif primary_intent == AnalyticalIntent.COMPOSITION and c_type == ChartType.ONE_HUNDRED_PERCENT_STACKED_BAR:
                comparison_efficiency = 0.95

            density_fit = 0.85
            mobile_fit = 0.80
            if c_type == ChartType.HORIZONTAL_BAR:
                mobile_fit = 0.95  # Natural vertical scroll on mobile
            elif c_type == ChartType.PIE:
                mobile_fit = 0.50

            # 7. Penalties
            ambiguity_penalty = 0.0
            clutter_penalty = 0.0

            # Time on x-axis does NOT imply line chart when question is composition
            if question.is_temporal_dimension and primary_intent in (AnalyticalIntent.COMPOSITION, AnalyticalIntent.PART_TO_WHOLE):
                if c_type == ChartType.LINE:
                    ambiguity_penalty += 0.45
                    clutter_penalty += 0.25

            # Flattening penalty for multi-series line with large scale gap
            if series_magnitude_ratio >= 3.0 and c_type == ChartType.LINE and len(question.measures) > 1:
                clutter_penalty += 0.35

            if has_incompatible_units and c_type in (ChartType.LINE, ChartType.STACKED_BAR):
                ambiguity_penalty += 0.50

            if c_type == ChartType.PIE and question.dimension_cardinality > 5:
                clutter_penalty += 0.40

            # Weighted Total Score
            score = (
                0.30 * intent_match
                + 0.20 * semantic_fit
                + 0.15 * unit_compatibility
                + 0.15 * scale_compatibility
                + 0.10 * audience_readability
                + 0.05 * comparison_efficiency
                + 0.05 * density_fit
                - ambiguity_penalty
                - clutter_penalty
            )
            score = round(max(0.0, min(1.0, score)), 4)

            rationale_parts = []
            if c_type in preferred:
                rationale_parts.append(f"Preferred match for {primary_intent.value}")
            if series_magnitude_ratio >= 3.0:
                if c_type == ChartType.ONE_HUNDRED_PERCENT_STACKED_BAR:
                    rationale_parts.append("Eliminates magnitude scale flattening via proportional composition")
                elif c_type == ChartType.LINE:
                    rationale_parts.append("Penalized: magnitude gap visually flattens smaller series")
            if has_incompatible_units:
                rationale_parts.append("Penalized: incompatible units cannot share single axis")

            candidates.append(
                ChartSuitabilityScore(
                    chart_type=c_type,
                    total_score=score,
                    intent_match=round(intent_match, 2),
                    semantic_fit=round(semantic_fit, 2),
                    unit_compatibility=round(unit_compatibility, 2),
                    scale_compatibility=round(scale_compatibility, 2),
                    audience_readability=round(audience_readability, 2),
                    comparison_efficiency=round(comparison_efficiency, 2),
                    density_fit=round(density_fit, 2),
                    mobile_fit=round(mobile_fit, 2),
                    ambiguity_penalty=round(ambiguity_penalty, 2),
                    clutter_penalty=round(clutter_penalty, 2),
                    rationale="; ".join(rationale_parts) or f"Suitability for {primary_intent.value}",
                )
            )

        candidates.sort(key=lambda s: s.total_score, reverse=True)
        return candidates
