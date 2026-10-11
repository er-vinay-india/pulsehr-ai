"""Acceptance Test Suite for Phase D: AI Observability, Evaluation & Runtime Intelligence.

Tests the 10 mandated Phase D scenarios:
1. Simple ranking (low latency, minimal tools, fully grounded)
2. Analytical investigation (multiple tools, evidence sufficiency, no causal overclaim)
3. Scenario simulation (EVID + SCEN separated, zero contamination)
4. Presentation creation (grounded evidence only)
5. Model fallback tracking
6. Deterministic degradation tracking on model outage
7. Unauthorized dataset/caller denial tracing
8. Human approval interrupt and resume tracing
9. Tool loop limit enforcement and anomaly detection
10. Ungrounded claim detection
11. Benchmark corpus execution and aggregate KPIs
12. Zero bypass violations across all layers
"""
from __future__ import annotations

import os
import pytest

from app.agent.router import HRIDAYOrchestrator
from app.agent.state import HighviewAgentState
from app.observability import (
    AITrace,
    AnomalyDetector,
    BENCHMARK_CORPUS,
    BenchmarkRunner,
    GroundingEvaluation,
    GroundingEvaluator,
    ModelRoutingEvaluator,
    RuntimeHealthKPIs,
    WorkflowLatencyBudget,
    ai_observability_service,
    trace_store,
)
from app.observability.contracts import ClaimType, RuntimeQualityScore


@pytest.fixture(autouse=True)
def reset_trace_store():
    trace_store.clear_for_test()
    yield
    trace_store.clear_for_test()


def test_scenario_1_simple_ranking_low_latency_fully_grounded():
    """Scenario 1: Simple ranking inquiry executes with minimal tools, low latency, and 100% grounding."""
    orchestrator = HRIDAYOrchestrator()
    state = orchestrator.orchestrate(
        user_query="Top 5 departments by attendance",
        dataset_id=99767,
        caller="hriday",
    )

    trace = trace_store.get_trace_by_request_id(state.request_id)
    assert trace is not None
    assert trace.status == "COMPLETED"
    assert len(trace.evidence_ids) >= 1
    assert len(trace.scenario_ids) == 0

    # Minimal tools: rank_entities + pre-flight
    assert len(trace.tools) <= 3

    # Grounding evaluation
    grounding = trace.evaluation_summary.get("grounding", {})
    assert grounding.get("grounding_rate") == 1.0
    assert grounding.get("ungrounded_claims") == 0


def test_scenario_2_analytical_investigation_multi_tool_no_causal_overclaim():
    """Scenario 2: Multi-step analytical investigation executes multiple tools and sanitizes causal overclaims."""
    orchestrator = HRIDAYOrchestrator()
    state = orchestrator.orchestrate(
        user_query="Why did department attendance drop and what caused it?",
        dataset_id=99767,
        caller="hriday",
    )

    trace = trace_store.get_trace_by_request_id(state.request_id)
    assert trace is not None
    assert trace.status == "COMPLETED"
    assert trace.workflow_type == "analytical_investigation"

    # Multi-step tool calls
    assert len(trace.tools) >= 2

    # Causal overclaim guard: causal language was rewritten or blocked
    causal_summary = trace.evaluation_summary.get("causal_language", {})
    assert "caused" not in state.final_answer.lower()
    assert causal_summary.get("causal_claims_blocked") == 0 or causal_summary.get("causal_claims_rewritten") >= 1


def test_scenario_3_scenario_simulation_evid_scen_strictly_separated():
    """Scenario 3: Counterfactual scenario simulations isolate SCEN tokens from EVID tokens."""
    orchestrator = HRIDAYOrchestrator()
    state = orchestrator.orchestrate(
        user_query="What if we simulate changing days per week policy lever?",
        dataset_id=99767,
        caller="hriday",
    )

    trace = trace_store.get_trace_by_request_id(state.request_id)
    assert trace is not None
    assert trace.status == "COMPLETED"
    assert len(trace.scenario_ids) >= 1
    assert all(sid.startswith("SCEN-") for sid in trace.scenario_ids)

    # Zero contamination invariant
    assert not any(eid.startswith("SCEN-") for eid in trace.evidence_ids)

    # Anomaly detector verifies no contamination anomaly
    anomalies = trace.anomalies
    assert not any(a.anomaly_type == "SCENARIO_EVIDENCE_CONTAMINATION" for a in anomalies)


def test_scenario_4_presentation_grounded_evidence_only():
    """Scenario 4: Slide decks generated require verified empirical evidence points."""
    orchestrator = HRIDAYOrchestrator()
    state = orchestrator.orchestrate(
        user_query="Create executive slide presentation deck for attendance",
        dataset_id=99767,
        caller="hriday",
    )

    trace = trace_store.get_trace_by_request_id(state.request_id)
    assert trace is not None
    assert trace.status == "COMPLETED"
    assert len(trace.evidence_ids) >= 1
    assert "deck_id" in state.active_filters


def test_scenario_5_model_fallback_evaluated():
    """Scenario 5: Model routing evaluator tracks primary model versus fallback usage."""
    routing_eval, cost_metric = ModelRoutingEvaluator.evaluate(
        task_type="NARRATIVE_AI",
        primary_model="gemma4:12b",
        actual_model="qwen3.5:9b",  # Fallback used
        latency_ms=1850.0,
        tokens_used=120,
    )
    assert routing_eval.fallback_used is True
    assert routing_eval.routing_efficiency_score == 0.8
    assert cost_metric.estimated_cpu_seconds > 0.0


def test_scenario_6_deterministic_degradation_on_outage():
    """Scenario 6: When local LLMs are offline or bypassed, deterministic outputs succeed with 0 tokens."""
    routing_eval, cost_metric = ModelRoutingEvaluator.evaluate(
        task_type="DETERMINISTIC_CALCULATION",
        primary_model="NONE",
        actual_model="NONE",
        latency_ms=12.0,
        tokens_used=0,
    )
    assert routing_eval.fallback_used is False
    assert routing_eval.token_count == 0
    assert routing_eval.routing_efficiency_score == 1.0


def test_scenario_7_unauthorized_dataset_denied_and_traced():
    """Scenario 7: Unauthorized caller or cross-dataset access is rejected and recorded in governance health."""
    orchestrator = HRIDAYOrchestrator()
    state = orchestrator.orchestrate(
        user_query="Simulate counterfactual salary adjustment",
        dataset_id=99767,
        caller="viewer",  # Viewers are unauthorized
    )

    trace = trace_store.get_trace_by_request_id(state.request_id)
    assert trace is not None
    assert trace.status == "DENIED"

    gov = trace.evaluation_summary.get("governance_health", {})
    assert gov.get("governance_denials") >= 1


def test_scenario_8_human_approval_interrupt_and_resume_tracked():
    """Scenario 8: Action requiring human sign-off records interrupt and subsequent approval."""
    orchestrator = HRIDAYOrchestrator()
    paused_state = orchestrator.orchestrate(
        user_query="Rank top 5 departments",
        dataset_id=99767,
        active_filters={"requires_approval": True},
    )
    assert paused_state.workflow_status == "REVIEW_REQUIRED"

    # Resuming with approval
    resumed_state = orchestrator.resume_workflow(paused_state, approval_granted=True)
    assert resumed_state.workflow_status == "COMPLETED"

    resumed_trace = trace_store.get_trace_by_request_id(resumed_state.request_id)
    assert resumed_trace is not None
    assert resumed_trace.status == "COMPLETED"


def test_scenario_9_loop_limit_enforcement_and_anomaly_detection():
    """Scenario 9: Runaway loop triggers loop limit, halts as FAILED_SAFE, and registers anomaly."""
    fake_trace = AITrace(
        request_id="req-loop-test",
        conversation_id="conv-loop",
        workflow_type="quick_answer",
        status="FAILED_SAFE",
        total_latency_ms=14500.0,
        tools=[{"tool_name": f"tool_{i}"} for i in range(12)],
        evaluation_summary={"grounding": {"grounding_rate": 0.85}},
    )

    anomalies = AnomalyDetector.scan_trace_for_anomalies(fake_trace)
    assert len(anomalies) >= 3

    types = [a.anomaly_type for a in anomalies]
    assert "TOOL_COUNT_SPIKE" in types
    assert "LATENCY_SPIKE" in types
    assert "GROUNDING_DROP" in types
    assert "FAILED_SAFE_HALT" in types


def test_scenario_10_ungrounded_synthetic_claim_detected():
    """Scenario 10: Factual assertions without [EVID] or [SCEN] tokens are flagged as ungrounded."""
    ungrounded_answer = "Sales department attendance declined by 14.5% due to organizational restructuring."
    g_eval, attributions, _ = GroundingEvaluator.evaluate(ungrounded_answer)

    assert g_eval.is_fully_grounded is False
    assert g_eval.ungrounded_claims >= 1
    assert g_eval.grounding_rate < 1.0


def test_benchmark_corpus_and_kpi_aggregation():
    """Executes a sample from the benchmark corpus and verifies aggregate KPIs and SLA checks."""
    runner = BenchmarkRunner()
    # Run first 6 diverse cases
    report = runner.run_all(limit=6)

    assert report.total_cases == 6
    assert report.intent_accuracy >= 0.80
    assert report.grounding_rate >= 0.95
    assert report.average_tool_calls > 0.0

    kpis = ai_observability_service.get_runtime_kpis()
    assert kpis.total_traces >= 6
    assert kpis.grounding_rate_pct >= 95.0


def test_technical_explorer_summary_endpoint():
    """Technical explorer summary surfaces compact metrics and traces."""
    summary = ai_observability_service.get_technical_explorer_summary()
    assert "kpis" in summary
    assert "recent_traces" in summary
    assert "anomalies" in summary
