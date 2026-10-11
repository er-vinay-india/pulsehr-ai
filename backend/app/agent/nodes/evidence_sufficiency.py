"""EvidenceSufficiencyNode: Evaluates whether gathered evidence satisfies the analytical contract."""
from __future__ import annotations

import logging
from typing import Any
from ..state import HighviewAgentState

logger = logging.getLogger(__name__)


def evaluate_evidence_sufficiency(state: HighviewAgentState) -> bool:
    """Evaluates whether state contains sufficient verified evidence for its declared intent."""
    intent = state.intent
    tools_called = [t.get("tool_name") for t in state.tool_history if t.get("success")]

    if intent == "MULTI_STEP_ANALYSIS":
        # Requires multi-dimensional evidence (e.g. comparison + correlation)
        has_comparison = any(t in tools_called for t in ["compare_segments", "rank_entities"])
        has_relationship = "analyze_relationship" in tools_called
        return (has_comparison and has_relationship and len(state.evidence_ids) >= 1)

    elif intent == "SCENARIO_ANALYSIS":
        # Requires scenario execution and non-empty scenario_ids
        return ("run_counterfactual" in tools_called and len(state.scenario_ids) >= 1)

    elif intent == "PRESENTATION_CREATION":
        # Requires deck creation tool execution
        return "create_deck" in tools_called

    elif intent in ("RANKING", "COMPARISON", "TREND", "RELATIONSHIP", "DATA_LOOKUP"):
        # Single verified analytical call is sufficient
        return len(tools_called) >= 1

    return len(tools_called) >= 1


def evidence_sufficiency_node(state: HighviewAgentState) -> HighviewAgentState:
    """Evaluates sufficiency and annotates state."""
    is_sufficient = evaluate_evidence_sufficiency(state)
    state.active_filters["sufficiency"] = "SUFFICIENT" if is_sufficient else "NEEDS_MORE_DATA"
    logger.debug(f"[EvidenceSufficiencyNode] Intent '{state.intent}' sufficiency: {state.active_filters['sufficiency']}")
    return state
