"""
HighView Ingestion V2 — Phase I8.2 Cutover & Routing Contracts
Stage: Governed Consumer Gateway, Circuit Breakers & Rollback Foundation
Enforces typed, zero-pollution contracts for cutover states, route decisions,
fallback records, and transition accountability.
"""

from __future__ import annotations

from enum import Enum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class ConsumerName(str, Enum):
    """Governed consumer identity."""
    HRIDAY = "HRIDAY"
    DASHBOARD = "DASHBOARD"
    PRESENTATION = "PRESENTATION"


class CutoverState(str, Enum):
    """
    Seven explicit cutover lifecycle states for each consumer.
    Transitions are strictly governed and fail closed.
    """
    SHADOW = "SHADOW"
    CERTIFIED = "CERTIFIED"
    CANARY = "CANARY"
    V2_PRIMARY_WITH_FALLBACK = "V2_PRIMARY_WITH_FALLBACK"
    V2_PRIMARY = "V2_PRIMARY"
    ROLLBACK = "ROLLBACK"
    V1_RETIREMENT_ELIGIBLE = "V1_RETIREMENT_ELIGIBLE"


class Route(str, Enum):
    """Explicit, unambiguous routing options."""
    V1 = "V1"
    V2 = "V2"


class CircuitBreakerState(str, Enum):
    """Local, deterministic circuit breaker states."""
    CLOSED = "CLOSED"      # Healthy: V2 execution permitted
    OPEN = "OPEN"          # Tripped: V2 blocked, automatic fallback/V1 route
    HALF_OPEN = "HALF_OPEN"  # Probe: single controlled canary evaluation allowed


class FallbackReason(str, Enum):
    """Typed taxonomy for fallback and circuit breaker triggers."""
    V2_ARTIFACT_MISSING = "V2_ARTIFACT_MISSING"
    V2_ARTIFACT_STALE = "V2_ARTIFACT_STALE"
    V2_RELATIONSHIP_AMBIGUOUS = "V2_RELATIONSHIP_AMBIGUOUS"
    V2_JOIN_PLAN_UNAVAILABLE = "V2_JOIN_PLAN_UNAVAILABLE"
    V2_ANALYTICAL_EVIDENCE_MISSING = "V2_ANALYTICAL_EVIDENCE_MISSING"
    V2_RETRIEVAL_UNAVAILABLE = "V2_RETRIEVAL_UNAVAILABLE"
    V2_SCHEMA_CONTRACT_FAILURE = "V2_SCHEMA_CONTRACT_FAILURE"
    V2_DATASET_VERSION_MISMATCH = "V2_DATASET_VERSION_MISMATCH"
    V2_CONTEXT_GROUNDING_FAILURE = "V2_CONTEXT_GROUNDING_FAILURE"
    V2_RUNTIME_ERROR = "V2_RUNTIME_ERROR"
    KILL_SWITCH_ACTIVE = "KILL_SWITCH_ACTIVE"
    STATE_NOT_V2_ELIGIBLE = "STATE_NOT_V2_ELIGIBLE"
    CIRCUIT_BREAKER_OPEN = "CIRCUIT_BREAKER_OPEN"
    CANARY_NOT_AUTHORIZED = "CANARY_NOT_AUTHORIZED"
    MANUAL_OVERRIDE = "MANUAL_OVERRIDE"


class ConsumerCutoverRecord(BaseModel):
    """
    Governed state record for an individual consumer.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    consumer_name: ConsumerName
    current_state: CutoverState = CutoverState.SHADOW
    previous_state: CutoverState | None = None
    feature_enabled: bool = False
    fallback_allowed: bool = True
    circuit_breaker_state: CircuitBreakerState = CircuitBreakerState.CLOSED
    certification_run_id: str | None = None
    dataset_version: str | None = None
    v2_manifest_fingerprint: str | None = None
    semantic_graph_fingerprint: str | None = None
    activated_at: str | None = None
    last_success_at: str | None = None
    last_failure_at: str | None = None
    fallback_count: int = 0
    last_fallback_reason: FallbackReason | None = None
    transition_version: int = 1


class ConsumerRouteDecision(BaseModel):
    """
    Strongly-typed decision envelope returned for every consumer routing request.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    decision_id: str
    decision_timestamp: str
    decision_version: str = "1.0.0"
    consumer: ConsumerName
    requested_route: Route = Route.V2
    selected_route: Route
    consumer_state: CutoverState
    feature_enabled: bool
    global_enabled: bool
    fallback_allowed: bool
    fallback_used: bool = False
    fallback_reason: FallbackReason | None = None
    circuit_breaker_state: CircuitBreakerState
    dataset_id: str | None = None
    dataset_version: str | None = None
    v2_manifest_fingerprint: str | None = None
    semantic_graph_fingerprint: str | None = None
    rationale: str = ""


class FallbackRecord(BaseModel):
    """
    Governed record created whenever a consumer falls back from V2 to V1.
    Never exists solely in logs or print statements.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    fallback_id: str
    consumer: ConsumerName
    dataset_id: str | None = None
    request_id: str
    reason: FallbackReason
    severity: str = "WARNING"
    failed_artifact_id: str | None = None
    dataset_version: str | None = None
    manifest_fingerprint: str | None = None
    original_route: Route = Route.V2
    fallback_route: Route = Route.V1
    exception_class: str | None = None
    timestamp: str
    resolved: bool = True


class CutoverTransitionLedgerEntry(BaseModel):
    """
    Audit record for state transitions in the cutover decision ledger.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    transition_id: str
    consumer: ConsumerName
    from_state: CutoverState
    to_state: CutoverState
    reason: str
    certification_evidence: str
    commit: str
    artifact_fingerprints: dict[str, str] = Field(default_factory=dict)
    authorized_configuration_source: str = "control-plane"
    timestamp: str


class ReadinessAssessment(BaseModel):
    """
    Result of an artifact and environment readiness inspection for a V2 dataset.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    is_ready: bool
    dataset_id: str
    dataset_version: str
    manifest_exists: bool
    manifest_fresh: bool
    manifest_fingerprint: str | None = None
    semantic_graph_fingerprint: str | None = None
    missing_artifacts: list[str] = Field(default_factory=list)
    evidence_grounding_valid: bool = True
    failure_reasons: list[FallbackReason] = Field(default_factory=list)
    notes: str = ""


class ConsumerRoutingSnapshot(BaseModel):
    """
    Observability snapshot for a consumer's live routing telemetry.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    consumer: ConsumerName
    state: CutoverState
    feature_enabled: bool
    global_enabled: bool
    fallback_allowed: bool
    route_v1_count: int
    route_v2_count: int
    fallback_count: int
    last_fallback_reason: FallbackReason | None
    circuit_state: CircuitBreakerState
    v2_failures: int
