"""PresentationCreationWorkflow: Grounded slide deck creation workflow."""
from __future__ import annotations

from ..graph import CompiledGraph, StateGraph, START, END
from ..nodes import (
    classify_intent_node,
    compose_response_node,
    execute_tool_node,
    governance_check_node,
    plan_tools_node,
    presentation_node,
    resolve_context_node,
)
from ..state import HighviewAgentState


def build_presentation_creation_graph() -> CompiledGraph:
    """Builds compiled StateGraph for evidence-grounded executive deck generation."""
    graph = StateGraph(HighviewAgentState)

    graph.add_node("resolve_context", resolve_context_node)
    graph.add_node("classify_intent", classify_intent_node)
    graph.add_node("governance_check", governance_check_node)
    graph.add_node("plan_tools", plan_tools_node)
    graph.add_node("execute_tool", execute_tool_node)
    graph.add_node("presentation", presentation_node)
    graph.add_node("compose_response", compose_response_node)

    graph.add_edge(START, "resolve_context")
    graph.add_edge("resolve_context", "classify_intent")
    graph.add_edge("classify_intent", "governance_check")

    def route_governance(state: HighviewAgentState) -> str:
        if state.workflow_status == "DENIED":
            return "compose_response"
        return "plan_tools"

    graph.add_conditional_edges("governance_check", route_governance)
    graph.add_edge("plan_tools", "execute_tool")
    graph.add_edge("execute_tool", "presentation")
    graph.add_edge("presentation", "compose_response")
    graph.add_edge("compose_response", END)

    return graph.compile()
