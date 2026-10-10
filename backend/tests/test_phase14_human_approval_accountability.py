"""Tests for Phase 14: Human Approval, Decision Accountability, and Tamper-Evident Ledger.

Verifies:
1. Risk-policy driven approval: R4 mandates human review; R0-R2 do not require review.
2. Separation of duties: Request proposer/generator cannot self-approve.
3. Evidence freshness check: Material evidence drift blocks approval.
4. Non-destructive superseding: Historical decisions are never rewritten.
5. Optimistic concurrency control: Racing reviews fail safely with conflict error.
6. Reviewer identity, timestamp, and executive comments captured.
7. ExecutiveDecisionReviewCard exposes only what decision-makers need.
8. Periodic trust anchors and tamper-evident chain verification.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.copilot.control_plane.contracts import (
    HighviewAIRequest,
    RiskTier,
)
from app.services.copilot.control_plane.facade import HighviewAI
from app.services.governance.contracts import (
    DecisionStatus,
    ExecutiveDecisionReviewCard,
    LedgerHeadAnchor,
)
from app.services.governance.ledger import DecisionLedger

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_ledger_state():
    """Resets ledger state before each test run."""
    DecisionLedger.reset_for_test()


# ==============================================================================
# 1. Risk-Policy Driven Approval Gate
# ==============================================================================
def test_r4_decision_mandates_review_and_r0_r2_do_not():
    """R4 policy decisions begin in REVIEW_REQUIRED; R0-R2 resolve without approval blocking."""
    # R0 Deterministic query
    r0 = HighviewAI.execute(HighviewAIRequest(query="What is attendance?", surface="hriday", user_role="viewer"))
    assert r0.is_blocked is False
    assert r0.audit_record.model_route == "deterministic"

    # R4 High-Impact policy decision
    r4 = HighviewAI.execute(
        HighviewAIRequest(
            query="Should we change company policy to mandate 4 days/week?",
            surface="hriday",
            user_role="executive",
            user_id="analyst_proposer_01",
        )
    )
    assert r4.audit_record.risk_tier == RiskTier.R4
    assert r4.audit_record.council_required is True

    ledger = DecisionLedger.get_instance()
    records = ledger.get_all_records()
    assert len(records) >= 1
    latest_r4 = records[-1]
    assert latest_r4.risk_tier == "R4"
    assert latest_r4.human_disposition == DecisionStatus.REVIEW_REQUIRED
    assert latest_r4.proposer_id == "analyst_proposer_01"


# ==============================================================================
# 2. Separation of Duties: Proposer Cannot Self-Approve
# ==============================================================================
def test_separation_of_duties_blocks_self_approval():
    """An analyst or system proposing an R4 decision cannot self-approve it."""
    ledger = DecisionLedger.get_instance()
    rec = ledger.record_decision(
        decision_id="DEC-2026-POL-01",
        dataset_id=99747,
        request_id="REQ-8291",
        provenance_hash="hash_8291",
        route="council_war_room",
        risk_tier="R4",
        complexity_tier="C3",
        recommendation="Mandate 4 days per week across all corporate functions.",
        proposer_id="vinay_analyst",
    )

    # 1. Self-approval attempt must fail
    with pytest.raises(ValueError, match="Separation of duties violation"):
        ledger.record_human_approval(
            decision_id="DEC-2026-POL-01",
            reviewer="vinay_analyst",  # Same as proposer!
            status=DecisionStatus.APPROVED,
            human_comment="Self-approving my proposal",
        )

    # 2. Independent executive approval succeeds
    disp = ledger.record_human_approval(
        decision_id="DEC-2026-POL-01",
        reviewer="sara_chro",  # Distinct authorized executive
        status=DecisionStatus.APPROVED,
        human_comment="Approved with 30-day employee pulse monitoring.",
    )
    assert disp.human_disposition == DecisionStatus.APPROVED
    assert disp.approval.reviewer == "sara_chro"


# ==============================================================================
# 3. Evidence Freshness & Drift Check Before Approval
# ==============================================================================
def test_evidence_drift_blocks_stale_approval():
    """Approval is blocked if dataset evidence changed since review began."""
    ledger = DecisionLedger.get_instance()
    ledger.record_decision(
        decision_id="DEC-2026-POL-02",
        dataset_id=99747,
        request_id="REQ-9102",
        provenance_hash="prov_hash_original",
        route="council_war_room",
        risk_tier="R4",
        complexity_tier="C3",
        recommendation="Adopt tiered hybrid presence schedule.",
        proposer_id="ai_coordinator",
        evidence_hash="evid_hash_original_1234",
    )

    # Attempt approval with mismatched/drifted evidence hash
    with pytest.raises(ValueError, match="Approval blocked: Evidence has changed"):
        ledger.record_human_approval(
            decision_id="DEC-2026-POL-02",
            reviewer="executive_director",
            status=DecisionStatus.APPROVED,
            current_evidence_hash="evid_hash_MODIFIED_5678",  # Underlying dataset changed!
        )

    # Approving with current fresh matching hash succeeds
    approved = ledger.record_human_approval(
        decision_id="DEC-2026-POL-02",
        reviewer="executive_director",
        status=DecisionStatus.APPROVED,
        current_evidence_hash="evid_hash_original_1234",
    )
    assert approved.human_disposition == DecisionStatus.APPROVED


# ==============================================================================
# 4. Non-Destructive Superseding
# ==============================================================================
def test_supersede_preserves_historical_records():
    """Superseding an approved policy decision creates a new linked record without mutation."""
    ledger = DecisionLedger.get_instance()
    # Initial decision
    orig = ledger.record_decision(
        decision_id="DEC-2026-001",
        dataset_id=99747,
        request_id="REQ-101",
        provenance_hash="h101",
        route="council_war_room",
        risk_tier="R4",
        complexity_tier="C3",
        recommendation="3 days per week mandatory.",
        proposer_id="analyst_alice",
    )
    ledger.record_human_approval(
        decision_id="DEC-2026-001",
        reviewer="chro_bob",
        status=DecisionStatus.APPROVED,
        human_comment="Initial approval for Q3.",
    )

    # Executive supersedes with updated policy in Q4
    disp_old, new_rec = ledger.supersede_decision(
        old_decision_id="DEC-2026-001",
        new_decision_id="DEC-2026-002",
        reviewer="chro_bob",
        reason="Updated based on Q3 department attendance analytics.",
        new_recommendation="3 days per week with Friday flexibility.",
    )

    assert disp_old.human_disposition == DecisionStatus.SUPERSEDED
    assert new_rec.decision_id == "DEC-2026-002"
    assert new_rec.supersedes_decision_id == "DEC-2026-001"
    assert new_rec.human_disposition == DecisionStatus.REVIEW_REQUIRED

    # Historical record DEC-2026-001 remains intact in chain
    assert ledger.get_decision("DEC-2026-001") is not None
    is_valid, _ = ledger.verify_chain_integrity()
    assert is_valid is True


# ==============================================================================
# 5. Optimistic Concurrency / Racing Review Protection
# ==============================================================================
def test_optimistic_concurrency_protects_racing_reviewers():
    """Two simultaneous reviewers racing to decide cannot corrupt state."""
    ledger = DecisionLedger.get_instance()
    ledger.record_decision(
        decision_id="DEC-2026-RACE",
        dataset_id=99747,
        request_id="REQ-RACE",
        provenance_hash="hrace",
        route="council_war_room",
        risk_tier="R4",
        complexity_tier="C3",
        recommendation="Phased workforce re-entry.",
        proposer_id="system_ai",
    )

    # Reviewer 1 approves first
    ledger.record_human_approval(
        decision_id="DEC-2026-RACE",
        reviewer="reviewer_one",
        status=DecisionStatus.APPROVED,
        expected_version=1,
    )

    # Reviewer 2 concurrently attempts to reject with stale expected_version
    with pytest.raises(ValueError, match="Optimistic lock conflict"):
        ledger.record_human_approval(
            decision_id="DEC-2026-RACE",
            reviewer="reviewer_two",
            status=DecisionStatus.REJECTED,
            expected_version=1,  # Version has already advanced!
        )


# ==============================================================================
# 6. Clean Executive Decision Review Card
# ==============================================================================
def test_executive_review_card_formatting():
    """Generates an executive-friendly review card presenting only what leadership needs."""
    ledger = DecisionLedger.get_instance()
    ledger.record_decision(
        decision_id="DEC-2026-EXEC-01",
        dataset_id=99747,
        request_id="REQ-EXEC-01",
        provenance_hash="hexec",
        route="council_war_room",
        risk_tier="R4",
        complexity_tier="C3",
        recommendation="Move corporate attendance policy from 3 to 4 days/week.",
        evidence_ids=["EVID-001", "EVID-002", "EVID-003"],
        scenario_ids=["SCEN-001"],
        proposer_id="coordinator_agent",
    )

    card = ledger.format_review_card("DEC-2026-EXEC-01")
    assert isinstance(card, ExecutiveDecisionReviewCard)
    assert "Move corporate attendance policy" in card.proposed_decision
    assert "3 verified findings" in card.evidence_summary
    assert "55.2% compliance" in card.observed_baseline
    assert "29.0%" in card.counterfactual_replay
    assert "Recommend against" in card.council_position
    assert len(card.critic_concerns) >= 2
    assert "behavioral adaptation" in card.epistemic_uncertainty.lower()
    assert "APPROVE" in card.available_actions
    assert "EVID-001" in card.technical_audit["evidence_ids"]


# ==============================================================================
# 7. Periodic Trust Anchors & Tamper-Evident Chain
# ==============================================================================
def test_ledger_head_anchor_and_tamper_detection():
    """Validates periodic head trust anchoring and tamper detection."""
    ledger = DecisionLedger.get_instance()
    ledger.record_decision(
        decision_id="DEC-2026-ANCHOR-01",
        dataset_id=99747,
        request_id="REQ-A1",
        provenance_hash="ha1",
        route="council_war_room",
        risk_tier="R4",
        complexity_tier="C3",
        recommendation="Annual workforce policy review.",
        proposer_id="system",
    )

    anchor = ledger.anchor_head(deployment_version="v1.14.0-prod")
    assert isinstance(anchor, LedgerHeadAnchor)
    assert len(anchor.head_hash) == 64
    assert anchor.block_height == 1
    assert len(anchor.anchor_signature) == 64

    # Tamper detection: modifying recommendation breaks chain
    block = ledger.get_decision("DEC-2026-ANCHOR-01")
    block.recommendation = "TAMPERED_POLICY_MANDATE"

    is_valid, msg = ledger.verify_chain_integrity()
    assert is_valid is False
    assert "Tampered block" in msg


# ==============================================================================
# 8. Governance REST API Endpoints
# ==============================================================================
def test_governance_api_endpoints_workflow():
    """Tests the full REST review lifecycle: retrieve card -> approve -> verify integrity."""
    ledger = DecisionLedger.get_instance()
    ledger.record_decision(
        decision_id="DEC-2026-API-01",
        dataset_id=99747,
        request_id="REQ-API",
        provenance_hash="hapi",
        route="council_war_room",
        risk_tier="R4",
        complexity_tier="C3",
        recommendation="Implement flexible summer attendance hours.",
        proposer_id="ai_agent",
        evidence_hash="evid_api_hash_1",
    )

    # 1. Fetch review card
    res_card = client.get("/api/governance/decisions/DEC-2026-API-01")
    assert res_card.status_code == 200
    card_data = res_card.json()
    assert card_data["decision_id"] == "DEC-2026-API-01"
    assert card_data["status"] == "REVIEW_REQUIRED"

    # 2. Separation of duties check via API
    res_self = client.post(
        "/api/governance/decisions/DEC-2026-API-01/approve",
        json={"reviewer": "ai_agent", "human_comment": "Self-approval"},
    )
    assert res_self.status_code == 403

    # 3. Independent approval via API
    res_appr = client.post(
        "/api/governance/decisions/DEC-2026-API-01/approve",
        json={
            "reviewer": "chief_people_officer",
            "human_comment": "Approved for pilot in Operations.",
            "current_evidence_hash": "evid_api_hash_1",
            "expected_version": 1,
        },
    )
    assert res_appr.status_code == 200
    assert res_appr.json()["status"] == "APPROVED"

    # 4. Verify ledger integrity endpoint
    res_integ = client.get("/api/governance/ledger/integrity")
    assert res_integ.status_code == 200
    assert res_integ.json()["is_valid"] is True
