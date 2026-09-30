"""Tests for SpatialOverflowMonitor AI Service & Layout Geometry Engine.

Layman explanation:
These unit tests verify that our Spatial Overflow Guardian AI successfully:
1. GEOMETRY MEASUREMENT: Accurately calculates pixel consumption on a 16:9 widescreen canvas (1920x1080).
2. TABLE PAGINATION: Automatically paginates dynamic data tables with > 6 rows across Part 1 and Part 2
   without losing column headers or truncating data.
3. SLIDE SPLITTING: Splits content-heavy slides into Part 1 (Core Insight & Visual) and Part 2 (Action Plan).
4. LOGICAL CONTINUITY: Preserves the same logical_slide_id across continuation slides.
5. CHART CONSOLIDATION: Keeps Top 5 categories and groups remainder into 'Other (N items)'.
6. EXECUTIVE TEXT CONDENSATION: Removes wordy filler phrases while guaranteeing that 100% of
   empirical figures, currency amounts, and percentages remain intact.
7. DECK-WIDE AUDIT: Automatically remediates an entire deck and re-indexes all slide numbers.
"""

import pytest
from app.services.presentation.spatial_overflow_monitor import (
    SpatialOverflowMonitor,
    MAX_CHART_CATEGORIES,
    MAX_BULLETS_PER_SLIDE,
    MAX_BULLETS_WITH_CHART,
    MAX_TABLE_ROWS,
    USABLE_CONTENT_HEIGHT_PX
)


def test_measure_slide_geometry_clean_slide():
    """Verify that a properly sized slide fits comfortably within the vertical pixel budget."""
    clean_slide = {
        "id": "s_clean",
        "order": 1,
        "layout": "chart_narrative",
        "title": "Executive Summary & Core Performance",
        "subtitle": "Quarterly Operational Metrics",
        "narrative": "Weekly sales averaged $28,450 across 100 audited store locations.",
        "bullets": [
            "Store 14 led the region with $34,200 peak throughput.",
            "Top 5 units accounted for 31.4% of total recorded revenue."
        ],
        "chart": {
            "categories": ["Store 1", "Store 2", "Store 3"],
            "series": [{"name": "Sales", "values": [300, 250, 200]}]
        }
    }
    geometry = SpatialOverflowMonitor.measure_slide_geometry(clean_slide)

    assert geometry["is_overflowing"] is False
    assert geometry["overflow_px"] == 0
    assert geometry["remaining_height_px"] > 0
    assert geometry["consumed_height_px"] <= USABLE_CONTENT_HEIGHT_PX
    assert geometry["recommended_strategy"] == "none"
    assert len(geometry["culprit_elements"]) == 0


def test_measure_slide_geometry_overflow_with_bullets():
    """Verify that placing 5 long bullets beside a visual chart triggers spatial overflow detection."""
    overloaded_slide = {
        "id": "s_bullets_overflow",
        "order": 2,
        "layout": "chart_narrative",
        "title": "Throughput Dispersion Across Regional Branches",
        "subtitle": "Operating variance and performance spread",
        "narrative": "A detailed diagnostic reflects performance variances between top and bottom quartiles.",
        "bullets": [
            "Branch 101 exceeded regional benchmark targets by 18.4% during peak morning cycles.",
            "Branch 104 maintained stable gross margins at 24.2% across audited transaction records.",
            "Branch 109 encountered delivery logistics bottlenecks resulting in an 8.6% delay rate.",
            "Branch 112 requires immediate inventory re-allocation within the next 14 operating days.",
            "Branch 115 completed all safety and compliance certifications with zero recorded incidents."
        ],
        "chart": {
            "categories": ["Store A", "Store B"],
            "series": [{"name": "Volume", "values": [100, 200]}]
        }
    }
    geometry = SpatialOverflowMonitor.measure_slide_geometry(overloaded_slide)

    assert geometry["is_overflowing"] is True
    assert geometry["overflow_px"] > 0
    assert any("bullets" in culprit for culprit in geometry["culprit_elements"])
    assert geometry["recommended_strategy"] == "split_slide"


def test_measure_slide_geometry_table_overflow():
    """Verify that an empirical data table with 10 rows triggers deterministic table pagination."""
    table_slide = {
        "id": "s_table",
        "order": 5,
        "layout": "table_detail",
        "title": "Department Performance & Headcount Breakdown",
        "subtitle": "Audited Evidence Ledger",
        "narrative": "Comprehensive breakdown of verified headcount across operating units.",
        "table": {
            "headers": ["Department", "Headcount", "Turnover", "Status"],
            "rows": [
                [f"Dept {i}", f"{50 + i * 10}", f"{4.2 + i * 0.5}%", "Audited"]
                for i in range(1, 11)  # 10 rows
            ]
        }
    }
    geometry = SpatialOverflowMonitor.measure_slide_geometry(table_slide)

    assert geometry["recommended_strategy"] == "paginate_table"
    assert any("table" in culprit for culprit in geometry["culprit_elements"])


def test_paginate_table_slide():
    """Verify deterministic table pagination splits 10 rows into Part 1 (rows 1-6) and Part 2 (rows 7-10)."""
    orig_table_slide = {
        "id": "s_table_deep",
        "order": 6,
        "layout": "table_detail",
        "title": "Operational Unit Evidence Ledger",
        "subtitle": "Full categorical evaluation",
        "narrative": "Empirical audit across all 10 evaluated regional divisions.",
        "table": {
            "headers": ["Division", "Records", "Percentage", "Audit Status"],
            "rows": [
                [f"Division {chr(65 + i)}", f"{1000 + i * 150:,}", f"{10.0 + i * 1.5}%", "Verified"]
                for i in range(10)  # 10 rows
            ]
        }
    }
    part1, part2 = SpatialOverflowMonitor.paginate_table_slide(orig_table_slide, next_order=7, max_rows=6)

    # 1. Row distribution
    assert len(part1["table"]["rows"]) == 6
    assert len(part2["table"]["rows"]) == 4

    # 2. Header preservation
    assert part1["table"]["headers"] == orig_table_slide["table"]["headers"]
    assert part2["table"]["headers"] == orig_table_slide["table"]["headers"]

    # 3. Titles and parts
    assert "Part 1" in part1["title"]
    assert "Part 2" in part2["title"]
    assert part1["is_split_part"] == 1
    assert part2["is_split_part"] == 2

    # 4. Logical slide ID link
    assert part1["logical_slide_id"] == "s_table_deep"
    assert part2["logical_slide_id"] == "s_table_deep"

    # 5. Order sequencing
    assert part1["order"] == 6
    assert part2["order"] == 7

    # 6. Speaker note coordination
    assert "[Speaker Note:" in part1["speaker_notes"]
    assert "Continuing audited data records" in part2["speaker_notes"]


def test_split_flooded_slide_preserves_logical_slide_id():
    """Verify autonomous slide splitting preserves logical slide identity and distributes bullets."""
    orig_slide = {
        "id": "s_initiatives",
        "order": 4,
        "layout": "chart_narrative",
        "title": "Throughput Optimization & Strategic Interventions",
        "subtitle": "Targeting productivity variance",
        "narrative": "Detailed analysis indicates opportunities to accelerate top-line throughput.",
        "bullets": [
            "Point 1: Consolidate distribution logistics in Region North.",
            "Point 2: Re-balance shift rosters to reduce overtime strain by 12.5%.",
            "Point 3: Introduce standardized inventory replenishment playbooks.",
            "Point 4: Establish weekly cross-departmental alignment cadence.",
            "Point 5: Track SLA compliance through real-time telemetry."
        ],
        "chart": {
            "categories": ["Region A", "Region B"],
            "series": [{"name": "Capacity", "values": [120, 85]}]
        }
    }
    part1, part2 = SpatialOverflowMonitor.split_flooded_slide(orig_slide, next_order=5)

    assert part1["logical_slide_id"] == "s_initiatives"
    assert part2["logical_slide_id"] == "s_initiatives"
    assert "Part 1" in part1["title"]
    assert "Part 2" in part2["title"]

    # Bullets cleanly distributed: 3 on Part 1, 2 on Part 2
    assert len(part1["bullets"]) == 3
    assert len(part2["bullets"]) == 2
    assert "Point 1" in part1["bullets"][0]
    assert "Point 4" in part2["bullets"][0]

    # Visual chart kept on Part 1, Part 2 is clean action focus
    assert "chart" in part1
    assert "chart" not in part2


def test_consolidate_chart_categories_preserves_totals():
    """Verify charts with > 5 categories group into Top 5 + 'Other' without altering data sums."""
    large_chart = {
        "chart_type": "bar",
        "title": "Department Headcount Distribution",
        "categories": [f"Dept {i}" for i in range(1, 10)],  # 9 categories
        "series": [
            {"name": "Staff", "values": [120, 110, 95, 80, 70, 45, 30, 20, 15]}
        ]
    }
    consolidated = SpatialOverflowMonitor.consolidate_chart_categories(large_chart, max_categories=5)

    # 5 top categories + 1 Other = 6 categories total
    assert len(consolidated["categories"]) == 6
    assert "Other (4 items)" in consolidated["categories"][-1]
    assert len(consolidated["series"][0]["values"]) == 6

    # Verify arithmetic sum of values is preserved exactly
    orig_sum = sum(large_chart["series"][0]["values"])
    new_sum = sum(consolidated["series"][0]["values"])
    assert orig_sum == new_sum


def test_condense_text_preserves_numbers_and_symbols():
    """Verify executive text tightening strips filler phrases while strictly preserving empirical numbers."""
    wordy_text = (
        "It is important to note that a detailed review indicates that Store 14 "
        "generated $48,500 in peak volume with an impressive 14.2% surge and a 2.4x margin spread."
    )
    condensed = SpatialOverflowMonitor.condense_text(wordy_text, max_chars=130)

    # Check filler words removed
    assert "It is important to note" not in condensed
    assert "a detailed review indicates" not in condensed

    # Check numbers, currency, and percentages guaranteed intact
    assert "$48,500" in condensed
    assert "14.2%" in condensed
    assert "2.4x" in condensed
    assert len(condensed) <= 130


def test_audit_and_remedy_deck_table_pagination_and_splitting():
    """Verify end-to-end deck remediation handles both table pagination and bullet splitting."""
    deck_spec = {
        "id": "deck_executive_review",
        "metadata": {"title": "Strategic Review", "total_slides": 3},
        "slides": [
            {
                "id": "slide_1",
                "order": 1,
                "layout": "title_hero",
                "title": "Executive Summary",
                "narrative": "Annual review of operational performance.",
                "bullets": ["Record baseline established.", "Key metrics verified."]
            },
            {
                "id": "slide_2",
                "order": 2,
                "layout": "table_detail",
                "title": "Division Performance Ledger",
                "narrative": "Verified division performance data.",
                "table": {
                    "headers": ["Division", "Headcount", "Variance"],
                    "rows": [
                        [f"Division {i}", f"{100 + i * 20}", f"+{i * 1.2}%"]
                        for i in range(1, 11)  # 10 rows -> needs table pagination!
                    ]
                }
            },
            {
                "id": "slide_3",
                "order": 3,
                "layout": "chart_narrative",
                "title": "Operational Headwinds & Dispersion",
                "narrative": "Analysis reflects performance spread between leaders and laggards.",
                "bullets": [
                    "Finding 1: Unit throughput showed wide spread.",
                    "Finding 2: Overtime hours concentrated in 3 branches.",
                    "Finding 3: Attendance variance triggered 6.4% delays.",
                    "Finding 4: Training completion rate lagged in branch 8.",
                    "Finding 5: Corrective action plan initiated immediately."
                ],
                "chart": {
                    "categories": ["A", "B"],
                    "series": [{"name": "Metric", "values": [10, 20]}]
                }
            }
        ]
    }
    remedied_deck = SpatialOverflowMonitor.audit_and_remedy_deck(deck_spec)

    # Initial deck: 3 slides
    # Slide 2 (10-row table) was paginated into 2 slides (+1)
    # Slide 3 (5 bullets beside chart) was split into 2 slides (+1)
    # Total slides should now be 5!
    slides = remedied_deck["slides"]
    assert len(slides) == 5
    assert remedied_deck["metadata"]["total_slides"] == 5

    summary = remedied_deck["spatial_remediation_summary"]
    assert summary["tables_paginated"] == 1
    assert summary["slides_split"] == 1

    # Verify orders are 1, 2, 3, 4, 5
    orders = [s["order"] for s in slides]
    assert orders == [1, 2, 3, 4, 5]

    # Verify total_slides property is synchronized on all slides
    for s in slides:
        assert s["total_slides"] == 5
