"""Canonical Contracts and Schemas for Phase 5 Visual QA & Automated Repair.

Defines the typed VisualQAReport, controlled issue taxonomy, severity levels,
multi-dimensional visual score metrics, and bounded VisualRepairPlan models.
"""

from __future__ import annotations

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class VisualIssueType(str, Enum):
    """The 22 controlled visual issue taxonomy types."""
    TEXT_OVERFLOW = "TEXT_OVERFLOW"
    TEXT_DENSITY = "TEXT_DENSITY"
    TITLE_OVERFLOW = "TITLE_OVERFLOW"
    LABEL_COLLISION = "LABEL_COLLISION"
    CHART_CLUTTER = "CHART_CLUTTER"
    CHART_UNREADABLE = "CHART_UNREADABLE"
    ALIGNMENT = "ALIGNMENT"
    SPACING = "SPACING"
    VISUAL_IMBALANCE = "VISUAL_IMBALANCE"
    EXCESSIVE_EMPTY_SPACE = "EXCESSIVE_EMPTY_SPACE"
    LOW_CONTRAST = "LOW_CONTRAST"
    WEAK_HIERARCHY = "WEAK_HIERARCHY"
    OVEREMPHASIS = "OVEREMPHASIS"
    UNDEREMPHASIS = "UNDEREMPHASIS"
    INCONSISTENT_STYLE = "INCONSISTENT_STYLE"
    COMPONENT_COLLISION = "COMPONENT_COLLISION"
    TABLE_OVERFLOW = "TABLE_OVERFLOW"
    IMAGE_CROP = "IMAGE_CROP"
    FOOTER_COLLISION = "FOOTER_COLLISION"
    VISUAL_REDUNDANCY = "VISUAL_REDUNDANCY"
    UNSUPPORTED_RENDERING = "UNSUPPORTED_RENDERING"
    UNKNOWN_VISUAL_ISSUE = "UNKNOWN_VISUAL_ISSUE"


class IssueSeverity(str, Enum):
    """Graded severity levels governing visual quality gates."""
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class VisualQAScoreDimensions(BaseModel):
    """Fine-grained multi-dimensional visual quality ratings (normalized 0.0 - 1.0)."""
    hierarchy: float = 0.90
    balance: float = 0.90
    readability: float = 0.90
    chart_clarity: float = 0.90
    spacing: float = 0.90
    alignment: float = 0.90
    consistency: float = 0.90
    density: float = 0.90
    emphasis: float = 0.90
    professionalism: float = 0.90


class VisualQAIssue(BaseModel):
    """A discrete visual or geometric defect identified on a rendered slide."""
    issue_type: VisualIssueType
    severity: IssueSeverity
    component: str = "slide"
    description: str
    recommended_action: str = ""
    bounding_box: dict[str, float] | None = None


class VisualQAReport(BaseModel):
    """The canonical visual quality audit contract returned by deterministic checks and Gemma."""
    slide_id: str
    sequence_number: int = 1
    status: str = "PASS"  # PASS | WARNING | FAIL
    overall_score: float = 0.90
    dimensions: VisualQAScoreDimensions = Field(default_factory=VisualQAScoreDimensions)
    issues: list[VisualQAIssue] = Field(default_factory=list)
    screenshot_path: str | None = None
    qa_model: str = "deterministic"
    latency_ms: float = 0.0
    repair_iteration: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def has_critical_issues(self) -> bool:
        return any(i.severity == IssueSeverity.CRITICAL for i in self.issues)

    @property
    def has_high_issues(self) -> bool:
        return any(i.severity == IssueSeverity.HIGH for i in self.issues)


class VisualRepairAction(str, Enum):
    """Allowed deterministic visual repair operations."""
    REDUCE_TEXT = "REDUCE_TEXT"
    SHORTEN_TITLE = "SHORTEN_TITLE"
    CHANGE_LAYOUT_VARIANT = "CHANGE_LAYOUT_VARIANT"
    INCREASE_CHART_AREA = "INCREASE_CHART_AREA"
    REDUCE_CHART_LABELS = "REDUCE_CHART_LABELS"
    ROTATE_LABELS = "ROTATE_LABELS"
    AGGREGATE_CATEGORIES = "AGGREGATE_CATEGORIES"
    MOVE_INSIGHT_PANEL = "MOVE_INSIGHT_PANEL"
    CHANGE_COMPONENT_ORDER = "CHANGE_COMPONENT_ORDER"
    REDUCE_KPI_COUNT = "REDUCE_KPI_COUNT"
    MOVE_DETAIL_TO_NOTES = "MOVE_DETAIL_TO_NOTES"
    MOVE_DETAIL_TO_APPENDIX = "MOVE_DETAIL_TO_APPENDIX"
    INCREASE_SPACING = "INCREASE_SPACING"
    REDUCE_PADDING = "REDUCE_PADDING"
    CHANGE_TEXT_SIZE_WITHIN_ALLOWED_BOUND = "CHANGE_TEXT_SIZE_WITHIN_ALLOWED_BOUND"
    USE_VISUAL_FALLBACK = "USE_VISUAL_FALLBACK"


class VisualRepairItem(BaseModel):
    """An individual bounded repair task dispatched to the repair engine."""
    action: VisualRepairAction
    target_component: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    reason: str


class VisualRepairPlan(BaseModel):
    """The controlled visual repair strategy constructed to remediate QA defects."""
    slide_id: str
    iteration: int = 1
    repairs: list[VisualRepairItem] = Field(default_factory=list)
    applied: bool = False
    safeguards_verified: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)
