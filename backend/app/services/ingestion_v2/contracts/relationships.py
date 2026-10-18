"""
HighView Ingestion V2 — Relationship Discovery and Validation Contracts
Stages 6 & 7: Relationship Discovery & Relationship Validation
Boundary: Discovery produces candidates; Validation mathematically verifies referential integrity and cardinality.
Neither stage executes joins, computes business metrics, or alters table grain.
"""

from enum import Enum
from pydantic import BaseModel, ConfigDict, Field
from app.services.ingestion_v2.contracts.base import IngestionContractBase


class CandidateKeyType(str, Enum):
    SINGLE = "SINGLE"
    COMPOSITE = "COMPOSITE"


class RelationshipCardinality(str, Enum):
    ONE_TO_ONE = "ONE_TO_ONE"
    ONE_TO_MANY = "ONE_TO_MANY"
    MANY_TO_ONE = "MANY_TO_ONE"
    MANY_TO_MANY = "MANY_TO_MANY"


class RelationshipStatus(str, Enum):
    VALIDATED = "VALIDATED"
    PROVISIONAL = "PROVISIONAL"
    REJECTED = "REJECTED"
    AMBIGUOUS = "AMBIGUOUS"


class RelationshipCandidate(BaseModel):
    """
    Stage 6: Unverified candidate relationship between tables.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_id: str
    source_table_id: str
    source_column_ids: list[str] = Field(default_factory=list)
    target_table_id: str
    target_column_ids: list[str] = Field(default_factory=list)
    key_type: CandidateKeyType = CandidateKeyType.SINGLE
    discovery_method: str  # e.g., "EXACT_NAME_MATCH", "VALUE_OVERLAP_HEURISTIC", "SEMANTIC_TYPE"
    confidence_score: float = Field(ge=0.0, le=1.0)


class RelationshipCandidateSet(IngestionContractBase):
    """
    Stage 6 Contract: Relationship Discovery Candidates.
    """
    stage_name: str = "relationship_discovery"

    candidates: list[RelationshipCandidate] = Field(default_factory=list)


class ValidatedRelationshipEdge(BaseModel):
    """
    Stage 7: Mathematically verified structural relationship edge.
    Proves referential integrity, cardinality, and grain compatibility.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    edge_id: str
    candidate_id: str
    source_table_id: str
    source_column_ids: list[str] = Field(default_factory=list)
    target_table_id: str
    target_column_ids: list[str] = Field(default_factory=list)
    key_type: CandidateKeyType = CandidateKeyType.SINGLE
    cardinality: RelationshipCardinality
    status: RelationshipStatus

    referential_coverage: float = Field(ge=0.0, le=1.0)
    source_overlap_ratio: float = Field(ge=0.0, le=1.0)
    target_overlap_ratio: float = Field(ge=0.0, le=1.0)

    is_grain_preserving: bool
    duplication_risk_flag: bool = False
    rejection_reason: str | None = None
    validation_evidence: dict[str, str | int | float | bool] = Field(default_factory=dict)


class ValidatedRelationshipGraph(IngestionContractBase):
    """
    Stage 7 Contract: Validated Relationship Graph.
    """
    stage_name: str = "relationship_validation"

    edges: list[ValidatedRelationshipEdge] = Field(default_factory=list)
