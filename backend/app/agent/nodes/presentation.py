"""PresentationNode: Builds grounded executive decks via Presentation MCP and ModelGateway."""
from __future__ import annotations

import logging
from typing import Any
from ...mcp import MCPToolRequest, mcp_gateway
from ...services.gateway.contracts import AIRequest, AITaskType
from ...services.gateway.model_gateway import ModelGateway
from ..state import HighviewAgentState

logger = logging.getLogger(__name__)


def presentation_node(state: HighviewAgentState) -> HighviewAgentState:
    """Creates executive presentations grounded strictly in verified evidence."""
    dataset_id = state.dataset_id or 99767
    caller = state.active_filters.get("caller", "hriday")

    # Invariant: Presentation requires verified evidence
    if not state.evidence_ids:
        state.workflow_status = "PARTIAL"
        state.error = "Cannot construct presentation deck: zero verified evidence points available."
        state.final_answer = "Presentation creation requires verified empirical evidence before generating slides."
        return state

    # 1. Dispatch deck creation via Presentation MCP
    deck_req = MCPToolRequest(
        tool_name="create_deck",
        dataset_id=dataset_id,
        arguments={
            "dataset_id": dataset_id,
            "evidence_ids": state.evidence_ids,
            "title_override": f"Strategic Executive Briefing ({len(state.evidence_ids)} Findings)",
        },
        caller=caller,
    )
    deck_res = mcp_gateway.execute(deck_req)

    state.tool_history.append({
        "tool_name": "create_deck",
        "arguments": {"evidence_ids": state.evidence_ids},
        "success": deck_res.success,
        "execution_id": deck_res.execution_id,
    })

    if not deck_res.success:
        state.workflow_status = "PARTIAL"
        state.error = deck_res.error_message
        return state

    deck_id = deck_res.result.get("deck_id")
    state.active_filters["deck_id"] = deck_id

    # 2. Refine executive slide headline via ModelGateway (PRESENTATION_AI task type)
    headline_prompt = f"Summarize key takeaway for deck {deck_id} covering {len(state.evidence_ids)} evidence points."
    ai_req = AIRequest(
        task_type=AITaskType.PRESENTATION_AI,
        prompt=headline_prompt,
        dataset_id=dataset_id,
        correlation_id=state.request_id,
    )
    ai_res = ModelGateway.execute(ai_req)
    state.active_filters["executive_headline"] = ai_res.raw_text

    logger.debug(f"[PresentationNode] Deck created: {deck_id} with headline: {ai_res.raw_text}")
    return state
