"""Loop limits, safety guards, and causal language checks for HRIDAY workflows (Phase C).

Enforces:
1. Hard loop boundaries:
   - max_graph_steps = 12
   - max_tool_calls = 10
   - max_same_tool_calls = 3
   - max_retries_per_node = 2
2. CausalLanguageGuard: Prohibits claiming causation ("caused", "drove", "triggered")
   when evidence only supports statistical association ("associated with").
"""
from __future__ import annotations

import re
from typing import Any
from .state import HighviewAgentState

PROHIBITED_CAUSAL_VERBS = [
    "caused", "resulted from", "drove the decline of", "responsible for", "leads to", "triggered"
]


class WorkflowLoopLimits:
    """Hard upper bounds preventing infinite agent loops and excessive execution."""
    MAX_GRAPH_STEPS = 16
    MAX_TOOL_CALLS = 10
    MAX_SAME_TOOL_CALLS = 3
    MAX_RETRIES_PER_NODE = 2


def evaluate_loop_guards(
    state: HighviewAgentState,
    candidate_tool: str | None = None,
) -> tuple[bool, str | None]:
    """Evaluates whether the agent has hit execution loop limits.

    Returns (is_valid, violation_reason).
    """
    # 1. Total graph steps limit
    if state.step_count >= WorkflowLoopLimits.MAX_GRAPH_STEPS:
        return False, f"Maximum graph steps exceeded ({state.step_count} >= {WorkflowLoopLimits.MAX_GRAPH_STEPS})"

    # 2. Total tool calls limit
    tool_calls_count = len(state.tool_history)
    if tool_calls_count >= WorkflowLoopLimits.MAX_TOOL_CALLS:
        return False, f"Maximum tool calls exceeded ({tool_calls_count} >= {WorkflowLoopLimits.MAX_TOOL_CALLS})"

    # 3. Same tool repetition limit
    if candidate_tool:
        same_tool_count = sum(1 for call in state.tool_history if call.get("tool_name") == candidate_tool)
        if same_tool_count >= WorkflowLoopLimits.MAX_SAME_TOOL_CALLS:
            return False, f"Maximum calls for tool '{candidate_tool}' exceeded ({same_tool_count} >= {WorkflowLoopLimits.MAX_SAME_TOOL_CALLS})"

    return True, None


class CausalLanguageGuard:
    """Ensures claims do not assert causality without experimental/counterfactual proof."""

    @classmethod
    def sanitize_claim(cls, claim_text: str, is_counterfactual_verified: bool = False) -> tuple[str, bool]:
        """Detects and reformulates unjustified causal verbs.

        Returns (sanitized_claim, was_modified).
        """
        if is_counterfactual_verified:
            return claim_text, False

        text_lower = claim_text.lower()
        has_causal = any(re.search(rf"\b{re.escape(w)}\b", text_lower) for w in PROHIBITED_CAUSAL_VERBS)

        if not has_causal:
            return claim_text, False

        # Reformulate causal verbs to associational language
        sanitized = re.sub(
            r"\b(caused|resulted from|drove the decline of|leads to|triggered)\b",
            "was associated with",
            claim_text,
            flags=re.IGNORECASE,
        )
        return sanitized, True
