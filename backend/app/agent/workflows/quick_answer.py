"""QuickAnswerWorkflow: Fast-path execution for direct analytical questions."""
from __future__ import annotations

from ..graph import CompiledGraph, StateGraph, START, END
from ..nodes import (
    approval_node,
    classify_intent_node,
    compose_response_node,
    execute_tool_node,
    governance_check_node,
    plan_tools_node,
    resolve_context_node,
)
from ..state import HighviewAgentState


def build_quick_answer_graph() -> CompiledGraph:
    """Builds the compiled StateGraph for fast-path single-turn analytical queries."""
    graph = StateGraph(HighviewAgentState)

    graph.add_node("resolve_context", resolve_context_node)
    graph.add_node("classify_intent", classify_intent_node)
    graph.add_node("governance_check", governance_check_node)
    graph.add_node("plan_tools", plan_tools_node)
    graph.add_node("approval", approval_node)
    graph.add_node("execute_tool", execute_tool_node)
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
    graph.add_edge("execute_tool", "compose_response")
    graph.add_edge("compose_response", END)

    return graph.compile()
