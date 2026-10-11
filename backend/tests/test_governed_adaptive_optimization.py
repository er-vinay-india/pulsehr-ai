"""Acceptance test suite for Governed Adaptive Optimization (Phase E).

Verifies the 11 core acceptance criteria:
1. Redundant QuickAnswer tools -> recommendation generated.
2. Slow primary model -> alternate routing candidate created.
3. Faster candidate but grounding drops -> candidate rejected by safety gate.
4. Candidate reduces latency with equal safety -> human review eligible.
5. Candidate fails dataset isolation -> hard reject.
6. Candidate causes EVID/SCEN contamination -> hard reject.
7. Shadow comparison executes -> user sees active result only, no mutations.
8. Human rejects candidate -> active policy unchanged.
9. Human approves candidate -> new immutable policy activated.
10. Rollback -> prior version restored.
11. Policy provenance -> trace records exact policy version.
"""
from __future__ import annotations

import time
import pytest
from uuid import uuid4

from app.agent.state import HighviewAgentState
from app.observability.contracts import AITrace, RuntimeAnomaly
from app.observability.benchmark.runner import BenchmarkReport
from app.optimization import (
    HighviewPolicy,
    OptimizationRecommendation,
    PolicyComparisonResult,
    PolicyStatus,
    RecommendationCategory,
    RiskLevel,
    governed_optimizer,
    policy_registry,
    recommendation_engine,
    rollback_manager,
    PolicyComparator,
    PromotionGate,
)


@pytest.fixture(autouse=True)
def clean_optimization_state():
    """Reset registry and engine between tests."""
    governed_optimizer.clear_for_test()
    yield
    governed_optimizer.clear_for_test()


def test_01_redundant_quick_answer_tools_generates_recommendation():
    """Scenario 1: Traces with excessive QuickAnswer tools emit a WORKFLOW recommendation."""
    traces = []
    for i in range(4):
        t = AITrace(
            request_id=f"req-qa-{i}",
            conversation_id="conv-1",
            workflow_type="quick_answer",
            tools=[
                {"tool_name": "calculate_distribution"},
                {"tool_name": "rank_entities"},
                {"tool_name": "compare_segments"},
                {"tool_name": "get_trend"},
            ],
            total_latency_ms=850.0,
            evaluation_summary={"grounding": {"grounding_rate": 1.0}},
        )
        traces.append(t)

    recs = governed_optimizer.analyze_traces_and_recommend(traces)
    workflow_recs = [r for r in recs if r.category == RecommendationCategory.WORKFLOW]

    assert len(workflow_recs) >= 1
    rec = workflow_recs[0]
    assert rec.current_policy_id == "POLICY-DEFAULT-001"
    assert "prune_unnecessary_preflights" in rec.proposed_policy_delta
    assert rec.benchmark_required is True
    assert rec.human_approval_required is True


def test_02_slow_primary_model_creates_alternate_routing_candidate():
    """Scenario 2: Slow primary model latency emits recommendation and creates candidate."""
    traces = []
    for i in range(3):
        t = AITrace(
            request_id=f"req-model-{i}",
            conversation_id="conv-2",
            workflow_type="analytical_investigation",
            evaluation_summary={
                "model_routing": {
                    "task_type": "AGENTIC_AI",
                    "actual_model": "qwen3.5:9b",
                    "latency_ms": 6200.0,
                    "fallback_used": False,
                },
                "grounding": {"grounding_rate": 1.0},
            },
            total_latency_ms=6200.0,
        )
        traces.append(t)

    recs = governed_optimizer.analyze_traces_and_recommend(traces)
    model_recs = [r for r in recs if r.category == RecommendationCategory.MODEL_ROUTING]

    assert len(model_recs) >= 1
    rec = model_recs[0]
    assert "cascade" in rec.proposed_policy_delta

    candidate = governed_optimizer.create_candidate_from_recommendation(rec)
    assert candidate.status == PolicyStatus.CANDIDATE
    assert candidate.version_number == 2
    assert candidate.parent_policy_id == "POLICY-DEFAULT-001"
    assert candidate.model_routing_policy.cascades["AGENTIC_AI"][0] == "gemma4:12b"


def make_benchmark_report(
    total_cases: int = 10,
    intent_accuracy: float = 1.0,
    workflow_selection_accuracy: float = 1.0,
    grounding_rate: float = 1.0,
    ungrounded_claim_count: int = 0,
    average_tool_calls: float = 2.0,
    average_latency_ms: float = 1200.0,
    p50_latency_ms: float = 1000.0,
    p95_latency_ms: float = 1400.0,
    governance_denial_count: int = 0,
    approval_handling_count: int = 0,
    overall_runtime_quality_score: float = 0.95,
) -> BenchmarkReport:
    return BenchmarkReport(
        total_cases=total_cases,
        intent_accuracy=intent_accuracy,
        workflow_selection_accuracy=workflow_selection_accuracy,
        grounding_rate=grounding_rate,
        ungrounded_claim_count=ungrounded_claim_count,
        average_tool_calls=average_tool_calls,
        average_latency_ms=average_latency_ms,
        p50_latency_ms=p50_latency_ms,
        p95_latency_ms=p95_latency_ms,
        governance_denial_count=governance_denial_count,
        approval_handling_count=approval_handling_count,
        overall_runtime_quality_score=overall_runtime_quality_score,
    )


def test_03_faster_candidate_with_grounding_drop_is_rejected_by_safety_gate():
    """Scenario 3: Faster candidate that drops grounding is strictly rejected by safety gate."""
    active = governed_optimizer.get_active_policy()
    candidate = HighviewPolicy(
        policy_id="POLICY-CANDIDATE-FAST",
        version_number=2,
        status=PolicyStatus.CANDIDATE,
        parent_policy_id=active.policy_id,
    )
    policy_registry.register_candidate(candidate)

    baseline_report = make_benchmark_report(
        total_cases=10,
        overall_runtime_quality_score=0.95,
        average_latency_ms=1200.0,
        average_tool_calls=2.0,
        grounding_rate=1.0,
        ungrounded_claim_count=0,
    )
    # Candidate is 600ms faster, but grounding dropped from 1.0 to 0.90
    candidate_report = make_benchmark_report(
        total_cases=10,
        overall_runtime_quality_score=0.91,
        average_latency_ms=600.0,
        average_tool_calls=1.5,
        grounding_rate=0.90,
        ungrounded_claim_count=2,
    )

    comparison = PolicyComparator.compare_policies(
        baseline_policy=active,
        candidate_policy=candidate,
        baseline_report=baseline_report,
        candidate_report=candidate_report,
    )

    assert comparison.recommendation == "REJECT"
    assert comparison.hard_safety_gates_passed is False
    assert any("ungrounded" in r.lower() for r in comparison.regressions)

    eligible, reason = PromotionGate.evaluate_eligibility(comparison)
    assert eligible is False
    assert "Hard safety gate failed" in reason

    # Attempting to activate candidate must fail
    success, msg = governed_optimizer.approve_and_activate(candidate.policy_id, comparison)
    assert success is False
    assert "refused" in msg.lower() or "safety gate" in msg.lower()


def test_04_candidate_reduces_latency_with_equal_safety_is_review_eligible():
    """Scenario 4: Candidate that reduces latency with 0 safety regressions is eligible for review."""
    active = governed_optimizer.get_active_policy()
    candidate = HighviewPolicy(
        policy_id="POLICY-CANDIDATE-PERF",
        version_number=2,
        status=PolicyStatus.CANDIDATE,
        parent_policy_id=active.policy_id,
    )
    policy_registry.register_candidate(candidate)

    baseline_report = make_benchmark_report(
        total_cases=10,
        overall_runtime_quality_score=0.95,
        average_latency_ms=1500.0,
        average_tool_calls=3.0,
        grounding_rate=1.0,
        ungrounded_claim_count=0,
    )
    candidate_report = make_benchmark_report(
        total_cases=10,
        overall_runtime_quality_score=0.96,
        average_latency_ms=1050.0,  # 450ms faster
        average_tool_calls=2.2,     # fewer tool calls
        grounding_rate=1.0,         # equal grounding
        ungrounded_claim_count=0,
    )

    comparison = PolicyComparator.compare_policies(
        baseline_policy=active,
        candidate_policy=candidate,
        baseline_report=baseline_report,
        candidate_report=candidate_report,
    )

    assert comparison.hard_safety_gates_passed is True
    assert comparison.recommendation == "PROMOTE"
    assert len(comparison.regressions) == 0

    eligible, reason = PromotionGate.evaluate_eligibility(comparison)
    assert eligible is True
    assert "eligible for human review" in reason.lower()


def test_05_candidate_with_dataset_isolation_violation_is_hard_rejected():
    """Scenario 5: Candidate with dataset isolation violation is unconditionally rejected."""
    active = governed_optimizer.get_active_policy()
    candidate = HighviewPolicy(
        policy_id="POLICY-CANDIDATE-ISO-BREACH",
        version_number=2,
        status=PolicyStatus.CANDIDATE,
    )
    policy_registry.register_candidate(candidate)

    base_rep = make_benchmark_report(total_cases=5, grounding_rate=1.0, average_latency_ms=1000.0)
    cand_rep = make_benchmark_report(total_cases=5, grounding_rate=1.0, average_latency_ms=500.0)

    comparison = PolicyComparator.compare_policies(
        baseline_policy=active,
        candidate_policy=candidate,
        baseline_report=base_rep,
        candidate_report=cand_rep,
        safety_override_flags={"dataset_isolation_violations": 1},
    )

    assert comparison.hard_safety_gates_passed is False
    assert comparison.recommendation == "REJECT"
    assert any("dataset isolation violation" in r.lower() for r in comparison.regressions)

    eligible, reason = PromotionGate.evaluate_eligibility(comparison)
    assert eligible is False


def test_06_candidate_with_evid_scen_contamination_is_hard_rejected():
    """Scenario 6: Candidate causing EVID/SCEN contamination is unconditionally rejected."""
    active = governed_optimizer.get_active_policy()
    candidate = HighviewPolicy(
        policy_id="POLICY-CANDIDATE-CONTAM",
        version_number=2,
        status=PolicyStatus.CANDIDATE,
    )
    policy_registry.register_candidate(candidate)

    base_rep = make_benchmark_report(total_cases=5, grounding_rate=1.0, average_latency_ms=1000.0)
    cand_rep = make_benchmark_report(total_cases=5, grounding_rate=1.0, average_latency_ms=600.0)

    comparison = PolicyComparator.compare_policies(
        baseline_policy=active,
        candidate_policy=candidate,
        baseline_report=base_rep,
        candidate_report=cand_rep,
        safety_override_flags={"evid_scen_contamination": 2},
    )

    assert comparison.hard_safety_gates_passed is False
    assert comparison.recommendation == "REJECT"
    assert any("contamination" in r.lower() for r in comparison.regressions)

    eligible, _ = PromotionGate.evaluate_eligibility(comparison)
    assert eligible is False


def test_07_shadow_comparison_executes_without_user_exposure_or_side_effects():
    """Scenario 7: Shadow policy evaluates candidate alongside active state without side effects."""
    active = governed_optimizer.get_active_policy()
    candidate = HighviewPolicy(
        policy_id="POLICY-CANDIDATE-SHADOW",
        version_number=2,
        status=PolicyStatus.CANDIDATE,
    )
    policy_registry.register_candidate(candidate)

    state = HighviewAgentState(
        request_id="req-shadow-test",
        dataset_id="workforce",
        intent="PRESENTATION_CREATION",
        active_filters={"_workflow_name": "presentation_creation", "_trace_id": "tr-shadow-1"},
        tool_history=[{"tool_name": "rank_entities"}, {"tool_name": "create_deck"}],
    )

    shadow_eval = governed_optimizer.run_shadow_evaluation(
        active_state=state,
        candidate_policy_id=candidate.policy_id,
        active_latency_ms=250.0,
    )

    assert shadow_eval is not None
    assert shadow_eval.active_workflow_decision == "presentation_creation"
    assert shadow_eval.side_effects_skipped is True
    assert shadow_eval.candidate_policy_id == candidate.policy_id

    # Verify history
    all_shadows = governed_optimizer.list_shadow_evaluations()
    assert len(all_shadows) == 1
    assert all_shadows[0].evaluation_id == shadow_eval.evaluation_id


def test_08_human_rejects_candidate_leaves_active_policy_unchanged():
    """Scenario 8: Explicit human rejection marks candidate REJECTED and preserves active baseline."""
    active_before = governed_optimizer.get_active_policy()
    candidate = HighviewPolicy(
        policy_id="POLICY-CANDIDATE-TO-REJECT",
        version_number=2,
        status=PolicyStatus.CANDIDATE,
    )
    policy_registry.register_candidate(candidate)

    governed_optimizer.reject_candidate(candidate.policy_id, reason="Rejected per security board")

    cand_after = governed_optimizer.get_policy(candidate.policy_id)
    assert cand_after is not None
    assert cand_after.status == PolicyStatus.REJECTED
    assert "Rejected per security board" in cand_after.approval_status

    active_after = governed_optimizer.get_active_policy()
    assert active_after.policy_id == active_before.policy_id
    assert active_after.status == PolicyStatus.ACTIVE


def test_09_human_approves_candidate_activates_new_policy_and_retires_old():
    """Scenario 9: Human approval promotes candidate to ACTIVE and retires previous policy."""
    active_before = governed_optimizer.get_active_policy()
    candidate = HighviewPolicy(
        policy_id="POLICY-CANDIDATE-APPROVED",
        version_number=2,
        status=PolicyStatus.CANDIDATE,
    )
    policy_registry.register_candidate(candidate)

    # Approve and activate
    success, msg = governed_optimizer.approve_and_activate(
        candidate_policy_id=candidate.policy_id,
        approved_by="governance_director",
    )

    assert success is True
    assert "now ACTIVE" in msg

    active_now = governed_optimizer.get_active_policy()
    assert active_now.policy_id == candidate.policy_id
    assert active_now.status == PolicyStatus.ACTIVE
    assert active_now.approved_by == "governance_director"

    old_policy = governed_optimizer.get_policy(active_before.policy_id)
    assert old_policy is not None
    assert old_policy.status == PolicyStatus.RETIRED


def test_10_rollback_restores_prior_policy_on_anomaly():
    """Scenario 10: Rollback manager inspects telemetry degradation and restores baseline."""
    # 1. Activate a new policy
    candidate = HighviewPolicy(
        policy_id="POLICY-CANDIDATE-V2",
        version_number=2,
        status=PolicyStatus.CANDIDATE,
    )
    policy_registry.register_candidate(candidate)
    governed_optimizer.approve_and_activate(candidate.policy_id, approved_by="admin")

    assert governed_optimizer.get_active_policy().policy_id == "POLICY-CANDIDATE-V2"

    # 2. Simulate runtime degradation under v2
    degraded_traces = [
        AITrace(
            request_id=f"tr-deg-{i}",
            conversation_id="conv-deg",
            total_latency_ms=13000.0,
            status="FAILED_SAFE" if i % 2 == 0 else "COMPLETED",
            evaluation_summary={"grounding": {"grounding_rate": 0.88}},
        )
        for i in range(4)
    ]

    anomalies = [
        RuntimeAnomaly(
            anomaly_type="GROUNDING_DROP",
            severity="CRITICAL",
            message="Factual grounding fell to 88%",
        )
    ]

    advisory = rollback_manager.inspect_telemetry(degraded_traces, anomalies)
    assert advisory is not None
    assert advisory.current_policy_id == "POLICY-CANDIDATE-V2"
    assert advisory.target_policy_id == "POLICY-DEFAULT-001"
    assert advisory.severity == "CRITICAL"

    # 3. Execute rollback
    success, msg = governed_optimizer.execute_rollback(to_policy_id=advisory.target_policy_id)
    assert success is True
    assert governed_optimizer.get_active_policy().policy_id == "POLICY-DEFAULT-001"


def test_11_policy_provenance_recorded_on_trace():
    """Scenario 11: Trace execution records exact active policy version in provenance."""
    from app.observability import ai_observability_service
    from app.agent.state import HighviewAgentState

    # Ensure clean state with default policy
    active_policy = governed_optimizer.get_active_policy()
    assert active_policy.policy_id == "POLICY-DEFAULT-001"

    state = HighviewAgentState(
        request_id="req-provenance-1",
        conversation_id="conv-prov-1",
        dataset_id="workforce",
        intent="DATA_LOOKUP",
        final_answer="Engineering headcount is 45.",
        workflow_status="COMPLETED",
    )

    trace = ai_observability_service.record_workflow_execution(
        state=state,
        workflow_type="quick_answer",
    )

    assert trace.policy_version == "POLICY-DEFAULT-001"


def test_12_optimization_api_endpoints():
    """Scenario 12: Verify FastAPI Technical Explorer endpoints under /api/optimization/."""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)

    # 1. Get policies
    res = client.get("/api/optimization/policies")
    assert res.status_code == 200
    policies = res.json()
    assert len(policies) >= 1

    # 2. Get active policy
    res = client.get("/api/optimization/policies/active")
    assert res.status_code == 200
    active = res.json()
    assert active["status"] == "ACTIVE"

    # 3. Recommendations list and generate
    res = client.get("/api/optimization/recommendations")
    assert res.status_code == 200

    res = client.post("/api/optimization/recommendations/generate")
    assert res.status_code == 200

    # 4. Rollback endpoint when no prior policy exists
    res = client.post("/api/optimization/rollback", json={"operator": "test_suite"})
    assert res.status_code == 400  # Correctly rejects rollback when only 1 baseline policy in history

    # 5. Shadow evaluation endpoint
    cand_id = active["policy_id"]
    res = client.post(
        "/api/optimization/shadow",
        json={"candidate_policy_id": cand_id, "intent": "DATA_LOOKUP", "dataset_id": "workforce"},
    )
    assert res.status_code == 200
    shadow_data = res.json()
    assert shadow_data["candidate_policy_id"] == cand_id
    assert shadow_data["active_workflow_decision"] == "quick_answer"
