"""OverOrchestrationDetector: Analyzes workflow node counts and tool call bloat (Phase E)."""
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


class OverOrchestrationDetector:
    """Detects excessive nodes, redundant tools, and unneeded model calls in workflows."""

    QUICK_ANSWER_TOOL_THRESHOLD = 2.5

    @classmethod
    def analyze_traces(
        cls,
        traces: list[AITrace],
        current_policy_id: str,
    ) -> list[OptimizationRecommendation]:
        recommendations: list[OptimizationRecommendation] = []
        if not traces:
            return recommendations

        # 1. Check QuickAnswer tool call bloat
        qa_traces = [t for t in traces if t.workflow_type == "quick_answer"]
        if qa_traces:
            avg_tools = sum(len(t.tools) for t in qa_traces) / len(qa_traces)
            if avg_tools > cls.QUICK_ANSWER_TOOL_THRESHOLD:
                evidence_ids = [t.trace_id for t in qa_traces[:5]]
                rec = OptimizationRecommendation(
                    category=RecommendationCategory.WORKFLOW,
                    current_policy_id=current_policy_id,
                    proposed_policy_delta={
                        "workflow": "quick_answer",
                        "prune_unnecessary_preflights": True,
                        "max_tools": 2,
                    },
                    evidence_trace_ids=evidence_ids,
                    reason=f"QuickAnswer average tool calls ({avg_tools:.1f}) exceeds optimal target (<= 2.0).",
                    expected_improvement="Reduce QuickAnswer latency by ~30% and eliminate redundant tool calls.",
                    risk_level=RiskLevel.LOW,
                )
                recommendations.append(rec)

        # 2. Check unneeded model calls in deterministic queries
        lookup_traces = [
            t for t in traces
            if t.evaluation_summary.get("intent_alignment", {}).get("detected_intent") in ("DATA_LOOKUP", "RANKING")
            and len(t.model_calls) > 0
        ]
        if len(lookup_traces) >= 3:
            rec = OptimizationRecommendation(
                category=RecommendationCategory.TOOL_SELECTION,
                current_policy_id=current_policy_id,
                proposed_policy_delta={"bypass_model_for_deterministic_lookups": True},
                evidence_trace_ids=[t.trace_id for t in lookup_traces[:5]],
                reason="Model Gateway was invoked on purely deterministic lookups/rankings.",
                expected_improvement="100% deterministic bypass, saving tokens and reducing latency by ~500ms.",
                risk_level=RiskLevel.LOW,
            )
            recommendations.append(rec)

        return recommendations
