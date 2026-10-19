"""
HighView Semantic Data Refinery — Phase SDR-1
Decomposition Candidate Contracts
"""

from __future__ import annotations

from enum import Enum
import hashlib
import json
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

from app.services.ingestion_v2.contracts.semantics import (
    SemanticColumnRole,
    SemanticConcept,
)
from app.services.sdr.contracts.profiles import SemanticDtype


class CompositePatternType(str, Enum):
    """
    Recognized deterministic composite structure patterns.
    """
    DELIMITER_SPLIT = "DELIMITER_SPLIT"            # Consistent punctuation delimiter (e.g. " | ", " - ")
    CODE_LABEL_PAIR = "CODE_LABEL_PAIR"            # Alphanumeric code followed by descriptive label
    TEMPORAL_COMPOSITE = "TEMPORAL_COMPOSITE"      # Year-Quarter (e.g. 2026-Q3), Fiscal-Month
    CURRENCY_WITH_UNIT = "CURRENCY_WITH_UNIT"      # Monetary amount with explicit currency symbol/code
    GEOGRAPHIC_HIERARCHY = "GEOGRAPHIC_HIERARCHY"  # City - State - Country multi-tier string
    UNKNOWN = "UNKNOWN"


class DecompositionValidationStatus(str, Enum):
    """Lifecycle status of a decomposition candidate."""
    PROVISIONAL = "PROVISIONAL"  # Initial hypothesis from pattern matching
    VALIDATED = "VALIDATED"      # Verified across sample rows and false-split filters
    AMBIGUOUS = "AMBIGUOUS"      # Pattern detected but contains contradictory tokens
    REJECTED = "REJECTED"        # Denied by false-split prevention guards


class DecompositionComponent(BaseModel):
    """
    Sub-component specification for a candidate decomposition.
    """
    model_config = ConfigDict(frozen=True)

    position: int
    candidate_name: str
    proposed_semantic_role: SemanticColumnRole
    proposed_semantic_dtype: SemanticDtype
    proposed_concept: SemanticConcept
    sample_extractions: list[str] = Field(default_factory=list)
    extraction_rule: str


class SemanticDecompositionCandidate(BaseModel):
    """
    SDR-1 Decomposition Candidate Contract.
    Captures non-destructive proposals for breaking a physical composite column
    into multiple logical semantic components.

    MANDATORY INVARIANT: is_destructive = False
    Source columns are NEVER modified, dropped, or mutated.
    """
    model_config = ConfigDict(frozen=True)

    candidate_id: str
    dataset_id: str
    sheet_id: str
    source_column_id: str
    source_column_name: str

    pattern_type: CompositePatternType
    delimiter: str | None = None

    components: list[DecompositionComponent] = Field(default_factory=list)
    sample_extractions: list[dict[str, str]] = Field(default_factory=list)

    confidence: float = Field(ge=0.0, le=1.0)
    validation_status: DecompositionValidationStatus = DecompositionValidationStatus.PROVISIONAL

    source_profile_fingerprint: str
    is_destructive: bool = False  # Hard invariant: non-destructive metadata only
    candidate_fingerprint: str = ""


def compute_candidate_fingerprint(
    dataset_id: str,
    sheet_id: str,
    source_column_id: str,
    pattern_type: CompositePatternType,
    component_names: list[str],
    source_profile_fingerprint: str,
) -> str:
    """
    Computes a deterministic SHA-256 fingerprint for a decomposition candidate.
    """
    payload = {
        "dataset_id": dataset_id,
        "sheet_id": sheet_id,
        "source_column_id": source_column_id,
        "pattern_type": pattern_type.value,
        "component_names": component_names,
        "source_profile_fingerprint": source_profile_fingerprint,
    }
    canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
