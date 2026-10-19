"""
HighView Semantic Data Refinery — Phase SDR-1
Semantic Column Profile Contracts
"""

from __future__ import annotations

from enum import Enum
import hashlib
import json
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

# Reused authoritative contracts from Ingestion V2
from app.services.ingestion_v2.contracts.semantics import (
    ClassificationSource,
    MeasureClass,
    SemanticColumnRole,
    SemanticConcept,
    SemanticEntityType,
)
from app.services.ingestion_v2.contracts.provenance import SourceCoordinateRef


class SemanticDtype(str, Enum):
    """
    Semantic Data Types representing logical, domain-level representation.
    Strictly decoupled from physical storage types (e.g. string, float64).
    """
    INTEGER_NUMBER = "INTEGER_NUMBER"
    DECIMAL_NUMBER = "DECIMAL_NUMBER"
    CURRENCY_AMOUNT = "CURRENCY_AMOUNT"
    PERCENTAGE_RATE = "PERCENTAGE_RATE"
    DATE = "DATE"
    DATETIME = "DATETIME"
    TIME_OF_DAY = "TIME_OF_DAY"
    BOOLEAN_FLAG = "BOOLEAN_FLAG"
    IDENTIFIER_CODE = "IDENTIFIER_CODE"
    GEOGRAPHIC_LOCATION = "GEOGRAPHIC_LOCATION"
    CATEGORICAL_CODE = "CATEGORICAL_CODE"
    NATURAL_LANGUAGE_TEXT = "NATURAL_LANGUAGE_TEXT"
    COMPOSITE_TEXT = "COMPOSITE_TEXT"
    UNKNOWN = "UNKNOWN"

    # Backward-compatible convenience aliases
    ID = "IDENTIFIER_CODE"
    TEXT = "NATURAL_LANGUAGE_TEXT"
    CATEGORICAL = "CATEGORICAL_CODE"
    DECIMAL = "DECIMAL_NUMBER"
    INTEGER = "INTEGER_NUMBER"
    TIMESTAMP = "DATETIME"



class PrivacyClassification(str, Enum):
    """
    SDR Privacy and Identifier Governance taxonomy.
    Differentiates direct keys from sensitive attributes and strictly prohibits inferred sensitivity.
    """
    DIRECT_IDENTIFIER = "DIRECT_IDENTIFIER"                   # Authorized for deterministic joins; masked from display
    SENSITIVE_ATTRIBUTE = "SENSITIVE_ATTRIBUTE"               # Restricted per governance; aggregations allowed
    INFERRED_SENSITIVE_ATTRIBUTE = "INFERRED_SENSITIVE_ATTRIBUTE" # Prohibited: probabilistic derivation forbidden
    GENERAL_ATTRIBUTE = "GENERAL_ATTRIBUTE"                   # Non-sensitive dimension/measure
    PUBLIC = "GENERAL_ATTRIBUTE"                              # Convenience alias
    UNKNOWN = "UNKNOWN"



class ProfilingAmbiguityState(str, Enum):
    """Explicit ambiguity tracking for semantic profiling."""
    CLEAR = "CLEAR"
    AMBIGUOUS_ROLE = "AMBIGUOUS_ROLE"
    AMBIGUOUS_TYPE = "AMBIGUOUS_TYPE"
    UNKNOWN_DISTRIBUTION = "UNKNOWN_DISTRIBUTION"
    CONTRADICTORY_SIGNALS = "CONTRADICTORY_SIGNALS"


class DeterministicColumnFeatures(BaseModel):
    """
    Deterministic statistical and structural observations extracted from column values.
    Pure calculations prior to any semantic role or model inference.
    """
    model_config = ConfigDict(frozen=True)

    row_count: int
    null_count: int
    null_ratio: float = Field(ge=0.0, le=1.0)
    distinct_count: int
    distinct_ratio: float = Field(ge=0.0, le=1.0)

    numeric_parseable_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    integer_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    date_parseable_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    boolean_vocabulary_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    currency_symbol_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    percentage_symbol_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    identifier_pattern_ratio: float = Field(default=0.0, ge=0.0, le=1.0)

    avg_value_length: float = 0.0
    delimiter_counts: dict[str, int] = Field(default_factory=dict)
    sample_values: list[str] = Field(default_factory=list)
    sample_fingerprint: str = ""


class SemanticColumnProfile(BaseModel):
    """
    SDR-1 Semantic Column Profile Contract.
    Captures what a physical column means, its physical vs semantic types,
    its semantic role hypothesis, and whether it represents composite concepts.
    """
    model_config = ConfigDict(frozen=True)

    profile_id: str
    dataset_id: str
    sheet_id: str
    column_id: str

    source_name: str
    canonical_name: str

    physical_dtype: str
    semantic_dtype: SemanticDtype

    semantic_role: SemanticColumnRole
    semantic_concept: SemanticConcept
    entity_type_hypothesis: SemanticEntityType = SemanticEntityType.UNKNOWN

    measure_class: MeasureClass | None = None
    unit: str | None = None
    currency: str | None = None

    privacy_classification: PrivacyClassification = PrivacyClassification.UNKNOWN

    features: DeterministicColumnFeatures

    confidence: float = Field(ge=0.0, le=1.0)
    authority: str = "DETERMINISTIC"
    classification_source: ClassificationSource = ClassificationSource.STATISTICAL

    ambiguity_state: ProfilingAmbiguityState = ProfilingAmbiguityState.CLEAR
    is_composite_candidate: bool = False

    source_lineage: SourceCoordinateRef
    artifact_fingerprint: str = ""


def compute_profile_fingerprint(
    dataset_id: str,
    sheet_id: str,
    column_id: str,
    source_name: str,
    physical_dtype: str,
    semantic_dtype: SemanticDtype,
    semantic_role: SemanticColumnRole,
    features_sample_fingerprint: str,
    policy_fingerprint: str,
) -> str:
    """
    Computes a deterministic SHA-256 fingerprint for a semantic column profile.
    Volatile runtime fields (timestamps, UUIDs, host paths) are strictly excluded.
    """
    payload = {
        "dataset_id": dataset_id,
        "sheet_id": sheet_id,
        "column_id": column_id,
        "source_name": source_name,
        "physical_dtype": physical_dtype,
        "semantic_dtype": semantic_dtype.value,
        "semantic_role": semantic_role.value,
        "sample_fingerprint": features_sample_fingerprint,
        "policy_fingerprint": policy_fingerprint,
    }
    canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
