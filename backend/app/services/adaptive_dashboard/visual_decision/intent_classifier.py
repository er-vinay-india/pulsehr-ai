"""Analytical Intent Classifier.

Determines the core analytical intent and secondary intent of a business question
or empirical finding before selecting any visual representation.
"""
from __future__ import annotations

import re
from typing import Any

from .contracts import AnalyticalIntent


class AnalyticalIntentClassifier:
    """Classifies the primary and secondary business intent from questions and finding context."""

    INTENT_KEYWORDS: dict[AnalyticalIntent, list[str]] = {
        AnalyticalIntent.COMPOSITION: [
            "distributed", "distribution of capacity", "composition", "breakdown", "mix",
            "share of", "proportions", "allocation", "makeup", "workforce disposition",
            "attendance vs approved leave", "reconciliation"
        ],
        AnalyticalIntent.GAP_EXPLANATION: [
            "gap", "unexplained", "deficit", "shortfall", "divergence", "reconciliation gap",
            "disparity explanation", "account for the difference", "where the gap is concentrated"
        ],
        AnalyticalIntent.RANKING: [
            "which department", "which cohort", "ranking", "rank", "largest", "smallest",
            "highest", "lowest", "top", "bottom", "spread across segments", "department disparity"
        ],
        AnalyticalIntent.TARGET_VS_ACTUAL: [
            "vs target", "target", "policy", "benchmark", "threshold", "actual vs",
            "compliance", "adherence", "policy benchmark"
        ],
        AnalyticalIntent.VARIANCE: [
            "variance", "diverged", "deviation", "delta", "budget vs actual", "over under"
        ],
        AnalyticalIntent.TREND: [
            "trajectory", "over time", "trend", "trended", "cadence", "progression", "evolution",
            "evolved", "evolve", "stability cadence", "historical", "weekly", "weekly trend",
            "monthly trend", "reporting periods", "reporting period", "across periods", "cycles"
        ],
        AnalyticalIntent.CHANGE: [
            "change between", "period over period", "shift from", "increased by", "decreased by"
        ],
        AnalyticalIntent.RELATIONSHIP: [
            "correlation", "associated with", "relationship between", "co-movement",
            "price vs sales", "elasticity", "scatter"
        ],
        AnalyticalIntent.DISTRIBUTION: [
            "distribution of values", "frequency", "spread of", "histogram", "dispersion", "outliers"
        ],
        AnalyticalIntent.CONTRIBUTION: [
            "contribution", "waterfall", "stepped", "bridge", "cumulative impact"
        ],
        AnalyticalIntent.PART_TO_WHOLE: [
            "part to whole", "percentage of total", "share", "proportion of 100"
        ],
        AnalyticalIntent.ANOMALY: [
            "anomaly", "outlier", "irregularity", "unexpected surge", "unexpected drop"
        ],
    }

    @classmethod
    def classify(
        cls,
        question: str,
        finding_context: dict[str, Any] | None = None
    ) -> tuple[AnalyticalIntent, AnalyticalIntent | None]:
        """Infers the primary and optional secondary analytical intent."""
        q_lower = (question or "").lower()
        context = finding_context or {}
        claim_type = str(context.get("claim_type", "")).lower()
        metric_family = str(context.get("metric_family", "")).lower()
        dimensions = context.get("dimensions", [])
        measures = context.get("measures", [])

        # 1. Structural multi-metric workforce composition check
        # E.g. Attendance + Approved Leave across periods
        is_capacity_mix = (
            ("attendance" in q_lower and "leave" in q_lower)
            or "reconciliation" in metric_family
            or ("attendance" in str(measures).lower() and "leave" in str(measures).lower())
            or ("attendance" in str(dimensions).lower() and "leave" in str(dimensions).lower())
        )
        if is_capacity_mix:
            return AnalyticalIntent.COMPOSITION, AnalyticalIntent.GAP_EXPLANATION

        # 2. Ranking check: categorical ranking against benchmark or across departments
        if (
            "department" in q_lower and any(w in q_lower for w in ("ranking", "largest", "highest", "lowest", "spread", "disparity"))
            or claim_type == "segment_difference"
            or "ranking" in metric_family
        ):
            sec = AnalyticalIntent.TARGET_VS_ACTUAL if any(w in q_lower for w in ("target", "benchmark", "policy")) else None
            return AnalyticalIntent.RANKING, sec

        # 3. Target vs actual benchmark check
        if any(w in q_lower for w in ("target", "benchmark", "policy", "threshold")) or claim_type == "target_gap":
            return AnalyticalIntent.TARGET_VS_ACTUAL, AnalyticalIntent.VARIANCE

        # 4. Keyword scoring
        scores: dict[AnalyticalIntent, int] = {intent: 0 for intent in AnalyticalIntent}
        for intent, kws in cls.INTENT_KEYWORDS.items():
            for kw in kws:
                if kw in q_lower:
                    scores[intent] += len(kw.split()) * 2

        # Claim type heuristics
        if claim_type == "trend_change" or "cadence" in metric_family or "temporal" in metric_family or context.get("is_temporal"):
            scores[AnalyticalIntent.TREND] += 8
        elif claim_type in ("capacity_gap", "target_gap"):
            scores[AnalyticalIntent.GAP_EXPLANATION] += 5
        elif claim_type == "correlation":
            scores[AnalyticalIntent.RELATIONSHIP] += 5

        sorted_intents = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top_intent, top_score = sorted_intents[0]

        if top_score > 0:
            second_intent = sorted_intents[1][0] if sorted_intents[1][1] > 0 and sorted_intents[1][0] != top_intent else None
            return top_intent, second_intent

        # Fallback based on temporal vs categorical
        if context.get("is_temporal", False):
            return AnalyticalIntent.TREND, None
        return AnalyticalIntent.COMPARISON, None
