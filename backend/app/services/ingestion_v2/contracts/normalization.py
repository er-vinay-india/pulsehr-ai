"""
HighView Ingestion V2 — Sanitization and Normalization Contract
Stage 3: Sanitization + Type/Unit Normalization (Silver Layer)
Boundary: Canonical typing, value cleaning, and unit normalization.
Zero business insights, zero cross-table relationship discovery, zero ranking.
"""

from enum import Enum
from pydantic import BaseModel, ConfigDict, Field
from app.services.ingestion_v2.contracts.base import IngestionContractBase


class CanonicalPhysicalType(str, Enum):
    INTEGER = "INTEGER"
    FLOAT = "FLOAT"
    BOOLEAN = "BOOLEAN"
    DATE = "DATE"
    DATETIME = "DATETIME"
    STRING = "STRING"
    CATEGORICAL = "CATEGORICAL"


class NormalizationRule(BaseModel):
    """
    Transformation rule applied during normalization.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    rule_name: str
    target_column_id: str
    description: str
    applied_count: int


class NormalizedFieldLineage(BaseModel):
    """
    Lineage linking a normalized field definition back to original raw token representation.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    column_id: str
    raw_header_name: str
    inferred_unit: str | None = None
    applied_rules: list[str] = Field(default_factory=list)


class NormalizedColumn(BaseModel):
    """
    Normalized column contract with canonical physical type and unit.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    column_id: str
    table_id: str
    column_name: str
    canonical_type: CanonicalPhysicalType
    inferred_unit: str | None = None
    lineage: NormalizedFieldLineage
    null_count: int
    non_null_count: int
    sample_values: list[str] = Field(default_factory=list)


class NormalizedTable(BaseModel):
    """
    Normalized logical table ready for profiling and canonical Parquet materialization.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    table_id: str
    table_name: str
    columns: list[NormalizedColumn] = Field(default_factory=list)
    row_count: int
    column_count: int
    parquet_path: str | None = None


class NormalizedDataset(IngestionContractBase):
    """
    Stage 3 Contract: Sanitization and Normalization.
    """
    stage_name: str = "sanitization_normalization"

    tables: list[NormalizedTable] = Field(default_factory=list)
    rules_applied: list[NormalizationRule] = Field(default_factory=list)
