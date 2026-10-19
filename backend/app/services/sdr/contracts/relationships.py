"""
HighView Semantic Data Refinery — Phase SDR-5
Relationship Intelligence & Governed Join Contracts

Reuses existing frozen Ingestion V2 relationship and join contracts wherever possible:
- ValidatedRelationshipEdge
- RelationshipCardinality
- RelationshipStatus
- CandidateKeyType
- JoinPlan
- JoinSafetyStatus
- MeasureAdditivity
- PreAggregationSpec
- JoinSafetyAssessment

Adds SDR-5 specific governed candidate models, relationship classes, and fingerprinting functions.
"""

from __future__ import annotations

from enum import Enum
import hashlib
import json
from typing import Any, Sequence
from pydantic import BaseModel, ConfigDict, Field

# Reused frozen contracts from Ingestion V2
from app.services.ingestion_v2.contracts.joins import (
    GovernedJoinPlanSet,
    JoinPlan,
    JoinSafetyAssessment,
    JoinSafetyStatus,
    MeasureAdditivity,
    PreAggregationSpec,
)
from app.services.ingestion_v2.contracts.relationships import (
    CandidateKeyType,
    RelationshipCandidate,
    RelationshipCandidateSet,
    RelationshipCardinality,
    RelationshipStatus,
    ValidatedRelationshipEdge,
    ValidatedRelationshipGraph,
)


class RelationshipClass(str, Enum):
    """
    SDR-5 Relationship Classification.
    Distinguishes structural/entity joins from semantic, analytical, or retrieval similarities.
    Only STRUCTURAL_RELATIONSHIP and ENTITY_RELATIONSHIP may become JoinPlans.
    """
    STRUCTURAL_RELATIONSHIP = "STRUCTURAL_RELATIONSHIP"  # Direct key/foreign key referential connection
    ENTITY_RELATIONSHIP = "ENTITY_RELATIONSHIP"          # Entity-to-entity business association
    SEMANTIC_RELATIONSHIP = "SEMANTIC_RELATIONSHIP"      # Conceptually related but no joinable key
    ANALYTICAL_RELATIONSHIP = "ANALYTICAL_RELATIONSHIP"  # High-level analytical co-occurrence
    ENRICHMENT_RELATIONSHIP = "ENRICHMENT_RELATIONSHIP"  # Reference/enrichment lookup dependency (e.g. GEO)
    RETRIEVAL_SIMILARITY = "RETRIEVAL_SIMILARITY"        # Lexical/embedding vector similarity for search


class SDRRelationshipCandidate(BaseModel):
    """
    SDR-5 Governed Relationship Candidate Contract.
    Captures multi-signal discovery evidence before deterministic validation.
    Candidate != ValidatedRelationshipEdge.
    """
    model_config = ConfigDict(frozen=True)

    candidate_id: str
    dataset_id: str

    left_sheet_id: str
    right_sheet_id: str

    left_column_ids: list[str]
    right_column_ids: list[str]

    left_key_candidate_id: str | None = None
    right_key_candidate_id: str | None = None

    left_grain: str = "UNKNOWN"
    right_grain: str = "UNKNOWN"

    relationship_class: RelationshipClass = RelationshipClass.STRUCTURAL_RELATIONSHIP

    semantic_compatibility: float = Field(default=0.0, ge=0.0, le=1.0)
    dtype_compatibility: float = Field(default=0.0, ge=0.0, le=1.0)
    normalized_value_compatibility: float = Field(default=0.0, ge=0.0, le=1.0)
    referential_overlap: float = Field(default=0.0, ge=0.0, le=1.0)

    left_coverage: float = Field(default=0.0, ge=0.0, le=1.0)
    right_coverage: float = Field(default=0.0, ge=0.0, le=1.0)

    left_null_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    right_null_ratio: float = Field(default=0.0, ge=0.0, le=1.0)

    left_duplicate_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    right_duplicate_ratio: float = Field(default=0.0, ge=0.0, le=1.0)

    candidate_cardinality: RelationshipCardinality = RelationshipCardinality.MANY_TO_ONE

    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence: dict[str, Any] = Field(default_factory=dict)

    dataset_version: str = "v1"
    artifact_fingerprint: str = ""

    def to_ingestion_candidate(self) -> RelationshipCandidate:
        """Converts to Ingestion V2 frozen RelationshipCandidate."""
        return RelationshipCandidate(
            candidate_id=self.candidate_id,
            source_table_id=self.left_sheet_id,
            source_column_ids=self.left_column_ids,
            target_table_id=self.right_sheet_id,
            target_column_ids=self.right_column_ids,
            key_type=CandidateKeyType.COMPOSITE if len(self.left_column_ids) > 1 else CandidateKeyType.SINGLE,
            discovery_method=self.relationship_class.value,
            confidence_score=self.confidence,
        )


class SDRValidatedRelationshipEdge(BaseModel):
    """
    SDR-5 Extended Validated Relationship Edge.
    Wraps/extends frozen ValidatedRelationshipEdge with SDR-5 governance attributes.
    """
    model_config = ConfigDict(frozen=True)

    edge_id: str
    candidate_id: str
    dataset_id: str

    left_sheet_id: str
    right_sheet_id: str

    left_column_ids: list[str]
    right_column_ids: list[str]

    key_type: CandidateKeyType = CandidateKeyType.SINGLE
    cardinality: RelationshipCardinality
    status: RelationshipStatus
    relationship_class: RelationshipClass = RelationshipClass.STRUCTURAL_RELATIONSHIP

    referential_coverage: float = Field(ge=0.0, le=1.0)
    left_coverage: float = Field(ge=0.0, le=1.0)
    right_coverage: float = Field(ge=0.0, le=1.0)

    unmatched_left_count: int = 0
    unmatched_right_count: int = 0

    left_null_count: int = 0
    right_null_count: int = 0

    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    estimated_row_multiplier: float = Field(default=1.0, ge=0.0)

    left_grain: str = "UNKNOWN"
    right_grain: str = "UNKNOWN"
    is_grain_preserving: bool = True
    duplication_risk_flag: bool = False

    left_rows: int = 0
    right_rows: int = 0
    matched_distinct_keys: int = 0
    matched_pairs: int = 0
    unmatched_left_rows: int = 0
    unmatched_right_rows: int = 0
    estimated_result_rows: int = 0
    expansion_ratio: float = 1.0
    max_frequency_bound: int = 1

    key_fingerprints: list[str] = Field(default_factory=list)
    grain_fingerprints: list[str] = Field(default_factory=list)
    policy_fingerprint: str = ""

    rejection_reason: str | None = None
    validation_evidence: dict[str, Any] = Field(default_factory=dict)

    dataset_version: str = "v1"
    artifact_fingerprint: str = ""

    def to_ingestion_edge(self) -> ValidatedRelationshipEdge:
        """Converts to Ingestion V2 frozen ValidatedRelationshipEdge."""
        return ValidatedRelationshipEdge(
            edge_id=self.edge_id,
            candidate_id=self.candidate_id,
            source_table_id=self.left_sheet_id,
            source_column_ids=self.left_column_ids,
            target_table_id=self.right_sheet_id,
            target_column_ids=self.right_column_ids,
            key_type=self.key_type,
            cardinality=self.cardinality,
            status=self.status,
            referential_coverage=self.referential_coverage,
            source_overlap_ratio=self.left_coverage,
            target_overlap_ratio=self.right_coverage,
            confidence=self.confidence,
            estimated_row_multiplier=self.estimated_row_multiplier,
            is_grain_preserving=self.is_grain_preserving,
            duplication_risk_flag=self.duplication_risk_flag,
            rejection_reason=self.rejection_reason,
            validation_evidence=self.validation_evidence,
        )


class SDRJoinPlan(BaseModel):
    """
    SDR-5 Governed Operational Join Plan.
    Extends frozen JoinPlan with SDR-5 governance attributes.
    """
    model_config = ConfigDict(frozen=True)

    join_plan_id: str
    relationship_edge_id: str
    dataset_id: str

    left_sheet_id: str
    right_sheet_id: str

    left_keys: list[str]
    right_keys: list[str]

    join_type: str  # "INNER", "LEFT" (CROSS is strictly forbidden)
    safety_status: JoinSafetyStatus

    left_grain: str
    right_grain: str
    target_grain: str

    required_preaggregation: bool = False
    preaggregation_side: str | None = None  # "LEFT" or "RIGHT"
    preaggregation_spec: PreAggregationSpec | None = None

    cardinality: RelationshipCardinality = RelationshipCardinality.MANY_TO_ONE
    coverage: float = Field(default=1.0, ge=0.0, le=1.0)

    measure_additivity_rules: dict[str, MeasureAdditivity] = Field(default_factory=dict)

    expected_input_rows: int = 0
    expected_output_rows: int = 0
    expansion_ratio: float = 1.0
    max_expected_multiplier: float = 1.0

    left_rows: int = 0
    right_rows: int = 0
    matched_distinct_keys: int = 0
    matched_pairs: int = 0
    unmatched_left_rows: int = 0
    unmatched_right_rows: int = 0
    estimated_result_rows: int = 0
    max_frequency_bound: int = 1

    edge_artifact_fingerprint: str = ""
    grain_artifact_fingerprint: str = ""
    policy_fingerprint: str = ""

    risk_flags: list[str] = Field(default_factory=list)
    forbidden_reason: str | None = None
    safe_operations: list[str] = Field(default_factory=list)
    forbidden_operations: list[str] = Field(default_factory=list)

    evidence: dict[str, Any] = Field(default_factory=dict)
    dataset_version: str = "v1"
    artifact_fingerprint: str = ""

    def to_ingestion_join_plan(self) -> JoinPlan:
        """Converts to Ingestion V2 frozen JoinPlan."""
        join_keys_tuples = list(zip(self.left_keys, self.right_keys))
        return JoinPlan(
            join_plan_id=self.join_plan_id,
            edge_id=self.relationship_edge_id,
            left_table_id=self.left_sheet_id,
            left_grain=self.left_grain,
            right_table_id=self.right_sheet_id,
            right_grain=self.right_grain,
            target_grain=self.target_grain,
            join_type=self.join_type,
            safety_status=self.safety_status,
            measure_additivity_rules=self.measure_additivity_rules,
            pre_aggregation=self.preaggregation_spec,
            forbidden_reason=self.forbidden_reason,
            safe_operations=self.safe_operations,
            forbidden_operations=self.forbidden_operations,
            join_keys=join_keys_tuples,
            max_expected_multiplier=self.max_expected_multiplier,
            expected_input_rows=self.expected_input_rows,
            expected_output_rows=self.expected_output_rows,
            dimension_propagation=[],
            post_aggregations=[],
        )


def compute_relationship_candidate_fingerprint(
    dataset_id: str,
    left_sheet_id: str,
    right_sheet_id: str,
    left_column_ids: Sequence[str],
    right_column_ids: Sequence[str],
    candidate_cardinality: RelationshipCardinality,
    dataset_version: str = "v1",
    policy_fingerprint: str = "",
) -> str:
    """Computes deterministic SHA-256 fingerprint for a relationship candidate."""
    raw = (
        f"{dataset_id}:{left_sheet_id}:{right_sheet_id}:"
        f"{','.join(sorted(left_column_ids))}:{','.join(sorted(right_column_ids))}:"
        f"{candidate_cardinality.value}:{dataset_version}:{policy_fingerprint}"
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def compute_validated_edge_fingerprint(
    edge_id: str,
    candidate_id: str,
    dataset_id: str,
    left_sheet_id: str,
    right_sheet_id: str,
    left_column_ids: Sequence[str],
    right_column_ids: Sequence[str],
    cardinality: RelationshipCardinality,
    status: RelationshipStatus,
    dataset_version: str = "v1",
    policy_fingerprint: str = "",
    key_fingerprints: Sequence[str] = (),
    grain_fingerprints: Sequence[str] = (),
) -> str:
    """Computes deterministic SHA-256 fingerprint for a validated relationship edge."""
    raw = (
        f"{edge_id}:{candidate_id}:{dataset_id}:{left_sheet_id}:{right_sheet_id}:"
        f"{','.join(sorted(left_column_ids))}:{','.join(sorted(right_column_ids))}:"
        f"{cardinality.value}:{status.value}:{dataset_version}:{policy_fingerprint}:"
        f"{','.join(sorted(key_fingerprints))}:{','.join(sorted(grain_fingerprints))}"
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def compute_join_plan_fingerprint(
    join_plan_id: str,
    relationship_edge_id: str,
    left_sheet_id: str,
    right_sheet_id: str,
    left_keys: Sequence[str],
    right_keys: Sequence[str],
    safety_status: JoinSafetyStatus,
    target_grain: str,
    dataset_version: str = "v1",
    policy_fingerprint: str = "",
    edge_artifact_fingerprint: str = "",
    grain_artifact_fingerprint: str = "",
) -> str:
    """Computes deterministic SHA-256 fingerprint for a governed JoinPlan."""
    raw = (
        f"{join_plan_id}:{relationship_edge_id}:{left_sheet_id}:{right_sheet_id}:"
        f"{','.join(sorted(left_keys))}:{','.join(sorted(right_keys))}:"
        f"{safety_status.value}:{target_grain}:{dataset_version}:{policy_fingerprint}:"
        f"{edge_artifact_fingerprint}:{grain_artifact_fingerprint}"
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def check_edge_invalidation(
    edge: SDRValidatedRelationshipEdge,
    current_key_fingerprints: Sequence[str] = (),
    current_grain_fingerprints: Sequence[str] = (),
    current_dataset_version: str = "v1",
    current_policy_fingerprint: str = "",
) -> tuple[bool, str | None]:
    """
    Evaluates whether an existing validated edge is invalidated by upstream changes.
    Returns (is_valid, invalidation_reason).
    """
    if edge.dataset_version != current_dataset_version:
        return False, f"Dataset version changed: edge has '{edge.dataset_version}', current is '{current_dataset_version}'"
    if edge.policy_fingerprint and current_policy_fingerprint and edge.policy_fingerprint != current_policy_fingerprint:
        return False, f"Policy fingerprint changed: edge has '{edge.policy_fingerprint}', current is '{current_policy_fingerprint}'"
    if edge.key_fingerprints and current_key_fingerprints:
        if sorted(edge.key_fingerprints) != sorted(current_key_fingerprints):
            return False, "SDR-3 Key fingerprints changed: candidate key invalidation"
    if edge.grain_fingerprints and current_grain_fingerprints:
        if sorted(edge.grain_fingerprints) != sorted(current_grain_fingerprints):
            return False, "SDR-2 Grain fingerprints changed: table grain invalidation"
    return True, None


def check_join_plan_invalidation(
    plan: SDRJoinPlan,
    current_edge_fingerprint: str = "",
    current_grain_fingerprints: Sequence[str] = (),
    current_dataset_version: str = "v1",
    current_policy_fingerprint: str = "",
) -> tuple[bool, str | None]:
    """
    Evaluates whether an existing JoinPlan is invalidated by upstream changes.
    Returns (is_valid, invalidation_reason).
    """
    if plan.dataset_version != current_dataset_version:
        return False, f"Dataset version changed: plan has '{plan.dataset_version}', current is '{current_dataset_version}'"
    if plan.policy_fingerprint and current_policy_fingerprint and plan.policy_fingerprint != current_policy_fingerprint:
        return False, f"Policy fingerprint changed: plan has '{plan.policy_fingerprint}', current is '{current_policy_fingerprint}'"
    if plan.edge_artifact_fingerprint and current_edge_fingerprint and plan.edge_artifact_fingerprint != current_edge_fingerprint:
        return False, f"Validated relationship edge changed: plan edge fingerprint '{plan.edge_artifact_fingerprint}' != current '{current_edge_fingerprint}'"
    if plan.grain_artifact_fingerprint and current_grain_fingerprints:
        if plan.grain_artifact_fingerprint not in current_grain_fingerprints:
            return False, "SDR-2 Grain changed: target grain fingerprint invalidation"
    return True, None
