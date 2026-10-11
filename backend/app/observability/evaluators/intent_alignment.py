"""AgentIntentAlignmentEvaluator: Evaluates intent detection and workflow/tool alignment (Phase D)."""
from __future__ import annotations

import logging
from typing import Any
from ..contracts import IntentAlignmentEvaluation

logger = logging.getLogger(__name__)

INTENT_OPTIMAL_TOOLS: dict[str, list[str]] = {
    "DATA_LOOKUP": ["get_schema", "calculate_distribution"],
    "RANKING": ["rank_entities", "verify_claim"],
    "COMPARISON": ["compare_segments", "verify_claim"],
    "TREND": ["get_trend", "verify_claim"],
    "RELATIONSHIP": ["analyze_relationship", "verify_claim"],
    "SCENARIO_ANALYSIS": ["get_valid_levers", "run_counterfactual", "compare_scenarios"],
    "PRESENTATION_CREATION": ["rank_entities", "create_deck", "generate_visual"],
    "MULTI_STEP_ANALYSIS": ["compare_segments", "analyze_relationship", "verify_claim"],
}

INTENT_OPTIMAL_WORKFLOW: dict[str, str] = {
    "DATA_LOOKUP": "quick_answer",
    "RANKING": "quick_answer",
    "COMPARISON": "quick_answer",
    "TREND": "quick_answer",
    "RELATIONSHIP": "quick_answer",
    "SCENARIO_ANALYSIS": "scenario_analysis",
    "PRESENTATION_CREATION": "presentation_creation",
    "MULTI_STEP_ANALYSIS": "analytical_investigation",
}


class AgentIntentAlignmentEvaluator:
    """Evaluates whether HRIDAY correctly mapped user inquiry to intent, workflow, and tools."""

    @classmethod
    def evaluate(
        cls,
        detected_intent: str,
        workflow_selected: str,
        tools_selected: list[str],
        expected_intent: str | None = None,
        expected_workflow: str | None = None,
        expected_tools: list[str] | None = None,
    ) -> IntentAlignmentEvaluation:
        exp_intent = expected_intent or detected_intent
        exp_wf = expected_workflow or INTENT_OPTIMAL_WORKFLOW.get(exp_intent, "quick_answer")
        exp_tools = expected_tools or INTENT_OPTIMAL_TOOLS.get(exp_intent, [])

        unnecessary_tools: list[str] = []
        missing_tools: list[str] = []

        # Check intent match
        intent_match = (detected_intent == exp_intent)
        workflow_match = (workflow_selected == exp_wf)

        # Check tool alignment
        allowed_set = set(exp_tools)
        actual_set = set(tools_selected)

        for t in tools_selected:
            if exp_tools and t not in allowed_set and t not in ("get_dataset_profile", "check_dataset_scope", "check_entitlement"):
                unnecessary_tools.append(t)

        for t in exp_tools:
            if t not in actual_set and exp_intent == detected_intent:
                # Essential tools missing
                if t in ("rank_entities", "run_counterfactual", "create_deck"):
                    missing_tools.append(t)

        # Calculate score
        score = 1.0
        if not intent_match:
            score -= 0.4
        if not workflow_match:
            score -= 0.3
        if unnecessary_tools:
            score -= min(0.2, len(unnecessary_tools) * 0.1)
        if missing_tools:
            score -= min(0.2, len(missing_tools) * 0.1)

        alignment_score = max(0.0, min(1.0, round(score, 3)))

        return IntentAlignmentEvaluation(
            detected_intent=detected_intent,
            expected_intent=exp_intent,
            workflow_selected=workflow_selected,
            expected_workflow=exp_wf,
            tools_selected=tools_selected,
            expected_tools=exp_tools,
            alignment_score=alignment_score,
            unnecessary_tools=unnecessary_tools,
            missing_tools=missing_tools,
        )
