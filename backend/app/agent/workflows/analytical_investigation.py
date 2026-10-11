"""AnalyticalInvestigationWorkflow: Multi-step investigative loop for diagnostic 'why' questions."""
from __future__ import annotations

from ..graph import CompiledGraph, StateGraph, START, END
from ..nodes import (
    approval_node,
    classify_intent_node,
    compose_response_node,
    evidence_sufficiency_node,
    execute_tool_node,
    governance_check_node,
    plan_tools_node,
    resolve_context_node,
    verify_claim_node,
)
from ..state import HighviewAgentState


def build_analytical_investigation_graph() -> CompiledGraph:
    """Builds compiled StateGraph for multi-step bounded diagnostic investigations."""
    graph = StateGraph(HighviewAgentState)

    graph.add_node("resolve_context", resolve_context_node)
    graph.add_node("classify_intent", classify_intent_node)
    graph.add_node("governance_check", governance_check_node)
    graph.add_node("plan_tools", plan_tools_node)
    graph.add_node("approval", approval_node)
    graph.add_node("execute_tool", execute_tool_node)
    graph.add_node("evidence_sufficiency", evidence_sufficiency_node)
    graph.add_node("verify_claim", verify_claim_node)
    graph.add_node("compose_response", compose_response_node)

    graph.add_edge(START, "resolve_context")
    graph.add_edge("resolve_context", "classify_intent")
    graph.add_edge("classify_intent", "governance_check")

    def route_governance(state: HighviewAgentState) -> str:
        if state.workflow_status == "DENIED":
            return "compose_response"
        return "plan_tools"

    graph.add_conditional_edges("governance_check", route_governance)
    graph.add_edge("plan_tools", "approval")
    graph.add_edge("approval", "execute_tool")
    graph.add_edge("execute_tool", "evidence_sufficiency")

    def route_sufficiency(state: HighviewAgentState) -> str:
        if state.workflow_status in ("DENIED", "FAILED_SAFE"):
            return "compose_response"
        if state.active_filters.get("sufficiency") == "SUFFICIENT":
            return "verify_claim"
        # If candidate tool wasn't found or loop limit reached, break loop
        if not state.active_filters.get("_candidate_tool") and len(state.tool_history) >= 2:
            return "verify_claim"
        return "plan_tools"

    graph.add_conditional_edges("evidence_sufficiency", route_sufficiency)
    graph.add_edge("verify_claim", "compose_response")
    graph.add_edge("compose_response", END)

    return graph.compile()
