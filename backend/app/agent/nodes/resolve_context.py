"""ResolveContextNode: Resolves active dataset, domain profile, and entities via Dataset MCP."""
from __future__ import annotations

import logging
from typing import Any
from ...mcp import MCPToolRequest, mcp_gateway
from ..state import HighviewAgentState

logger = logging.getLogger(__name__)


def resolve_context_node(state: HighviewAgentState) -> HighviewAgentState:
    """Queries Dataset MCP to establish domain context and verified scope."""
    dataset_id = state.dataset_id or 99767
    state.dataset_id = dataset_id

    req = MCPToolRequest(
        tool_name="get_dataset_profile",
        dataset_id=dataset_id,
        arguments={"dataset_id": dataset_id},
        caller="hriday_orchestrator",
    )
    res = mcp_gateway.execute(req)
    if res.success:
        domain = res.result.get("domain", "general")
        state.active_filters["domain"] = domain
        logger.debug(f"[ResolveContextNode] Resolved dataset {dataset_id} domain: {domain}")
    else:
        logger.warning(f"[ResolveContextNode] Profile resolution failed: {res.error_message}")

    return state
