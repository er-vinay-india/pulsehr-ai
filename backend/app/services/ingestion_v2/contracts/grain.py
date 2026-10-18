"""
HighView Ingestion V2 — Grain Inference Contract
Stage: Grain Inference (Bridge between Semantic Modeling & Relationship Validation)
Boundary: Determination of row-level entity identity and temporal granularity.
Prevents Cartesian explosions and grain-incompatible joins before any relationship validation.
"""

from enum import Enum
from pydantic import BaseModel, ConfigDict, Field
from app.services.ingestion_v2.contracts.base import IngestionContractBase


class CanonicalGrain(str, Enum):
    PERSON = "PERSON"
    ORGANIZATION = "ORGANIZATION"
    DEPARTMENT = "DEPARTMENT"
    STORE = "STORE"
    POSITION = "POSITION"
    EVENT = "EVENT"
    TRANSACTION = "TRANSACTION"
    SNAPSHOT = "SNAPSHOT"
    COMPOSITE = "COMPOSITE"
    UNKNOWN = "UNKNOWN"


class TemporalGrain(str, Enum):
    NONE = "NONE"
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"
    ANNUAL = "ANNUAL"


class TableGrainProfile(BaseModel):
    """
    Inferred grain definition for an individual table.
    Supports single-key and composite grains (e.g. PERSON x DAY, DEPARTMENT x MONTH).
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    table_id: str
    table_name: str
    primary_entity: CanonicalGrain
    temporal_grain: TemporalGrain = TemporalGrain.NONE
    key_columns: list[str] = Field(default_factory=list)
    grain_expression: str  # e.g., "PERSON x DAY", "DEPARTMENT x MONTH", "EMPLOYEE"
    is_unique: bool
    uniqueness_ratio: float = Field(ge=0.0, le=1.0)
    grain_confidence: float = Field(ge=0.0, le=1.0)
    duplicate_key_rows: int = 0
    rationale: str


class GrainProfile(IngestionContractBase):
    """
    Stage Contract: Grain Inference.
    """
    stage_name: str = "grain_inference"

    table_grains: list[TableGrainProfile] = Field(default_factory=list)
