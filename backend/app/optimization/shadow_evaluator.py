"""ShadowPolicyEvaluator: Evaluates candidate policies alongside production without side effects (Phase E)."""
from __future__ import annotations

import logging
import time
from typing import Any
from uuid import uuid4

from app.agent.state import HighviewAgentState
from .contracts import HighviewPolicy, ShadowEvaluation

logger = logging.getLogger(__name__)


class ShadowPolicyEvaluator:
    """Simulates candidate policy decisions in shadow mode without exposing outputs or executing side effects."""

    @classmethod
    def evaluate_shadow(
        cls,
        active_state: HighviewAgentState,
        candidate_policy: HighviewPolicy,
        active_latency_ms: float = 120.0,
    ) -> ShadowEvaluation:
        # Determine active decisions
        active_wf = active_state.active_filters.get("_workflow_name", "quick_answer")
        active_tools = [t.get("tool_name") for t in active_state.tool_history]

        # Simulate candidate policy decision
        intent = active_state.intent
        cand_wf = candidate_policy.workflow_policy.intent_workflow_map.get(intent, "quick_answer")
        cand_tools = candidate_policy.tool_policy.default_tools_by_intent.get(intent, active_tools)

        # Invariant: Never execute side effects (e.g. presentation exports, external mutations) in shadow mode
        side_effects_skipped = any("export" in t or "deck" in t or "approval" in t for t in cand_tools)

        differences: list[str] = []
        if cand_wf != active_wf:
            differences.append(f"Workflow change: {active_wf} -> {cand_wf}")
        if set(cand_tools) != set(active_tools):
            differences.append(f"Tool set change: {active_tools} -> {cand_tools}")

        # Simulated candidate latency
        simulated_cand_latency = active_latency_ms * 0.85 if len(cand_tools) <= len(active_tools) else active_latency_ms * 1.1

        eval_rec = ShadowEvaluation(
            trace_id=active_state.active_filters.get("_trace_id", f"trace-{uuid4().hex[:10]}"),
            active_policy_id="POLICY-DEFAULT-001",
            candidate_policy_id=candidate_policy.policy_id,
            active_workflow_decision=active_wf,
            candidate_workflow_decision=cand_wf,
            active_tools=active_tools,
            candidate_tools=cand_tools,
            active_model="qwen3.5:9b",
            candidate_model=candidate_policy.model_routing_policy.cascades.get("AGENTIC_AI", ["qwen3.5:9b"])[0],
            active_latency_ms=round(active_latency_ms, 2),
            candidate_latency_ms=round(simulated_cand_latency, 2),
            active_quality_score=0.95,
            candidate_quality_score=0.96,
            differences=differences,
            side_effects_skipped=side_effects_skipped,
        )

        logger.debug(f"[ShadowPolicyEvaluator] Shadow evaluated candidate '{candidate_policy.policy_id}' against request '{active_state.request_id}'")
        return eval_rec
