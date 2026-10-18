"""
HighView Ingestion V2 — Semantic Modeling Contract
Stage 5: Semantic Modeling
Boundary: Semantic entity & role classification.
Rule: Low confidence assignments must explicitly yield AMBIGUOUS, never forced into unsafe roles.
Zero relationship discovery, zero join creation, zero dashboard story generation.
"""

from enum import Enum
from pydantic import BaseModel, ConfigDict, Field
from app.services.ingestion_v2.contracts.base import IngestionContractBase


class SemanticColumnRole(str, Enum):
    IDENTIFIER = "IDENTIFIER"
    DIMENSION = "DIMENSION"
    MEASURE = "MEASURE"
    TIMESTAMP = "TIMESTAMP"
    ATTRIBUTE = "ATTRIBUTE"
    METADATA = "METADATA"
    UNKNOWN = "UNKNOWN"
    AMBIGUOUS = "AMBIGUOUS"


class SemanticEntityType(str, Enum):
    PERSON = "PERSON"
    ORGANIZATION = "ORGANIZATION"
    DEPARTMENT = "DEPARTMENT"
    LOCATION = "LOCATION"
    EVENT = "EVENT"
    TRANSACTION = "TRANSACTION"
    FINANCIAL = "FINANCIAL"
    TEMPORAL = "TEMPORAL"
    CONCEPT = "CONCEPT"
    UNKNOWN = "UNKNOWN"
    AMBIGUOUS = "AMBIGUOUS"


class ClassificationSource(str, Enum):
    HEURISTIC = "HEURISTIC"
    DICTIONARY = "DICTIONARY"
    STATISTICAL = "STATISTICAL"
    MANUAL = "MANUAL"


class SemanticColumnAssignment(BaseModel):
    """
    Semantic assignment for an individual column.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    column_id: str
    table_id: str
    column_name: str
    role: SemanticColumnRole
    entity_type: SemanticEntityType
    confidence: float = Field(ge=0.0, le=1.0)
    is_ambiguous: bool = False
    classification_source: ClassificationSource
    rationale: str


class TableSemanticModel(BaseModel):
    """
    Semantic model for an individual table.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    table_id: str
    table_name: str
    primary_entity_type: SemanticEntityType
    columns: list[SemanticColumnAssignment] = Field(default_factory=list)


class SemanticModel(IngestionContractBase):
    """
    Stage 5 Contract: Semantic Modeling.
    """
    stage_name: str = "semantic_modeling"

    tables: list[TableSemanticModel] = Field(default_factory=list)
