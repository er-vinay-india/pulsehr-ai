"""
HighView Semantic Data Refinery — Phase SDR-1
Semantic Confidence & Execution Policies
"""

from __future__ import annotations

import hashlib
import json
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class SemanticConfidencePolicy(BaseModel):
    """
    Configurable confidence thresholds for semantic profiling and classification.
    Replaces hardcoded magic constants with an audited, tunable contract.
    """
    model_config = ConfigDict(frozen=True)

    promotion_threshold: float = Field(
        default=0.75, ge=0.0, le=1.0,
        description="Minimum confidence score required to promote a semantic hypothesis to confirmed status."
    )
    review_band_lower: float = Field(
        default=0.45, ge=0.0, le=1.0,
        description="Lower bound for ambiguous assignments that require human review or escalation."
    )
    abstention_threshold: float = Field(
        default=0.45, ge=0.0, le=1.0,
        description="Scores below this threshold trigger responsible abstention (UNKNOWN/AMBIGUOUS)."
    )

    # Deterministic signal thresholds
    min_distinct_ratio_for_identifier: float = Field(default=0.85, ge=0.50, le=1.0)
    max_null_ratio_for_identifier: float = Field(default=0.05, ge=0.0, le=0.20)
    currency_symbol_threshold: float = Field(default=0.70, ge=0.10, le=1.0)
    percentage_symbol_threshold: float = Field(default=0.70, ge=0.10, le=1.0)
    date_parseable_threshold: float = Field(default=0.80, ge=0.10, le=1.0)
    numeric_parseable_threshold: float = Field(default=0.85, ge=0.10, le=1.0)
    boolean_threshold: float = Field(default=0.90, ge=0.50, le=1.0)

    # Decomposition thresholds
    min_composite_consistency_ratio: float = Field(
        default=0.80, ge=0.50, le=1.0,
        description="Minimum proportion of sample rows that must match candidate composite pattern."
    )
    min_sample_rows_for_decomposition: int = Field(default=5, ge=2)


class GrainConfidencePolicy(BaseModel):
    """
    Configurable confidence thresholds for grain discovery and composite combination pruning.
    Enforces bounded combinatorial search and prevents measure/surrogate pollution.
    """
    model_config = ConfigDict(frozen=True)

    max_composite_width: int = Field(default=3, ge=1, le=5)
    max_composite_candidates_eval: int = Field(default=15, ge=1, le=50)
    min_uniqueness_for_single_grain: float = Field(default=0.85, ge=0.50, le=1.0)
    min_uniqueness_for_composite_grain: float = Field(default=0.90, ge=0.60, le=1.0)
    max_null_ratio_for_grain: float = Field(default=0.05, ge=0.0, le=0.20)
    ambiguity_margin: float = Field(default=0.05, ge=0.01, le=0.20)
    entity_support_min_columns: int = Field(default=1, ge=1)


class KeyConfidencePolicy(BaseModel):
    """
    Configurable confidence thresholds for candidate key discovery and identity intelligence.
    Enforces minimality, grain alignment, and bounded functional dependency search.
    """
    model_config = ConfigDict(frozen=True)

    max_composite_width: int = Field(default=3, ge=1, le=5)
    min_uniqueness_for_candidate: float = Field(default=0.90, ge=0.50, le=1.0)
    min_uniqueness_for_high_confidence: float = Field(default=0.99, ge=0.80, le=1.0)
    max_null_ratio: float = Field(default=0.05, ge=0.0, le=0.20)
    minimality_tolerance: float = Field(default=0.0, ge=0.0, le=0.05)
    max_candidates: int = Field(default=20, ge=1, le=100)
    ambiguity_margin: float = Field(default=0.03, ge=0.01, le=0.10)

    # Functional dependency observation thresholds
    fd_max_determinant_width: int = Field(default=2, ge=1, le=3)
    fd_min_support: float = Field(default=0.98, ge=0.80, le=1.0)
    fd_sample_size: int = Field(default=5000, ge=100)


class SDRPolicySuite(BaseModel):
    """
    Unified SDR Policy Suite capturing semantic and analytical execution configuration.
    """
    model_config = ConfigDict(frozen=True)

    policy_id: str = "default_enterprise_balanced"
    version: str = "1.0.0"
    semantic: SemanticConfidencePolicy = SemanticConfidencePolicy()
    grain: GrainConfidencePolicy = GrainConfidencePolicy()
    key: KeyConfidencePolicy = KeyConfidencePolicy()

    def compute_policy_fingerprint(self) -> str:
        """Deterministic fingerprint of active policy configuration."""
        payload = {
            "policy_id": self.policy_id,
            "version": self.version,
            "semantic": self.semantic.model_dump(),
            "grain": self.grain.model_dump(),
            "key": self.key.model_dump(),
        }
        canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

