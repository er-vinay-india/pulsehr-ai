"""Canonical VisualSpecification Contract for Phase 4.

The renderer-neutral contract transforming approved SlideExecutionPackages
into explicit visual architectures rendered across React, standalone HTML, and native PPTX.
"""

from __future__ import annotations

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field

from .chart_models import ChartSpec
from .diagram_models import DiagramSpec, MatrixSpec
from .layout_registry import ContentBudget, LayoutFamily, LayoutSpec


class TransitionType(str, Enum):
    """Presentation transition animations honoring accessibility and reduced motion."""
    NONE = "NONE"
    FADE = "FADE"
    SLIDE = "SLIDE"
    SCALE = "SCALE"
    REVEAL = "REVEAL"


class VisualStoryPriority(str, Enum):
    """Priority focus driving visual density and element hierarchy."""
    DATA = "data"
    NARRATIVE = "narrative"
    COMPARISON = "comparison"
    KPI = "kpi"
    PROCESS = "process"
    EXECUTIVE_ACTION = "executive_action"


class VisualStory(BaseModel):
    """Semantic pacing and narrative density instructions for the visual renderer."""
    primary_message: str
    priority: VisualStoryPriority = VisualStoryPriority.DATA
    density: str = "medium"  # low | medium | high
    strategic_intent: str = ""
    takeaway: str = ""
    audience_focus: str = "Executive Decision Makers"
    intent: str = ""


class PrimaryVisualDescriptor(BaseModel):
    """Summary descriptor for the primary visual element anchored on the slide."""
    visual_family: str  # e.g. BAR_HORIZONTAL, SANKEY, TALENT_9BOX, PROCESS_FLOW
    variant: str = "standard"
    purpose: str = "data_insight"
    chart_spec_id: str | None = None
    diagram_spec_id: str | None = None
    matrix_spec_id: str | None = None


class SourceFooterSpec(BaseModel):
    """Audited provenance footer displaying ground-truth data references."""
    visible: bool = True
    dataset_label: str = ""
    reporting_period: str = ""
    source_sheets: list[str] = Field(default_factory=list)
    source_citation: str = ""
    evidence_citation: str = ""
    confidence_statement: str = "Audited Ground Truth (±0.1%)"
    slide_counter_text: str = ""


class VisualSpecification(BaseModel):
    """The canonical, renderer-neutral visual presentation slide contract."""
    slide_id: str = ""
    sequence_number: int = 1
    headline: str
    subtitle: str = ""
    visual_story: VisualStory
    layout: LayoutSpec
    primary_visual: PrimaryVisualDescriptor
    secondary_visuals: list[dict[str, Any]] = Field(default_factory=list)
    components: list[str] = Field(
        default_factory=lambda: [
            "headline", "primary_visual", "insight_panel", "source_footer"
        ]
    )
    theme_id: str = "bold_signal"
    transition: TransitionType = TransitionType.FADE

    # Concrete visual payloads
    chart_spec: ChartSpec | None = None
    diagram_spec: DiagramSpec | None = None
    matrix_spec: MatrixSpec | None = None
    kpis: list[dict[str, Any]] = Field(default_factory=list)
    insights: list[str] = Field(default_factory=list)
    table_data: dict[str, Any] | None = None
    structured_proposals: list[dict[str, Any]] | None = None
    speaker_notes: str = ""

    # Explainability & Provenance
    chart_selection_reason: str = ""
    source_footer: SourceFooterSpec = Field(default_factory=SourceFooterSpec)
    design_tokens: Any = None
    accessibility_report: dict[str, Any] = Field(default_factory=dict)
    budget_validation: dict[str, Any] = Field(default_factory=dict)
    generated_at: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
