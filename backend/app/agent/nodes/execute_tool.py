"""ExecuteToolNode: Dispatches MCP tool calls strictly through GovernedMCPGateway."""
from __future__ import annotations

import logging
from typing import Any
from ...mcp import MCPToolRequest, mcp_gateway
from ..state import HighviewAgentState

logger = logging.getLogger(__name__)


def execute_tool_node(
    state: HighviewAgentState,
    tool_name_override: str | None = None,
    args_override: dict[str, Any] | None = None,
) -> HighviewAgentState:
    """Executes planned or specified MCP tool and updates pointer state."""
    tool_name = tool_name_override or state.active_filters.pop("_candidate_tool", None)
    args = args_override or state.active_filters.pop("_candidate_args", {})

    if not tool_name:
        logger.debug("[ExecuteToolNode] No tool scheduled to execute.")
        return state

    dataset_id = state.dataset_id or args.get("dataset_id") or 99767
    caller = state.active_filters.get("caller", "hriday")

    # Invariant: Presentation tools need evidence_ids
    if tool_name == "create_deck" and "evidence_ids" not in args:
        args["evidence_ids"] = state.evidence_ids

    req = MCPToolRequest(
        tool_name=tool_name,
        dataset_id=dataset_id,
        arguments=args,
        caller=caller,
    )

    res = mcp_gateway.execute(req)

    # 1. Record tool execution in history
    history_entry = {
        "tool_name": tool_name,
        "arguments": args,
        "success": res.success,
        "execution_id": res.execution_id,
        "evidence_ids": res.evidence_ids,
        "governance_status": res.governance_status.value,
        "error_message": res.error_message,
        "result_summary": {k: type(v).__name__ for k, v in res.result.items()} if res.result else {},
    }
    state.tool_history.append(history_entry)

    if not res.success:
        logger.warning(f"[ExecuteToolNode] Tool '{tool_name}' failed: {res.error_message}")
        state.error = res.error_message
        return state

    # 2. Update pointer IDs with strict mathematical/evidence isolation
    for eid in res.evidence_ids:
        if eid not in state.evidence_ids and not eid.startswith("SCEN-"):
            state.evidence_ids.append(eid)

    for pid in res.provenance_ids:
        if pid not in state.provenance_ids:
            state.provenance_ids.append(pid)

    # Scenario IDs separation
    if res.result:
        scen_id = res.result.get("scenario_id")
        if scen_id and scen_id not in state.scenario_ids:
            state.scenario_ids.append(scen_id)

        # In case tool returned a list of items or comparisons with scenario identifiers
        items = res.result.get("items") or []
        for item in items:
            if isinstance(item, dict) and "scenario_id" in item:
                sid = item["scenario_id"]
                if sid not in state.scenario_ids:
                    state.scenario_ids.append(sid)

    logger.debug(
        f"[ExecuteToolNode] Tool '{tool_name}' completed. "
        f"Evid count: {len(state.evidence_ids)}, Scen count: {len(state.scenario_ids)}"
    )
    return state
