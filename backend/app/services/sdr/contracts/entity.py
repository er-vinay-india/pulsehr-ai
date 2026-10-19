"""
HighView Semantic Data Refinery — Phase SDR-2
Entity Hypothesis Contracts
"""

from __future__ import annotations

from enum import Enum
import hashlib
import json
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

from app.services.ingestion_v2.contracts.semantics import SemanticEntityType


class EntityHypothesisState(str, Enum):
    """Lifecycle state of an entity hypothesis within a sheet."""
    PROVISIONAL = "PROVISIONAL"
    CONFIRMED = "CONFIRMED"
    AMBIGUOUS = "AMBIGUOUS"
    REJECTED = "REJECTED"


class SemanticEntityHypothesis(BaseModel):
    """
    SDR-2 Semantic Entity Hypothesis Contract.
    Captures what business object a sheet appears to describe.

    CORE EPISTEMIC LAW:
    EntityConfidence != KeyConfidence != GrainConfidence.
    The presence of duplicate or dirty keys does NOT invalidate entity existence.
    """
    model_config = ConfigDict(frozen=True)

    entity_hypothesis_id: str
    dataset_id: str
    sheet_id: str

    entity_type: SemanticEntityType
    canonical_name: str  # e.g., "EMPLOYEE", "STORE", "DEPARTMENT", "TRANSACTION"

    supporting_column_ids: list[str] = Field(default_factory=list)
    identifier_like_column_ids: list[str] = Field(default_factory=list)
    descriptor_column_ids: list[str] = Field(default_factory=list)
    measure_column_ids: list[str] = Field(default_factory=list)
    temporal_column_ids: list[str] = Field(default_factory=list)

    entity_confidence: float = Field(ge=0.0, le=1.0)
    evidence: str
    state: EntityHypothesisState = EntityHypothesisState.PROVISIONAL

    authority: str = "DETERMINISTIC_HEURISTIC"
    source_profile_fingerprints: list[str] = Field(default_factory=list)
    artifact_fingerprint: str = ""


def compute_entity_hypothesis_fingerprint(
    dataset_id: str,
    sheet_id: str,
    entity_type: SemanticEntityType,
    canonical_name: str,
    supporting_column_ids: list[str],
    source_profile_fingerprints: list[str],
    policy_fingerprint: str,
) -> str:
    """
    Computes a deterministic SHA-256 fingerprint for an entity hypothesis.
    Excludes volatile fields (timestamps, UUIDs, runtime paths).
    """
    payload = {
        "dataset_id": dataset_id,
        "sheet_id": sheet_id,
        "entity_type": entity_type.value,
        "canonical_name": canonical_name,
        "supporting_column_ids": sorted(supporting_column_ids),
        "source_profile_fingerprints": sorted(source_profile_fingerprints),
        "policy_fingerprint": policy_fingerprint,
    }
    canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
