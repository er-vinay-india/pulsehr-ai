"""Tests for Visual Presence, Title Compression, and Semantic Redundancy Gates."""
from app.services.adaptive_dashboard.visual_presence_gates import (
    ExecutiveTitleCompressionIntegrity,
    VisualDataPresenceIntegrity,
    VisualStoryRedundancyIntegrity,
)


def test_executive_title_compression_converts_raw_queries():
    # Case 1: Early-July Leave Concentration
    raw1 = "Leaves (1st To 5th July) by Department: Corporate Functions vs Alliance Initiative"
    res1 = ExecutiveTitleCompressionIntegrity.compress_title(
        raw_title=raw1,
        primary_measure="Leaves (1st To 5th July)",
        primary_dimension="Department",
        top_cohort="Corporate Functions",
        bottom_cohort="Alliance Initiative - Design",
        spread=10.2,
    )
    assert res1.compressed_title == "Early-July Leave Concentration"
    assert "Corp Functions ↑" in res1.annotation_subtitle
    assert "Spread: 10.2" in res1.annotation_subtitle
    assert res1.raw_analytical_question == raw1

    # Case 2: Mid-July Attendance Gap
    raw2 = "6th To 12th July by Department: Operations and Infrastructure vs Alliance Initiative - Design"
    res2 = ExecutiveTitleCompressionIntegrity.compress_title(
        raw_title=raw2,
        primary_measure="6th To 12th July",
        primary_dimension="Department",
        top_cohort="Operations & Infra",
        bottom_cohort="Alliance Initiative - Design",
        spread=8.5,
    )
    assert res2.compressed_title == "Mid-July Attendance Gap"
    assert "Design ↓" in res2.annotation_subtitle
    assert "Operations & Infra ↑" in res2.annotation_subtitle


def test_visual_data_presence_gate():
    # Empty spec
    audit1 = VisualDataPresenceIntegrity.evaluate({})
    assert not audit1.is_valid
    assert audit1.rendered_mark_count == 0
    assert "INSUFFICIENT_RENDERABLE_DATA" in audit1.suppression_reason

    # All-zero values
    audit2 = VisualDataPresenceIntegrity.evaluate({
        "chart_type": "ranked_bar",
        "values": [0.0, 0, None],
        "categories": ["A", "B", "C"],
    })
    assert not audit2.is_valid
    assert audit2.rendered_mark_count == 0

    # Multi-series with empty values
    audit3 = VisualDataPresenceIntegrity.evaluate({
        "chart_type": "100_percent_stacked_bar",
        "series": [
            {"name": "Series 1", "values": []},
            {"name": "Series 2", "values": [0, 0]},
        ],
    })
    assert not audit3.is_valid

    # Valid ranked bar
    audit4 = VisualDataPresenceIntegrity.evaluate({
        "chart_type": "ranked_bar",
        "values": [18.2, 17.1, 15.4, 13.5, 8.2],
        "categories": ["Ops", "Eng", "NRP", "Corp", "Design"],
    })
    assert audit4.is_valid
    assert audit4.rendered_mark_count == 5
    assert audit4.renderable_series_count == 1

    # Valid stacked bar
    audit5 = VisualDataPresenceIntegrity.evaluate({
        "chart_type": "100_percent_stacked_bar",
        "series": [
            {"name": "Presence", "values": [113, 169, 135]},
            {"name": "Leave", "values": [4, 12, 9]},
            {"name": "Gap", "values": [43, 0, 16]},
        ],
    })
    assert audit5.is_valid
    assert audit5.rendered_mark_count == 9
    assert audit5.renderable_series_count == 3


def test_visual_story_redundancy_gate():
    hero = {
        "title": "Department Attendance Ranking & Policy Benchmark",
        "metric_family": "department_ranking",
        "analytical_intent": "RANKING",
        "primary_measure": "attendance_days",
        "dimensions": ["Operations", "Design"],
        "recommended_visual": "ranked_bar",
    }
    hero_fp = VisualStoryRedundancyIntegrity.fingerprint(hero)

    # Valid supporting topic: Capacity composition
    recon = {
        "title": "Weekly Workforce Capacity Distribution",
        "metric_family": "reconciliation",
        "analytical_intent": "COMPOSITION",
        "primary_measure": "capacity",
        "dimensions": ["Presence", "Leave", "Gap"],
        "recommended_visual": "100_percent_stacked_bar",
    }
    recon_fp = VisualStoryRedundancyIntegrity.fingerprint(recon)

    is_dup, reason = VisualStoryRedundancyIntegrity.should_suppress_supporting(hero_fp, recon_fp)
    assert not is_dup, f"Recon should not be duplicate of Hero ranking: {reason}"

    # Redundant candidate: Another department ranking
    duplicate_hero = {
        "title": "Department Presence Ranking",
        "metric_family": "department_ranking",
        "analytical_intent": "RANKING",
        "primary_measure": "attendance_days",
        "dimensions": ["Operations", "Design"],
        "recommended_visual": "ranked_bar",
    }
    dup_fp = VisualStoryRedundancyIntegrity.fingerprint(duplicate_hero)

    is_dup2, reason2 = VisualStoryRedundancyIntegrity.should_suppress_supporting(hero_fp, dup_fp)
    assert is_dup2
    assert "SUPPRESS_DUPLICATE" in reason2
