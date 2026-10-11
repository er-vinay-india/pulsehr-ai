"""GovernanceCheckNode: Pre-flight dataset scope and entitlement verification."""
from __future__ import annotations

import logging
from typing import Any
from ...mcp import MCPToolRequest, mcp_gateway
from ..state import HighviewAgentState

logger = logging.getLogger(__name__)


def governance_check_node(state: HighviewAgentState) -> HighviewAgentState:
    """Evaluates dataset isolation and caller entitlement constraints before analytical execution."""
    dataset_id = state.dataset_id or 99767
    caller = state.active_filters.get("caller", "hriday")

    # 1. Dataset Scope Check
    scope_req = MCPToolRequest(
        tool_name="check_dataset_scope",
        dataset_id=dataset_id,
        arguments={
            "active_dataset_id": dataset_id,
            "requested_dataset_id": dataset_id,
            "allow_cross_dataset": False,
        },
        caller=caller,
    )
    scope_res = mcp_gateway.execute(scope_req)
    if not scope_res.success or not scope_res.result.get("in_scope", True) or scope_res.result.get("violation_detected", False):
        state.workflow_status = "DENIED"
        reason = scope_res.result.get("reason") or scope_res.error_message or "Cross-dataset leakage detected"
        state.error = f"Dataset scope violation: {reason}"
        state.final_answer = f"Access denied: Dataset {dataset_id} failed isolation governance."
        return state

    # 2. Entitlement Check for current intent/operation
    capability = state.intent.lower()
    # If the user query is about scenario/salary/mutation, ensure capability reflects it
    query_lower = state.user_query.lower()
    if any(k in query_lower for k in ["simulate", "counterfactual", "scenario", "salary"]):
        capability = "scenario_mutation"

    entitlement_req = MCPToolRequest(
        tool_name="check_entitlement",
        dataset_id=dataset_id,
        arguments={"caller": caller, "requested_capability": capability, "dataset_id": dataset_id},
        caller=caller,
    )
    ent_res = mcp_gateway.execute(entitlement_req)
    if not ent_res.success or not ent_res.result.get("allowed", True):
        reason = ent_res.result.get("rejection_reason", "Caller unauthorized for capability.")
        state.workflow_status = "DENIED"
        state.error = reason
        state.final_answer = f"Access denied: {reason}"
        logger.warning(f"[GovernanceCheckNode] Caller '{caller}' denied for capability '{capability}': {reason}")
        return state

    logger.debug(f"[GovernanceCheckNode] Governance checks passed for dataset {dataset_id}, caller '{caller}'")
    return state
