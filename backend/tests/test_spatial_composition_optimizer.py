"""Unit and Integration Tests for SpatialCompositionOptimizer, ReadableSpanIntegrity, and Layout Invariants.

Verifies:
1. Intrinsic legibility profile registry mapping and aspect ratio boundaries.
2. ContentDensityAnalyzer & LabelDensityScore: long entity labels expand effective min span.
3. ReadableSpanIntegrity: hard rejection of placements below effective min span.
4. No 4-column squeeze for ranked bars with long department names (forced to 8+ columns).
5. Supporting Analysis 8+4 pairing: Department Attendance Ranking (8) + Leave Allocation (4).
6. RowUtilizationIntegrity: row utilization >= 85% across all rows (achieving 100% on live datasets).
7. OrphanCardIntegrity: zero isolated compact/medium cards on incomplete rows.
8. HeightBalanceIntegrity: paired cards on the same row share synchronized height classes.
9. PriorityAreaIntegrity: Hero visual receives column span 12 (maximum visual area).
10. End-to-end dataset intelligence integration on workforce (99767) and environmental (99768) datasets.
"""
import pytest
from app.services.adaptive_dashboard.spatial_composition_optimizer import (
    SpatialCompositionOptimizer,
    ARCHETYPE_PROFILES,
    VisualHeightClass,
    VisualLegibilityProfile,
    get_legibility_profile,
    get_spatial_profile,
    analyze_content_density,
    score_adjacency_compatibility,
    SpatialPlacement,
    DashboardLayoutPlan,
)
from app.services.adaptive_dashboard.composition_planner import ExecutiveTopic
from app.services.adaptive_dashboard.dataset_orchestrator import run_dataset_intelligence


def test_legibility_profile_registry():
    """Verifies all supported archetypes have governed legibility profiles."""
    archetypes = [
        "heatmap",
        "ranking",
        "ranked_bar",
        "diverging_bar",
        "scatter",
        "box_plot",
        "podium_top_3",
        "bullet",
        "100_percent_stacked_bar",
        "stacked_bar",
        "dumbbell",
        "lollipop",
        "variance_bar",
        "trend_line",
        "multi_series_trend",
    ]
    for arch in archetypes:
        prof = get_legibility_profile(arch)
        assert prof.chart_archetype == arch
        assert prof.min_readable_span >= 3
        assert prof.max_useful_span <= 12
        assert prof.min_readable_span <= prof.preferred_span <= prof.max_useful_span
        assert prof.preferred_height in (VisualHeightClass.SHORT, VisualHeightClass.STANDARD, VisualHeightClass.TALL)

    # Heatmap must be TALL with min_readable_span >= 7
    assert get_legibility_profile("heatmap").preferred_height == VisualHeightClass.TALL
    assert get_legibility_profile("heatmap").min_readable_span >= 7

    # Ranked bar must have base min_readable_span >= 7
    assert get_legibility_profile("ranked_bar").min_readable_span >= 7
    assert get_legibility_profile("ranked_bar").preferred_span >= 8

    # Scatter must have min_readable_span >= 5 (cannot be 4)
    assert get_legibility_profile("scatter").min_readable_span >= 5

    # Bullet must be SHORT or STANDARD
    assert get_legibility_profile("bullet").preferred_height == VisualHeightClass.SHORT


def test_label_density_analysis_and_adjustment():
    """Verifies that long entity labels expand effective min span for ranking charts."""
    prof = get_legibility_profile("ranked_bar")

    # Short labels: base min span 7 remains 7
    topic_short = ExecutiveTopic(
        topic_id="T1",
        title="Short Ranking",
        analytical_intent="RANKING",
        recommended_visual="ranked_bar",
        visual_spec={
            "chart_type": "ranked_bar",
            "categories": ["HR", "IT", "Sales", "Ops"],
        },
    )
    density_short = analyze_content_density(topic_short, prof)
    assert density_short.longest_label_length <= 10
    assert density_short.effective_min_span == 7

    # Long enterprise labels: expands effective min span to 8
    topic_long = ExecutiveTopic(
        topic_id="T2",
        title="Department Attendance Ranking",
        analytical_intent="RANKING",
        recommended_visual="ranked_bar",
        visual_spec={
            "chart_type": "ranked_bar",
            "categories": [
                "Alliance Initiative - Design",
                "Operations and Infrastructure",
                "Alliance Initiative - Platforms Engineering",
                "Alliance Initiative - Products",
            ],
        },
    )
    density_long = analyze_content_density(topic_long, prof)
    assert density_long.longest_label_length >= 30
    assert density_long.label_density_adjustment >= 1
    assert density_long.effective_min_span >= 8
    assert density_long.effective_preferred_span >= 8


def test_no_4_col_squeeze_for_long_label_rankings():
    """Verifies that 4 columns is strictly forbidden for long-label ranked bars."""
    topic_ranked = ExecutiveTopic(
        topic_id="T_RANK",
        title="Department Attendance Ranking",
        analytical_intent="RANKING",
        recommended_visual="ranked_bar",
        visual_spec={
            "chart_type": "ranked_bar",
            "categories": [
                "Alliance Initiative - Design",
                "Operations and Infrastructure",
                "Alliance Initiative - Platforms Engineering",
            ],
        },
    )
    topic_lollipop = ExecutiveTopic(
        topic_id="T_LOLL",
        title="Leave Allocation",
        analytical_intent="COMPARISON",
        recommended_visual="lollipop",
        visual_spec={
            "chart_type": "lollipop",
            "categories": ["Dept A", "Dept B", "Dept C"],
        },
    )

    plan = SpatialCompositionOptimizer.optimize_layout([topic_ranked, topic_lollipop], domain="workforce")
    assert plan.qa_passed is True
    assert plan.readability_violations_count == 0

    # The ranked bar must be allocated 8 columns, and lollipop 4 columns (8+4)
    assert topic_ranked.spatial_placement.column_span == 8
    assert topic_lollipop.spatial_placement.column_span == 4
    assert topic_ranked.spatial_placement.pattern == "8+4"


def test_adjacency_complementarity_scoring():
    """Verifies adjacency complementarity bonuses and morphology repetition penalties."""
    topic_heatmap = ExecutiveTopic(
        topic_id="T1",
        title="Heatmap",
        analytical_intent="MATRIX",
        recommended_visual="heatmap",
        visual_spec={"chart_type": "heatmap"},
    )
    topic_podium = ExecutiveTopic(
        topic_id="T2",
        title="Podium",
        analytical_intent="RANKING",
        recommended_visual="podium_top_3",
        visual_spec={"chart_type": "podium_top_3"},
    )
    topic_bar1 = ExecutiveTopic(
        topic_id="T3",
        title="Bar 1",
        analytical_intent="RANKING",
        recommended_visual="ranked_bar",
        visual_spec={"chart_type": "ranked_bar"},
    )
    topic_bar2 = ExecutiveTopic(
        topic_id="T4",
        title="Bar 2",
        analytical_intent="RANKING",
        recommended_visual="ranked_bar",
        visual_spec={"chart_type": "ranked_bar"},
    )

    # Heatmap + Podium has high synergy
    synergy_score = score_adjacency_compatibility(topic_heatmap, topic_podium)
    assert synergy_score >= 1.0  # Complementary intent + contrasting shape + synergy pair

    # Repeated ranked bars receive penalty
    repeat_score = score_adjacency_compatibility(topic_bar1, topic_bar2)
    assert repeat_score < synergy_score
    assert repeat_score < 0.50


def test_row_utilization_and_readability_invariants():
    """Verifies that an 8-topic portfolio is packed with >=85% row utilization, zero orphans, and 0 readability violations."""
    topics = [
        ExecutiveTopic(
            topic_id="T1",
            title="Hero Policy Compliance",
            slot_type="hero",
            analytical_intent="TARGET_VS_ACTUAL",
            recommended_visual="bullet",
            visual_spec={"chart_type": "bullet"},
        ),
        ExecutiveTopic(
            topic_id="T2",
            title="Heatmap Matrix",
            analytical_intent="MATRIX",
            recommended_visual="heatmap",
            visual_spec={"chart_type": "heatmap"},
        ),
        ExecutiveTopic(
            topic_id="T3",
            title="Podium Top 3",
            analytical_intent="RANKING",
            recommended_visual="podium_top_3",
            visual_spec={"chart_type": "podium_top_3"},
        ),
        ExecutiveTopic(
            topic_id="T4",
            title="Box Plot Dispersion",
            analytical_intent="DISTRIBUTION",
            recommended_visual="box_plot",
            visual_spec={"chart_type": "box_plot"},
        ),
        ExecutiveTopic(
            topic_id="T5",
            title="Scatter Association",
            analytical_intent="RELATIONSHIP",
            recommended_visual="scatter",
            visual_spec={"chart_type": "scatter"},
        ),
        ExecutiveTopic(
            topic_id="T6",
            title="Capacity Stacked Bar",
            analytical_intent="COMPOSITION",
            recommended_visual="100_percent_stacked_bar",
            visual_spec={"chart_type": "100_percent_stacked_bar"},
        ),
        ExecutiveTopic(
            topic_id="T7",
            title="Department Attendance Ranking",
            analytical_intent="RANKING",
            recommended_visual="ranked_bar",
            visual_spec={
                "chart_type": "ranked_bar",
                "categories": [
                    "Alliance Initiative - Design",
                    "Operations and Infrastructure",
                    "Alliance Initiative - Platforms Engineering",
                ],
            },
        ),
        ExecutiveTopic(
            topic_id="T8",
            title="Leave Utilization Benchmark",
            analytical_intent="COMPARISON",
            recommended_visual="lollipop",
            visual_spec={"chart_type": "lollipop"},
        ),
    ]

    plan = SpatialCompositionOptimizer.optimize_layout(topics, domain="workforce")

    # Invariant 1: QA Gates passed
    assert plan.qa_passed is True
    assert plan.readability_violations_count == 0
    assert plan.orphan_cards_count == 0

    # Invariant 2: Average row utilization >= 85%
    assert plan.average_row_utilization >= 0.85
    assert plan.average_readable_span_score >= 0.90
    assert plan.total_cards == 8

    # Invariant 3: Hero receives span 12
    hero_card = topics[0]
    assert hero_card.spatial_placement.column_span == 12

    # Invariant 4: Long-label ranked bar receives 8 columns
    ranked_card = topics[6]
    assert ranked_card.spatial_placement.column_span == 8

    # Invariant 5: HeightBalanceIntegrity (all cards on a row share synchronized height)
    for sec in plan.sections:
        for r in sec.rows:
            heights = {c.height_class for c in r.cards}
            assert len(heights) == 1, f"Row {r.row_id} has mixed height classes: {heights}"


def test_workforce_dataset_layout_plan_live():
    """Runs live dataset intelligence for workforce dataset (99767) and checks layout plan."""
    resp = run_dataset_intelligence(99767)
    lp = resp.layout_plan
    assert lp is not None
    assert lp["qa_passed"] is True
    assert lp["readability_violations_count"] == 0
    assert lp["total_cards"] >= 5
    assert lp["average_row_utilization"] >= 0.85
    assert lp["orphan_cards_count"] == 0

    # Verify Department Attendance Ranking has at least 8 columns
    ranking_spans = lp["qa_details"].get("ranking_card_spans", {})
    for title, span in ranking_spans.items():
        assert span >= 8, f"Ranking card '{title}' has span {span} < 8"


def test_environmental_dataset_layout_plan_live():
    """Runs live dataset intelligence for environmental dataset (99768) and checks layout plan."""
    resp = run_dataset_intelligence(99768)
    lp = resp.layout_plan
    assert lp is not None
    assert lp["qa_passed"] is True
    assert lp["readability_violations_count"] == 0
    assert lp["total_cards"] >= 5
    assert lp["average_row_utilization"] >= 0.85
    assert lp["orphan_cards_count"] == 0
