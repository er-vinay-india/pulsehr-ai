"""Intelligent Spatial Composition Engine & Layout Optimizer.

Optimizes executive dashboard spatial layout:
- Flexible column spans (3 to 12 columns in a 12-column grid)
- Archetype-specific intrinsic shape profiles and aspect ratios
- Deterministic row packing into balanced patterns: 12, 8+4, 4+8, 6+6, 7+5, 5+7, 4+4+4
- Semantic complementarity and morphology contrast adjacency scoring
- Spatial layout integrity gates:
  * RowUtilizationIntegrity (>= 85% row utilization, ideal 100%)
  * OrphanCardIntegrity (zero isolated compact/medium cards on incomplete rows)
  * HeightBalanceIntegrity (paired cards on a row share synchronized visual height classes)
  * PriorityAreaIntegrity (P1 hero receives >= area of supporting cards)
"""
from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class VisualHeightClass(str, Enum):
    SHORT = "short"        # ~190-200px
    STANDARD = "standard"  # ~250-260px
    TALL = "tall"          # ~320-340px


class VisualSpatialProfile(BaseModel):
    model_config = ConfigDict(extra="ignore")
    chart_archetype: str
    min_col_span: int = 4
    preferred_col_span: int = 6
    max_col_span: int = 8
    preferred_height: VisualHeightClass = VisualHeightClass.STANDARD
    allowed_heights: list[VisualHeightClass] = Field(default_factory=lambda: [VisualHeightClass.STANDARD])
    is_hero_eligible: bool = False
    natural_aspect_ratio: float = 1.6  # width / height ratio


class SpatialPlacement(BaseModel):
    """Server-driven placement metadata assigned to each ExecutiveTopic."""
    model_config = ConfigDict(extra="ignore")
    column_span: int = 6  # 3 to 12
    height_class: str = "standard"  # "short", "standard", "tall"
    row_index: int = 0
    row_id: str = ""
    pattern: str = "6+6"  # "12", "8+4", "4+8", "6+6", "7+5", "5+7", "4+4+4"
    section_id: str = "priority"
    order_index: int = 0


class DashboardCardPlacement(BaseModel):
    topic_id: str
    title: str
    chart_archetype: str
    column_span: int
    height_class: str
    order_index: int


class DashboardRowLayout(BaseModel):
    row_id: str
    row_index: int
    pattern: str
    total_span: int
    utilization: float
    cards: list[DashboardCardPlacement]


class DashboardSectionLayout(BaseModel):
    section_id: str
    title: str
    badge: str = ""
    subtitle: str = ""
    rows: list[DashboardRowLayout]
    total_cards: int = 0
    average_row_utilization: float = 1.0


class DashboardLayoutPlan(BaseModel):
    model_config = ConfigDict(extra="ignore")
    sections: list[DashboardSectionLayout]
    total_cards: int
    total_rows: int
    average_row_utilization: float
    orphan_cards_count: int
    qa_passed: bool = True
    qa_details: dict[str, Any] = Field(default_factory=dict)


# ==============================================================================
# Archetype Spatial Profile Registry
# ==============================================================================

ARCHETYPE_PROFILES: dict[str, VisualSpatialProfile] = {
    "heatmap": VisualSpatialProfile(
        chart_archetype="heatmap",
        min_col_span=7,
        preferred_col_span=8,
        max_col_span=12,
        preferred_height=VisualHeightClass.TALL,
        allowed_heights=[VisualHeightClass.TALL, VisualHeightClass.STANDARD],
    ),
    "ranking": VisualSpatialProfile(
        chart_archetype="ranking",
        min_col_span=5,
        preferred_col_span=7,
        max_col_span=12,
        preferred_height=VisualHeightClass.STANDARD,
        allowed_heights=[VisualHeightClass.STANDARD, VisualHeightClass.TALL],
        is_hero_eligible=True,
    ),
    "ranked_bar": VisualSpatialProfile(
        chart_archetype="ranked_bar",
        min_col_span=5,
        preferred_col_span=7,
        max_col_span=12,
        preferred_height=VisualHeightClass.STANDARD,
        allowed_heights=[VisualHeightClass.STANDARD, VisualHeightClass.TALL],
        is_hero_eligible=True,
    ),
    "diverging_bar": VisualSpatialProfile(
        chart_archetype="diverging_bar",
        min_col_span=5,
        preferred_col_span=7,
        max_col_span=12,
        preferred_height=VisualHeightClass.STANDARD,
        allowed_heights=[VisualHeightClass.STANDARD, VisualHeightClass.TALL],
    ),
    "scatter": VisualSpatialProfile(
        chart_archetype="scatter",
        min_col_span=4,
        preferred_col_span=6,
        max_col_span=8,
        preferred_height=VisualHeightClass.STANDARD,
        allowed_heights=[VisualHeightClass.STANDARD],
    ),
    "box_plot": VisualSpatialProfile(
        chart_archetype="box_plot",
        min_col_span=3,
        preferred_col_span=5,
        max_col_span=6,
        preferred_height=VisualHeightClass.STANDARD,
        allowed_heights=[VisualHeightClass.STANDARD],
    ),
    "podium_top_3": VisualSpatialProfile(
        chart_archetype="podium_top_3",
        min_col_span=3,
        preferred_col_span=4,
        max_col_span=6,
        preferred_height=VisualHeightClass.STANDARD,
        allowed_heights=[VisualHeightClass.STANDARD, VisualHeightClass.TALL],
    ),
    "bullet": VisualSpatialProfile(
        chart_archetype="bullet",
        min_col_span=5,
        preferred_col_span=6,
        max_col_span=12,
        preferred_height=VisualHeightClass.SHORT,
        allowed_heights=[VisualHeightClass.SHORT, VisualHeightClass.STANDARD],
        is_hero_eligible=True,
    ),
    "100_percent_stacked_bar": VisualSpatialProfile(
        chart_archetype="100_percent_stacked_bar",
        min_col_span=4,
        preferred_col_span=6,
        max_col_span=8,
        preferred_height=VisualHeightClass.STANDARD,
        allowed_heights=[VisualHeightClass.STANDARD, VisualHeightClass.TALL],
    ),
    "stacked_bar": VisualSpatialProfile(
        chart_archetype="stacked_bar",
        min_col_span=4,
        preferred_col_span=6,
        max_col_span=8,
        preferred_height=VisualHeightClass.STANDARD,
        allowed_heights=[VisualHeightClass.STANDARD, VisualHeightClass.TALL],
    ),
    "dumbbell": VisualSpatialProfile(
        chart_archetype="dumbbell",
        min_col_span=4,
        preferred_col_span=6,
        max_col_span=7,
        preferred_height=VisualHeightClass.STANDARD,
        allowed_heights=[VisualHeightClass.STANDARD],
    ),
    "lollipop": VisualSpatialProfile(
        chart_archetype="lollipop",
        min_col_span=3,
        preferred_col_span=5,
        max_col_span=6,
        preferred_height=VisualHeightClass.STANDARD,
        allowed_heights=[VisualHeightClass.STANDARD],
    ),
    "variance_bar": VisualSpatialProfile(
        chart_archetype="variance_bar",
        min_col_span=4,
        preferred_col_span=6,
        max_col_span=7,
        preferred_height=VisualHeightClass.STANDARD,
        allowed_heights=[VisualHeightClass.STANDARD],
    ),
    "trend_line": VisualSpatialProfile(
        chart_archetype="trend_line",
        min_col_span=5,
        preferred_col_span=7,
        max_col_span=12,
        preferred_height=VisualHeightClass.STANDARD,
        allowed_heights=[VisualHeightClass.STANDARD, VisualHeightClass.TALL],
    ),
    "multi_series_trend": VisualSpatialProfile(
        chart_archetype="multi_series_trend",
        min_col_span=5,
        preferred_col_span=7,
        max_col_span=12,
        preferred_height=VisualHeightClass.STANDARD,
        allowed_heights=[VisualHeightClass.STANDARD, VisualHeightClass.TALL],
    ),
}

DEFAULT_PROFILE = VisualSpatialProfile(
    chart_archetype="standard",
    min_col_span=4,
    preferred_col_span=6,
    max_col_span=8,
    preferred_height=VisualHeightClass.STANDARD,
    allowed_heights=[VisualHeightClass.STANDARD],
)


def get_spatial_profile(chart_type: str) -> VisualSpatialProfile:
    normalized = (chart_type or "").lower().replace("-", "_").replace(" ", "_")
    return ARCHETYPE_PROFILES.get(normalized, DEFAULT_PROFILE)


# ==============================================================================
# Adjacency & Complementarity Intelligence
# ==============================================================================

def score_adjacency_compatibility(card_a: Any, card_b: Any) -> float:
    """Computes spatial adjacency compatibility between two candidate cards on the same row.

    Rewards:
    - Complementary analytical intents (e.g. TARGET_VS_ACTUAL <-> MATRIX, DISTRIBUTION <-> RELATIONSHIP)
    - Contrasting visual morphologies (different shapes)
    - Asymmetric focal pairings (Heatmap 8 + Podium 4)

    Penalizes:
    - Identical visual morphologies side-by-side (e.g. two ranked bars)
    """
    intent_a = getattr(card_a, "analytical_intent", "")
    intent_b = getattr(card_b, "analytical_intent", "")
    chart_a = getattr(card_a, "recommended_visual", "") or getattr(card_a, "visual_spec", {}).get("chart_type", "")
    chart_b = getattr(card_b, "recommended_visual", "") or getattr(card_b, "visual_spec", {}).get("chart_type", "")

    score = 0.50

    # 1. Intent complementarity
    complementary_pairs = {
        frozenset({"TARGET_VS_ACTUAL", "MATRIX"}): 0.35,
        frozenset({"DISTRIBUTION", "RELATIONSHIP"}): 0.35,
        frozenset({"RANKING", "MATRIX"}): 0.30,
        frozenset({"RANKING", "DISTRIBUTION"}): 0.25,
        frozenset({"COMPOSITION", "COMPARISON"}): 0.30,
        frozenset({"COMPOSITION", "RELATIONSHIP"}): 0.25,
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
        frozenset({"100_percent_stacked_bar", "scatter"}): 0.35,
        frozenset({"box_plot", "scatter"}): 0.35,
        frozenset({"ranked_bar", "podium_top_3"}): 0.35,
        frozenset({"dumbbell", "lollipop"}): 0.30,
    }
    charts = frozenset({chart_a, chart_b})
    score += synergy_pairs.get(charts, 0.0)

    return score


# ==============================================================================
# Spatial Composition Optimizer Engine
# ==============================================================================

class SpatialCompositionOptimizer:
    """Deterministic server-driven executive dashboard layout and spatial composition engine."""

    @classmethod
    def optimize_layout(
        cls,
        topics: list[Any],
        domain: str = "general",
    ) -> DashboardLayoutPlan:
        """Takes executive topics and generates a structured DashboardLayoutPlan,

        mutating each topic with its resolved SpatialPlacement.
        """
        if not topics:
            return DashboardLayoutPlan(
                sections=[],
                total_cards=0,
                total_rows=0,
                average_row_utilization=1.0,
                orphan_cards_count=0,
                qa_passed=True,
            )

        # 1. Partition topics into semantic decision sections
        sections_data = cls._partition_topics_into_sections(topics)

        section_layouts: list[DashboardSectionLayout] = []
        global_row_index = 0
        global_order_index = 0
        all_row_utilizations: list[float] = []
        orphan_count = 0

        for sec_id, sec_meta in sections_data.items():
            sec_topics = sec_meta["topics"]
            if not sec_topics:
                continue

            sec_rows: list[DashboardRowLayout] = []

            # 2. Pack section topics into balanced 12-column rows
            packed_rows = cls._pack_section_into_rows(sec_topics, is_priority_section=(sec_id == "priority"))

            for row_spec in packed_rows:
                cards_in_row = row_spec["cards"]
                pattern = row_spec["pattern"]
                total_span = sum(c["column_span"] for c in cards_in_row)
                utilization = round(total_span / 12.0, 3)
                all_row_utilizations.append(utilization)

                row_id = f"{sec_id}-r{len(sec_rows) + 1}"
                row_cards_placements: list[DashboardCardPlacement] = []

                # Determine synchronized height class for row (HeightBalanceIntegrity)
                row_height = cls._resolve_row_height_class(cards_in_row)

                for c_item in cards_in_row:
                    topic = c_item["topic"]
                    span = c_item["column_span"]

                    # Assign spatial placement to topic object
                    placement = SpatialPlacement(
                        column_span=span,
                        height_class=row_height.value,
                        row_index=global_row_index,
                        row_id=row_id,
                        pattern=pattern,
                        section_id=sec_id,
                        order_index=global_order_index,
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
                    chart_type = getattr(topic, "recommended_visual", "") or topic.visual_spec.get("chart_type", "")
                    row_cards_placements.append(
                        DashboardCardPlacement(
                            topic_id=getattr(topic, "topic_id", f"T-{global_order_index}"),
                            title=getattr(topic, "title", f"Card {global_order_index}"),
                            chart_archetype=chart_type,
                            column_span=span,
                            height_class=row_height.value,
                            order_index=global_order_index,
                        )
                    )
                    global_order_index += 1

                # Check orphan integrity: single card with span < 10
                if len(cards_in_row) == 1 and total_span < 10:
                    orphan_count += 1

                sec_rows.append(
                    DashboardRowLayout(
                        row_id=row_id,
                        row_index=global_row_index,
                        pattern=pattern,
                        total_span=total_span,
                        utilization=utilization,
                        cards=row_cards_placements,
                    )
                )
                global_row_index += 1

            avg_sec_util = round(
                sum(r.utilization for r in sec_rows) / len(sec_rows) if sec_rows else 1.0, 3
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
                )
            )

        avg_total_util = round(
            sum(all_row_utilizations) / len(all_row_utilizations) if all_row_utilizations else 1.0, 3
        )

        # 3. Evaluate Spatial Layout Gates
        qa_results = cls._evaluate_spatial_gates(
            section_layouts=section_layouts,
            average_utilization=avg_total_util,
            orphan_count=orphan_count,
            topics=topics,
        )

        return DashboardLayoutPlan(
            sections=section_layouts,
            total_cards=len(topics),
            total_rows=global_row_index,
            average_row_utilization=avg_total_util,
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

        hero_idx = next(
            (i for i, t in enumerate(topics) if getattr(t, "slot_type", "") == "hero"), 0
        )
        hero = topics[hero_idx]
        remaining = [t for i, t in enumerate(topics) if i != hero_idx]

        priority_topics = [hero]
        diagnostic_topics = []
        supporting_topics = []

        # Find ideal companion for Priority:
        # High impact matrix heatmap, top ranking benchmark, or policy target
        priority_intents = {"TARGET_VS_ACTUAL", "MATRIX", "COMPOSITION", "RANKING"}
        diagnostic_intents = {"DISTRIBUTION", "RELATIONSHIP", "ANOMALY", "VARIANCE"}

        # We look for 1 or 2 high priority companions for the priority section
        # Best pairing is Heatmap (8) + Podium (4), or Heatmap + Target
        heatmap_topic = next(
            (t for t in remaining if (getattr(t, "recommended_visual", "") == "heatmap" or t.visual_spec.get("chart_type") == "heatmap")),
            None,
        )
        podium_topic = next(
            (t for t in remaining if (getattr(t, "recommended_visual", "") == "podium_top_3" or t.visual_spec.get("chart_type") == "podium_top_3")),
            None,
        )

        allocated: set[int] = set()

        if heatmap_topic:
            priority_topics.append(heatmap_topic)
            allocated.add(id(heatmap_topic))
            if podium_topic:
                priority_topics.append(podium_topic)
                allocated.add(id(podium_topic))

        # Distribute remaining
        for t in remaining:
            if id(t) in allocated:
                continue
            intent = getattr(t, "analytical_intent", "")
            chart = getattr(t, "recommended_visual", "") or t.visual_spec.get("chart_type", "")

            if (
                intent in diagnostic_intents
                or chart in ("scatter", "box_plot")
            ):
                diagnostic_topics.append(t)
            elif (
                len(priority_topics) < 3
                and (intent in priority_intents or t.layout_hint == "LARGE")
            ):
                priority_topics.append(t)
            else:
                supporting_topics.append(t)

        # Balance diagnostic vs supporting if diagnostic is empty
        if not diagnostic_topics and supporting_topics:
            half = max(1, len(supporting_topics) // 2)
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
                "subtitle": "Underlying statistical distributions, bivariate associations, and top benchmark performers.",
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
    # Internal Row Packing Algorithm
    # --------------------------------------------------------------------------

    @classmethod
    def _pack_section_into_rows(
        cls, topics: list[Any], is_priority_section: bool = False
    ) -> list[dict[str, Any]]:
        """Packs a list of topics into rows summing to 12 columns with >=85% row utilization."""
        if not topics:
            return []

        rows: list[dict[str, Any]] = []
        pool = list(topics)

        # If priority section, Topic 1 is Hero -> Always gets a dedicated full-width row (12)
        if is_priority_section and pool:
            hero = pool.pop(0)
            rows.append({
                "pattern": "12",
                "cards": [{"topic": hero, "column_span": 12}],
            })

        # Pack remaining items in pool
        while pool:
            n = len(pool)

            # Case 1: Exactly 1 card left -> Expand to span 12 (Zero orphan card empty space)
            if n == 1:
                card = pool.pop(0)
                rows.append({
                    "pattern": "12",
                    "cards": [{"topic": card, "column_span": 12}],
                })
                break

            # Case 2: Exactly 3 cards left and all are compact/standard -> 4 + 4 + 4
            if n == 3:
                charts = [
                    getattr(c, "recommended_visual", "") or c.visual_spec.get("chart_type", "")
                    for c in pool
                ]
                # If none is heatmap or wide ranking
                if not any(c in ("heatmap", "multi_series_trend") for c in charts):
                    c1, c2, c3 = pool.pop(0), pool.pop(0), pool.pop(0)
                    rows.append({
                        "pattern": "4+4+4",
                        "cards": [
                            {"topic": c1, "column_span": 4},
                            {"topic": c2, "column_span": 4},
                            {"topic": c3, "column_span": 4},
                        ],
                    })
                    break

            # Case 3: Pair 2 cards into a balanced 12-column row
            # Best pairing: Check best adjacency compatibility among first candidate pairs
            card_a = pool.pop(0)
            profile_a = get_spatial_profile(
                getattr(card_a, "recommended_visual", "") or card_a.visual_spec.get("chart_type", "")
            )

            # Find best companion in pool
            best_idx = 0
            best_score = -1.0
            for idx, cand in enumerate(pool):
                score = score_adjacency_compatibility(card_a, cand)
                if score > best_score:
                    best_score = score
                    best_idx = idx

            card_b = pool.pop(best_idx)
            profile_b = get_spatial_profile(
                getattr(card_b, "recommended_visual", "") or card_b.visual_spec.get("chart_type", "")
            )

            # Resolve column spans summing to 12
            span_a, span_b, pattern = cls._resolve_pair_spans(card_a, profile_a, card_b, profile_b)

            rows.append({
                "pattern": pattern,
                "cards": [
                    {"topic": card_a, "column_span": span_a},
                    {"topic": card_b, "column_span": span_b},
                ],
            })

        return rows

    @classmethod
    def _resolve_pair_spans(
        cls,
        card_a: Any,
        profile_a: VisualSpatialProfile,
        card_b: Any,
        profile_b: VisualSpatialProfile,
    ) -> tuple[int, int, str]:
        """Resolves optimal column spans summing to exactly 12 for two paired cards."""
        chart_a = profile_a.chart_archetype
        chart_b = profile_b.chart_archetype

        # 1. Asymmetric 8 + 4 focal pairing (e.g. Heatmap / Wide Ranking + Podium / Box Plot)
        if chart_a == "heatmap" and profile_b.min_col_span <= 4:
            return 8, 4, "8+4"
        if chart_b == "heatmap" and profile_a.min_col_span <= 4:
            return 4, 8, "4+8"

        if chart_a in ("ranking", "ranked_bar") and chart_b in ("podium_top_3", "box_plot", "lollipop"):
            return 8, 4, "8+4"
        if chart_b in ("ranking", "ranked_bar") and chart_a in ("podium_top_3", "box_plot", "lollipop"):
            return 4, 8, "4+8"

        # 2. Asymmetric 7 + 5 balance
        if profile_a.preferred_col_span >= 7 and profile_b.min_col_span <= 5:
            return 7, 5, "7+5"
        if profile_b.preferred_col_span >= 7 and profile_a.min_col_span <= 5:
            return 5, 7, "5+7"

        # 3. Default: Balanced 6 + 6
        return 6, 6, "6+6"

    @classmethod
    def _resolve_row_height_class(cls, cards_in_row: list[dict[str, Any]]) -> VisualHeightClass:
        """Enforces HeightBalanceIntegrity: all cards on the same row share a synchronized height class."""
        if not cards_in_row:
            return VisualHeightClass.STANDARD

        # If any card prefers TALL (e.g. Heatmap), the entire row becomes TALL so cards align cleanly
        for c in cards_in_row:
            chart = getattr(c["topic"], "recommended_visual", "") or c["topic"].visual_spec.get("chart_type", "")
            prof = get_spatial_profile(chart)
            if prof.preferred_height == VisualHeightClass.TALL:
                return VisualHeightClass.TALL

        # If all cards in row are SHORT (e.g. single bullet or compact KPI)
        if all(
            get_spatial_profile(
                getattr(c["topic"], "recommended_visual", "") or c["topic"].visual_spec.get("chart_type", "")
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
        orphan_count: int,
        topics: list[Any],
    ) -> dict[str, Any]:
        """Evaluates spatial integrity invariants:

        1. RowUtilizationIntegrity: average row utilization >= 85% (0.85)
        2. OrphanCardIntegrity: orphan count == 0
        3. PriorityAreaIntegrity: Hero visual has span 12 >= any supporting visual
        4. HeightBalanceIntegrity: all rows have uniform height across cards
        """
        passed = True
        failures = []

        # Gate 1: Row utilization >= 85%
        if average_utilization < 0.85:
            passed = False
            failures.append(f"RowUtilizationIntegrity failed: avg utilization {average_utilization:.2f} < 0.85")

        # Gate 2: Orphan cards
        if orphan_count > 0:
            passed = False
            failures.append(f"OrphanCardIntegrity failed: {orphan_count} orphan cards detected")

        # Gate 3: Priority Area
        hero_topic = topics[0] if topics else None
        if hero_topic:
            hero_span = getattr(hero_topic.spatial_placement, "column_span", 0) if hasattr(hero_topic, "spatial_placement") else 0
            if hero_span < 12 and len(topics) > 1:
                passed = False
                failures.append(f"PriorityAreaIntegrity failed: Hero span {hero_span} < 12")

        return {
            "passed": passed,
            "average_row_utilization": average_utilization,
            "orphan_cards_count": orphan_count,
            "failures": failures,
            "total_sections": len(section_layouts),
        }
