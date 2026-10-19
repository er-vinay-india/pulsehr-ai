"""
HighView Semantic Data Refinery — Phase SDR-2
Grain Discovery Contracts
"""

from __future__ import annotations

from enum import Enum
import hashlib
import json
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

# Reused authoritative contracts from Ingestion V2
from app.services.ingestion_v2.contracts.grain import (
    CanonicalGrain,
    TemporalGrain,
)


class GrainStatus(str, Enum):
    """Governed status of grain inference for a sheet."""
    RESOLVED = "RESOLVED"        # Clean dominant candidate with clear semantic support
    PROVISIONAL = "PROVISIONAL"  # Plausible candidate discovered with moderate uniqueness
    AMBIGUOUS = "AMBIGUOUS"      # Multiple competing candidates or conflicting evidence
    UNKNOWN = "UNKNOWN"          # No plausible business grain discovered


class GrainCandidate(BaseModel):
    """
    Evaluated determinant column combination candidate.
    Captures structural combination uniqueness and duplicate statistics.
    DO NOT CALL THESE 'PRIMARY KEY': They are grain evidence only.
    """
    model_config = ConfigDict(frozen=True)

    candidate_id: str
    determinant_column_ids: list[str]
    determinant_column_names: list[str]
    grain_expression: str
    width: int

    row_count: int
    unique_combination_count: int
    uniqueness_ratio: float = Field(ge=0.0, le=1.0)
    duplicate_combination_count: int = 0
    duplicate_row_count: int = 0
    null_involvement_ratio: float = Field(default=0.0, ge=0.0, le=1.0)

    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str


class SDRGrainProfile(BaseModel):
    """
    SDR-2 Governed Table Grain Profile Contract.
    Captures what ONE ROW physically and semantically represents in a sheet.

    CORE EPISTEMIC LAW:
    Uniqueness is evidence, not meaning.
    Surrogate sequence keys or arbitrary unique measures NEVER override business grain.
    """
    model_config = ConfigDict(frozen=True)

    profile_id: str
    dataset_id: str
    sheet_id: str

    primary_entity: CanonicalGrain
    temporal_grain: TemporalGrain = TemporalGrain.NONE

    resolved_grain_expression: str  # e.g., "EMPLOYEE", "EMPLOYEE x MONTH", "STORE x SKU x DAY"
    grain_status: GrainStatus

    best_candidate: GrainCandidate | None = None
    ranked_candidates: list[GrainCandidate] = Field(default_factory=list)

    is_unique: bool = False
    grain_confidence: float = Field(ge=0.0, le=1.0)
    rationale: str

    source_profile_fingerprints: list[str] = Field(default_factory=list)
    artifact_fingerprint: str = ""


def compute_grain_profile_fingerprint(
    dataset_id: str,
    sheet_id: str,
    primary_entity: CanonicalGrain,
    temporal_grain: TemporalGrain,
    resolved_grain_expression: str,
    best_candidate_ids: list[str],
    grain_status: GrainStatus,
    policy_fingerprint: str,
) -> str:
    """
    Computes a deterministic SHA-256 fingerprint for a table grain profile.
    """
    payload = {
        "dataset_id": dataset_id,
        "sheet_id": sheet_id,
        "primary_entity": primary_entity.value,
        "temporal_grain": temporal_grain.value,
        "resolved_grain_expression": resolved_grain_expression,
        "best_candidate_ids": sorted(best_candidate_ids),
        "grain_status": grain_status.value,
        "policy_fingerprint": policy_fingerprint,
    }
    canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
