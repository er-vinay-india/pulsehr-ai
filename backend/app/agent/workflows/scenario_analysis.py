"""ScenarioAnalysisWorkflow: Counterfactual policy simulation workflow."""
from __future__ import annotations

from ..graph import CompiledGraph, StateGraph, START, END
from ..nodes import (
    classify_intent_node,
    compose_response_node,
    governance_check_node,
    resolve_context_node,
    scenario_node,
)
from ..state import HighviewAgentState


def build_scenario_analysis_graph() -> CompiledGraph:
    """Builds compiled StateGraph for policy simulation and counterfactual projections."""
    graph = StateGraph(HighviewAgentState)

    graph.add_node("resolve_context", resolve_context_node)
    graph.add_node("classify_intent", classify_intent_node)
    graph.add_node("governance_check", governance_check_node)
    graph.add_node("scenario", scenario_node)
    graph.add_node("compose_response", compose_response_node)

    graph.add_edge(START, "resolve_context")
    graph.add_edge("resolve_context", "classify_intent")
    graph.add_edge("classify_intent", "governance_check")

    def route_governance(state: HighviewAgentState) -> str:
        if state.workflow_status == "DENIED":
            return "compose_response"
        return "scenario"

    graph.add_conditional_edges("governance_check", route_governance)
    graph.add_edge("scenario", "compose_response")
    graph.add_edge("compose_response", END)

    return graph.compile()
