"""Spatial Composition Planner (Phase G5.6).

Authoritative engine for planning 12-column responsive dashboard layouts.
Guarantees:
- Semantically blind: strictly zero domain-specific branches or business concept inspection.
- Purely structural: derives placement from archetype profiles, content density, and readability envelopes.
- ExecutiveTopic and VisualSpec immutability: strictly zero in-place mutation of topics or visual specs.
- Multi-objective scoring: adjacency compatibility, morphology contrast, height balance, and row utilization.
"""
from __future__ import annotations

import logging
from typing import Any

from .contracts import (
    CompositionCandidate,
    CompositionItem,
    CompositionRow,
    CompositionSection,
    ContentDensityMetrics,
    DashboardLayoutPlan,
    VisualHeightClass,
    VisualLegibilityProfile,
)
from .candidate_builder import (
    analyze_content_density,
    get_legibility_profile,
)
from .integrity import (
    CompositionIntegrity,
    CompositionIntegrityError,
)

logger = logging.getLogger(__name__)


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
        frozenset({"ranked_bar", "lollipop"}): 0.30,
        frozenset({"ranked_bar", "dumbbell"}): 0.25,
        frozenset({"scatter", "box_plot"}): 0.30,
        frozenset({"100_percent_stacked_bar", "bullet"}): 0.25,
    }
    charts = frozenset({chart_a, chart_b})
    score += synergy_pairs.get(charts, 0.0)

    return round(score, 3)


class SpatialCompositionPlanner:
    """Plans balanced 12-column dashboard layouts without mutating ExecutiveTopic or VisualSpec."""

    @classmethod
    def plan_layout(
        cls,
        topics: list[Any],
        domain: str = "general",
        **kwargs: Any,
    ) -> DashboardLayoutPlan:
        """Generates an immutable DashboardLayoutPlan for the given topics.
        
        Semantically blind: domain and kwargs are ignored during layout derivation.
        """
        if not topics:
            return DashboardLayoutPlan(
                sections=[],
                items=[],
                items_by_topic_id={},
                total_cards=0,
                total_rows=0,
                average_row_utilization=1.0,
                utilization=1.0,
                average_readable_span_score=1.0,
                readability_violations_count=0,
                intentional_partial_rows_count=0,
                orphan_cards_count=0,
                qa_passed=True,
            )

        # 1. Take semantic fingerprints before layout to verify immutability
        initial_topic_fps = {
            getattr(t, "topic_id", id(t)): CompositionIntegrity.compute_topic_semantic_fingerprint(t)
            for t in topics
        }
        initial_visual_fps = {
            getattr(t, "topic_id", id(t)): CompositionIntegrity.compute_visual_semantic_fingerprint(
                getattr(t, "visual_spec", {}) or {}
            )
            for t in topics
        }

        # 2. Pre-compute legibility profiles and content density metrics
        metrics_map: dict[str, ContentDensityMetrics] = {}
        for t in topics:
            tid = str(getattr(t, "topic_id", "") or id(t))
            chart_t = getattr(t, "recommended_visual", "") or getattr(t, "visual_spec", {}).get("chart_type", "")
            prof = get_legibility_profile(chart_t)
            metrics_map[tid] = analyze_content_density(t, prof)

        # 3. Partition topics into structural decision sections
        sections_data = cls._partition_topics_into_sections(topics)

        section_layouts: list[CompositionSection] = []
        all_items: list[CompositionItem] = []
        items_by_topic_id: dict[str, CompositionItem] = {}

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

            sec_rows: list[CompositionRow] = []

            # 4. Pack section topics into readability-aware 12-column rows
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
                if is_partial and total_span >= 6:
                    intentional_partial_count += 1

                row_id = f"{sec_id}-r{len(sec_rows) + 1}"
                row_cards_placements: list[CompositionItem] = []

                # Determine synchronized height class for row (HeightBalanceIntegrity)
                row_height = cls._resolve_row_height_class(cards_in_row)
                row_readability_sum = 0.0

                current_col = 0
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

                    chart_type = getattr(topic, "recommended_visual", "") or getattr(topic, "visual_spec", {}).get("chart_type", "")
                    title = getattr(topic, "title", f"Card {global_order_index}")

                    # Construct immutable CompositionItem WITHOUT mutating the topic object
                    placement_item = CompositionItem(
                        topic_id=tid,
                        display_order=global_order_index,
                        row=global_row_index,
                        column=current_col,
                        span=span,
                        height=row_height.value,
                        pattern=pattern,
                        section_id=sec_id,
                        priority=global_order_index + 1,
                        layout_role="hero" if (global_order_index == 0 and sec_id == "priority") else "supporting",
                        readable_span_score=card_readability,
                        title=title,
                        chart_archetype=chart_type,
                    )
                    current_col += span

                    row_cards_placements.append(placement_item)
                    all_items.append(placement_item)
                    items_by_topic_id[tid] = placement_item
                    global_order_index += 1

                avg_row_readability = round(row_readability_sum / max(1, len(cards_in_row)), 2)
                all_readability_scores.append(avg_row_readability)

                # Orphan card check: single isolated card with span < 7 that wasn't intentional
                if not is_partial and len(cards_in_row) == 1 and total_span < 7:
                    orphan_count += 1

                sec_rows.append(
                    CompositionRow(
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
                CompositionSection(
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

        # 5. Evaluate Spatial Layout Gates
        qa_results = cls._evaluate_spatial_gates(
            section_layouts=section_layouts,
            average_utilization=avg_total_util,
            average_readability=avg_total_read,
            orphan_count=orphan_count,
            readability_violations=readability_violations,
            intentional_partials=intentional_partial_count,
            items_by_topic_id=items_by_topic_id,
            topics=topics,
        )

        plan = DashboardLayoutPlan(
            sections=section_layouts,
            items=all_items,
            items_by_topic_id=items_by_topic_id,
            column_count=12,
            row_count=global_row_index,
            total_cards=len(topics),
            total_rows=global_row_index,
            average_row_utilization=avg_total_util,
            utilization=avg_total_util,
            average_readable_span_score=avg_total_read,
            readability_violations_count=len(readability_violations),
            intentional_partial_rows_count=intentional_partial_count,
            orphan_cards_count=orphan_count,
            qa_passed=qa_results["passed"],
            qa_details=qa_results,
        )

        # 6. Verify topic and visual spec immutability
        for t in topics:
            tid = getattr(t, "topic_id", id(t))
            post_topic_fp = CompositionIntegrity.compute_topic_semantic_fingerprint(t)
            if post_topic_fp != initial_topic_fps[tid]:
                raise CompositionIntegrityError(
                    f"IMMUTABILITY_VIOLATION: ExecutiveTopic('{tid}') semantic fingerprint mutated during composition layout."
                )
            post_visual_fp = CompositionIntegrity.compute_visual_semantic_fingerprint(
                getattr(t, "visual_spec", {}) or {}
            )
            if post_visual_fp != initial_visual_fps[tid]:
                raise CompositionIntegrityError(
                    f"IMMUTABILITY_VIOLATION: VisualSpec for topic '{tid}' semantic fingerprint mutated during composition layout."
                )

        # 7. Validate grid boundaries and topic uniqueness
        CompositionIntegrity.assert_valid_plan(plan, topics)

        return plan

    @classmethod
    def optimize_layout(
        cls,
        topics: list[Any],
        domain: str = "general",
    ) -> DashboardLayoutPlan:
        """Backward-compatible facade method; domain parameter is ignored for semantic blindness."""
        return cls.plan_layout(topics)

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

        for t in remaining:
            if id(t) in allocated:
                continue
            intent = getattr(t, "analytical_intent", "")
            chart = getattr(t, "recommended_visual", "") or getattr(t, "visual_spec", {}).get("chart_type", "")

            if intent in diagnostic_intents or chart in ("scatter", "box_plot", "100_percent_stacked_bar", "variance_bar"):
                diagnostic_topics.append(t)
            elif chart in ("ranked_bar", "ranking", "horizontal_bar", "lollipop", "dumbbell"):
                supporting_topics.append(t)
            else:
                diagnostic_topics.append(t)

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

            # Case 1: Exactly 1 card left -> Right-size low density card to 6 rather than stretching to 12
            if n == 1:
                card = pool.pop(0)
                cid = str(getattr(card, "topic_id", "") or id(card))
                m_card = metrics_map.get(cid, ContentDensityMetrics())
                chart_t = getattr(card, "recommended_visual", "") or getattr(card, "visual_spec", {}).get("chart_type", "")
                prof = get_legibility_profile(chart_t)

                is_hero_card = getattr(card, "slot_type", "") == "hero"
                cats_len = len(getattr(card, "visual_spec", {}).get("categories", []))
                # Single low-density card (e.g. single boxplot, compact card, <= 4 categories) should be placed in a 6-column card
                if not is_hero_card and prof.max_useful_span <= 8 and (cats_len <= 6 or chart_t in ("box_plot", "boxplot", "dumbbell", "bullet")):
                    span = max(m_card.effective_min_span, min(6, prof.preferred_span))
                    rows.append({
                        "pattern": f"{span}",
                        "cards": [{"topic": card, "column_span": span}],
                        "is_intentional_partial": True,
                    })
                else:
                    rows.append({
                        "pattern": "12",
                        "cards": [{"topic": card, "column_span": 12}],
                        "is_intentional_partial": False,
                    })
                break

            # Case 2: Exactly 3 cards left
            if n == 3:
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

            # Case 3: Pair 2 cards into a balanced row
            card_a = pool.pop(0)
            cid_a = str(getattr(card_a, "topic_id", "") or id(card_a))
            m_a = metrics_map.get(cid_a, ContentDensityMetrics())
            prof_a = get_legibility_profile(
                getattr(card_a, "recommended_visual", "") or getattr(card_a, "visual_spec", {}).get("chart_type", "")
            )

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

        for c in cards_in_row:
            if getattr(c["topic"], "slot_type", "") == "hero" or getattr(c["topic"], "layout_hint", "") == "HERO":
                return VisualHeightClass.TALL
            chart = getattr(c["topic"], "recommended_visual", "") or getattr(c["topic"], "visual_spec", {}).get("chart_type", "")
            prof = get_legibility_profile(chart)
            if prof.preferred_height == VisualHeightClass.TALL:
                return VisualHeightClass.TALL

        if all(
            get_legibility_profile(
                getattr(c["topic"], "recommended_visual", "") or getattr(c["topic"], "visual_spec", {}).get("chart_type", "")
            ).preferred_height == VisualHeightClass.SHORT
            for c in cards_in_row
        ):
            return VisualHeightClass.SHORT

        return VisualHeightClass.STANDARD

    @classmethod
    def _evaluate_spatial_gates(
        cls,
        section_layouts: list[CompositionSection],
        average_utilization: float,
        average_readability: float,
        orphan_count: int,
        readability_violations: list[str],
        intentional_partials: int,
        items_by_topic_id: dict[str, CompositionItem],
        topics: list[Any],
    ) -> dict[str, Any]:
        """Evaluates spatial quality gates without touching topic object spatial placement."""
        passed = True
        failures = []

        if readability_violations:
            passed = False
            failures.append(f"ReadableSpanIntegrity failed: {len(readability_violations)} violations detected")

        if average_utilization < 0.85:
            passed = False
            failures.append(f"RowUtilizationIntegrity failed: avg utilization {average_utilization:.2f} < 0.85")

        if orphan_count > 0:
            passed = False
            failures.append(f"OrphanCardIntegrity failed: {orphan_count} orphan cards detected")

        hero_topic = next((t for t in topics if getattr(t, "slot_type", "") == "hero"), None)
        if not hero_topic and len(topics) >= 4:
            hero_topic = topics[0]
        if hero_topic:
            hero_tid = getattr(hero_topic, "topic_id", "")
            hero_item = items_by_topic_id.get(hero_tid)
            hero_span = hero_item.span if hero_item else 0
            if hero_span < 12 and len(topics) > 1:
                passed = False
                failures.append(f"PriorityAreaIntegrity failed: Hero span {hero_span} < 12")

        ranking_card_spans: dict[str, int] = {}
        for t in topics:
            chart = getattr(t, "recommended_visual", "") or getattr(t, "visual_spec", {}).get("chart_type", "")
            if chart in ("ranked_bar", "ranking", "horizontal_bar"):
                tid = getattr(t, "topic_id", "")
                item = items_by_topic_id.get(tid)
                if item:
                    ranking_card_spans[getattr(t, "title", "ranking")] = item.span

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
