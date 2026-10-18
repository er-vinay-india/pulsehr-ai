"""
HighView Ingestion V2 — Controlled Enrichment Contract
Stage 9: Controlled Enrichment
Boundary: Governed calculation of derived metrics and dimensional augmentations.
Rule: Relational derived metrics MUST reference an explicit, validated JoinPlan.
No arbitrary, unguarded cross-table calculations are permitted.
"""

from enum import Enum
from pydantic import BaseModel, ConfigDict, Field
from app.services.ingestion_v2.contracts.base import IngestionContractBase


class MetricScope(str, Enum):
    LOCAL = "LOCAL"            # Intra-table calculation at table grain
    RELATIONAL = "RELATIONAL"  # Cross-table calculation requiring validated JoinPlan


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


class EnrichedDataset(IngestionContractBase):
    """
    Stage 9 Contract: Controlled Enrichment.
    """
    stage_name: str = "controlled_enrichment"

    local_metrics: list[LocalDerivedMetric] = Field(default_factory=list)
    relational_metrics: list[RelationalDerivedMetric] = Field(default_factory=list)
