"""ApprovalNode: Handles human-in-the-loop pauses for CRITICAL risk actions."""
from __future__ import annotations

import logging
from typing import Any
from ...mcp import ToolRiskLevel, mcp_registry
from ..graph import GraphInterrupt
from ..state import HighviewAgentState

logger = logging.getLogger(__name__)


def approval_node(state: HighviewAgentState) -> HighviewAgentState:
    """Evaluates whether the next action requires human sign-off and raises GraphInterrupt if so."""
    candidate_tool = state.active_filters.get("_candidate_tool")
    candidate_args = state.active_filters.get("_candidate_args", {})

    requires_approval = False
    action_name = candidate_tool or "critical_action"

    if candidate_tool:
        tool_entry = mcp_registry.get_tool(candidate_tool)
        if tool_entry:
            defn, _ = tool_entry
            if defn.risk_level == ToolRiskLevel.CRITICAL or defn.requires_human_approval:
                requires_approval = True

    # Check state flag override
    if state.active_filters.get("requires_approval"):
        requires_approval = True

    if requires_approval and not state.active_filters.get("_approval_granted"):
        state.workflow_status = "REVIEW_REQUIRED"
        state.pending_approval = {
            "action": action_name,
            "arguments": candidate_args,
            "risk_level": ToolRiskLevel.CRITICAL.value,
            "reason": f"Execution of high-impact action '{action_name}' requires human confirmation.",
        }
        logger.info(f"[ApprovalNode] Action '{action_name}' requires approval. Interrupting graph.")
        raise GraphInterrupt(state, reason=f"Human approval required for '{action_name}'")

    return state
