"""ScenarioNode: Executes counterfactual simulations strictly via Scenario MCP."""
from __future__ import annotations

import logging
from typing import Any
from ...mcp import MCPToolRequest, mcp_gateway
from ..state import HighviewAgentState

logger = logging.getLogger(__name__)


def scenario_node(state: HighviewAgentState) -> HighviewAgentState:
    """Executes counterfactual scenario simulation and isolates outputs from empirical evidence."""
    dataset_id = state.dataset_id or 99767
    caller = state.active_filters.get("caller", "hriday")

    # 1. Discover valid levers
    levers_req = MCPToolRequest(
        tool_name="get_valid_levers",
        dataset_id=dataset_id,
        arguments={"dataset_id": dataset_id},
        caller=caller,
    )
    levers_res = mcp_gateway.execute(levers_req)

    if not levers_res.success:
        state.workflow_status = "PARTIAL"
        state.error = levers_res.error_message
        return state

    valid_levers = levers_res.result.get("valid_levers") or levers_res.result.get("levers") or []
    if not valid_levers:
        state.workflow_status = "DENIED"
        state.error = f"Dataset {dataset_id} is not entitled for scenario policy simulation."
        state.final_answer = "Scenario simulation denied: this dataset domain does not support policy levers."
        return state

    selected_lever = valid_levers[0]["lever_id"] if isinstance(valid_levers[0], dict) else valid_levers[0].lever_id

    # 2. Run counterfactual simulation
    sim_req = MCPToolRequest(
        tool_name="run_counterfactual",
        dataset_id=dataset_id,
        arguments={
            "dataset_id": dataset_id,
            "levers": {selected_lever: 4.0},
        },
        caller=caller,
    )
    sim_res = mcp_gateway.execute(sim_req)

    # Record in history
    state.tool_history.append({
        "tool_name": "run_counterfactual",
        "arguments": {"levers": {selected_lever: 4.0}},
        "success": sim_res.success,
        "execution_id": sim_res.execution_id,
    })

    if sim_res.success:
        scen_id = sim_res.result.get("scenario_id")
        if scen_id and scen_id not in state.scenario_ids:
            state.scenario_ids.append(scen_id)

        # Invariant: Verify that NO scenario tokens leaked into evidence_ids
        for eid in list(state.evidence_ids):
            if eid.startswith("SCEN-"):
                state.evidence_ids.remove(eid)

        logger.debug(f"[ScenarioNode] Counterfactual simulation generated scenario: {scen_id}")
    else:
        state.workflow_status = "PARTIAL"
        state.error = sim_res.error_message

    return state
