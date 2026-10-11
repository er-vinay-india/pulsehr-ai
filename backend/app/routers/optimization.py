"""API endpoints for Governed Adaptive Optimization (Phase E).

Exposes:
- GET /api/optimization/policies: List registered policies.
- GET /api/optimization/policies/active: Get current active immutable policy.
- GET /api/optimization/policies/{policy_id}: Get details for specific policy.
- GET /api/optimization/recommendations: List recommendations generated from telemetry.
- POST /api/optimization/recommendations/generate: Run analyzers on historical traces.
- POST /api/optimization/candidates: Derive candidate policy from recommendation.
- POST /api/optimization/compare: Run offline benchmark comparison under safety gates.
- POST /api/optimization/approve: Human approval and promotion to ACTIVE.
- POST /api/optimization/reject: Reject candidate policy.
- POST /api/optimization/rollback: Anomaly-driven or manual rollback to previous baseline.
- GET /api/optimization/shadow: List shadow policy evaluations.
- POST /api/optimization/shadow: Simulate candidate execution in shadow mode.
"""
from __future__ import annotations

import logging
from typing import Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.agent.state import HighviewAgentState
from app.optimization import (
    HighviewPolicy,
    OptimizationRecommendation,
    PolicyComparisonResult,
    PolicyStatus,
    governed_optimizer,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/optimization", tags=["Governed Adaptive Optimization"])


class CandidateCreateRequest(BaseModel):
    recommendation_id: str
    author: str = "human_governance"


class CompareRequest(BaseModel):
    candidate_policy_id: str
    limit: int = 10
    safety_override_flags: dict[str, Any] | None = None


class ApproveRequest(BaseModel):
    candidate_policy_id: str
    approved_by: str = "human_governance"


class RejectRequest(BaseModel):
    candidate_policy_id: str
    reason: str = "Rejected by governance board"


class RollbackRequest(BaseModel):
    to_policy_id: str | None = None
    operator: str = "governance_safety"


class ShadowEvalRequest(BaseModel):
    candidate_policy_id: str
    intent: str = "DATA_LOOKUP"
    request_id: str = "req-shadow-001"
    dataset_id: str = "workforce"


@router.get("/policies")
def list_policies(
    status: PolicyStatus | None = Query(default=None, description="Optional status filter"),
) -> list[dict[str, Any]]:
    """Lists registered policies."""
    policies = governed_optimizer.list_policies(status=status)
    return [p.model_dump() for p in policies]


@router.get("/policies/active")
def get_active_policy() -> dict[str, Any]:
    """Retrieves current active immutable production policy."""
    policy = governed_optimizer.get_active_policy()
    return policy.model_dump()


@router.get("/policies/{policy_id}")
def get_policy(policy_id: str) -> dict[str, Any]:
    """Retrieves specific policy by ID."""
    policy = governed_optimizer.get_policy(policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail=f"Policy '{policy_id}' not found.")
    return policy.model_dump()


@router.get("/recommendations")
def list_recommendations(
    category: str | None = Query(default=None),
    status: str | None = Query(default=None),
) -> list[dict[str, Any]]:
    """Lists optimization recommendations derived from Phase D telemetry."""
    recs = governed_optimizer.list_recommendations(category=category, status=status)
    return [r.model_dump() for r in recs]


@router.post("/recommendations/generate")
def generate_recommendations() -> list[dict[str, Any]]:
    """Runs all 6 deterministic analyzers across stored telemetry traces."""
    recs = governed_optimizer.analyze_traces_and_recommend()
    return [r.model_dump() for r in recs]


@router.post("/candidates")
def create_candidate_policy(req: CandidateCreateRequest) -> dict[str, Any]:
    """Derives a new candidate policy from a recommendation."""
    rec = None
    for r in governed_optimizer.list_recommendations():
        if r.recommendation_id == req.recommendation_id:
            rec = r
            break
    if not rec:
        raise HTTPException(status_code=404, detail=f"Recommendation '{req.recommendation_id}' not found.")

    candidate = governed_optimizer.create_candidate_from_recommendation(rec, author=req.author)
    return candidate.model_dump()


@router.post("/compare")
def compare_candidate_policy(req: CompareRequest) -> dict[str, Any]:
    """Runs benchmark comparison between active baseline and candidate under safety gates."""
    candidate = governed_optimizer.get_policy(req.candidate_policy_id)
    if not candidate:
        raise HTTPException(status_code=404, detail=f"Candidate policy '{req.candidate_policy_id}' not found.")

    comparison = governed_optimizer.benchmark_and_compare(
        candidate_policy=candidate,
        limit=req.limit,
        safety_override_flags=req.safety_override_flags,
    )
    return comparison.model_dump()


@router.post("/approve")
def approve_candidate_policy(req: ApproveRequest) -> dict[str, Any]:
    """Promotes an approved candidate policy to ACTIVE status."""
    success, msg = governed_optimizer.approve_and_activate(
        candidate_policy_id=req.candidate_policy_id,
        approved_by=req.approved_by,
    )
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "SUCCESS", "message": msg, "active_policy_id": req.candidate_policy_id}


@router.post("/reject")
def reject_candidate_policy(req: RejectRequest) -> dict[str, Any]:
    """Rejects a candidate policy."""
    governed_optimizer.reject_candidate(req.candidate_policy_id, reason=req.reason)
    return {"status": "SUCCESS", "message": f"Policy '{req.candidate_policy_id}' rejected."}


@router.post("/rollback")
def rollback_policy(req: RollbackRequest) -> dict[str, Any]:
    """Restores prior baseline policy."""
    success, msg = governed_optimizer.execute_rollback(
        to_policy_id=req.to_policy_id,
        operator=req.operator,
    )
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "SUCCESS", "message": msg, "active_policy_id": governed_optimizer.get_active_policy().policy_id}


@router.get("/shadow")
def list_shadow_evaluations() -> list[dict[str, Any]]:
    """Lists completed shadow policy evaluations."""
    evals = governed_optimizer.list_shadow_evaluations()
    return [e.model_dump() for e in evals]


@router.post("/shadow")
def run_shadow_evaluation(req: ShadowEvalRequest) -> dict[str, Any]:
    """Executes shadow policy evaluation without user exposure or side effects."""
    state = HighviewAgentState(
        request_id=req.request_id,
        dataset_id=req.dataset_id,
        intent=req.intent,
        active_filters={"_workflow_name": "quick_answer"},
    )
    eval_rec = governed_optimizer.run_shadow_evaluation(
        active_state=state,
        candidate_policy_id=req.candidate_policy_id,
    )
    if not eval_rec:
        raise HTTPException(status_code=404, detail="Candidate policy not found.")
    return eval_rec.model_dump()
