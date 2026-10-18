"""
HighView Ingestion V2 — Controlled Enrichment Contract
Stage 9: Controlled Enrichment
Boundary: Governed calculation of derived metrics and dimensional augmentations.
Rule: Relational derived metrics MUST reference an explicit, validated JoinPlan.
No arbitrary, unguarded cross-table calculations are permitted.
"""

from enum import Enum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field
from app.services.ingestion_v2.contracts.base import IngestionContractBase


class MetricScope(str, Enum):
    LOCAL = "LOCAL"            # Intra-table calculation at table grain
    RELATIONAL = "RELATIONAL"  # Cross-table calculation requiring validated JoinPlan


class MetricAdditivity(str, Enum):
    ADDITIVE = "ADDITIVE"
    SEMI_ADDITIVE = "SEMI_ADDITIVE"
    NON_ADDITIVE = "NON_ADDITIVE"
    RATIO = "RATIO"
    DISTINCT_COUNT = "DISTINCT_COUNT"
    UNKNOWN = "UNKNOWN"


class LocalDerivedMetric(BaseModel):
    """
    Intra-table derived metric (e.g. tenure_years = (end_date - start_date) / 365.25).
    Evaluated strictly within table grain.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    metric_id: str
    table_id: str
    metric_name: str
    formula: str
    source_columns: list[str] = Field(default_factory=list)
    unit: str | None = None
    grain: str

    # Extended Stage 9 governed metadata
    metric_type: str = "LOCAL"
    source_table_id: str | None = None
    source_column_ids: list[str] = Field(default_factory=list)
    target_grain: str | None = None
    numerator_definition: str | None = None
    denominator_definition: str | None = None
    additivity: MetricAdditivity = MetricAdditivity.NON_ADDITIVE
    null_policy: str = "EXCLUDE"
    filter_policy: str = "ALL"
    provenance_refs: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    definition_confidence: float = 1.0
    derivation_method: str = "DETERMINISTIC"
    display_aliases: list[str] = Field(default_factory=list)
    fingerprint: str = ""

    def model_post_init(self, __context: Any) -> None:
        if not self.source_table_id and self.table_id:
            object.__setattr__(self, "source_table_id", self.table_id)
        if not self.table_id and self.source_table_id:
            object.__setattr__(self, "table_id", self.source_table_id)
        if not self.target_grain and self.grain:
            object.__setattr__(self, "target_grain", self.grain)
        if not self.grain and self.target_grain:
            object.__setattr__(self, "grain", self.target_grain)
        if not self.source_column_ids and self.source_columns:
            object.__setattr__(self, "source_column_ids", list(self.source_columns))
        if not self.source_columns and self.source_column_ids:
            object.__setattr__(self, "source_columns", list(self.source_column_ids))


class RelationalDerivedMetric(BaseModel):
    """
    Cross-table derived metric (e.g., absenteeism_rate = total_leave_days / total_scheduled_days).
    Requires an explicit, validated join_plan_id to ensure denominator safety.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    metric_id: str
    metric_name: str
    join_plan_id: str
    numerator_metric: str
    denominator_metric: str
    formula: str
    target_grain: str
    unit: str | None = None
    denominator_safety_verified: bool = True

    # Extended Stage 9 governed metadata
    metric_type: str = "RELATIONAL"
    source_table_ids: list[str] = Field(default_factory=list)
    source_column_ids: list[str] = Field(default_factory=list)
    numerator_definition: str | None = None
    denominator_definition: str | None = None
    additivity: MetricAdditivity = MetricAdditivity.RATIO
    null_policy: str = "EXCLUDE"
    filter_policy: str = "ALL"
    provenance_refs: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    definition_confidence: float = 1.0
    derivation_method: str = "RELATIONAL_JOIN_PLAN"
    display_aliases: list[str] = Field(default_factory=list)
    fingerprint: str = ""


class SemanticFamily(BaseModel):
    """
    Stage 9 Contract: Semantic Family organizational grouping.
    Purely organizational metadata grouping semantically related metrics,
    dimensions, and entities. Cannot alter formulas, grains, or evidence.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    family_id: str
    family_name: str
    concept_type: str
    metric_ids: list[str] = Field(default_factory=list)
    dimension_ids: list[str] = Field(default_factory=list)
    entity_types: list[str] = Field(default_factory=list)
    grain_scope: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    provenance_refs: list[str] = Field(default_factory=list)
    description: str | None = None


class EnrichedDataset(IngestionContractBase):
    """
    Stage 9 Contract: Controlled Enrichment.
    """
    stage_name: str = "controlled_enrichment"

    local_metrics: list[LocalDerivedMetric] = Field(default_factory=list)
    relational_metrics: list[RelationalDerivedMetric] = Field(default_factory=list)
    semantic_families: list[SemanticFamily] = Field(default_factory=list)

