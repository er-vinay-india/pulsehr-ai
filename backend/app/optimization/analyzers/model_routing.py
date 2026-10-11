"""ModelRoutingAnalyzer: Evaluates model performance, fallback spikes, and routing scores (Phase E)."""
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


def compute_model_routing_score(
    quality: float,
    structured_success: float,
    latency_efficiency: float,
    compute_efficiency: float,
    fallback_stability: float,
) -> float:
    """Computes composite ModelRoutingScore."""
    score = (
        0.35 * quality
        + 0.25 * structured_success
        + 0.20 * latency_efficiency
        + 0.15 * compute_efficiency
        + 0.05 * fallback_stability
    )
    return round(score, 3)


class ModelRoutingAnalyzer:
    """Analyzes model telemetry to recommend cascade improvements and alternate primaries."""

    FALLBACK_RATE_THRESHOLD = 0.20
    SLOW_MODEL_LATENCY_THRESHOLD_MS = 5000.0

    @classmethod
    def analyze_traces(
        cls,
        traces: list[AITrace],
        current_policy_id: str,
    ) -> list[OptimizationRecommendation]:
        recommendations: list[OptimizationRecommendation] = []
        if not traces:
            return recommendations

        # Check fallback usage rate
        model_traces = [t for t in traces if "model_routing" in t.evaluation_summary]
        if not model_traces:
            return recommendations

        fallbacks = sum(
            1 for t in model_traces
            if t.evaluation_summary["model_routing"].get("fallback_used", False)
        )
        fallback_rate = fallbacks / len(model_traces)

        if fallback_rate > cls.FALLBACK_RATE_THRESHOLD:
            evidence_ids = [t.trace_id for t in model_traces if t.evaluation_summary["model_routing"].get("fallback_used")][:5]
            rec = OptimizationRecommendation(
                category=RecommendationCategory.MODEL_ROUTING,
                current_policy_id=current_policy_id,
                proposed_policy_delta={
                    "task_type": "NARRATIVE_AI",
                    "promote_fallback_to_primary": True,
                    "target_model": "qwen3.5:9b",
                },
                evidence_trace_ids=evidence_ids,
                reason=f"Primary model experienced excessive fallback rate ({fallback_rate * 100:.1f}% > 20.0%).",
                expected_improvement="Reduce circuit-breaker trips and eliminate fallback retry latency.",
                risk_level=RiskLevel.MEDIUM,
            )
            recommendations.append(rec)

        # Check slow primary model across task types
        slow_traces = [
            t for t in model_traces
            if t.total_latency_ms > cls.SLOW_MODEL_LATENCY_THRESHOLD_MS
        ]
        if len(slow_traces) >= 2:
            first_slow = slow_traces[0].evaluation_summary.get("model_routing", {})
            task_type = first_slow.get("task_type", "AGENTIC_AI")
            actual_model = first_slow.get("actual_model", "qwen3.5:9b")
            alternate_model = "gemma4:12b" if actual_model != "gemma4:12b" else "qwen3.5:9b"
            rec = OptimizationRecommendation(
                category=RecommendationCategory.MODEL_ROUTING,
                current_policy_id=current_policy_id,
                proposed_policy_delta={
                    "task_type": task_type,
                    "evaluate_alternate_primary": alternate_model,
                    "cascade": {task_type: [alternate_model, actual_model, "phi4-mini:latest"]},
                },
                evidence_trace_ids=[t.trace_id for t in slow_traces[:5]],
                reason=f"Primary model {actual_model} latency exceeds 5000ms SLA target ({slow_traces[0].total_latency_ms:.1f}ms).",
                expected_improvement="Improve workflow generation speed while preserving execution quality.",
                risk_level=RiskLevel.MEDIUM,
            )
            recommendations.append(rec)

        return recommendations
