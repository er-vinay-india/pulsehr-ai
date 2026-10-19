"""
HighView Semantic Data Refinery — Phase SDR-4
Controlled Enrichment Framework Contracts
"""

from __future__ import annotations

from enum import Enum
import hashlib
import json
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

from app.services.ingestion_v2.contracts.provenance import SourceCoordinateRef
from app.services.sdr.contracts.profiles import (
    PrivacyClassification,
    ProfilingAmbiguityState,
    SemanticDtype,
)


class EnrichmentProviderType(str, Enum):
    """Execution modality of an enrichment provider."""
    LOCAL_REFERENCE = "LOCAL_REFERENCE"       # In-memory dictionary, code list, or local asset
    DETERMINISTIC_RULE = "DETERMINISTIC_RULE" # Pure algorithmic projection (calendar math, unit conversion)
    MODEL_ASSISTED = "MODEL_ASSISTED"         # LLM/Classifier opportunity hypothesis (values must still be verified)
    EXTERNAL_API = "EXTERNAL_API"             # Remote HTTP/cloud API (out-of-scope for SDR-4 core)


class EnrichmentStatus(str, Enum):
    """Governed lifecycle status of an enrichment candidate or validated output."""
    CANDIDATE = "CANDIDATE"                   # Proposed by provider; pending gate & decision evaluation
    AUTHORIZED = "AUTHORIZED"                 # Passed hard gates, utility scoring, and governance approval
    AMBIGUOUS = "AMBIGUOUS"                   # Input meaning unclear or multiple conflicting targets exist
    DEFERRED = "DEFERRED"                     # Low utility or currently unfunded by enrichment budget
    REJECTED = "REJECTED"                     # Failed utility threshold, domain relevance, or budget cap
    BLOCKED = "BLOCKED"                       # Hard gate violation (privacy block, sensitive inference, etc.)


class EnrichmentMaterialization(str, Enum):
    """Storage policy for derived enrichment values."""
    VIRTUAL_ENRICHMENT = "VIRTUAL_ENRICHMENT"         # Logical projection evaluated on demand
    MATERIALIZED_ENRICHMENT = "MATERIALIZED_ENRICHMENT" # Physical Silver column persisted for performance/reuse


class EnrichmentDecisionType(str, Enum):
    """Definitive decision issued by the Information Gain Engine."""
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    AMBIGUOUS = "AMBIGUOUS"
    DEFER = "DEFER"


class EnrichmentProviderMetadata(BaseModel):
    """Contractual capability metadata registered by an EnrichmentProvider."""
    model_config = ConfigDict(frozen=True)

    provider_id: str
    provider_name: str
    provider_version: str
    provider_type: EnrichmentProviderType
    supported_input_semantics: list[SemanticDtype]
    supported_output_semantics: list[SemanticDtype]
    is_offline: bool = True
    is_deterministic: bool = True
    reference_data_version: str = "1.0.0"
    license_or_provenance: str = "Internal HighView Built-in"


class EnrichmentCandidate(BaseModel):
    """
    Proposed candidate enrichment produced by a provider.
    Important: Candidate != Accepted/Authorized Enrichment.
    """
    model_config = ConfigDict(frozen=True)

    candidate_id: str
    dataset_id: str
    sheet_id: str
    source_column_ids: list[str]
    source_column_names: list[str]

    source_semantic_type: SemanticDtype
    source_values_fingerprint: str

    proposed_enrichment_type: str
    proposed_output_name: str
    proposed_output_semantic_type: SemanticDtype

    provider_id: str
    provider_version: str
    reference_data_version: str = "1.0.0"

    confidence: float = Field(ge=0.0, le=1.0)
    ambiguity_state: ProfilingAmbiguityState = ProfilingAmbiguityState.CLEAR

    information_gain_record: dict[str, Any] = Field(default_factory=dict)
    privacy_classification: PrivacyClassification = PrivacyClassification.GENERAL_ATTRIBUTE
    validation_status: EnrichmentStatus = EnrichmentStatus.CANDIDATE

    depth: int = 1
    parent_enrichment_id: str | None = None

    provenance: SourceCoordinateRef
    artifact_fingerprint: str = ""


class EnrichmentDecisionRecord(BaseModel):
    """
    Audit record evaluating hard governance gates and multi-factor information gain.
    """
    model_config = ConfigDict(frozen=True)

    decision_id: str
    candidate_id: str
    dataset_id: str
    sheet_id: str
    decision: EnrichmentDecisionType

    # Hard governance evaluation
    hard_gate_passed: bool
    hard_gate_failures: list[str] = Field(default_factory=list)

    # Multi-factor utility metrics (0.0 to 1.0)
    analytical_utility: float = Field(default=0.0, ge=0.0, le=1.0)
    domain_relevance: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    ambiguity_score: float = Field(default=0.0, ge=0.0, le=1.0)
    privacy_risk_score: float = Field(default=0.0, ge=0.0, le=1.0)
    provenance_quality: float = Field(default=1.0, ge=0.0, le=1.0)
    compute_cost: float = Field(default=0.1, ge=0.0, le=1.0)
    storage_cost: float = Field(default=0.1, ge=0.0, le=1.0)

    net_information_gain: float = Field(default=0.0)
    rationale: str = ""
    artifact_fingerprint: str = ""


class ValidatedEnrichment(BaseModel):
    """
    Governed, accepted derived enrichment output.
    Observed source evidence (EVID-*) remains distinct from derived evidence (ENRICH-*).
    """
    model_config = ConfigDict(frozen=True)

    enrichment_id: str  # Conceptual prefix ENRICH-* (e.g. ENRICH-DATE-001)
    dataset_id: str
    sheet_id: str

    source_column_ids: list[str]
    source_column_names: list[str]

    output_name: str
    output_semantic_type: SemanticDtype

    # Projection definition: virtual expression or materialized data reference
    output_values_reference: str | None = None
    deterministic_projection_expression: str | None = None
    materialization: EnrichmentMaterialization = EnrichmentMaterialization.VIRTUAL_ENRICHMENT

    provider_id: str
    provider_version: str
    reference_data_version: str

    confidence: float = Field(ge=0.0, le=1.0)
    authority: str = "DERIVED_ENRICHMENT"

    depth: int = 1
    parent_enrichment_id: str | None = None

    lineage: dict[str, Any] = Field(default_factory=dict)
    decision_record_id: str

    is_valid: bool = True
    invalidation_reason: str | None = None

    artifact_fingerprint: str = ""


def compute_enrichment_candidate_fingerprint(
    dataset_id: str,
    sheet_id: str,
    source_column_ids: list[str],
    source_values_fingerprint: str,
    proposed_output_name: str,
    proposed_output_semantic_type: SemanticDtype,
    provider_id: str,
    provider_version: str,
    reference_data_version: str,
    policy_fingerprint: str,
) -> str:
    """Computes deterministic SHA-256 fingerprint for an enrichment candidate."""
    payload = {
        "dataset_id": dataset_id,
        "sheet_id": sheet_id,
        "source_column_ids": sorted(source_column_ids),
        "source_values_fingerprint": source_values_fingerprint,
        "proposed_output_name": proposed_output_name,
        "proposed_output_semantic_type": proposed_output_semantic_type.value,
        "provider_id": provider_id,
        "provider_version": provider_version,
        "reference_data_version": reference_data_version,
        "policy_fingerprint": policy_fingerprint,
    }
    canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def compute_enrichment_decision_fingerprint(
    candidate_id: str,
    decision: EnrichmentDecisionType,
    hard_gate_passed: bool,
    hard_gate_failures: list[str],
    analytical_utility: float,
    net_information_gain: float,
    policy_fingerprint: str,
) -> str:
    """Computes deterministic SHA-256 fingerprint for an enrichment decision."""
    payload = {
        "candidate_id": candidate_id,
        "decision": decision.value,
        "hard_gate_passed": hard_gate_passed,
        "hard_gate_failures": sorted(hard_gate_failures),
        "analytical_utility": round(analytical_utility, 4),
        "net_information_gain": round(net_information_gain, 4),
        "policy_fingerprint": policy_fingerprint,
    }
    canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def compute_validated_enrichment_fingerprint(
    enrichment_id: str,
    dataset_id: str,
    sheet_id: str,
    source_column_ids: list[str],
    output_name: str,
    output_semantic_type: SemanticDtype,
    provider_id: str,
    provider_version: str,
    reference_data_version: str,
    materialization: EnrichmentMaterialization,
    decision_record_id: str,
    policy_fingerprint: str,
) -> str:
    """Computes deterministic SHA-256 fingerprint for a validated enrichment."""
    payload = {
        "enrichment_id": enrichment_id,
        "dataset_id": dataset_id,
        "sheet_id": sheet_id,
        "source_column_ids": sorted(source_column_ids),
        "output_name": output_name,
        "output_semantic_type": output_semantic_type.value,
        "provider_id": provider_id,
        "provider_version": provider_version,
        "reference_data_version": reference_data_version,
        "materialization": materialization.value,
        "decision_record_id": decision_record_id,
        "policy_fingerprint": policy_fingerprint,
    }
    canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
