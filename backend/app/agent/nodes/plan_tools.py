"""PlanToolsNode: Deterministically selects candidate MCP tools or routes complex planning via ModelGateway."""
from __future__ import annotations

import logging
from typing import Any
from ...services.gateway.contracts import AIRequest, AITaskType
from ...services.gateway.model_gateway import ModelGateway
from ..guards import evaluate_loop_guards
from ..state import HighviewAgentState

logger = logging.getLogger(__name__)


def plan_next_tool(state: HighviewAgentState) -> tuple[str | None, dict[str, Any]]:
    """Determines the next MCP tool to execute based on intent and execution history."""
    executed_tools = [entry.get("tool_name") for entry in state.tool_history]
    dataset_id = state.dataset_id or 99767
    entity = state.selected_entities[0] if state.selected_entities else "department"
    measure = state.selected_measures[0] if state.selected_measures else "attendance"

    intent = state.intent

    if intent == "RANKING":
        if "rank_entities" not in executed_tools:
            return "rank_entities", {
                "dataset_id": dataset_id,
                "entity_dimension": entity,
                "measure": measure,
                "limit": 5,
                "direction": "desc",
            }

    elif intent == "COMPARISON":
        if "compare_segments" not in executed_tools:
            return "compare_segments", {
                "dataset_id": dataset_id,
                "dimension": entity,
                "measure": measure,
                "segment_a": "Engineering",
                "segment_b": "Sales",
            }

    elif intent == "TREND":
        if "get_trend" not in executed_tools:
            return "get_trend", {
                "dataset_id": dataset_id,
                "time_dimension": "date",
                "measure": measure,
            }

    elif intent == "RELATIONSHIP":
        if "analyze_relationship" not in executed_tools:
            measure_x = measure
            measure_y = "leave" if measure == "attendance" else "attendance"
            return "analyze_relationship", {
                "dataset_id": dataset_id,
                "measure_x": measure_x,
                "measure_y": measure_y,
            }

    elif intent == "SCENARIO_ANALYSIS":
        if "get_valid_levers" not in executed_tools:
            return "get_valid_levers", {"dataset_id": dataset_id}
        if "run_counterfactual" not in executed_tools:
            return "run_counterfactual", {
                "dataset_id": dataset_id,
                "levers": {"days_per_week": 4.0},
            }

    elif intent == "PRESENTATION_CREATION":
        if not state.evidence_ids and "rank_entities" not in executed_tools:
            # Need at least one verified evidence item first
            return "rank_entities", {
                "dataset_id": dataset_id,
                "entity_dimension": entity,
                "measure": measure,
                "limit": 5,
                "direction": "desc",
            }
        if "create_deck" not in executed_tools:
            return "create_deck", {
                "dataset_id": dataset_id,
                "evidence_ids": state.evidence_ids,
                "title_override": f"Executive Review: {measure.capitalize()} by {entity.capitalize()}",
            }

    elif intent == "MULTI_STEP_ANALYSIS":
        # Step 1: compare segments / identify variance
        if "compare_segments" not in executed_tools:
            return "compare_segments", {
                "dataset_id": dataset_id,
                "dimension": entity,
                "measure": measure,
                "segment_a": "Engineering",
                "segment_b": "Sales",
            }
        # Step 2: analyze relationship with potential co-factor
        if "analyze_relationship" not in executed_tools:
            return "analyze_relationship", {
                "dataset_id": dataset_id,
                "measure_x": measure,
                "measure_y": "leave" if measure == "attendance" else "attendance",
            }
        # Step 3: verify synthesized claim
        if "verify_claim" not in executed_tools and state.evidence_ids:
            return "verify_claim", {
                "dataset_id": dataset_id,
                "claim_text": f"Attendance variation across {entity}s is associated with leave patterns.",
            }

    elif intent == "DATA_LOOKUP":
        if "calculate_distribution" not in executed_tools:
            return "calculate_distribution", {
                "dataset_id": dataset_id,
                "measure": measure,
            }

    # No further tools planned
    return None, {}


def plan_tools_node(state: HighviewAgentState) -> HighviewAgentState:
    """Plans next candidate tool and verifies execution loop limits."""
    candidate_tool, candidate_args = plan_next_tool(state)

    if candidate_tool:
        is_valid, violation = evaluate_loop_guards(state, candidate_tool=candidate_tool)
        if not is_valid:
            logger.warning(f"[PlanToolsNode] Loop guard triggered: {violation}")
            state.workflow_status = "FAILED_SAFE"
            state.error = violation
            return state

        # Store candidate plan in state active_filters for execution node
        state.active_filters["_candidate_tool"] = candidate_tool
        state.active_filters["_candidate_args"] = candidate_args
    else:
        state.active_filters.pop("_candidate_tool", None)
        state.active_filters.pop("_candidate_args", None)

    return state
