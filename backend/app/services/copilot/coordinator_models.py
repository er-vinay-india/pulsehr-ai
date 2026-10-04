"""Data contracts for the Council Coordinator routing and dispatch engine."""
from enum import Enum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


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
    CHART_LIBRARY = "chart_library"
    SINGLE_SPECIALIST_MODEL = "single_specialist_model"
    UNION_WAR_ROOM = "union_war_room"


class CoordinatorDecision(BaseModel):
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
