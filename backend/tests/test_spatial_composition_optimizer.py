"""Unit and Integration Tests for SpatialCompositionOptimizer and Layout Invariants.

Verifies:
1. Intrinsic profile registry mapping and aspect ratio boundaries.
2. RowUtilizationIntegrity: row utilization >= 85% across all rows.
3. OrphanCardIntegrity: zero isolated compact/medium cards on incomplete rows.
4. HeightBalanceIntegrity: paired cards on the same row share synchronized height classes.
5. PriorityAreaIntegrity: Hero visual receives column span 12 (maximum visual area).
6. AdjacencyIntegrity: complementary pairings and morphology contrast bonuses.
7. End-to-end dataset intelligence integration on workforce (99767) and environmental (99768) datasets.
"""
import pytest
from app.services.adaptive_dashboard.spatial_composition_optimizer import (
    SpatialCompositionOptimizer,
    ARCHETYPE_PROFILES,
    VisualHeightClass,
    get_spatial_profile,
    score_adjacency_compatibility,
    SpatialPlacement,
    DashboardLayoutPlan,
)
from app.services.adaptive_dashboard.composition_planner import ExecutiveTopic
from app.services.adaptive_dashboard.dataset_orchestrator import run_dataset_intelligence


def test_spatial_profile_registry():
    """Verifies all supported archetypes have governed spatial profiles."""
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
        prof = get_spatial_profile(arch)
        assert prof.chart_archetype == arch
        assert prof.min_col_span >= 3
        assert prof.max_col_span <= 12
        assert prof.min_col_span <= prof.preferred_col_span <= prof.max_col_span
        assert prof.preferred_height in (VisualHeightClass.SHORT, VisualHeightClass.STANDARD, VisualHeightClass.TALL)

    # Heatmap must be TALL
    assert get_spatial_profile("heatmap").preferred_height == VisualHeightClass.TALL
    assert get_spatial_profile("heatmap").min_col_span >= 7

    # Bullet must be SHORT or STANDARD
    assert get_spatial_profile("bullet").preferred_height == VisualHeightClass.SHORT


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


def test_row_utilization_and_orphan_integrity():
    """Verifies that an 8-topic portfolio is packed with >=85% row utilization and zero orphans."""
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
            title="Department Benchmarking",
            analytical_intent="COMPARISON",
            recommended_visual="lollipop",
            visual_spec={"chart_type": "lollipop"},
        ),
        ExecutiveTopic(
            topic_id="T8",
            title="Variance Anomaly",
            analytical_intent="ANOMALY",
            recommended_visual="variance_bar",
            visual_spec={"chart_type": "variance_bar"},
        ),
    ]

    plan = SpatialCompositionOptimizer.optimize_layout(topics, domain="workforce")

    # Invariant 1: QA Gates passed
    assert plan.qa_passed is True
    assert plan.orphan_cards_count == 0

    # Invariant 2: Average row utilization >= 85% (in practice, 100%)
    assert plan.average_row_utilization >= 0.85
    assert plan.total_cards == 8

    # Invariant 3: Hero receives span 12
    hero_card = topics[0]
    assert hero_card.spatial_placement.column_span == 12

    # Invariant 4: Every row achieves >= 10 columns out of 12
    for sec in plan.sections:
        for r in sec.rows:
            assert r.total_span >= 10, f"Row {r.row_id} has total span {r.total_span} < 10"
            assert r.utilization >= 0.85

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
    assert lp["total_cards"] >= 5
    assert lp["average_row_utilization"] >= 0.85
    assert lp["orphan_cards_count"] == 0

    # Check sections exist
    section_ids = [s["section_id"] for s in lp["sections"]]
    assert "priority" in section_ids
    assert "diagnostic" in section_ids


def test_environmental_dataset_layout_plan_live():
    """Runs live dataset intelligence for environmental dataset (99768) and checks layout plan."""
    resp = run_dataset_intelligence(99768)
    lp = resp.layout_plan
    assert lp is not None
    assert lp["qa_passed"] is True
    assert lp["total_cards"] >= 5
    assert lp["average_row_utilization"] >= 0.85
    assert lp["orphan_cards_count"] == 0
