"""
HighView Semantic Data Refinery — Phase SDR-3
Key Intelligence & Candidate Key Contracts
"""

from __future__ import annotations

from enum import Enum
import hashlib
import json
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

from app.services.ingestion_v2.contracts.semantics import SemanticEntityType


class KeyCandidateType(str, Enum):
    """Classification of candidate key structures within a sheet."""
    SYSTEM_ROW_ID = "SYSTEM_ROW_ID"                         # System-assigned counter (row_number, idx)
    CANDIDATE_KEY = "CANDIDATE_KEY"                         # Plausible natural business key
    ATOMIC_NATURAL_KEY = "CANDIDATE_KEY"                    # Alias
    COMPOSITE_CANDIDATE_KEY = "COMPOSITE_CANDIDATE_KEY"     # Multi-column natural business key (width <= 3)
    COMPOSITE_NATURAL_KEY = "COMPOSITE_CANDIDATE_KEY"       # Alias
    HIGH_CONFIDENCE_CANDIDATE_KEY = "HIGH_CONFIDENCE_CANDIDATE_KEY"  # Strong unique natural business key
    FOREIGN_KEY_CANDIDATE = "FOREIGN_KEY_CANDIDATE"         # Local identifier column pointing to external entity
    NON_KEY = "NON_KEY"                                     # Column excluded from key candidacy (measure, free text)
    UNKNOWN = "UNKNOWN"                                     # Insufficient evidence to establish key candidacy



class KeyCandidateStatus(str, Enum):
    """Governed status of a candidate key."""
    HIGH_CONFIDENCE = "HIGH_CONFIDENCE"                     # Clean, unique, minimal, grain-compatible
    HIGH_CONFIDENCE_CANDIDATE_KEY = "HIGH_CONFIDENCE"       # alias
    CANDIDATE = "CANDIDATE"                                 # Plausible with minor dirty/null evidence
    PLAUSIBLE_CANDIDATE_KEY = "CANDIDATE"                   # alias
    AMBIGUOUS = "AMBIGUOUS"                                 # Competing candidates with identical discriminative power
    REJECTED = "REJECTED"                                   # Non-minimal, measure, free text, or grain-incompatible
    UNKNOWN = "UNKNOWN"                                     # Low uniqueness, high nulls, or unclassified
    NON_KEY = "NON_KEY"                                     # Excluded column status
    SUSPECT_KEY = "SUSPECT_KEY"                             # Dirty/inconclusive candidate
    PRIMARY_KEY_CONFIRMED = "PRIMARY_KEY_CONFIRMED"         # Only when upstream declared or human confirmed


class KeyAuthority(str, Enum):
    """Provenance authority of candidate key metadata."""
    INFERRED = "INFERRED"                                   # Discovered deterministically from data and semantics
    STATISTICALLY_INFERRED = "INFERRED"                     # alias
    SOURCE_DECLARED = "SOURCE_DECLARED"                     # Stated in authoritative upstream schema/DDL metadata
    HUMAN_CONFIRMED = "HUMAN_CONFIRMED"                     # Explicitly approved via future human governance interface


class SDRKeyCandidate(BaseModel):
    """
    SDR-3 Governed Key Candidate Contract.
    Captures which column or column set could reliably identify a row/entity at the discovered grain.

    CORE GOVERNANCE INVARIANT:
    Statistical uniqueness != Confirmed Primary Key.
    Uniqueness without source declaration or human confirmation yields HIGH_CONFIDENCE_CANDIDATE_KEY.
    """
    model_config = ConfigDict(frozen=True)

    candidate_id: str
    dataset_id: str
    sheet_id: str

    column_ids: list[str]
    column_names: list[str]

    candidate_type: KeyCandidateType
    entity_type: SemanticEntityType
    grain_expression: str

    width: int
    row_count: int
    unique_combination_count: int
    uniqueness_ratio: float = Field(ge=0.0, le=1.0)

    null_count: int = 0
    null_ratio: float = Field(default=0.0, ge=0.0, le=1.0)

    duplicate_combination_count: int = 0
    duplicate_row_count: int = 0

    semantic_support_score: float = Field(default=0.0, ge=0.0, le=1.0)
    grain_support_score: float = Field(default=0.0, ge=0.0, le=1.0)
    stability_score: float = Field(default=1.0, ge=0.0, le=1.0)
    minimality_score: float = Field(default=1.0, ge=0.0, le=1.0)
    is_minimal: bool = True

    key_confidence: float = Field(ge=0.0, le=1.0)
    authority: KeyAuthority = KeyAuthority.INFERRED
    status: KeyCandidateStatus = KeyCandidateStatus.CANDIDATE

    evidence: str
    sample_duplicate_coordinates: list[str] = Field(default_factory=list)

    source_profile_fingerprints: list[str] = Field(default_factory=list)
    grain_artifact_fingerprint: str = ""
    artifact_fingerprint: str = ""

    @property
    def duplicate_coordinates(self) -> list[str]:
        return self.sample_duplicate_coordinates

    @property
    def duplicate_count(self) -> int:
        return self.duplicate_combination_count

    @property
    def composite_width(self) -> int:
        return self.width

    @property
    def key_type(self) -> KeyCandidateType:
        return self.candidate_type

    @property
    def confidence(self) -> float:
        return self.key_confidence

    @property
    def quality_notes(self) -> str:
        return self.evidence

    @property
    def candidate_fingerprint(self) -> str:
        return self.artifact_fingerprint

    @property
    def entity_reference(self) -> str:
        return self.entity_type.value


class ObservedFunctionalDependency(BaseModel):
    """
    SDR-3 Observed Local Functional Dependency Contract.
    Captures deterministic attribute determination within the current dataset scope.

    CORE EPISTEMIC LAW:
    Scope = CURRENT_DATASET. Never promote local empirical FD to universal business truth.
    """
    model_config = ConfigDict(frozen=True)

    fd_id: str
    dataset_id: str
    sheet_id: str

    determinant_column_ids: list[str]
    determinant_column_names: list[str]

    dependent_column_ids: list[str]
    dependent_column_names: list[str]

    support_ratio: float = Field(ge=0.0, le=1.0)  # Fraction of distinct determinant values with unique dependent value
    violation_count: int = 0
    scope: str = "CURRENT_DATASET"
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = ""

    artifact_fingerprint: str = ""

    @property
    def determinant_columns(self) -> tuple[str, ...]:
        return tuple(self.determinant_column_names)

    @property
    def dependent_columns(self) -> tuple[str, ...]:
        return tuple(self.dependent_column_names)

    @property
    def support(self) -> float:
        return self.support_ratio

    @property
    def exception_count(self) -> int:
        return self.violation_count

    @property
    def status(self) -> str:
        return "CONFIRMED" if self.support_ratio >= 1.0 else "PLAUSIBLE"

    @property
    def fd_fingerprint(self) -> str:
        return self.artifact_fingerprint


def compute_key_candidate_fingerprint(
    dataset_id: str,
    sheet_id: str,
    column_ids: list[str],
    candidate_type: KeyCandidateType,
    grain_expression: str,
    uniqueness_ratio: float,
    key_confidence: float,
    status: KeyCandidateStatus,
    grain_artifact_fingerprint: str,
    policy_fingerprint: str,
) -> str:
    """
    Computes deterministic SHA-256 fingerprint for a key candidate.
    Excludes volatile runtime fields (timestamps, UUIDs, memory addresses).
    """
    payload = {
        "dataset_id": dataset_id,
        "sheet_id": sheet_id,
        "column_ids": sorted(column_ids),
        "candidate_type": candidate_type.value,
        "grain_expression": grain_expression,
        "uniqueness_ratio": round(uniqueness_ratio, 6),
        "key_confidence": round(key_confidence, 4),
        "status": status.value,
        "grain_artifact_fingerprint": grain_artifact_fingerprint,
        "policy_fingerprint": policy_fingerprint,
    }
    canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def compute_fd_fingerprint(
    dataset_id: str,
    sheet_id: str,
    determinant_column_ids: list[str],
    dependent_column_ids: list[str],
    support_ratio: float,
    violation_count: int,
    policy_fingerprint: str,
) -> str:
    """Computes deterministic SHA-256 fingerprint for an observed functional dependency."""
    payload = {
        "dataset_id": dataset_id,
        "sheet_id": sheet_id,
        "determinant_column_ids": sorted(determinant_column_ids),
        "dependent_column_ids": sorted(dependent_column_ids),
        "support_ratio": round(support_ratio, 6),
        "violation_count": violation_count,
        "scope": "CURRENT_DATASET",
        "policy_fingerprint": policy_fingerprint,
    }
    canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
