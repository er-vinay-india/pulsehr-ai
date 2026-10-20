"""
HighView Semantic Data Refinery — Phase SDR-9
SDR Controlled Adoption & Governance Contracts
Enforces typed contracts for SDR consumer adoption states, eligibility assessments,
canary routing envelopes, and multi-tier fallback provenance.
"""

from __future__ import annotations

from enum import Enum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

from app.services.ingestion_v2.contracts.cutover import (
    ConsumerName,
    FallbackReason,
    Route,
)


class SDRAdoptionState(str, Enum):
    """
    Seven explicit SDR adoption lifecycle states for each consumer.
    Progresses from shadow certification to canary and governed primary with fallback.
    """
    SHADOW = "SHADOW"
    CERTIFIED = "CERTIFIED"
    CANARY = "CANARY"
    SDR_PRIMARY_WITH_V2_FALLBACK = "SDR_PRIMARY_WITH_V2_FALLBACK"
    SDR_PRIMARY = "SDR_PRIMARY"
    ROLLBACK = "ROLLBACK"
    SDR_RETIREMENT_ELIGIBLE = "SDR_RETIREMENT_ELIGIBLE"


class SDREligibilityAssessment(BaseModel):
    """
    Assessment of dataset artifacts and safety invariants for SDR adoption.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    is_eligible: bool
    dataset_id: str
    dataset_version: str
    sdr_artifact_fingerprint: str | None = None
    consumer_contract_fingerprint: str | None = None
    missing_artifacts: list[str] = Field(default_factory=list)
    stale_views_count: int = 0
    unsafe_joins_count: int = 0
    ambiguous_joins_count: int = 0
    ambiguous_geo_count: int = 0
    rejection_reasons: list[str] = Field(default_factory=list)
    fallback_reason: FallbackReason | None = None
    notes: str = ""


class SDRAdoptionRecord(BaseModel):
    """
    Governed adoption state record for an individual consumer.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    consumer: ConsumerName
    adoption_state: SDRAdoptionState = SDRAdoptionState.CERTIFIED
    previous_state: SDRAdoptionState | None = None
    feature_enabled: bool = True
    v2_fallback_allowed: bool = True
    dataset_version: str | None = None
    sdr_artifact_fingerprint: str | None = None
    consumer_contract_fingerprint: str | None = None
    canary_percentage: float | None = None
    canary_datasets: list[str] = Field(default_factory=list)
    fallback_count: int = 0
    last_fallback_reason: FallbackReason | None = None
    last_fallback_diagnostic: str | None = None
    activated_at: str | None = None
    last_transition_timestamp: str | None = None


class SDRRouteDecision(BaseModel):
    """
    Decision envelope for SDR controlled adoption routing.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    decision_id: str
    timestamp: str
    consumer: ConsumerName
    requested_route: Route = Route.SDR
    selected_route: Route
    adoption_state: SDRAdoptionState
    dataset_id: str | None = None
    dataset_version: str | None = None
    sdr_artifact_fingerprint: str | None = None
    consumer_contract_fingerprint: str | None = None
    is_canary: bool = False
    canary_authorized: bool = False
    fallback_used: bool = False
    fallback_reason: FallbackReason | None = None
    internal_diagnostic_reason: str | None = None
    rationale: str = ""
