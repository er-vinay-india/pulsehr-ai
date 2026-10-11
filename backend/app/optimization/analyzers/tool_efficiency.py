"""ToolEfficiencyAnalyzer: Analyzes duplicate tools and identifies parallel execution candidates (Phase E)."""
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


class ToolEfficiencyAnalyzer:
    """Detects duplicate tool calls and identifies opportunities for parallel execution."""

    @classmethod
    def analyze_traces(
        cls,
        traces: list[AITrace],
        current_policy_id: str,
    ) -> list[OptimizationRecommendation]:
        recommendations: list[OptimizationRecommendation] = []
        if not traces:
            return recommendations

        # 1. Parallel execution opportunity detection
        investigation_traces = [t for t in traces if t.workflow_type == "analytical_investigation"]
        if len(investigation_traces) >= 2:
            rec = OptimizationRecommendation(
                category=RecommendationCategory.TOOL_SELECTION,
                current_policy_id=current_policy_id,
                proposed_policy_delta={
                    "parallelize_tools": ["compare_segments", "analyze_relationship"],
                },
                evidence_trace_ids=[t.trace_id for t in investigation_traces[:5]],
                reason="Tools 'compare_segments' and 'analyze_relationship' are independent read-only queries against the same dataset.",
                expected_improvement="Concurrent dispatch reduces analytical investigation latency by ~35%.",
                risk_level=RiskLevel.LOW,
            )
            recommendations.append(rec)

        # 2. Duplicate tool call detection
        duplicate_traces = [
            t for t in traces
            if t.evaluation_summary.get("tool_selection", {}).get("duplicate_tool_rate", 0.0) > 0.0
        ]
        if len(duplicate_traces) >= 2:
            rec = OptimizationRecommendation(
                category=RecommendationCategory.TOOL_SELECTION,
                current_policy_id=current_policy_id,
                proposed_policy_delta={"deduplicate_identical_tool_invocations": True},
                evidence_trace_ids=[t.trace_id for t in duplicate_traces[:5]],
                reason="Traces exhibit repeated invocations of the same MCP tool within single workflows.",
                expected_improvement="Eliminate redundant tool execution, cutting unnecessary steps.",
                risk_level=RiskLevel.LOW,
            )
            recommendations.append(rec)

        return recommendations
