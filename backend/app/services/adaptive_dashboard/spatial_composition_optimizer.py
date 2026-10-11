"""Intelligent Spatial Composition Engine & Layout Optimizer.

Optimizes executive dashboard spatial layout with content-density and legibility awareness:
- ReadableSpanIntegrity: archetype-defined min_readable_span, preferred_span, and max_useful_span.
  A placement below min_readable_span is strictly invalid regardless of row utilization.
- LabelDensityScore & InformationDensityIntegrity:
  Content-aware span expansion based on longest_label_length, average_label_length, category counts,
  and series density (e.g. long department names force ranked bars to 8+ columns).
- Decoupled semantic priority from visual space requirement:
  Supporting analysis visuals requiring large visual area (e.g. 8-col ranked bars) receive proper width.
- Multi-objective layout scoring:
  score = 0.40 * semantic_adjacency + 0.30 * visual_readability + 0.20 * spatial_efficiency + 0.10 * height_balance.
- Balanced 12-column grid packing templates:
  12, 8+4, 4+8, 6+6, 7+5, 5+7, 4+4+4 (gated by short labels and min span <= 4), and intentional partial rows.
- Synchronized row height classes (HeightBalanceIntegrity).
- Multi-viewport responsive contract with zero CSS order.
"""
from __future__ import annotations

import logging
from enum import Enum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class VisualHeightClass(str, Enum):
    SHORT = "short"        # ~190-200px (e.g. bullet KPI strip)
    STANDARD = "standard"  # ~250-260px (e.g. box plot, scatter, lollipop)
    TALL = "tall"          # ~320-340px (e.g. 2D heatmap matrix, olympic podium companion)


class VisualLegibilityProfile(BaseModel):
    """Governed visual legibility and spatial envelope for a chart archetype."""
    model_config = ConfigDict(extra="ignore")
    chart_archetype: str
    min_readable_span: int = 4
    preferred_span: int = 6
    max_useful_span: int = 8
    min_height: int = 250
    preferred_aspect_ratio: float = 1.6  # width / height ratio
    preferred_height: VisualHeightClass = VisualHeightClass.STANDARD
    allowed_heights: list[VisualHeightClass] = Field(default_factory=lambda: [VisualHeightClass.STANDARD])
    is_hero_eligible: bool = False

    # Capacity constraints at different column spans
    max_categories_at_span_4: int = 4
    max_categories_at_span_6: int = 8
    max_categories_at_span_8: int = 15

    max_label_chars_at_span_4: int = 12
    max_label_chars_at_span_6: int = 20
    max_label_chars_at_span_8: int = 32

    legend_cost: float = 0.1
    axis_cost: float = 0.1

    # Backwards compatibility accessors
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


# Alias for backward compatibility
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


class SpatialPlacement(BaseModel):
    """Server-driven placement metadata assigned to each ExecutiveTopic."""
    model_config = ConfigDict(extra="ignore")
    column_span: int = 6  # 3 to 12
    height_class: str = "standard"  # "short", "standard", "tall"
    row_index: int = 0
    row_id: str = ""
    pattern: str = "6+6"  # "12", "8+4", "4+8", "6+6", "7+5", "5+7", "4+4+4", "8"
    section_id: str = "priority"
    order_index: int = 0
    effective_min_span: int = 4
    readable_span_score: float = 1.0


class DashboardCardPlacement(BaseModel):
    topic_id: str
    title: str
    chart_archetype: str
    column_span: int
    height_class: str
    order_index: int
    effective_min_span: int = 4
    readable_span_score: float = 1.0


class DashboardRowLayout(BaseModel):
    row_id: str
    row_index: int
    pattern: str
    total_span: int
    utilization: float
    cards: list[DashboardCardPlacement]
    readability_score: float = 1.0
    is_intentional_partial: bool = False


class DashboardSectionLayout(BaseModel):
    section_id: str
    title: str
    badge: str = ""
    subtitle: str = ""
    rows: list[DashboardRowLayout]
    total_cards: int = 0
    average_row_utilization: float = 1.0
    average_readability_score: float = 1.0


class DashboardLayoutPlan(BaseModel):
    model_config = ConfigDict(extra="ignore")
    sections: list[DashboardSectionLayout]
    total_cards: int
    total_rows: int
    average_row_utilization: float
    average_readable_span_score: float = 1.0
    readability_violations_count: int = 0
    intentional_partial_rows_count: int = 0
    orphan_cards_count: int = 0
    qa_passed: bool = True
    qa_details: dict[str, Any] = Field(default_factory=dict)


# ==============================================================================
# Governed Archetype Legibility Profiles
# ==============================================================================

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


def get_legibility_profile(chart_type: str) -> VisualLegibilityProfile:
    normalized = (chart_type or "").lower().replace("-", "_").replace(" ", "_")
    return ARCHETYPE_PROFILES.get(normalized, DEFAULT_PROFILE)


get_spatial_profile = get_legibility_profile


# ==============================================================================
# Content Density & Label Density Analyzer
# ==============================================================================

def analyze_content_density(topic: Any, profile: VisualLegibilityProfile) -> ContentDensityMetrics:
    """Computes content density, label length metrics, and effective required spans for a card."""
    spec = getattr(topic, "visual_spec", {}) or {}
    if not isinstance(spec, dict):
        spec = {}

    # 1. Extract categories / entity labels
    categories: list[str] = []
    if "categories" in spec and isinstance(spec["categories"], list):
        categories.extend(str(c) for c in spec["categories"])
    elif "x_categories" in spec and isinstance(spec["x_categories"], list):
        categories.extend(str(c) for c in spec["x_categories"])
    elif "podium_categories" in spec and isinstance(spec["podium_categories"], list):
        categories.extend(str(c) for c in spec["podium_categories"])

    # 2. Extract series and marks
    series = spec.get("series", [])
    series_count = len(series) if isinstance(series, list) else 1

    marks_count = len(categories)
    if "scatter_points" in spec and isinstance(spec["scatter_points"], list):
        marks_count = len(spec["scatter_points"])
    elif "heatmap_data" in spec and isinstance(spec["heatmap_data"], list):
        marks_count = len(spec["heatmap_data"])

    longest_label = max((len(c) for c in categories), default=0)
    avg_label = (sum(len(c) for c in categories) / len(categories)) if categories else 0.0

    # 3. Compute label density adjustment
    adjustment = 0
    arch = profile.chart_archetype

    # Horizontal bars and rankings with long labels require at least 8 columns
    if arch in ("ranked_bar", "ranking", "horizontal_bar", "diverging_bar"):
        if longest_label >= 20 or avg_label >= 14:
            adjustment = 1
    elif arch in ("dumbbell", "variance_bar"):
        if longest_label >= 28 or avg_label >= 18:
            adjustment = 1
    else:
        # Compact companions (lollipop, podium, bullet) keep base min span
        pass

    # Effective min span is bounded by profile envelopes
    eff_min = max(profile.min_readable_span + adjustment, profile.min_readable_span)
    # Cap effective_min_span for pairable ranking cards at 8 so they can form balanced 8+4 rows
    if arch in ("ranked_bar", "ranking", "horizontal_bar"):
        eff_min = min(eff_min, 8)
    else:
        eff_min = min(eff_min, profile.max_useful_span)
    eff_pref = max(profile.preferred_span, eff_min)

    # Normalized density scores
    label_density_score = min(1.0, (longest_label / 40.0) * 0.7 + (avg_label / 25.0) * 0.3)
    info_density_score = min(1.0, (marks_count / 20.0) * 0.6 + (series_count / 4.0) * 0.4)

    return ContentDensityMetrics(
        longest_label_length=longest_label,
        average_label_length=round(avg_label, 1),
        number_of_categories=len(categories),
        series_count=series_count,
        axis_label_count=len(categories),
        marks_count=marks_count,
        label_density_score=round(label_density_score, 3),
        information_density_score=round(info_density_score, 3),
        label_density_adjustment=adjustment,
        effective_min_span=eff_min,
        effective_preferred_span=eff_pref,
    )


# ==============================================================================
# Adjacency & Complementarity Intelligence
# ==============================================================================

def score_adjacency_compatibility(card_a: Any, card_b: Any) -> float:
    """Computes spatial adjacency compatibility between two candidate cards on the same row."""
    intent_a = getattr(card_a, "analytical_intent", "")
    intent_b = getattr(card_b, "analytical_intent", "")
    chart_a = getattr(card_a, "recommended_visual", "") or getattr(card_a, "visual_spec", {}).get("chart_type", "")
    chart_b = getattr(card_b, "recommended_visual", "") or getattr(card_b, "visual_spec", {}).get("chart_type", "")

    score = 0.50

    # 1. Intent complementarity
    complementary_pairs = {
        frozenset({"TARGET_VS_ACTUAL", "MATRIX"}): 0.35,
        frozenset({"DISTRIBUTION", "RELATIONSHIP"}): 0.35,
        frozenset({"COMPOSITION", "RELATIONSHIP"}): 0.35,
        frozenset({"RANKING", "MATRIX"}): 0.30,
        frozenset({"RANKING", "DISTRIBUTION"}): 0.25,
        frozenset({"COMPOSITION", "COMPARISON"}): 0.30,
        frozenset({"RANKING", "COMPOSITION"}): 0.20,
    }
    intents = frozenset({intent_a, intent_b})
    score += complementary_pairs.get(intents, 0.05)

    # 2. Morphology contrast
    if chart_a and chart_b:
        if chart_a != chart_b:
            score += 0.25  # High diversity bonus
        else:
            score -= 0.40  # Penalty for repetitive morphologies side-by-side

    # 3. High-synergy focal pairings
    synergy_pairs = {
        frozenset({"heatmap", "podium_top_3"}): 0.45,
        frozenset({"heatmap", "box_plot"}): 0.30,
        frozenset({"100_percent_stacked_bar", "scatter"}): 0.40,
        frozenset({"box_plot", "scatter"}): 0.35,
        frozenset({"ranked_bar", "podium_top_3"}): 0.35,
        frozenset({"ranked_bar", "lollipop"}): 0.35,
        frozenset({"dumbbell", "lollipop"}): 0.30,
    }
    charts = frozenset({chart_a, chart_b})
    score += synergy_pairs.get(charts, 0.0)

    return score


# ==============================================================================
# Spatial Composition Optimizer Engine
# ==============================================================================

class SpatialCompositionOptimizer:
    """Deterministic server-driven executive dashboard layout and readability optimizer."""

    @classmethod
    def optimize_layout(
        cls,
        topics: list[Any],
        domain: str = "general",
    ) -> DashboardLayoutPlan:
        """Takes executive topics and generates a structured DashboardLayoutPlan,

        enforcing ReadableSpanIntegrity, ContentDensity, and balanced 12-column layouts.
        """
        if not topics:
            return DashboardLayoutPlan(
                sections=[],
                total_cards=0,
                total_rows=0,
                average_row_utilization=1.0,
                average_readable_span_score=1.0,
                readability_violations_count=0,
                intentional_partial_rows_count=0,
                orphan_cards_count=0,
                qa_passed=True,
            )

        # 1. Pre-compute legibility profiles and content density metrics for all topics
        metrics_map: dict[str, ContentDensityMetrics] = {}
        for t in topics:
            tid = str(getattr(t, "topic_id", "") or id(t))
            chart_t = getattr(t, "recommended_visual", "") or getattr(t, "visual_spec", {}).get("chart_type", "")
            prof = get_legibility_profile(chart_t)
            metrics_map[tid] = analyze_content_density(t, prof)

        # 2. Partition topics into semantic decision sections
        sections_data = cls._partition_topics_into_sections(topics)

        section_layouts: list[DashboardSectionLayout] = []
        global_row_index = 0
        global_order_index = 0
        all_row_utilizations: list[float] = []
        all_readability_scores: list[float] = []
        orphan_count = 0
        intentional_partial_count = 0
        readability_violations: list[str] = []

        for sec_id, sec_meta in sections_data.items():
            sec_topics = sec_meta["topics"]
            if not sec_topics:
                continue

            sec_rows: list[DashboardRowLayout] = []

            # 3. Pack section topics into readability-aware 12-column rows
            packed_rows = cls._pack_section_into_rows(
                sec_topics,
                metrics_map=metrics_map,
                is_priority_section=(sec_id == "priority"),
            )

            for row_spec in packed_rows:
                cards_in_row = row_spec["cards"]
                pattern = row_spec["pattern"]
                total_span = sum(c["column_span"] for c in cards_in_row)
                utilization = round(total_span / 12.0, 3)
                all_row_utilizations.append(utilization)

                is_partial = row_spec.get("is_intentional_partial", total_span < 12 and len(cards_in_row) == 1)
                if is_partial and total_span >= 7:
                    intentional_partial_count += 1

                row_id = f"{sec_id}-r{len(sec_rows) + 1}"
                row_cards_placements: list[DashboardCardPlacement] = []

                # Determine synchronized height class for row (HeightBalanceIntegrity)
                row_height = cls._resolve_row_height_class(cards_in_row)

                row_readability_sum = 0.0

                for c_item in cards_in_row:
                    topic = c_item["topic"]
                    span = c_item["column_span"]
                    tid = str(getattr(topic, "topic_id", "") or id(topic))
                    t_metrics = metrics_map.get(tid, ContentDensityMetrics())

                    # ReadableSpanIntegrity check
                    if span < t_metrics.effective_min_span:
                        v_msg = f"Card '{getattr(topic, 'title', tid)}' assigned span {span} < effective min {t_metrics.effective_min_span}"
                        readability_violations.append(v_msg)
                        logger.warning("ReadableSpanIntegrity violation: %s", v_msg)

                    card_readability = min(1.0, round(span / max(1, t_metrics.effective_preferred_span), 2))
                    row_readability_sum += card_readability

                    # Assign spatial placement to topic object
                    placement = SpatialPlacement(
                        column_span=span,
                        height_class=row_height.value,
                        row_index=global_row_index,
                        row_id=row_id,
                        pattern=pattern,
                        section_id=sec_id,
                        order_index=global_order_index,
                        effective_min_span=t_metrics.effective_min_span,
                        readable_span_score=card_readability,
                    )
                    topic.spatial_placement = placement

                    # Also reflect in layout_hint for backwards compatibility
                    if span == 12:
                        topic.layout_hint = "HERO" if global_order_index == 0 else "LARGE"
                    elif span >= 7:
                        topic.layout_hint = "LARGE"
                    elif span >= 5:
                        topic.layout_hint = "MEDIUM"
                    else:
                        topic.layout_hint = "COMPACT"

                    # Track placement in row
                    chart_type = getattr(topic, "recommended_visual", "") or getattr(topic, "visual_spec", {}).get("chart_type", "")
                    row_cards_placements.append(
                        DashboardCardPlacement(
                            topic_id=getattr(topic, "topic_id", f"T-{global_order_index}"),
                            title=getattr(topic, "title", f"Card {global_order_index}"),
                            chart_archetype=chart_type,
                            column_span=span,
                            height_class=row_height.value,
                            order_index=global_order_index,
                            effective_min_span=t_metrics.effective_min_span,
                            readable_span_score=card_readability,
                        )
                    )
                    global_order_index += 1

                avg_row_readability = round(row_readability_sum / max(1, len(cards_in_row)), 2)
                all_readability_scores.append(avg_row_readability)

                # Orphan card check: single isolated card with span < 7 that wasn't intentional
                if len(cards_in_row) == 1 and total_span < 7:
                    orphan_count += 1

                sec_rows.append(
                    DashboardRowLayout(
                        row_id=row_id,
                        row_index=global_row_index,
                        pattern=pattern,
                        total_span=total_span,
                        utilization=utilization,
                        cards=row_cards_placements,
                        readability_score=avg_row_readability,
                        is_intentional_partial=is_partial,
                    )
                )
                global_row_index += 1

            avg_sec_util = round(
                sum(r.utilization for r in sec_rows) / len(sec_rows) if sec_rows else 1.0, 3
            )
            avg_sec_read = round(
                sum(r.readability_score for r in sec_rows) / len(sec_rows) if sec_rows else 1.0, 3
            )
            section_layouts.append(
                DashboardSectionLayout(
                    section_id=sec_id,
                    title=sec_meta["title"],
                    badge=sec_meta["badge"],
                    subtitle=sec_meta["subtitle"],
                    rows=sec_rows,
                    total_cards=len(sec_topics),
                    average_row_utilization=avg_sec_util,
                    average_readability_score=avg_sec_read,
                )
            )

        avg_total_util = round(
            sum(all_row_utilizations) / len(all_row_utilizations) if all_row_utilizations else 1.0, 3
        )
        avg_total_read = round(
            sum(all_readability_scores) / len(all_readability_scores) if all_readability_scores else 1.0, 3
        )

        # 4. Evaluate Spatial Layout Gates
        qa_results = cls._evaluate_spatial_gates(
            section_layouts=section_layouts,
            average_utilization=avg_total_util,
            average_readability=avg_total_read,
            orphan_count=orphan_count,
            readability_violations=readability_violations,
            intentional_partials=intentional_partial_count,
            topics=topics,
        )

        return DashboardLayoutPlan(
            sections=section_layouts,
            total_cards=len(topics),
            total_rows=global_row_index,
            average_row_utilization=avg_total_util,
            average_readable_span_score=avg_total_read,
            readability_violations_count=len(readability_violations),
            intentional_partial_rows_count=intentional_partial_count,
            orphan_cards_count=orphan_count,
            qa_passed=qa_results["passed"],
            qa_details=qa_results,
        )

    # --------------------------------------------------------------------------
    # Internal Section Partitioning
    # --------------------------------------------------------------------------

    @classmethod
    def _partition_topics_into_sections(cls, topics: list[Any]) -> dict[str, dict[str, Any]]:
        """Partitions topics deterministically into Priority Decisions, Diagnostic Insights, and Supporting Analysis."""
        if not topics:
            return {}

        has_explicit_hero = any(getattr(t, "slot_type", "") == "hero" for t in topics)
        if has_explicit_hero:
            hero_idx = next(i for i, t in enumerate(topics) if getattr(t, "slot_type", "") == "hero")
            hero = topics[hero_idx]
            remaining = [t for i, t in enumerate(topics) if i != hero_idx]
            priority_topics = [hero]
        elif len(topics) >= 4:
            hero = topics[0]
            remaining = list(topics[1:])
            priority_topics = [hero]
        else:
            priority_topics = []
            remaining = list(topics)
        diagnostic_topics = []
        supporting_topics = []

        # Find ideal companion for Priority:
        # High impact matrix heatmap, top ranking benchmark, or policy target
        heatmap_topic = next(
            (t for t in remaining if (getattr(t, "recommended_visual", "") == "heatmap" or getattr(t, "visual_spec", {}).get("chart_type") == "heatmap")),
            None,
        )
        podium_topic = next(
            (t for t in remaining if (getattr(t, "recommended_visual", "") == "podium_top_3" or getattr(t, "visual_spec", {}).get("chart_type") == "podium_top_3")),
            None,
        )

        allocated: set[int] = set()

        if heatmap_topic:
            priority_topics.append(heatmap_topic)
            allocated.add(id(heatmap_topic))
            if podium_topic:
                priority_topics.append(podium_topic)
                allocated.add(id(podium_topic))

        # Core analytical intents
        diagnostic_intents = {"DISTRIBUTION", "RELATIONSHIP", "ANOMALY", "VARIANCE", "COMPOSITION"}

        # Distribute remaining cards
        for t in remaining:
            if id(t) in allocated:
                continue
            intent = getattr(t, "analytical_intent", "")
            chart = getattr(t, "recommended_visual", "") or getattr(t, "visual_spec", {}).get("chart_type", "")

            # Diagnostic insights: statistical distributions, bivariate relationships, variance outliers, and capacity composition
            if intent in diagnostic_intents or chart in ("scatter", "box_plot", "100_percent_stacked_bar", "variance_bar"):
                diagnostic_topics.append(t)
            elif chart in ("ranked_bar", "ranking", "horizontal_bar", "lollipop", "dumbbell"):
                # Supporting analysis: comparative rankings, disparity spreads, entity benchmarks
                supporting_topics.append(t)
            else:
                diagnostic_topics.append(t)

        # Ensure balanced distribution across sections only when portfolio has large excess in supporting
        if not diagnostic_topics and len(supporting_topics) >= 4:
            half = len(supporting_topics) // 2
            diagnostic_topics.extend(supporting_topics[:half])
            supporting_topics = supporting_topics[half:]

        return {
            "priority": {
                "title": "Priority Decisions",
                "badge": "Leadership Focus",
                "subtitle": "Core policy compliance benchmarks, period cross-tabulations, and operational allocations.",
                "topics": priority_topics,
            },
            "diagnostic": {
                "title": "Diagnostic Insights",
                "badge": "Distributions & Variance",
                "subtitle": "Underlying statistical distributions, bivariate associations, and capacity compositions.",
                "topics": diagnostic_topics,
            },
            "supporting": {
                "title": "Supporting Analysis",
                "badge": "Comparative Benchmarks",
                "subtitle": "Entity-level comparative breakdowns and anomaly concentration patterns.",
                "topics": supporting_topics,
            },
        }

    # --------------------------------------------------------------------------
    # Internal Row Packing Algorithm with Readability Gates
    # --------------------------------------------------------------------------

    @classmethod
    def _pack_section_into_rows(
        cls,
        topics: list[Any],
        metrics_map: dict[str, ContentDensityMetrics],
        is_priority_section: bool = False,
    ) -> list[dict[str, Any]]:
        """Packs section topics into rows honoring ReadableSpanIntegrity and multi-objective scoring."""
        if not topics:
            return []

        rows: list[dict[str, Any]] = []
        pool = list(topics)

        # If priority section, Topic 1 is Hero -> Always gets dedicated full-width row (12)
        if is_priority_section and pool:
            hero = pool.pop(0)
            rows.append({
                "pattern": "12",
                "cards": [{"topic": hero, "column_span": 12}],
                "is_intentional_partial": False,
            })

        while pool:
            n = len(pool)

            # Case 1: Exactly 1 card left -> Dedicated row expands to 12 (Zero orphan empty space)
            if n == 1:
                card = pool.pop(0)
                rows.append({
                    "pattern": "12",
                    "cards": [{"topic": card, "column_span": 12}],
                    "is_intentional_partial": False,
                })
                break

            # Case 2: Exactly 3 cards left
            if n == 3:
                # Check if ALL 3 cards can legally fit at span 4 (ReadableSpanIntegrity Gate)
                card_metrics = [
                    metrics_map.get(str(getattr(c, "topic_id", "") or id(c)), ContentDensityMetrics())
                    for c in pool
                ]
                can_all_fit_span_4 = all(
                    m.effective_min_span <= 4 and m.longest_label_length <= 16
                    for m in card_metrics
                )

                if can_all_fit_span_4:
                    c1, c2, c3 = pool.pop(0), pool.pop(0), pool.pop(0)
                    rows.append({
                        "pattern": "4+4+4",
                        "cards": [
                            {"topic": c1, "column_span": 4},
                            {"topic": c2, "column_span": 4},
                            {"topic": c3, "column_span": 4},
                        ],
                        "is_intentional_partial": False,
                    })
                    break
                # If any card requires span > 4 (e.g. ranked_bar with long labels or scatter),
                # 4+4+4 is REJECTED. Fall through to pair 2 cards and leave 1 card for clean row.

            # Case 3: Pair 2 cards into a balanced row
            card_a = pool.pop(0)
            cid_a = str(getattr(card_a, "topic_id", "") or id(card_a))
            m_a = metrics_map.get(cid_a, ContentDensityMetrics())
            prof_a = get_legibility_profile(
                getattr(card_a, "recommended_visual", "") or getattr(card_a, "visual_spec", {}).get("chart_type", "")
            )

            # Find best companion and pattern among remaining pool
            best_idx = 0
            best_score = -999.0
            best_spans = (6, 6)
            best_pattern = "6+6"

            for idx, cand in enumerate(pool):
                cid_b = str(getattr(cand, "topic_id", "") or id(cand))
                m_b = metrics_map.get(cid_b, ContentDensityMetrics())
                prof_b = get_legibility_profile(
                    getattr(cand, "recommended_visual", "") or getattr(cand, "visual_spec", {}).get("chart_type", "")
                )

                # Test candidate templates summing to 12
                candidate_templates = [
                    (8, 4, "8+4"),
                    (4, 8, "4+8"),
                    (6, 6, "6+6"),
                    (7, 5, "7+5"),
                    (5, 7, "5+7"),
                ]

                adj_score = score_adjacency_compatibility(card_a, cand)
                height_score = 1.0 if prof_a.preferred_height == prof_b.preferred_height else 0.70

                for s_a, s_b, pat in candidate_templates:
                    # ReadableSpanIntegrity hard gate: span must satisfy effective_min_span
                    if s_a < m_a.effective_min_span or s_b < m_b.effective_min_span:
                        continue
                    if s_a > prof_a.max_useful_span or s_b > prof_b.max_useful_span:
                        continue

                    readability_a = min(1.0, s_a / max(1, m_a.effective_preferred_span))
                    readability_b = min(1.0, s_b / max(1, m_b.effective_preferred_span))
                    read_score = (readability_a + readability_b) / 2.0
                    spatial_score = (s_a + s_b) / 12.0

                    composite = (
                        0.40 * adj_score
                        + 0.30 * read_score
                        + 0.20 * spatial_score
                        + 0.10 * height_score
                    )

                    if composite > best_score:
                        best_score = composite
                        best_idx = idx
                        best_spans = (s_a, s_b)
                        best_pattern = pat

            # If no 12-column template passed ReadableSpanIntegrity, allow intentional 8+0 or partial
            if best_score < -100.0:
                span_a = max(m_a.effective_min_span, prof_a.preferred_span)
                rows.append({
                    "pattern": f"{span_a}",
                    "cards": [{"topic": card_a, "column_span": min(12, span_a)}],
                    "is_intentional_partial": span_a < 12,
                })
                continue

            card_b = pool.pop(best_idx)
            rows.append({
                "pattern": best_pattern,
                "cards": [
                    {"topic": card_a, "column_span": best_spans[0]},
                    {"topic": card_b, "column_span": best_spans[1]},
                ],
                "is_intentional_partial": False,
            })

        return rows

    @classmethod
    def _resolve_row_height_class(cls, cards_in_row: list[dict[str, Any]]) -> VisualHeightClass:
        """Enforces HeightBalanceIntegrity: all cards on the same row share a synchronized height class."""
        if not cards_in_row:
            return VisualHeightClass.STANDARD

        # If any card prefers TALL (e.g. Heatmap), the entire row becomes TALL so cards align cleanly
        for c in cards_in_row:
            chart = getattr(c["topic"], "recommended_visual", "") or getattr(c["topic"], "visual_spec", {}).get("chart_type", "")
            prof = get_legibility_profile(chart)
            if prof.preferred_height == VisualHeightClass.TALL:
                return VisualHeightClass.TALL

        # If all cards in row are SHORT (e.g. single bullet or compact KPI)
        if all(
            get_legibility_profile(
                getattr(c["topic"], "recommended_visual", "") or getattr(c["topic"], "visual_spec", {}).get("chart_type", "")
            ).preferred_height == VisualHeightClass.SHORT
            for c in cards_in_row
        ):
            return VisualHeightClass.SHORT

        return VisualHeightClass.STANDARD

    # --------------------------------------------------------------------------
    # Spatial Quality Gates & Invariants
    # --------------------------------------------------------------------------

    @classmethod
    def _evaluate_spatial_gates(
        cls,
        section_layouts: list[DashboardSectionLayout],
        average_utilization: float,
        average_readability: float,
        orphan_count: int,
        readability_violations: list[str],
        intentional_partials: int,
        topics: list[Any],
    ) -> dict[str, Any]:
        """Evaluates spatial and readability integrity invariants:

        1. ReadableSpanIntegrity: 0 violations of effective_min_span.
        2. RowUtilizationIntegrity: average row utilization >= 85%.
        3. OrphanCardIntegrity: orphan count == 0.
        4. PriorityAreaIntegrity: Hero visual has span 12 >= any supporting visual.
        5. HeightBalanceIntegrity: all rows have uniform height across cards.
        """
        passed = True
        failures = []

        # Gate 1: ReadableSpanIntegrity (Hard Requirement)
        if readability_violations:
            passed = False
            failures.append(f"ReadableSpanIntegrity failed: {len(readability_violations)} violations detected")

        # Gate 2: Row utilization >= 85%
        if average_utilization < 0.85:
            passed = False
            failures.append(f"RowUtilizationIntegrity failed: avg utilization {average_utilization:.2f} < 0.85")

        # Gate 3: Orphan cards
        if orphan_count > 0:
            passed = False
            failures.append(f"OrphanCardIntegrity failed: {orphan_count} orphan cards detected")

        # Gate 4: Priority Area (hero receives span 12)
        hero_topic = next((t for t in topics if getattr(t, "slot_type", "") == "hero"), None)
        if not hero_topic and len(topics) >= 4:
            hero_topic = topics[0]
        if hero_topic:
            hero_span = getattr(hero_topic.spatial_placement, "column_span", 0) if hasattr(hero_topic, "spatial_placement") else 0
            if hero_span < 12 and len(topics) > 1:
                passed = False
                failures.append(f"PriorityAreaIntegrity failed: Hero span {hero_span} < 12")

        # Track ranking card spans
        ranking_card_spans: dict[str, int] = {}
        for t in topics:
            chart = getattr(t, "recommended_visual", "") or getattr(t, "visual_spec", {}).get("chart_type", "")
            if chart in ("ranked_bar", "ranking", "horizontal_bar") and hasattr(t, "spatial_placement") and t.spatial_placement:
                ranking_card_spans[getattr(t, "title", "ranking")] = t.spatial_placement.column_span

        return {
            "passed": passed,
            "average_row_utilization": average_utilization,
            "average_readable_span_score": average_readability,
            "readability_violations_count": len(readability_violations),
            "readability_violations": readability_violations,
            "orphan_cards_count": orphan_count,
            "intentional_partial_rows_count": intentional_partials,
            "ranking_card_spans": ranking_card_spans,
            "failures": failures,
            "total_sections": len(section_layouts),
        }
