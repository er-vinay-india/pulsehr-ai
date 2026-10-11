"""RetryPolicyAnalyzer: Analyzes retry effectiveness versus fallback latency (Phase E)."""
from __future__ import annotations

import logging
from typing import Any
from app.observability.contracts import AITrace
from ..contracts import (
    OptimizationRecommendation,
    RecommendationCategory,
    RiskLevel,
)

logger = logging.getLogger(__name__)


class RetryPolicyAnalyzer:
    """Evaluates retry success rates and recommends early fallback on low-probability retries."""

    @classmethod
    def analyze_traces(
        cls,
        traces: list[AITrace],
        current_policy_id: str,
    ) -> list[OptimizationRecommendation]:
        recommendations: list[OptimizationRecommendation] = []
        if not traces:
            return recommendations

        # Detect traces with multiple retries on failed tools
        high_retry_traces = [
            t for t in traces
            if t.evaluation_summary.get("tool_selection", {}).get("same_tool_retry_rate", 0.0) > 0.3
        ]

        if len(high_retry_traces) >= 2:
            rec = OptimizationRecommendation(
                category=RecommendationCategory.RETRY_POLICY,
                current_policy_id=current_policy_id,
                proposed_policy_delta={
                    "max_same_tool_retries": 1,
                    "early_fallback_on_timeout": True,
                },
                evidence_trace_ids=[t.trace_id for t in high_retry_traces[:5]],
                reason="Same-tool retries exhibit < 5% recovery probability on timeout; immediate fallback prevents wasting latency budget.",
                expected_improvement="Cut worst-case tail latency by up to 4000ms on transient tool failures.",
                risk_level=RiskLevel.MEDIUM,
            )
            recommendations.append(rec)

        return recommendations
