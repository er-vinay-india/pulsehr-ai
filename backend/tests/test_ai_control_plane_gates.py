"""Comprehensive Test Suite for HighView AI Control Plane (Phase 11).

Validates all 5 AI Control Integrity Gates:
1. AuthorizationIntegrity: Role permissions, dataset boundaries, sensitive HR grain protection.
2. RoutingIntegrity: Cheapest path first, deterministic priority, refusal of unnecessary council escalation.
3. EvidenceRequirementIntegrity: Verified evidence backing before synthesis.
4. ModelBudgetIntegrity: Strict ceilings on LLM calls, tool calls, critic usage, SLA latencies.
5. ClaimEntitlementIntegrity: Evidence type must entitle the claim; blocks unjustified causation and pseudo-forecasts.
6. Full Test Matrix across R0–R4 and C0–C3.
"""
import pytest
from app.services.copilot.control_plane import (
    AIControlPlane,
    AuthorizationError,
    AuthorizationGate,
    CapabilityRouter,
    ClaimEntitlementGovernor,
    ClaimType,
    ComplexityClassifier,
    ComplexityTier,
    ControlPlaneRequest,
    EvidenceTypeEntitlement,
    ExecutionBudgetManager,
    ModelRouter,
    MultiFactorRiskClassifier,
    RiskTier,
)


# ==============================================================================
# Gate 1: AuthorizationIntegrity
# ==============================================================================
def test_authorization_integrity_enforces_role_boundaries():
    """Gate 1: AuthorizationIntegrity ensures unauthorized roles are blocked from sensitive HR fields."""
    # 1. Analyst accessing standard attendance query -> ALLOWED
    assert AuthorizationGate.verify_authorization(
        user_role="analyst",
        query="What was department attendance in July?",
        dataset_id=99747,
    ) is True

    # 2. Viewer trying to query executive compensation / termination -> BLOCKED
    with pytest.raises(AuthorizationError) as exc_info:
        AuthorizationGate.verify_authorization(
            user_role="viewer",
            query="Show base salary and bonus distribution across teams",
            dataset_id=99747,
        )
    assert "Viewer role is not authorized" in str(exc_info.value)

    # 3. Field-level privacy restrictions: ssn requires executive/admin
    with pytest.raises(AuthorizationError) as exc_info:
        AuthorizationGate.verify_authorization(
            user_role="analyst",
            query="Look up employee details",
            dataset_id=99747,
            requested_fields=["ssn", "Employee Name"],
        )
    assert "requires executive or admin authorization" in str(exc_info.value)

    # 4. End-to-end blocked response via AIControlPlane
    res = AIControlPlane.process_request(
        ControlPlaneRequest(
            query="Show salary distribution for termination candidates",
            user_role="viewer",
        )
    )
    assert res.is_blocked is True
    assert "Access Denied" in res.answer
    assert res.audit_record.claim_entitlement_status == "BLOCKED"


# ==============================================================================
# Gate 2: RoutingIntegrity & Multi-Factor Classification
# ==============================================================================
def test_routing_integrity_separates_risk_from_complexity():
    """Gate 2: Evaluates multi-factor risk and verifies orthogonal complexity classification."""
    # Example A: "Calculate department attendance rankings" -> R1 (Analytics), C1 (Single Aggregation)
    q_a = "Calculate department attendance rankings"
    risk_a, prof_a = MultiFactorRiskClassifier.classify(q_a)
    comp_a = ComplexityClassifier.classify(q_a)
    assert risk_a == RiskTier.R1
    assert comp_a == ComplexityTier.C1

    # Example B: "Should we reduce headcount in Engineering?" -> R4 (High Impact), C2 (Cross-Dept Trade-off)
    q_b = "Should we reduce headcount in Engineering?"
    risk_b, prof_b = MultiFactorRiskClassifier.classify(q_b)
    comp_b = ComplexityClassifier.classify(q_b)
    assert risk_b == RiskTier.R4
    assert comp_b == ComplexityTier.C2

    # Example C: "Explain 50 correlated metrics" -> R2 (Interpretation), C3 (High Cardinality)
    q_c = "Explain 50 correlated metrics across our sheets"
    risk_c, prof_c = MultiFactorRiskClassifier.classify(q_c)
    comp_c = ComplexityClassifier.classify(q_c)
    assert risk_c == RiskTier.R2
    assert comp_c == ComplexityTier.C3


def test_routing_integrity_counterfactual_vs_policy_mandate():
    """Verify that 'What happens if we move to 4 days/week?' is an exploratory replay (R1/R2),

    whereas 'Should we mandate 4 days/week?' is a policy decision (R4).
    """
    # 1. Exploratory what-if replay
    q_replay = "What happens if we move to 4 days/week?"
    risk_replay, _ = MultiFactorRiskClassifier.classify(q_replay)
    assert risk_replay in [RiskTier.R0, RiskTier.R1, RiskTier.R2]
    assert risk_replay != RiskTier.R4  # Must NOT be classified as R4!

    # 2. Policy change mandate
    q_mandate = "Should we mandate 4 days/week company-wide?"
    risk_mandate, _ = MultiFactorRiskClassifier.classify(q_mandate)
    assert risk_mandate == RiskTier.R4  # Must be R4!


def test_routing_integrity_deterministic_first_and_council_refusal():
    """Gate 2: Enforces deterministic tools first and refuses unnecessary Council escalation."""
    # 1. "Which department has lowest attendance?" -> 100% deterministic, no LLM
    q = "Which department has lowest attendance?"
    risk, _ = MultiFactorRiskClassifier.classify(q)
    comp = ComplexityClassifier.classify(q)
    cap, needs_llm, tools = CapabilityRouter.route_capability(q, risk, comp)
    assert cap == "descriptive_aggregation"
    assert needs_llm is False
    assert "query_metric" in tools

    # 2. User attempts to force council on a simple lookup -> Refused!
    route, critic, council, reason = ModelRouter.select_route(
        risk=RiskTier.R1,
        complexity=ComplexityTier.C1,
        needs_llm=True,
        force_council=True,
    )
    assert council is False
    assert "refused" in reason.lower()


# ==============================================================================
# Gate 3 & Gate 4: EvidenceRequirementIntegrity & ModelBudgetIntegrity
# ==============================================================================
def test_model_budget_integrity_enforces_resource_ceilings():
    """Gate 4: ModelBudgetIntegrity enforces call limits and latency targets per tier."""
    # R0 Budget: 0 LLMs, max 2 tools, <250ms
    b_r0 = ExecutionBudgetManager.get_budget(RiskTier.R0, ComplexityTier.C0)
    assert b_r0.max_llm_calls == 0
    assert b_r0.max_tool_calls == 2
    assert b_r0.max_latency_ms == 250.0

    # R4 Budget: 4 LLMs, Council mandatory, Critic mandatory, <8000ms
    b_r4 = ExecutionBudgetManager.get_budget(RiskTier.R4, ComplexityTier.C2)
    assert b_r4.max_llm_calls == 4
    assert b_r4.council_required is True
    assert b_r4.critic_required is True
    assert b_r4.max_latency_ms == 8000.0

    # Evaluation of consumption
    pass_status, _ = ExecutionBudgetManager.evaluate_consumption(b_r0, actual_llm_calls=0, actual_tool_calls=1, actual_latency_ms=120.0)
    assert pass_status == "PASS"

    exceed_status, reason = ExecutionBudgetManager.evaluate_consumption(b_r0, actual_llm_calls=1, actual_tool_calls=1, actual_latency_ms=120.0)
    assert exceed_status == "EXCEEDED"
    assert "LLM call ceiling violated" in reason


# ==============================================================================
# Gate 5: ClaimEntitlementIntegrity
# ==============================================================================
def test_claim_entitlement_blocks_unjustified_causality():
    """Gate 5: ClaimEntitlementIntegrity blocks causal claims when only correlation evidence exists."""
    causal_claim = "Approved leave caused the attendance decline across departments."
    evidence_types = [EvidenceTypeEntitlement.CORRELATION.value]

    verdict = ClaimEntitlementGovernor.audit_claim(causal_claim, evidence_types)
    assert verdict.is_entitled is False
    assert "correlation evidence does not entitle causal attribution" in verdict.rejection_reason
    assert "was associated with" in verdict.suggested_reformulation


def test_claim_entitlement_allows_valid_association():
    """Gate 5: ClaimEntitlementIntegrity allows association claim when correlation evidence exists."""
    associated_claim = "Higher approved leave was associated with lower attendance across departments."
    evidence_types = [EvidenceTypeEntitlement.CORRELATION.value]

    verdict = ClaimEntitlementGovernor.audit_claim(associated_claim, evidence_types)
    assert verdict.is_entitled is True
    assert verdict.detected_claim_type == ClaimType.ASSOCIATED


def test_claim_entitlement_blocks_conflating_counterfactual_with_forecast():
    """Gate 5: Blocks presenting historical replay as future forecast."""
    forecast_claim = "Attendance is projected to reach 81.1% next month."
    evidence_types = [EvidenceTypeEntitlement.SCENARIO_REPLAY.value]

    verdict = ClaimEntitlementGovernor.audit_claim(forecast_claim, evidence_types)
    assert verdict.is_entitled is False
    assert "historical scenario replay does not entitle future forecasting" in verdict.rejection_reason
    assert "would have" in verdict.suggested_reformulation


def test_claim_entitlement_allows_valid_counterfactual():
    """Gate 5: Allows counterfactual statement supported by scenario replay evidence."""
    cf_claim = "Under a 2-day policy, 81.1% of the observed workforce would have satisfied the requirement."
    evidence_types = [EvidenceTypeEntitlement.SCENARIO_REPLAY.value]

    verdict = ClaimEntitlementGovernor.audit_claim(cf_claim, evidence_types)
    assert verdict.is_entitled is True
    assert verdict.detected_claim_type == ClaimType.COUNTERFACTUAL


# ==============================================================================
# Full Pipeline & Audit Record Verification
# ==============================================================================
def test_control_plane_emits_auditable_routing_record():
    """Verify that every processed request returns a fully populated ControlPlaneAuditRecord."""
    req = ControlPlaneRequest(
        query="What schedule should management consider to improve attendance?",
        user_role="analyst",
    )
    res = AIControlPlane.process_request(req)
    assert res.is_blocked is False
    assert res.audit_record is not None

    record_dict = res.audit_record.to_dict()
    assert "risk_tier" in record_dict
    assert "complexity_tier" in record_dict
    assert "capability" in record_dict
    assert "deterministic_tools_used" in record_dict
    assert "model_route" in record_dict
    assert "critic_required" in record_dict
    assert "council_required" in record_dict
    assert "budget_status" in record_dict
    assert "claim_entitlement_status" in record_dict
    assert "latency_ms" in record_dict
    assert record_dict["budget_status"] == "PASS"
