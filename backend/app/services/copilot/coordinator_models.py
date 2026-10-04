"""Data contracts for the Council Coordinator routing and dispatch engine."""
from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class UserIntent(str, Enum):
    CALCULATE = "CALCULATE"
    VISUALIZE = "VISUALIZE"
    QUERY_DATASET = "QUERY_DATASET"
    EXPLAIN = "EXPLAIN"
    DELIBERATE = "DELIBERATE"
    GREET = "GREET"
    UNKNOWN = "UNKNOWN"


class ExecutionRoute(str, Enum):
    MATH_ENGINE = "MATH_ENGINE"
    CHART_ENGINE = "CHART_ENGINE"
    DATASET_ENGINE = "DATASET_ENGINE"
    EXPLANATION_WORKER = "EXPLANATION_WORKER"
    COUNCIL_WAR_ROOM = "COUNCIL_WAR_ROOM"


class ContextRelation(str, Enum):
    NEW_TOPIC = "NEW_TOPIC"
    FOLLOW_UP = "FOLLOW_UP"
    CLARIFICATION = "CLARIFICATION"


class RouteContract(BaseModel):
    """Pydantic contract emitted by the Control-Plane Coordinator."""
    model_config = ConfigDict(extra="ignore")

    intent: UserIntent = UserIntent.UNKNOWN
    route: ExecutionRoute = ExecutionRoute.EXPLANATION_WORKER
    context_relation: ContextRelation = ContextRelation.NEW_TOPIC
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    entities: dict[str, Any] = Field(default_factory=dict)
    rationale: str = ""
    extracted_expression: str | None = None
    suggested_model: str | None = None


class RoutingAssignment(str, Enum):
    SAFE_CALCULATOR = "safe_calculator"
    IMMEDIATE_GREETING = "immediate_greeting"
    LIGHTWEIGHT_EXPLANATION = "lightweight_explanation"
    DATASET_CALCULATION = "dataset_calculation"
    VISUAL_CHART = "visual_chart"
    SHEET_QUALITY = "sheet_quality"
    SLIDE_MUTATION = "slide_mutation"
    COUNCIL_DELIBERATION = "council_deliberation"


class WorkerTarget(str, Enum):
    DETERMINISTIC_CALCULATOR = "deterministic_calculator"
    IMMEDIATE_IDENTITY = "immediate_identity"
    SHEET_QUALITY_INSPECTOR = "sheet_quality_inspector"
    SLIDE_MUTATOR = "slide_mutator"
    ANALYTICAL_PLANNER = "analytical_planner"
    DATASET_METADATA_INSPECTOR = "dataset_metadata_inspector"
    EXPLICIT_TOOL = "explicit_tool"
    CHART_LIBRARY = "chart_library"
    SINGLE_SPECIALIST_MODEL = "single_specialist_model"
    UNION_WAR_ROOM = "union_war_room"


class CoordinatorDecision(BaseModel):
    """Execution decision returned by CouncilCoordinator for dispatch and budget management."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    assignment: RoutingAssignment
    worker_target: WorkerTarget
    timeout_seconds: float
    max_retries: int = 1
    requires_visual: bool = False
    resolved_context: dict[str, Any] = Field(default_factory=dict)
    rationale: str = ""
    is_follow_up: bool = False
    confidence: float = 1.0
    extracted_expression: str | None = None
    route_contract: RouteContract | None = None
