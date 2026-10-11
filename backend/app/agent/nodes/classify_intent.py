"""ClassifyIntentNode: Maps user query to analytical intent and entity focus."""
from __future__ import annotations

import logging
import re
from typing import Any
from ..state import HighviewAgentState

logger = logging.getLogger(__name__)


def classify_intent_node(state: HighviewAgentState) -> HighviewAgentState:
    """Classifies user intent deterministically from query patterns.

    Supported Intents:
    - DATA_LOOKUP: simple metric / schema query
    - RANKING: top / bottom / best / worst / rank
    - COMPARISON: compare / vs / difference between
    - TREND: historical change / over time / trend
    - RELATIONSHIP: correlation / relationship / association
    - SCENARIO_ANALYSIS: what if / simulate / scenario / policy change
    - PRESENTATION_CREATION: deck / presentation / slides / executive brief
    - MULTI_STEP_ANALYSIS: why / root cause / investigate / explain decline
    """
    query = state.user_query.lower().strip()

    # 1. Check for scenario / counterfactual intent
    if any(k in query for k in ["what if", "scenario", "simulate", "if we change", "if we increase", "if we reduce", "lever"]):
        state.intent = "SCENARIO_ANALYSIS"
    # 2. Check for presentation / deck intent
    elif any(k in query for k in ["deck", "presentation", "slide", "slides", "briefing"]):
        state.intent = "PRESENTATION_CREATION"
    # 3. Check for multi-step / causal diagnostic inquiry
    elif any(k in query for k in ["why", "root cause", "investigate", "explain why", "deep dive", "driver"]):
        state.intent = "MULTI_STEP_ANALYSIS"
    # 4. Check for relationship / correlation
    elif any(k in query for k in ["correlat", "relationship", "associated with", "link between"]):
        state.intent = "RELATIONSHIP"
    # 5. Check for comparison
    elif any(k in query for k in ["compare", " vs ", "versus", "difference between", "against"]):
        state.intent = "COMPARISON"
    # 6. Check for trend
    elif any(k in query for k in ["trend", "over time", "history", "monthly", "weekly", "trajectory"]):
        state.intent = "TREND"
    # 7. Check for ranking
    elif any(k in query for k in ["rank", "top", "bottom", "highest", "lowest", "best", "worst"]):
        state.intent = "RANKING"
    # 8. Default to data lookup
    else:
        state.intent = "DATA_LOOKUP"

    # Extract entities and measures if mentioned
    if "department" in query or "dept" in query:
        if "department" not in state.selected_entities:
            state.selected_entities.append("department")
    if "employee" in query:
        if "employee" not in state.selected_entities:
            state.selected_entities.append("employee")

    if any(k in query for k in ["attendance", "present", "wfo"]):
        if "attendance" not in state.selected_measures:
            state.selected_measures.append("attendance")
    if any(k in query for k in ["leave", "absence", "absent"]):
        if "leave" not in state.selected_measures:
            state.selected_measures.append("leave")
    if any(k in query for k in ["salary", "compensation"]):
        if "salary" not in state.selected_measures:
            state.selected_measures.append("salary")

    logger.debug(f"[ClassifyIntentNode] Query '{state.user_query}' classified as '{state.intent}'")
    return state
