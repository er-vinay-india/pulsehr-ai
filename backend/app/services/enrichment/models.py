"""Canonical data models for Controlled Semantic Data Enrichment and Scientific Feature Discovery."""

from __future__ import annotations

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class SemanticRole(str, Enum):
    """Canonical analytical and scientific semantic roles."""
    IDENTIFIER = "IDENTIFIER"
    DIMENSION = "DIMENSION"
    MEASURE = "MEASURE"
    TIME = "TIME"
    GEO = "GEO"
    CATEGORY = "CATEGORY"
    ORDINAL = "ORDINAL"
    BOOLEAN = "BOOLEAN"
    TEXT = "TEXT"
    UNIT = "UNIT"
    QUANTITY = "QUANTITY"
    SCIENTIFIC_MEASURE = "SCIENTIFIC_MEASURE"


class EnrichmentColumnProfile(BaseModel):
    """Exhaustive statistical, morphological, and semantic profile of a single dataset column."""
    column: str
    original_name: str
    physical_type: str                  # float, int, string, datetime, bool, object
    semantic_type: str                  # distance, currency, mass, date, identifier, count, ratio, etc.
    roles: list[SemanticRole] = Field(default_factory=list)
    null_count: int = 0
    null_ratio: float = 0.0
    unique_count: int = 0
    cardinality: int = 0
    min_val: Any = None
    max_val: Any = None
    mean_val: float | None = None
    median_val: float | None = None
    variance: float | None = None
    std_dev: float | None = None
    sample_values: list[Any] = Field(default_factory=list)
    frequent_values: list[dict[str, Any]] = Field(default_factory=list)
    pattern: str | None = None          # regex pattern or structure label
    detected_unit: str | None = None    # km, $, %, kg, hours, m2, etc.
    display_name: str | None = None     # Humanized, sentence-cased display label
    is_synthetic: bool = False          # True if derived via feature engineering
    probable_semantic_role: str | None = None
    possible_domain: str | None = None  # physics, finance, transportation, hr, operations
    confidence: float = 1.0


class ColumnRelationship(BaseModel):
    """Discovered hybrid dependency between two columns with multi-signal attribution."""
    left_column: str
    right_column: str
    relationship_score: float
    semantic_similarity: float = 0.0
    statistical_dependency: float = 0.0
    structural_compatibility: float = 0.0
    domain_relationship: float = 0.0
    unit_compatibility: float = 0.0
    relationship_type: str = "general_dependency"
    reasons: list[str] = Field(default_factory=list)


class SemanticColumnGroup(BaseModel):
    """Cluster of tightly coupled columns forming an isolated semantic reasoning boundary."""
    group_id: str
    group_name: str
    domain_interpretation: str
    columns: list[str]
    primary_roles: list[SemanticRole] = Field(default_factory=list)
    cohesion_score: float = 1.0


class CandidateFeature(BaseModel):
    """A prioritized feature candidate undergoing validation, deduplication, and budget gating."""
    name: str
    derivation_type: str
    expression: str
    source_columns: list[str]
    target_group_id: str | None = None
    expected_utility_score: float = 1.0
    expected_confidence: float = 1.0
    unit: str | None = None
    priority: float = 1.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class DerivedFeature(BaseModel):
    """A generated, normalized, scientific, or interaction feature bounded by budget."""
    name: str
    display_name: str | None = None
    is_synthetic: bool = True
    source_columns: list[str]
    derivation_type: str  # primitive_date, primitive_measurement, scientific_formula, interaction_ratio, etc.
    expression: str
    depth: int = 1
    confidence: float = 1.0
    utility_score: float = 1.0
    unit: str | None = None
    roles: list[SemanticRole] = Field(default_factory=list)


class AnalyticalTable(BaseModel):
    """Synthesized cross-dimensional analytical table or grouped rollup."""
    table_id: str
    title: str
    description: str
    group_by_columns: list[str]
    aggregated_measures: list[str]
    row_count: int
    col_count: int
    columns: list[str]
    utility_score: float = 1.0
    data_preview: list[dict[str, Any]] = Field(default_factory=list)


class EnrichedDatasetPackage(BaseModel):
    """The complete immutable package emitted by the enrichment pipeline."""
    dataset_id: str
    original_row_count: int
    original_col_count: int
    enriched_row_count: int
    enriched_col_count: int
    column_profiles: dict[str, EnrichmentColumnProfile] = Field(default_factory=dict)
    relationships: list[ColumnRelationship] = Field(default_factory=list)
    semantic_groups: list[SemanticColumnGroup] = Field(default_factory=list)
    derived_features: list[DerivedFeature] = Field(default_factory=list)
    analytical_tables: list[AnalyticalTable] = Field(default_factory=list)
    budget_summary: dict[str, Any] = Field(default_factory=dict)
