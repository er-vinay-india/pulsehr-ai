"""LatencyAnalyzer: Analyzes SLA violations and bottlenecks across workflows (Phase E)."""
from __future__ import annotations

import logging
from typing import Any
from app.observability.contracts import AITrace
from app.observability.latency_budget import WorkflowLatencyBudget
from ..contracts import (
    OptimizationRecommendation,
    RecommendationCategory,
    RiskLevel,
)

logger = logging.getLogger(__name__)


class LatencyAnalyzer:
    """Detects SLA violations and pinpoints slow execution bottlenecks."""

    @classmethod
    def analyze_traces(
        cls,
        traces: list[AITrace],
        current_policy_id: str,
    ) -> list[OptimizationRecommendation]:
        recommendations: list[OptimizationRecommendation] = []
        if not traces:
            return recommendations

        violations = [
            t for t in traces
            if not t.evaluation_summary.get("sla_compliant", True)
        ]

        if len(violations) >= 2:
            wf_names = list({t.workflow_type for t in violations if t.workflow_type})
            rec = OptimizationRecommendation(
                category=RecommendationCategory.LATENCY,
                current_policy_id=current_policy_id,
                proposed_policy_delta={
                    "enable_mcp_response_caching": True,
                    "target_workflows": wf_names,
                },
                evidence_trace_ids=[t.trace_id for t in violations[:5]],
                reason=f"Repeated SLA violations observed in workflows: {', '.join(wf_names)}.",
                expected_improvement="Reduce P95 tail latency within SLA targets by caching deterministic metadata queries.",
                risk_level=RiskLevel.LOW,
            )
            recommendations.append(rec)

        return recommendations
