"""Contracts and schemas for Phase 13 Production Evaluation, Red-Team & Drift Governance,
Component Versioning, and Highview Decision Ledger.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, Field, ConfigDict


# ==============================================================================
# 1. Human Approval & Decision Status (Phase 14 Accountability)
# ==============================================================================

class DecisionStatus(str, Enum):
    """Lifecycle disposition of high-impact organizational decisions."""
    DRAFT = "DRAFT"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    REVISION_REQUESTED = "REVISION_REQUESTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"


class ApprovalRecord(BaseModel):
    """Human review disposition binding a high-impact decision to an accountable executive."""
    model_config = ConfigDict(extra="ignore")

    approval_id: str = Field(default_factory=lambda: f"APPR-{uuid.uuid4().hex[:8].upper()}")
    decision_id: str
    request_id: str
    decision_provenance_hash: str
    reviewer: str
    review_timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: DecisionStatus
    human_comment: str | None = None


class ExecutiveDecisionReviewCard(BaseModel):
    """Clean, decision-maker-focused review card exposing only what leadership needs."""
    model_config = ConfigDict(extra="ignore")

    decision_id: str
    proposed_decision: str
    evidence_summary: str
    observed_baseline: str
    counterfactual_replay: str
    council_position: str
    critic_concerns: list[str] = Field(default_factory=list)
    epistemic_uncertainty: str
    status: DecisionStatus
    proposer_id: str = "ai_coordinator"
    available_actions: list[str] = Field(default_factory=lambda: ["APPROVE", "REJECT", "REQUEST_REVISION", "SUPERSEDE"])
    technical_audit: dict[str, Any] = Field(default_factory=dict)


# ==============================================================================
# 2. Comprehensive System Component Versioning & Latency SLIs
# ==============================================================================

class SystemComponentVersions(BaseModel):
    """Explicit semantic and engine versions captured with every decision."""
    model_config = ConfigDict(extra="ignore")

    semantic_catalog_version: str = "v2.4.0"
    evidence_engine_version: str = "v3.1.0"
    policy_version: str = "v1.2.0"
    ranking_version: str = "v2.0.0"
    visual_compiler_version: str = "v2.1.0"
    control_plane_version: str = "v1.12.0"
    routing_policy_version: str = "v1.0.0"
    scenario_engine_version: str = "v1.10.0"
    model_name: str = "qwen2.5:7b-instruct"
    model_version: str = "2026.1"
    prompt_version: str = "v4.2.0"

    def compute_version_fingerprint(self) -> str:
        """Returns deterministic SHA-256 hash of all runtime component versions."""
        dumped = json.dumps(self.model_dump(), sort_keys=True)
        return hashlib.sha256(dumped.encode("utf-8")).hexdigest()[:16]


class LatencySLISnapshot(BaseModel):
    """Production service level indicators broken down by pipeline stage."""
    model_config = ConfigDict(extra="ignore")

    risk_tier: str
    control_plane_routing_latency_ms: float = 0.0
    deterministic_tool_latency_ms: float = 0.0
    model_invocation_latency_ms: float = 0.0
    council_latency_ms: float = 0.0
    end_to_end_user_latency_ms: float = 0.0
    sla_target_ms: float = 500.0
    meets_sla: bool = True


# ==============================================================================
# 3. Highview Tamper-Evident Append-Only Decision Ledger & Anchors
# ==============================================================================

class LedgerHeadAnchor(BaseModel):
    """Periodic trust anchor binding the ledger head hash to deployment metadata."""
    model_config = ConfigDict(extra="ignore")

    anchor_id: str = Field(default_factory=lambda: f"ANCHOR-{uuid.uuid4().hex[:8].upper()}")
    head_hash: str
    block_height: int
    deployment_version: str = "v1.14.0-prod"
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    anchor_signature: str = ""

    def calculate_signature(self) -> str:
        payload = f"{self.anchor_id}:{self.head_hash}:{self.block_height}:{self.deployment_version}:{self.timestamp}"
        return hashlib.sha256(payload.encode()).hexdigest()


class DecisionLedgerRecord(BaseModel):
    """Tamper-evident, append-only record linking request, evidence, models, human review, and hash chain."""
    model_config = ConfigDict(extra="ignore")

    decision_id: str = Field(description="Unique ledger ID, e.g. DEC-2026-00182")
    dataset_id: str | int
    request_id: str
    provenance_hash: str
    previous_record_hash: str = "0" * 64
    route: str
    risk_tier: str
    complexity_tier: str
    evidence_ids: list[str] = Field(default_factory=list)
    scenario_ids: list[str] = Field(default_factory=list)
    models_used: list[str] = Field(default_factory=list)
    recommendation: str
    human_disposition: DecisionStatus = DecisionStatus.REVIEW_REQUIRED
    proposer_id: str = "ai_coordinator"
    version: int = 1
    supersedes_decision_id: str | None = None
    superseded_by_decision_id: str | None = None
    evidence_hash_at_creation: str = ""
    approval: ApprovalRecord | None = None
    versions: SystemComponentVersions = Field(default_factory=SystemComponentVersions)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    record_hash: str = ""

    def calculate_hash(self) -> str:
        """Computes SHA-256 over all tamper-evident payload fields including parent hash."""
        payload = {
            "decision_id": self.decision_id,
            "dataset_id": str(self.dataset_id),
            "request_id": self.request_id,
            "provenance_hash": self.provenance_hash,
            "previous_record_hash": self.previous_record_hash,
            "route": self.route,
            "risk_tier": self.risk_tier,
            "complexity_tier": self.complexity_tier,
            "evidence_ids": sorted(self.evidence_ids),
            "scenario_ids": sorted(self.scenario_ids),
            "models_used": sorted(self.models_used),
            "recommendation": self.recommendation,
            "human_disposition": self.human_disposition.value,
            "proposer_id": self.proposer_id,
            "version": self.version,
            "supersedes_decision_id": self.supersedes_decision_id,
            "superseded_by_decision_id": self.superseded_by_decision_id,
            "evidence_hash_at_creation": self.evidence_hash_at_creation,
            "versions": self.versions.model_dump(),
            "timestamp": self.timestamp,
        }
        serialized = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


# ==============================================================================
# 4. Production Evaluation & Red-Team Records
# ==============================================================================

class ProductionEvalRecord(BaseModel):
    """Result of evaluating an adversarial, corrupted, or complex real-world request."""
    model_config = ConfigDict(extra="ignore")

    eval_id: str = Field(default_factory=lambda: f"EVAL-{uuid.uuid4().hex[:8].upper()}")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    scenario_name: str
    request_query: str
    request_surface: str
    user_role: str
    expected_route: str
    expected_evidence_types: list[str] = Field(default_factory=list)
    expected_claim_type: str | None = None
    expected_auth_passed: bool = True
    expected_council: bool = False
    expected_critic: bool = False

    actual_route: str = ""
    actual_evidence_ids: list[str] = Field(default_factory=list)
    actual_auth_passed: bool = True
    actual_council_invoked: bool = False
    actual_critic_invoked: bool = False
    actual_answer: str = ""
    actual_claim_violations: int = 0
    latency_ms: float = 0.0

    injected_attack_type: str | None = None
    attack_neutralized: bool = True
    passed: bool = True
    failure_reasons: list[str] = Field(default_factory=list)


class OperationalMetricsSnapshot(BaseModel):
    """Aggregate operational and reliability metrics for Highview AI."""
    model_config = ConfigDict(extra="ignore")

    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    total_evals: int = 0
    passed_evals: int = 0
    routing_accuracy: float = 100.0
    authorization_violation_rate: float = 0.0
    unsupported_claim_rate: float = 0.0
    evidence_coverage: float = 100.0
    council_escalation_precision: float = 100.0
    council_escalation_recall: float = 100.0
    deterministic_resolution_rate: float = 0.0
    fallback_success_rate: float = 100.0

    latency_p50_ms: float = 0.0
    latency_p95_ms: float = 0.0
    latency_p99_ms: float = 0.0
    model_failure_rate: float = 0.0
    tool_failure_rate: float = 0.0
    budget_violation_rate: float = 0.0

    data_drift_rate: float = 0.0
    semantic_drift_rate: float = 0.0
    evidence_staleness_rate: float = 0.0


# ==============================================================================
# 5. Drift, Staleness, and Conflict Detection Schemas
# ==============================================================================

class DataDriftReport(BaseModel):
    """Evaluation of structural schema changes, broken joins, and entity anomalies."""
    model_config = ConfigDict(extra="ignore")

    dataset_id: str | int
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    has_drift: bool = False
    missing_columns: list[str] = Field(default_factory=list)
    unexpected_columns: list[str] = Field(default_factory=list)
    duplicate_entities: list[str] = Field(default_factory=list)
    broken_joins: list[str] = Field(default_factory=list)
    null_ratio_spikes: dict[str, float] = Field(default_factory=dict)
    remediation_required: bool = False


class SemanticDriftReport(BaseModel):
    """Evaluation of type/domain shifts in mapped business concepts."""
    model_config = ConfigDict(extra="ignore")

    dataset_id: str | int
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    has_drift: bool = False
    drifted_concepts: list[dict[str, Any]] = Field(default_factory=list)
    severity: Literal["low", "medium", "critical"] = "low"


class EvidenceStalenessReport(BaseModel):
    """Evaluation of age and TTL status of cached evidence nodes."""
    model_config = ConfigDict(extra="ignore")

    dataset_id: str | int
    stale_node_ids: list[str] = Field(default_factory=list)
    fresh_node_ids: list[str] = Field(default_factory=list)
    max_age_hours: float = 0.0
    staleness_ratio: float = 0.0
    recomputation_needed: bool = False


class ConflictingEvidenceReport(BaseModel):
    """Evaluation of contradictory evidence claims across different sheets/sources."""
    model_config = ConfigDict(extra="ignore")

    conflict_detected: bool = False
    conflicting_pairs: list[dict[str, Any]] = Field(default_factory=list)
    arbitration_route: str = "council_arbitration"
    arbitration_summary: str = ""
