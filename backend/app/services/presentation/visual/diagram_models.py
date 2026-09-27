"""Deterministic Diagram and Matrix Models for Phase 4.

Provides structured schemas for reusable process flows, architecture topologies,
timelines, roadmaps, pyramid hierarchies, and 2x2 / 3x3 matrices.
Guarantees deterministic, structured rendering without LLM raw SVG hallucinations.
"""

from __future__ import annotations

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class DiagramFamily(str, Enum):
    """Canonical diagram and structural visual families."""
    PROCESS_FLOW = "process_flow"
    HORIZONTAL_PROCESS = "process_flow"
    ARCHITECTURE = "architecture"
    ARCHITECTURE_LAYERS = "architecture"
    TIMELINE = "timeline"
    TIMELINE_CHEVRON = "timeline"
    ROADMAP = "roadmap"
    FUNNEL = "funnel"
    HIERARCHY = "hierarchy"
    RELATIONSHIP = "relationship"
    DECISION_TREE = "decision_tree"
    SWIMLANE = "swimlane"
    LIFECYCLE = "lifecycle"
    BEFORE_AFTER = "before_after"
    PYRAMID = "pyramid"


class MatrixFamily(str, Enum):
    """Canonical matrix visual families."""
    MATRIX_2X2 = "matrix_2x2"
    QUADRANT_2X2 = "matrix_2x2"
    MATRIX_3X3 = "matrix_3x3"
    TALENT_9BOX = "talent_9box"
    RISK_MATRIX = "risk_matrix"
    IMPACT_EFFORT = "impact_effort"
    PRIORITY_MATRIX = "priority_matrix"
    GROWTH_SHARE = "growth_share"


class DiagramNode(BaseModel):
    """An atomic step, component, tier, or milestone in a diagram."""
    id: str = ""
    label: str
    subtext: str = ""
    sublabel: str = ""
    status: str = "default"  # default | active | complete | at_risk
    color: str | None = None
    icon: str | None = None
    value: str | float | None = None
    order: int = 1
    metadata: dict[str, Any] = Field(default_factory=dict)


class DiagramConnection(BaseModel):
    """A directed edge or transition between diagram nodes."""
    source_id: str = ""
    target_id: str = ""
    from_node: str = ""
    to_node: str = ""
    label: str = ""
    style: str = "solid"  # solid | dashed | arrow

    def model_post_init(self, __context: Any) -> None:
        if self.from_node and not self.source_id:
            self.source_id = self.from_node
        elif self.source_id and not self.from_node:
            self.from_node = self.source_id
        if self.to_node and not self.target_id:
            self.target_id = self.to_node
        elif self.target_id and not self.to_node:
            self.to_node = self.target_id


class DiagramSpec(BaseModel):
    """The canonical, renderer-neutral diagram specification."""
    diagram_id: str = ""
    family: DiagramFamily
    variant: str = "standard"
    title: str = ""
    nodes: list[DiagramNode] = Field(default_factory=list)
    connections: list[DiagramConnection] = Field(default_factory=list)
    stages: list[str] = Field(default_factory=list)
    swimlanes: list[dict[str, Any]] = Field(default_factory=list)
    extra_options: dict[str, Any] = Field(default_factory=dict)


class MatrixQuadrant(BaseModel):
    """An individual cell or quadrant in a 2x2 or 3x3 matrix."""
    id: str = ""
    row: int = 1
    col: int = 1
    x: int = 1
    y: int = 1
    label: str
    description: str = ""
    color_tier: str = "neutral"  # neutral | positive | warning | critical
    items_count: int = 0
    items: list[str] = Field(default_factory=list)
    action_note: str = ""


class MatrixSpec(BaseModel):
    """The canonical, renderer-neutral matrix specification."""
    matrix_id: str = ""
    family: MatrixFamily
    variant: str = "standard"
    title: str = ""
    x_axis_label: str = "Impact / Performance"
    y_axis_label: str = "Effort / Potential"
    rows: int = 2
    cols: int = 2
    quadrants: list[MatrixQuadrant] = Field(default_factory=list)
    cells: list[MatrixQuadrant] = Field(default_factory=list)
    summary_stats: dict[str, Any] = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        if self.quadrants and not self.cells:
            self.cells = self.quadrants
        elif self.cells and not self.quadrants:
            self.quadrants = self.cells
