"""Router for Highview Decision Ledger & Human Approval Governance (Phase 14).

Provides authenticated endpoints for:
- Reviewing high-impact R4 decisions (ExecutiveDecisionReviewCard)
- Approving decisions with Separation of Duties and Evidence Freshness checks
- Rejecting decisions and requesting revisions
- Non-destructively superseding approved historical decisions
- Cryptographic ledger integrity verification and trust anchors
"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from ..services.governance.contracts import (
    DecisionStatus,
    ExecutiveDecisionReviewCard,
    LedgerHeadAnchor,
)
from ..services.governance.ledger import DecisionLedger

router = APIRouter(prefix="/api/governance", tags=["decision governance"])


class DecisionReviewActionRequest(BaseModel):
    reviewer: str = Field(description="Name or ID of reviewing executive")
    human_comment: str | None = Field(default=None, description="Executive justification comment")
    current_evidence_hash: str | None = Field(default=None, description="Hash of active evidence at review time")
    expected_version: int | None = Field(default=None, description="Optimistic locking version number")


class DecisionSupersedeRequest(BaseModel):
    new_decision_id: str
    reviewer: str
    reason: str
    new_recommendation: str
    new_evidence_ids: list[str] | None = None
    new_scenario_ids: list[str] | None = None


@router.get("/decisions", response_model=list[dict[str, Any]])
def list_governed_decisions(
    status_filter: str | None = Query(None, description="Filter by DecisionStatus: REVIEW_REQUIRED, APPROVED, etc.")
):
    """Lists all decisions recorded in the Highview Tamper-Evident Ledger."""
    ledger = DecisionLedger.get_instance()
    records = ledger.get_all_records()
    if status_filter:
        records = [r for r in records if r.human_disposition.value == status_filter.upper()]
    return [r.model_dump() for r in records]


@router.get("/decisions/{decision_id}", response_model=ExecutiveDecisionReviewCard)
def get_decision_review_card(decision_id: str):
    """Returns a clean, executive-focused decision card exposing only what leadership needs."""
    ledger = DecisionLedger.get_instance()
    try:
        return ledger.format_review_card(decision_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/decisions/{decision_id}/approve")
def approve_decision(decision_id: str, payload: DecisionReviewActionRequest):
    """Approves an R4 decision with Separation of Duties, Evidence Freshness, and Optimistic Locking checks."""
    ledger = DecisionLedger.get_instance()
    try:
        record = ledger.record_human_approval(
            decision_id=decision_id,
            reviewer=payload.reviewer,
            status=DecisionStatus.APPROVED,
            human_comment=payload.human_comment,
            current_evidence_hash=payload.current_evidence_hash,
            expected_version=payload.expected_version,
        )
        return {
            "status": "APPROVED",
            "decision_id": decision_id,
            "audit_block_id": record.decision_id,
            "record_hash": record.record_hash,
            "reviewer": payload.reviewer,
        }
    except ValueError as e:
        err_msg = str(e)
        if "Separation of duties" in err_msg:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=err_msg)
        elif "Optimistic lock conflict" in err_msg:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=err_msg)
        elif "Approval blocked" in err_msg:
            raise HTTPException(status_code=status.HTTP_412_PRECONDITION_FAILED, detail=err_msg)
        elif "not found" in err_msg:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)


@router.post("/decisions/{decision_id}/reject")
def reject_decision(decision_id: str, payload: DecisionReviewActionRequest):
    """Rejects an R4 decision, recording executive rationale into the tamper-evident ledger."""
    ledger = DecisionLedger.get_instance()
    try:
        record = ledger.record_human_approval(
            decision_id=decision_id,
            reviewer=payload.reviewer,
            status=DecisionStatus.REJECTED,
            human_comment=payload.human_comment or "Rejected by executive review",
            current_evidence_hash=payload.current_evidence_hash,
            expected_version=payload.expected_version,
        )
        return {
            "status": "REJECTED",
            "decision_id": decision_id,
            "audit_block_id": record.decision_id,
            "record_hash": record.record_hash,
            "reviewer": payload.reviewer,
        }
    except ValueError as e:
        err_msg = str(e)
        if "Optimistic lock conflict" in err_msg:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)


@router.post("/decisions/{decision_id}/request-revision")
def request_decision_revision(decision_id: str, payload: DecisionReviewActionRequest):
    """Requests revision from the Council or analysis team with reviewer feedback."""
    ledger = DecisionLedger.get_instance()
    try:
        record = ledger.record_human_approval(
            decision_id=decision_id,
            reviewer=payload.reviewer,
            status=DecisionStatus.REVISION_REQUESTED,
            human_comment=payload.human_comment or "Revision requested",
            expected_version=payload.expected_version,
        )
        return {
            "status": "REVISION_REQUESTED",
            "decision_id": decision_id,
            "audit_block_id": record.decision_id,
            "record_hash": record.record_hash,
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/decisions/{decision_id}/supersede")
def supersede_decision(decision_id: str, payload: DecisionSupersedeRequest):
    """Non-destructively supersedes an approved historical decision by creating a replacement block."""
    ledger = DecisionLedger.get_instance()
    try:
        disp_rec, new_rec = ledger.supersede_decision(
            old_decision_id=decision_id,
            new_decision_id=payload.new_decision_id,
            reviewer=payload.reviewer,
            reason=payload.reason,
            new_recommendation=payload.new_recommendation,
            new_evidence_ids=payload.new_evidence_ids,
            new_scenario_ids=payload.new_scenario_ids,
        )
        return {
            "status": "SUPERSEDED",
            "old_decision_id": decision_id,
            "new_decision_id": new_rec.decision_id,
            "supersedes_record_hash": new_rec.record_hash,
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/ledger/integrity")
def verify_ledger_integrity():
    """Validates SHA-256 continuity and payload authenticity across the entire decision ledger."""
    ledger = DecisionLedger.get_instance()
    is_valid, message = ledger.verify_chain_integrity()
    return {
        "is_valid": is_valid,
        "message": message,
        "total_blocks": len(ledger.get_all_records()),
    }


@router.post("/ledger/anchor", response_model=LedgerHeadAnchor)
def anchor_ledger_head(deployment_version: str = "v1.14.0-prod"):
    """Creates a periodic trust anchor linking current ledger head hash to deployment metadata."""
    ledger = DecisionLedger.get_instance()
    return ledger.anchor_head(deployment_version=deployment_version)
