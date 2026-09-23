"""Pydantic schemas defining the structured Evidence and Finding representations."""

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class FindingType(str, Enum):
    PERFORMANCE_GAP = "performance_gap"
    OUTPERFORMER = "outperformer"
    HEADWIND = "headwind"
    BASELINE_BENCHMARK = "baseline_benchmark"
    TREND_SHIFT = "trend_shift"
    RISK_ALERT = "risk_alert"
    CONCENTRATION = "concentration"


class Importance(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EvidenceReference(BaseModel):
    """Deterministic link to the underlying dataset source and calculation proof."""
    source_sheet: str
    metric: str
    segment: str | None = None
    row_count: int
    calculation_method: str = "deterministic_aggregation"
    proof: dict[str, Any] = Field(default_factory=dict)


class Finding(BaseModel):
    """Structured, verified analytical finding representing actionable empirical evidence."""
    finding_id: str = Field(description="Unique deterministic ID (e.g. F-001, F-017)")
    type: FindingType
    metric: str
    segment: str | None = None
    segment_value: float | None = None
    overall_value: float | None = None
    difference: float | None = None
    difference_percentage_points: float | None = None
    importance: Importance = Importance.MEDIUM
    headline: str = Field(description="Assertive summary of what the data shows")
    business_implication: str = Field(description="Why this finding matters to executive leadership")
    evidence: list[EvidenceReference] = Field(default_factory=list)
