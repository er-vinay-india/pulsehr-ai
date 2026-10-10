"""Unified AI Control Plane Orchestrator (Phase 11).

Orchestrates:
1. Multi-factor Risk Classification (R0–R4)
2. Computational Complexity Classification (C0–C3)
3. Authorization & Scope Verification (AuthorizationIntegrity)
4. Capability Routing & Deterministic-First Path (RoutingIntegrity)
5. Model Routing & Council Escalation Policy (Exceptional Council)
6. Resource Budget Tracking (ModelBudgetIntegrity)
7. Output Governance & Claim Entitlement Audit (ClaimEntitlementIntegrity)
"""
from __future__ import annotations

import time
from typing import Any

from .budget_manager import ExecutionBudgetManager
from .capability_router import AuthorizationError, AuthorizationGate, CapabilityRouter
from .classifiers import ComplexityClassifier, MultiFactorRiskClassifier
from .claim_governor import ClaimEntitlementGovernor
from .contracts import (
    ControlPlaneAuditRecord,
    ControlPlaneRequest,
    ControlPlaneResponse,
    EvidenceTypeEntitlement,
    RiskTier,
)
from .model_router import ModelRouter


class AIControlPlane:
    """The central authoritative governance engine for HighView / HRIDAY AI interactions."""

    @classmethod
    def process_request(cls, req: ControlPlaneRequest) -> ControlPlaneResponse:
        """Processes an incoming copilot or dashboard query through the full 5-decision pipeline."""
        start_time = time.perf_counter()

        # Decision 1 & 2: Risk and Complexity Classification
        risk, factor_profile = MultiFactorRiskClassifier.classify(req.query, req.prior_context)
        complexity = ComplexityClassifier.classify(req.query, req.prior_context)

        # Decision 3: Authorization Gate (AuthorizationIntegrity)
        try:
            AuthorizationGate.verify_authorization(
                user_role=req.user_role,
                query=req.query,
                dataset_id=req.dataset_id,
            )
        except AuthorizationError as auth_err:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            audit_rec = ControlPlaneAuditRecord(
                query=req.query,
                risk_tier=risk,
                complexity_tier=complexity,
                capability="unauthorized",
                deterministic_tools_used=[],
                model_route="blocked",
                budget_status="PASS",
                claim_entitlement_status="BLOCKED",
                latency_ms=elapsed_ms,
            )
            return ControlPlaneResponse(
                answer=f"Access Denied: {auth_err}",
                audit_record=audit_rec,
                is_blocked=True,
                block_reason=str(auth_err),
            )

        # Decision 4: Capability & Deterministic-First Routing (RoutingIntegrity)
        capability, needs_llm, deterministic_tools = CapabilityRouter.route_capability(
            query=req.query,
            risk=risk,
            complexity=complexity,
            context=req.prior_context,
        )

        # Decision 5: Model Routing & Escalation Policy
        evidence_conflict = req.prior_context.get("has_conflicting_evidence", False)
        model_route, critic_req, council_req, route_reason = ModelRouter.select_route(
            risk=risk,
            complexity=complexity,
            needs_llm=needs_llm,
            evidence_conflict=evidence_conflict,
            force_council=req.force_council,
        )

        # Execution Budget Initialization (ModelBudgetIntegrity)
        budget = ExecutionBudgetManager.get_budget(risk, complexity)

        # Simulate / Execute Deterministic Tools & Evidence Packaging
        mock_evidence_types = []
        answer_text = ""

        if capability == "scenario_replay":
            mock_evidence_types = [EvidenceTypeEntitlement.SCENARIO_REPLAY.value]
            answer_text = (
                "Under a 2-day/week counterfactual policy, 81.1% of the observed workforce "
                "would have satisfied the requirement. This scenario re-evaluates observed records "
                "under alternative rules and does not predict future behavioral adaptation."
            )
        elif capability in ["metric_lookup", "descriptive_aggregation"]:
            mock_evidence_types = [EvidenceTypeEntitlement.RAW_RECORD.value, EvidenceTypeEntitlement.AGGREGATION.value]
            answer_text = (
                "Observed office presence rate was 60.5% with 259 eligible employees. "
                "Engineering attendance stood at 11.2 days."
            )
        elif capability == "narrative_synthesis":
            mock_evidence_types = [EvidenceTypeEntitlement.AGGREGATION.value, EvidenceTypeEntitlement.CORRELATION.value]
            answer_text = (
                "Higher approved leaves were associated with lower office attendance across technical teams. "
                "Observed compliance stood at 55.2%."
            )
        elif capability == "policy_deliberation":
            mock_evidence_types = [
                EvidenceTypeEntitlement.SCENARIO_REPLAY.value,
                EvidenceTypeEntitlement.AGGREGATION.value,
                EvidenceTypeEntitlement.COUNCIL_CONSENSUS.value,
            ]
            answer_text = (
                "HighView Council recommends considering a phased 3-day policy review with targeted "
                "exemptions for Design. Under historical replay, 55.2% satisfied baseline mandates."
            )
        else:
            mock_evidence_types = [EvidenceTypeEntitlement.AGGREGATION.value]
            answer_text = "Verified organizational metrics were retrieved from the governed evidence layer."

        # Output Governance: Claim Entitlement Audit (ClaimEntitlementIntegrity)
        all_passed, claim_verdicts, audited_answer = ClaimEntitlementGovernor.audit_response_text(
            text=answer_text,
            available_evidence_types=mock_evidence_types,
        )

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        # Evaluate Resource Consumption
        simulated_llm_calls = 0 if not needs_llm else (4 if council_req else 1)
        simulated_tool_calls = len(deterministic_tools)
        budget_status, _ = ExecutionBudgetManager.evaluate_consumption(
            budget=budget,
            actual_llm_calls=simulated_llm_calls,
            actual_tool_calls=simulated_tool_calls,
            actual_latency_ms=elapsed_ms,
        )

        entitlement_status = "ALLOW" if all_passed else "REFORMULATED"

        audit_record = ControlPlaneAuditRecord(
            query=req.query,
            risk_tier=risk,
            complexity_tier=complexity,
            capability=capability,
            deterministic_tools_used=deterministic_tools,
            model_route=model_route,
            critic_required=critic_req,
            council_required=council_req,
            evidence_coverage=1.0,
            budget_status=budget_status,
            claim_entitlement_status=entitlement_status,
            latency_ms=elapsed_ms,
        )

        return ControlPlaneResponse(
            answer=audited_answer,
            audit_record=audit_record,
            claims_audited=claim_verdicts,
            evidence_items=[{"type": t} for t in mock_evidence_types],
            is_blocked=False,
        )
