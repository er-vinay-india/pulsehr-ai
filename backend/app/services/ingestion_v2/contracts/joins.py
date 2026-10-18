"""
HighView Ingestion V2 — Join Plan & Safety Contract
Stage: Join Plan & Join Safety Specification
Boundary: Operational plan governing how validated relationships may be safely joined.
Distinguishes between raw structural joins and analytically safe joins.
Enforces measure additivity and pre-aggregation requirements to prevent metric distortion.
"""

from enum import Enum
from pydantic import BaseModel, ConfigDict, Field
from app.services.ingestion_v2.contracts.base import IngestionContractBase


class JoinSafetyStatus(str, Enum):
    SAFE = "SAFE"
    FORBIDDEN_CARTESIAN = "FORBIDDEN_CARTESIAN"
    REQUIRES_PRE_AGGREGATION = "REQUIRES_PRE_AGGREGATION"
    SAFE_WITH_PREAGGREGATION = "SAFE_WITH_PREAGGREGATION"
    LOSS_OF_GRAIN = "LOSS_OF_GRAIN"
    UNSAFE = "UNSAFE"
    AMBIGUOUS = "AMBIGUOUS"


class MeasureAdditivity(str, Enum):
    ADDITIVE = "ADDITIVE"
    SEMI_ADDITIVE = "SEMI_ADDITIVE"
    NON_ADDITIVE = "NON_ADDITIVE"
    RATIO = "RATIO"
    DISTINCT_COUNT = "DISTINCT_COUNT"
    UNKNOWN = "UNKNOWN"


class PreAggregationSpec(BaseModel):
    """
    Mandatory pre-aggregation specification required before joining multi-row tables
    to prevent fanout/inflation in the target grain.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_table_id: str
    group_by_columns: list[str] = Field(default_factory=list)
    aggregations: dict[str, str] = Field(default_factory=dict)  # column_id -> AGG_FUNC (SUM, AVG, etc.)
    target_grain: str


class JoinSafetyAssessment(BaseModel):
    """
    Stage: Join Safety Assessment.
    Evaluates referential, grain, and fanout risks before a join plan is formulated.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    assessment_id: str
    edge_id: str
    left_table_id: str
    right_table_id: str
    safety_status: JoinSafetyStatus
    is_grain_compatible: bool
    fact_duplication_risk: bool
    dimension_propagation_safe: bool
    measure_duplication_risk: bool
    temporal_mismatch: bool
    many_to_many_risk: bool
    estimated_row_multiplier: float
    required_pre_aggregation: bool
    rationale: str
    recommended_target_grain: str | None = None


class JoinPlan(BaseModel):
    """
    Governed operational join plan between two tables.
    Guarantees that denominators and metric summations are analytically safe.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    join_plan_id: str
    edge_id: str
    left_table_id: str
    left_grain: str
    right_table_id: str
    right_grain: str
    target_grain: str
    join_type: str  # "INNER", "LEFT", "RIGHT", "FULL"

    safety_status: JoinSafetyStatus
    measure_additivity_rules: dict[str, MeasureAdditivity] = Field(default_factory=dict)
    pre_aggregation: PreAggregationSpec | None = None
    forbidden_reason: str | None = None
    safe_operations: list[str] = Field(default_factory=list)
    forbidden_operations: list[str] = Field(default_factory=list)

    join_keys: list[tuple[str, str]] = Field(default_factory=list)
    max_expected_multiplier: float = 1.0
    expected_input_rows: int = 0
    expected_output_rows: int = 0
    dimension_propagation: list[str] = Field(default_factory=list)
    post_aggregations: list[str] = Field(default_factory=list)


class GovernedJoinPlanSet(IngestionContractBase):
    """
    Contract for set of governed join plans.
    """
    stage_name: str = "join_safety_planning"

    plans: list[JoinPlan] = Field(default_factory=list)
