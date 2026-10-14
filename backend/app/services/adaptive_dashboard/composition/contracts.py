"""Composition and Spatial Contracts (Phase G5.6).

Defines strongly typed, semantically blind contracts for dashboard spatial composition:
- VisualLegibilityProfile: Archetype spatial requirements and readable envelope.
- ContentDensityMetrics: Measurement of labels, categories, and series density.
- CompositionCandidate: Spatial candidate extracted from visual metadata without domain knowledge.
- CompositionItem: Pure layout coordinate specification keyed by topic_id.
- DashboardLayoutPlan: Immutable multi-section 12-column layout plan.
"""
from __future__ import annotations

from enum import Enum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class VisualHeightClass(str, Enum):
    SHORT = "short"        # ~190-200px (e.g. bullet KPI strip)
    STANDARD = "standard"  # ~250-260px (e.g. box plot, scatter, lollipop)
    TALL = "tall"          # ~320-340px (e.g. 2D heatmap matrix, companion)


class VisualLegibilityProfile(BaseModel):
    """Governed visual legibility and spatial envelope for a chart archetype."""
    model_config = ConfigDict(extra="ignore")

    chart_archetype: str
    min_readable_span: int = 4
    preferred_span: int = 6
    max_useful_span: int = 8
    min_height: int = 250
    preferred_aspect_ratio: float = 1.6
    preferred_height: VisualHeightClass = VisualHeightClass.STANDARD
    allowed_heights: list[VisualHeightClass] = Field(default_factory=lambda: [VisualHeightClass.STANDARD])
    is_hero_eligible: bool = False

    max_categories_at_span_4: int = 4
    max_categories_at_span_6: int = 8
    max_categories_at_span_8: int = 15

    max_label_chars_at_span_4: int = 12
    max_label_chars_at_span_6: int = 20
    max_label_chars_at_span_8: int = 32

    legend_cost: float = 0.1
    axis_cost: float = 0.1

    @property
    def min_col_span(self) -> int:
        return self.min_readable_span

    @property
    def preferred_col_span(self) -> int:
        return self.preferred_span

    @property
    def max_col_span(self) -> int:
        return self.max_useful_span

    @property
    def natural_aspect_ratio(self) -> float:
        return self.preferred_aspect_ratio


ARCHETYPE_PROFILES: dict[str, VisualLegibilityProfile] = {
    "ranked_bar": VisualLegibilityProfile(
        chart_archetype="ranked_bar",
        min_readable_span=7,
        preferred_span=8,
        max_useful_span=12,
        min_height=260,
        preferred_aspect_ratio=1.5,
        preferred_height=VisualHeightClass.STANDARD,
        allowed_heights=[VisualHeightClass.STANDARD, VisualHeightClass.TALL],
        is_hero_eligible=True,
        max_categories_at_span_4=3,
        max_categories_at_span_6=6,
        max_categories_at_span_8=12,
        max_label_chars_at_span_4=12,
        max_label_chars_at_span_6=20,
        max_label_chars_at_span_8=32,
    ),
    "ranking": VisualLegibilityProfile(
        chart_archetype="ranking",
        min_readable_span=7,
        preferred_span=8,
        max_useful_span=12,
        min_height=260,
        preferred_aspect_ratio=1.5,
        preferred_height=VisualHeightClass.STANDARD,
        allowed_heights=[VisualHeightClass.STANDARD, VisualHeightClass.TALL],
        is_hero_eligible=True,
        max_categories_at_span_4=3,
        max_categories_at_span_6=6,
        max_categories_at_span_8=12,
        max_label_chars_at_span_4=12,
        max_label_chars_at_span_6=20,
        max_label_chars_at_span_8=32,
    ),
    "horizontal_bar": VisualLegibilityProfile(
        chart_archetype="horizontal_bar",
        min_readable_span=7,
        preferred_span=8,
        max_useful_span=12,
        min_height=260,
        preferred_aspect_ratio=1.5,
        preferred_height=VisualHeightClass.STANDARD,
        allowed_heights=[VisualHeightClass.STANDARD, VisualHeightClass.TALL],
    ),
    "diverging_bar": VisualLegibilityProfile(
        chart_archetype="diverging_bar",
        min_readable_span=6,
        preferred_span=8,
        max_useful_span=12,
        min_height=260,
        preferred_aspect_ratio=1.5,
        preferred_height=VisualHeightClass.STANDARD,
        allowed_heights=[VisualHeightClass.STANDARD, VisualHeightClass.TALL],
    ),
    "heatmap": VisualLegibilityProfile(
        chart_archetype="heatmap",
        min_readable_span=7,
        preferred_span=8,
        max_useful_span=12,
        min_height=320,
        preferred_aspect_ratio=2.4,
        preferred_height=VisualHeightClass.TALL,
        allowed_heights=[VisualHeightClass.TALL, VisualHeightClass.STANDARD],
    ),
    "scatter": VisualLegibilityProfile(
        chart_archetype="scatter",
        min_readable_span=5,
        preferred_span=6,
        max_useful_span=8,
        min_height=260,
        preferred_aspect_ratio=1.5,
        preferred_height=VisualHeightClass.STANDARD,
        allowed_heights=[VisualHeightClass.STANDARD],
    ),
    "box_plot": VisualLegibilityProfile(
        chart_archetype="box_plot",
        min_readable_span=4,
        preferred_span=6,
        max_useful_span=8,
        min_height=250,
        preferred_aspect_ratio=1.6,
        preferred_height=VisualHeightClass.STANDARD,
        allowed_heights=[VisualHeightClass.STANDARD],
    ),
    "podium_top_3": VisualLegibilityProfile(
        chart_archetype="podium_top_3",
        min_readable_span=3,
        preferred_span=4,
        max_useful_span=6,
        min_height=250,
        preferred_aspect_ratio=1.2,
        preferred_height=VisualHeightClass.STANDARD,
        allowed_heights=[VisualHeightClass.STANDARD, VisualHeightClass.TALL],
    ),
    "bullet": VisualLegibilityProfile(
        chart_archetype="bullet",
        min_readable_span=5,
        preferred_span=6,
        max_useful_span=12,
        min_height=190,
        preferred_aspect_ratio=3.0,
        preferred_height=VisualHeightClass.SHORT,
        allowed_heights=[VisualHeightClass.SHORT, VisualHeightClass.STANDARD],
        is_hero_eligible=True,
    ),
    "100_percent_stacked_bar": VisualLegibilityProfile(
        chart_archetype="100_percent_stacked_bar",
        min_readable_span=5,
        preferred_span=6,
        max_useful_span=8,
        min_height=250,
        preferred_aspect_ratio=1.6,
        preferred_height=VisualHeightClass.STANDARD,
        allowed_heights=[VisualHeightClass.STANDARD, VisualHeightClass.TALL],
    ),
    "stacked_bar": VisualLegibilityProfile(
        chart_archetype="stacked_bar",
        min_readable_span=5,
        preferred_span=6,
        max_useful_span=8,
        min_height=250,
        preferred_aspect_ratio=1.6,
        preferred_height=VisualHeightClass.STANDARD,
        allowed_heights=[VisualHeightClass.STANDARD, VisualHeightClass.TALL],
    ),
    "dumbbell": VisualLegibilityProfile(
        chart_archetype="dumbbell",
        min_readable_span=4,
        preferred_span=6,
        max_useful_span=7,
        min_height=250,
        preferred_aspect_ratio=1.3,
        preferred_height=VisualHeightClass.STANDARD,
        allowed_heights=[VisualHeightClass.STANDARD],
    ),
    "lollipop": VisualLegibilityProfile(
        chart_archetype="lollipop",
        min_readable_span=4,
        preferred_span=5,
        max_useful_span=6,
        min_height=250,
        preferred_aspect_ratio=1.3,
        preferred_height=VisualHeightClass.STANDARD,
        allowed_heights=[VisualHeightClass.STANDARD],
    ),
    "variance_bar": VisualLegibilityProfile(
        chart_archetype="variance_bar",
        min_readable_span=4,
        preferred_span=6,
        max_useful_span=7,
        min_height=250,
        preferred_aspect_ratio=1.3,
        preferred_height=VisualHeightClass.STANDARD,
        allowed_heights=[VisualHeightClass.STANDARD],
    ),
    "trend_line": VisualLegibilityProfile(
        chart_archetype="trend_line",
        min_readable_span=6,
        preferred_span=8,
        max_useful_span=12,
        min_height=250,
        preferred_aspect_ratio=1.8,
        preferred_height=VisualHeightClass.STANDARD,
        allowed_heights=[VisualHeightClass.STANDARD, VisualHeightClass.TALL],
    ),
    "multi_series_trend": VisualLegibilityProfile(
        chart_archetype="multi_series_trend",
        min_readable_span=6,
        preferred_span=8,
        max_useful_span=12,
        min_height=280,
        preferred_aspect_ratio=1.8,
        preferred_height=VisualHeightClass.STANDARD,
        allowed_heights=[VisualHeightClass.STANDARD, VisualHeightClass.TALL],
    ),
    "treemap": VisualLegibilityProfile(
        chart_archetype="treemap",
        min_readable_span=6,
        preferred_span=8,
        max_useful_span=12,
        min_height=280,
        preferred_aspect_ratio=1.8,
        preferred_height=VisualHeightClass.STANDARD,
        allowed_heights=[VisualHeightClass.STANDARD, VisualHeightClass.TALL],
    ),
}

DEFAULT_PROFILE = VisualLegibilityProfile(
    chart_archetype="standard",
    min_readable_span=5,
    preferred_span=6,
    max_useful_span=8,
    min_height=250,
    preferred_aspect_ratio=1.6,
    preferred_height=VisualHeightClass.STANDARD,
    allowed_heights=[VisualHeightClass.STANDARD],
)


VisualSpatialProfile = VisualLegibilityProfile


class ContentDensityMetrics(BaseModel):
    """Empirical content density measurements extracted from visual specifications."""
    model_config = ConfigDict(extra="ignore")

    longest_label_length: int = 0
    average_label_length: float = 0.0
    number_of_categories: int = 0
    series_count: int = 1
    axis_label_count: int = 0
    marks_count: int = 0
    label_density_score: float = 0.0
    information_density_score: float = 0.0
    label_density_adjustment: int = 0
    effective_min_span: int = 4
    effective_preferred_span: int = 6


class CompositionCandidate(BaseModel):
    """Candidate representation for spatial layout planning.
    
    Contains strictly structural, graphical, and legibility metadata.
    Contains zero domain or analytical semantics.
    """
    model_config = ConfigDict(extra="ignore")

    topic_id: str
    visual_family: str = "general"
    chart_archetype: str = "ranked_bar"
    morphology: str = "bar"
    importance: float = 0.5
    priority: int = 1
    readability_constraints: dict[str, Any] = Field(default_factory=dict)
    content_density: ContentDensityMetrics = Field(default_factory=ContentDensityMetrics)
    preferred_span: int = 6
    minimum_span: int = 4
    maximum_span: int = 12
    height_class: str = "standard"
    slot_type: str = "supporting"
    analytical_intent: str = "general"
    is_hero: bool = False
    title: str = ""


class CompositionItem(BaseModel):
    """Immutable spatial placement coordinate for a topic card within the 12-column grid."""
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    topic_id: str
    display_order: int = 0
    row: int = 0
    column: int = 0
    span: int = 6
    height: str = "standard"
    pattern: str = "6+6"
    section_id: str = "priority"
    priority: int = 1
    layout_role: str = "supporting"
    readable_span_score: float = 1.0
    title: str = ""
    chart_archetype: str = ""

    # Synchronized fields for complete serialization and backward compatibility
    column_span: int = 6
    height_class: str = "standard"
    order_index: int = 0
    row_index: int = 0

    def model_post_init(self, __context: Any) -> None:
        if self.column_span != self.span:
            if self.column_span != 6 and self.span == 6:
                self.span = self.column_span
            else:
                self.column_span = self.span
        if self.height_class != self.height:
            if self.height_class != "standard" and self.height == "standard":
                self.height = self.height_class
            else:
                self.height_class = self.height
        if self.order_index != self.display_order:
            if self.order_index != 0 and self.display_order == 0:
                self.display_order = self.order_index
            else:
                self.order_index = self.display_order
        if self.row_index != self.row:
            if self.row_index != 0 and self.row == 0:
                self.row = self.row_index
            else:
                self.row_index = self.row

    @property
    def effective_min_span(self) -> int:
        return self.span


DashboardCardPlacement = CompositionItem
SpatialPlacement = CompositionItem


class CompositionRow(BaseModel):
    """A single row of cards in the 12-column layout grid."""
    model_config = ConfigDict(extra="ignore")

    row_id: str
    row_index: int = 0
    pattern: str = "12"
    total_span: int = 12
    utilization: float = 1.0
    cards: list[CompositionItem] = Field(default_factory=list)
    readability_score: float = 1.0
    is_intentional_partial: bool = False

    @property
    def items(self) -> list[CompositionItem]:
        return self.cards


DashboardRowLayout = CompositionRow


class CompositionSection(BaseModel):
    """A logical section grouping rows of cards (e.g. priority, diagnostic, supporting)."""
    model_config = ConfigDict(extra="ignore")

    section_id: str
    title: str = ""
    badge: str = ""
    subtitle: str = ""
    rows: list[CompositionRow] = Field(default_factory=list)
    total_cards: int = 0
    average_row_utilization: float = 1.0
    average_readability_score: float = 1.0


DashboardSectionLayout = CompositionSection


class DashboardLayoutPlan(BaseModel):
    """Authoritative, immutable dashboard spatial layout plan.
    
    Guarantees:
    - Owns all spatial and placement coordinates.
    - References topics strictly by topic_id.
    - Preserves zero-orphan, 12-column balanced grid invariants.
    """
    model_config = ConfigDict(extra="ignore")

    sections: list[CompositionSection] = Field(default_factory=list)
    items: list[CompositionItem] = Field(default_factory=list)
    items_by_topic_id: dict[str, CompositionItem] = Field(default_factory=dict)
    column_count: int = 12
    row_count: int = 0
    total_cards: int = 0
    total_rows: int = 0
    average_row_utilization: float = 1.0
    utilization: float = 1.0
    average_readable_span_score: float = 1.0
    readability_violations_count: int = 0
    intentional_partial_rows_count: int = 0
    orphan_cards_count: int = 0
    qa_passed: bool = True
    qa_details: dict[str, Any] = Field(default_factory=dict)

    def get_placement(self, topic_id: str) -> CompositionItem | None:
        return self.items_by_topic_id.get(topic_id)
