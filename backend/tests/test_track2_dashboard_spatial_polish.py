"""Product Track 2.3 — Spatial Polish, Responsive Geometry & Rendering Quality Tests.

Validates the Core Invariant:
"Verified meaning and verified representation must remain unchanged;
only spatial placement, responsive sizing, and rendering readability may improve."

Acceptance Gates:
1. ChartReadabilityProfile archetypes, aspect ratios, and spatial envelopes.
2. No semantic mutation: analytical truth, fact_id, evidence_ids, and titles invariant.
3. Hero row height dominance (VisualHeightClass.TALL).
4. Row height coherence: paired cards on the same row share synchronized height classes.
5. Partial row quality: span-6 isolated cards right-sized with is_intentional_partial.
6. Layout generation performance (< 10ms execution budget).
"""
import pytest
import time
from app.services.adaptive_dashboard.composition.contracts import (
    ARCHETYPE_PROFILES,
    VisualHeightClass,
    VisualLegibilityProfile,
    ChartReadabilityProfile,
)
from app.services.adaptive_dashboard.composition.candidate_builder import (
    get_legibility_profile,
    analyze_content_density,
)
from app.services.adaptive_dashboard.composition.planner import (
    SpatialCompositionPlanner,
    DashboardLayoutPlan,
)
from app.services.adaptive_dashboard.composition_planner import ExecutiveTopic


def test_track2_3_chart_readability_profiles_and_archetypes():
    """Verifies generic ChartReadabilityProfile morphology, aspect ratios, and envelopes."""
    # 1. Alias parity
    assert ChartReadabilityProfile is VisualLegibilityProfile

    # 2. Scatter archetype: near-square preference
    prof_scatter = get_legibility_profile("scatter")
    assert prof_scatter.min_width >= 260
    assert prof_scatter.min_height >= 250
    assert 1.0 <= prof_scatter.preferred_aspect_ratio <= 1.8
    assert prof_scatter.min_readable_span >= 5

    # 3. Heatmap archetype: grid-dimension-sensitive, tall height
    prof_heatmap = get_legibility_profile("heatmap")
    assert prof_heatmap.preferred_height == VisualHeightClass.TALL
    assert prof_heatmap.min_height >= 300
    assert prof_heatmap.min_readable_span >= 7
    assert prof_heatmap.preferred_span >= 8

    # 4. Ranked bar archetype: width-sensitive horizontal ranking
    prof_bar = get_legibility_profile("ranked_bar")
    assert prof_bar.min_readable_span >= 7
    assert prof_bar.preferred_span >= 8
    assert prof_bar.max_useful_span == 12

    # 5. Podium archetype: compact balanced area
    prof_podium = get_legibility_profile("podium_top_3")
    assert prof_podium.min_readable_span >= 3
    assert prof_podium.preferred_span <= 6
    assert prof_podium.preferred_aspect_ratio <= 1.5

    # 6. Boxplot archetype: moderate width distribution
    prof_box = get_legibility_profile("box_plot")
    assert prof_box.min_readable_span >= 4
    assert prof_box.preferred_span <= 8


def test_track2_3_hero_row_height_dominance():
    """Verifies that hero card rows resolve to VisualHeightClass.TALL for visual dominance."""
    hero_topic = ExecutiveTopic(
        topic_id="HERO_01",
        title="Which departments meet the attendance benchmark?",
        analytical_intent="TARGET_VS_ACTUAL",
        recommended_visual="bullet",
        slot_type="hero",
        layout_hint="HERO",
        visual_spec={
            "chart_type": "bullet",
            "categories": ["Ops", "IT", "HR"],
            "values": [16.2, 14.8, 15.5],
            "benchmark": 15.0,
        },
    )
    supporting_topic = ExecutiveTopic(
        topic_id="SUPP_01",
        title="How does attendance relate to approved leaves?",
        analytical_intent="RELATIONSHIP",
        recommended_visual="scatter",
        visual_spec={
            "chart_type": "scatter",
            "scatter_points": [{"x": 10, "y": 2}],
        },
    )

    plan = SpatialCompositionPlanner.plan_layout([hero_topic, supporting_topic])
    assert len(plan.sections) >= 1

    # Find the hero row
    priority_section = next((s for s in plan.sections if "Priority" in s.title), None)
    assert priority_section is not None
    hero_row = priority_section.rows[0]
    assert hero_row.pattern == "12"
    assert hero_row.height_class == VisualHeightClass.TALL
    assert hero_row.cards[0].column_span == 12


def test_track2_3_row_height_coherence_and_balance():
    """Verifies that all paired cards sharing a row in a layout plan share the exact same height class."""
    card_a = ExecutiveTopic(
        topic_id="PAIR_A",
        title="Which departments have the highest attendance?",
        analytical_intent="RANKING",
        recommended_visual="ranked_bar",
        visual_spec={"chart_type": "ranked_bar", "categories": ["A", "B", "C"], "values": [10, 20, 30]},
    )
    card_b = ExecutiveTopic(
        topic_id="PAIR_B",
        title="Which departments have the highest leave utilization?",
        analytical_intent="COMPARISON",
        recommended_visual="lollipop",
        visual_spec={"chart_type": "lollipop", "categories": ["A", "B", "C"], "values": [5, 8, 12]},
    )

    plan = SpatialCompositionPlanner.plan_layout([card_a, card_b])
    for section in plan.sections:
        for row in section.rows:
            if len(row.cards) > 1:
                # All cards in this row must share the row height class
                for c in row.cards:
                    assert c.height_class == row.height_class


def test_track2_3_partial_row_quality_and_tagging():
    """Verifies that single low-density isolated cards are right-sized to span 6 with is_intentional_partial."""
    boxplot_topic = ExecutiveTopic(
        topic_id="BOX_01",
        title="How do sales vary across store locations?",
        analytical_intent="DISTRIBUTION",
        recommended_visual="box_plot",
        visual_spec={
            "chart_type": "box_plot",
            "categories": ["Stores"],
            "box_data": [[5.0, 10.0, 15.0, 20.0, 25.0]],
        },
    )

    plan = SpatialCompositionPlanner.plan_layout([boxplot_topic])
    assert len(plan.sections) >= 1
    row = plan.sections[0].rows[0]
    # Single boxplot should not be stretched to 12
    assert row.cards[0].column_span <= 8
    assert row.is_intentional_partial is True


def test_track2_3_no_semantic_mutation_invariant():
    """Verifies that Track 2.3 preserves all analytical facts, evidence IDs, and semantic titles."""
    topic = ExecutiveTopic(
        topic_id="SEM_01",
        evidence_ids=["ev_record_99770_01", "ev_record_99770_02"],
        title="Which departments meet the hybrid attendance target?",
        technical_title="Workforce Attendance vs Governed Policy Benchmark",
        primary_takeaway="Core operational departments meet or exceed the hybrid attendance benchmark.",
        analytical_intent="TARGET_VS_ACTUAL",
        recommended_visual="bullet",
        key_metric="15d Target",
        inspect_payload={"fact_id": "fact_attendance_benchmark_001", "leader": "Operations", "val": 17.2},
        visual_spec={
            "chart_type": "bullet",
            "categories": ["Operations", "IT"],
            "values": [17.2, 14.1],
            "benchmark": 15.0,
            "x_label": "Attendance Days",
            "y_label": "Department",
        },
    )

    # Capture semantics before layout planning
    orig_evidence = list(topic.evidence_ids)
    orig_title = topic.title
    orig_tech_title = topic.technical_title
    orig_takeaway = topic.primary_takeaway
    orig_metric = topic.key_metric
    orig_payload = dict(topic.inspect_payload)
    orig_chart = topic.visual_spec["chart_type"]
    orig_x = topic.visual_spec["x_label"]
    orig_y = topic.visual_spec["y_label"]

    # Execute spatial layout
    plan = SpatialCompositionPlanner.plan_layout([topic])

    # Assert 100% semantic preservation
    assert topic.evidence_ids == orig_evidence
    assert topic.title == orig_title
    assert topic.technical_title == orig_tech_title
    assert topic.primary_takeaway == orig_takeaway
    assert topic.key_metric == orig_metric
    assert topic.inspect_payload == orig_payload
    assert topic.visual_spec["chart_type"] == orig_chart
    assert topic.visual_spec["x_label"] == orig_x
    assert topic.visual_spec["y_label"] == orig_y


def test_track2_3_layout_plan_generation_performance():
    """Verifies that layout plan generation completes in < 10ms for benchmark dashboard topic sets."""
    topics = [
        ExecutiveTopic(topic_id=f"T_{i}", title=f"Question {i}?", analytical_intent="RANKING", recommended_visual="ranked_bar", visual_spec={"chart_type": "ranked_bar", "categories": ["A", "B"], "values": [1, 2]})
        for i in range(8)
    ]
    topics[0].slot_type = "hero"
    topics[0].layout_hint = "HERO"

    t0 = time.perf_counter()
    for _ in range(10):
        SpatialCompositionPlanner.plan_layout(topics)
    elapsed_ms = (time.perf_counter() - t0) * 1000 / 10.0

    # Must be sub-10ms (typical is 0.5 - 2.0ms)
    assert elapsed_ms < 10.0
