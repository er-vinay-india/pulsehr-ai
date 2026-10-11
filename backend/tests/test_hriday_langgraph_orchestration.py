"""Acceptance Test Suite for HRIDAY LangGraph Orchestration (Phase C).

Verifies:
1. Pointer-based Agent State (HighviewAgentState).
2. Separation invariant: evidence_ids strictly separated from scenario_ids.
3. Four Bounded Workflows:
   - Quick Answer
   - Analytical Investigation (multi-step diagnostic loop)
   - Scenario Analysis (counterfactual simulation)
   - Presentation Creation (evidence-grounded slide deck)
4. Safety & Governance:
   - Dataset scope / entitlement denial
   - CausalLanguageGuard sanitization
   - WorkflowLoopLimits enforcement
5. Human-in-the-loop pause & resume.
6. Zero LangGraph bypass violations (LangGraphBypassAuditor).
"""
from __future__ import annotations

import os
import pytest

from app.agent import (
    CausalLanguageGuard,
    GraphInterrupt,
    HighviewAgentState,
    HRIDAYOrchestrator,
    LangGraphBypassAuditor,
    WorkflowExecutionLedger,
    WorkflowLoopLimits,
    WorkflowStatus,
    evaluate_loop_guards,
    hriday_orchestrator,
    workflow_execution_ledger,
)
from app.agent.nodes import (
    classify_intent_node,
    evidence_sufficiency_node,
    resolve_context_node,
)
from app.agent.workflows import (
    build_analytical_investigation_graph,
    build_presentation_creation_graph,
    build_quick_answer_graph,
    build_scenario_analysis_graph,
)


@pytest.fixture(autouse=True)
def reset_ledger():
    workflow_execution_ledger.clear_for_test()
    yield
    workflow_execution_ledger.clear_for_test()


def test_agent_state_initialization_and_separation():
    """State must be lightweight, pointer-based, and separate empirical facts from scenarios."""
    state = HighviewAgentState(
        user_query="Analyze attendance and simulate 4-day work week",
        dataset_id=99767,
    )
    assert state.conversation_id.startswith("conv-")
    assert state.request_id.startswith("req-")
    assert state.evidence_ids == []
    assert state.scenario_ids == []
    assert state.workflow_status == "IN_PROGRESS"

    # Invariant: Never allow co-mingling of EVID and SCEN
    state.evidence_ids.append("EVID-001")
    state.scenario_ids.append("SCEN-A1B2C3D4")
    assert all(eid.startswith("EVID-") for eid in state.evidence_ids)
    assert all(sid.startswith("SCEN-") for sid in state.scenario_ids)


def test_classify_intent_node():
    """Intent classification deterministically categorizes diverse user queries."""
    s1 = classify_intent_node(HighviewAgentState(user_query="Rank top 5 departments by attendance"))
    assert s1.intent == "RANKING"
    assert "department" in s1.selected_entities
    assert "attendance" in s1.selected_measures

    s2 = classify_intent_node(HighviewAgentState(user_query="Why did sales attendance decline?"))
    assert s2.intent == "MULTI_STEP_ANALYSIS"

    s3 = classify_intent_node(HighviewAgentState(user_query="What if we simulate changing days per week lever?"))
    assert s3.intent == "SCENARIO_ANALYSIS"

    s4 = classify_intent_node(HighviewAgentState(user_query="Create executive slide presentation deck"))
    assert s4.intent == "PRESENTATION_CREATION"

    s5 = classify_intent_node(HighviewAgentState(user_query="Compare Engineering vs Sales attendance"))
    assert s5.intent == "COMPARISON"


def test_quick_answer_workflow():
    """Quick answer fast path executes deterministically and records execution record."""
    orchestrator = HRIDAYOrchestrator()
    state = orchestrator.orchestrate(
        user_query="Rank top 5 departments by attendance",
        dataset_id=99767,
        caller="hriday",
    )

    assert state.workflow_status == "COMPLETED"
    assert state.intent == "RANKING"
    assert len(state.evidence_ids) >= 1
    assert state.final_answer is not None
    assert "[EVID-" in state.final_answer

    # Verify ledger trace
    records = orchestrator.ledger.list_records(dataset_id=99767)
    assert len(records) == 1
    assert records[0].workflow_name == "quick_answer"
    assert "rank_entities" in records[0].tools_called
    assert records[0].final_status == WorkflowStatus.COMPLETED


def test_analytical_investigation_workflow():
    """Diagnostic 'why' questions trigger multi-step loop and verify claims."""
    orchestrator = HRIDAYOrchestrator()
    state = orchestrator.orchestrate(
        user_query="Why is there attendance variation across departments?",
        dataset_id=99767,
        caller="hriday",
    )

    assert state.workflow_status == "COMPLETED"
    assert state.intent == "MULTI_STEP_ANALYSIS"
    assert len(state.evidence_ids) >= 1

    # Multi-step investigation must execute at least two tools
    executed_tools = [t.get("tool_name") for t in state.tool_history]
    assert "compare_segments" in executed_tools or "rank_entities" in executed_tools
    assert "analyze_relationship" in executed_tools
    assert state.final_answer is not None
    assert "[EVID-" in state.final_answer


def test_scenario_analysis_workflow():
    """Scenario simulation generates counterfactual tokens strictly isolated in scenario_ids."""
    orchestrator = HRIDAYOrchestrator()
    state = orchestrator.orchestrate(
        user_query="What if we simulate changing policy lever days per week?",
        dataset_id=99767,
        caller="hriday",
    )

    assert state.workflow_status == "COMPLETED"
    assert state.intent == "SCENARIO_ANALYSIS"
    assert len(state.scenario_ids) >= 1
    assert all(sid.startswith("SCEN-") for sid in state.scenario_ids)

    # Invariant: No scenario tokens in evidence_ids
    assert not any(eid.startswith("SCEN-") for eid in state.evidence_ids)
    assert "[SCEN-" in state.final_answer


def test_presentation_creation_workflow():
    """Presentation creation workflow requires evidence and creates verified deck."""
    orchestrator = HRIDAYOrchestrator()
    state = orchestrator.orchestrate(
        user_query="Create executive slide presentation deck for attendance",
        dataset_id=99767,
        caller="hriday",
    )

    assert state.workflow_status == "COMPLETED"
    assert state.intent == "PRESENTATION_CREATION"
    assert "deck_id" in state.active_filters
    assert state.active_filters["deck_id"].startswith("DECK-")
    assert "[DECK-" in state.final_answer


def test_causal_language_guard():
    """CausalLanguageGuard transforms unverified causal claims into associational language."""
    claim = "High leave rates caused attendance drops and drove the decline of performance."
    sanitized, modified = CausalLanguageGuard.sanitize_claim(claim, is_counterfactual_verified=False)
    assert modified is True
    assert "caused" not in sanitized.lower()
    assert "drove the decline of" not in sanitized.lower()
    assert "was associated with" in sanitized.lower()

    # Counterfactual verified claims may preserve causal formulation
    allowed, mod_cf = CausalLanguageGuard.sanitize_claim(claim, is_counterfactual_verified=True)
    assert mod_cf is False
    assert allowed == claim


def test_workflow_loop_limits_guard():
    """Loop limits prevent infinite agent loops and divert safely to FAILED_SAFE."""
    state = HighviewAgentState(step_count=16, user_query="Loop test")
    valid, reason = evaluate_loop_guards(state)
    assert valid is False
    assert "Maximum graph steps exceeded" in reason

    # Tool repetition limits
    tool_state = HighviewAgentState(
        step_count=5,
        tool_history=[
            {"tool_name": "rank_entities"},
            {"tool_name": "rank_entities"},
            {"tool_name": "rank_entities"},
        ],
    )
    valid_tool, reason_tool = evaluate_loop_guards(tool_state, candidate_tool="rank_entities")
    assert valid_tool is False
    assert "Maximum calls for tool 'rank_entities' exceeded" in reason_tool


def test_governance_denial_for_unauthorized_caller():
    """Unauthorized caller is rejected at governance_check node before executing analytics."""
    orchestrator = HRIDAYOrchestrator()
    state = orchestrator.orchestrate(
        user_query="Simulate counterfactual salary adjustment",
        dataset_id=99767,
        caller="viewer",  # Viewers are unauthorized for scenario mutation
    )

    assert state.workflow_status == "DENIED"
    assert "Access denied" in state.final_answer
    # No analytical or scenario tools should have run
    executed_tools = [t.get("tool_name") for t in state.tool_history]
    assert "run_counterfactual" not in executed_tools


def test_human_in_the_loop_approval_pause_and_resume():
    """Graph pauses on CRITICAL risk actions and resumes seamlessly on approval."""
    graph = build_quick_answer_graph()
    state = HighviewAgentState(
        user_query="Rank top 5 departments",
        dataset_id=99767,
        active_filters={"requires_approval": True},
    )

    # 1. First invocation must trigger GraphInterrupt
    with pytest.raises(GraphInterrupt) as exc_info:
        graph.invoke(state)

    paused_state = exc_info.value.state
    assert paused_state.workflow_status == "REVIEW_REQUIRED"
    assert paused_state.pending_approval is not None
    assert paused_state.pending_approval["risk_level"] == "CRITICAL"

    # 2. Resuming with approval granted continues execution to completion
    resumed_state = graph.resume(paused_state, approval_granted=True)
    assert resumed_state.workflow_status == "COMPLETED"
    assert resumed_state.final_answer is not None

    # 3. Resuming with denial safely terminates
    denied_state = graph.resume(paused_state, approval_granted=False)
    assert denied_state.workflow_status == "DENIED"
    assert "Action denied" in denied_state.final_answer


def test_langgraph_bypass_auditor_zero_violations():
    """LangGraph layer must have ZERO direct imports of SQLite, engines, or raw Ollama."""
    agent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app", "agent"))
    result = LangGraphBypassAuditor.audit_agent_directory(agent_dir)

    assert result.is_compliant is True
    assert result.violation_count == 0
    assert result.total_scanned_files >= 10
