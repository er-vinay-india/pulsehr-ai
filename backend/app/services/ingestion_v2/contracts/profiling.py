"""
HighView Ingestion V2 — Structural Profiling Contract
Stage 4: Structural Profiling / EDA-A
Boundary: Pure deterministic data characterization.
Zero embeddings, zero LLM calls, zero semantic role classification, zero cross-sheet joins, zero business metric ranking.
"""

from typing import Any
from pydantic import BaseModel, ConfigDict, Field
from app.services.ingestion_v2.contracts.base import IngestionContractBase


class StructuralDataQuality(BaseModel):
    """
    Physical & Structural data quality indicators.
    Measures completeness, validity, uniqueness, consistency, and reconstruction fidelity.
    Does NOT contain analytical confidence or business grain validity (which belongs to EDA-B).
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    completeness_score: float = Field(ge=0.0, le=1.0)
    validity_score: float = Field(ge=0.0, le=1.0)
    uniqueness_score: float = Field(ge=0.0, le=1.0)
    consistency_score: float = Field(ge=0.0, le=1.0)
    reconstruction_fidelity_score: float = Field(ge=0.0, le=1.0)
    overall_structural_quality: float = Field(ge=0.0, le=1.0)


class ColumnStructuralProfile(BaseModel):
    """
    Deterministic structural profile for a single column.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    column_id: str
    table_id: str
    column_name: str
    physical_type: str
    logical_type_candidate: str | None = None

    row_count: int
    null_count: int
    null_ratio: float = Field(ge=0.0, le=1.0)
    non_null_count: int = 0

    distinct_count: int
    uniqueness_ratio: float = Field(ge=0.0, le=1.0)

    is_constant: bool = False
    is_quasi_constant: bool = False
    is_unique_candidate: bool = False

    constant_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    near_constant_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    categorical_entropy: float | None = None
    normalized_entropy: float | None = None

    pattern_signature: str | None = None
    dominant_pattern: str | None = None
    pattern_coverage: float = Field(default=0.0, ge=0.0, le=1.0)
    pattern_variants: int = 0
    fixed_length_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    leading_zero_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    all_digit_ratio: float = Field(default=0.0, ge=0.0, le=1.0)

    date_min: str | None = None
    date_max: str | None = None
    date_span_days: int | None = None

    candidate_identifier_score: float = Field(default=0.0, ge=0.0, le=1.0)
    candidate_dimension_score: float = Field(default=0.0, ge=0.0, le=1.0)

    min_value: Any | None = None
    max_value: Any | None = None
    mean: float | None = None
    stddev: float | None = None
    median: float | None = None
    quantiles: dict[str, float] = Field(default_factory=dict)

    top_frequent_values: list[dict[str, Any]] = Field(default_factory=list)


class TableStructuralProfile(BaseModel):
    """
    Structural profile for an individual table.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    table_id: str
    table_name: str
    row_count: int
    column_count: int
    duplicate_row_count: int = 0
    duplicate_row_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    all_null_row_count: int = 0
    structural_warnings: list[str] = Field(default_factory=list)
    candidate_composite_keys: list[dict[str, Any]] = Field(default_factory=list)
    columns: list[ColumnStructuralProfile] = Field(default_factory=list)
    quality: StructuralDataQuality


class StructuralProfile(IngestionContractBase):
    """
    Stage 4 Contract: Structural Profiling / EDA-A.
    """
    stage_name: str = "structural_profiling_eda_a"

    tables: list[TableStructuralProfile] = Field(default_factory=list)
    dataset_structural_quality: StructuralDataQuality
