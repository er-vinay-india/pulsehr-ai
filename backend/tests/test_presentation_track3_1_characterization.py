"""Track 3.1 Characterization Tests for HighView Presentation Studio.

These tests capture and freeze the baseline behavior, contract boundaries,
and failure modes identified during the Product Track 3.1 audit:
1. Contract bypass: Presentation Studio currently operates independently of the
   upstream frozen ExecutiveTopic and VisualSpec contracts.
2. Dual routing: Datasets with attendance aliases route to bespoke hr_attendance_v1,
   bypassing AI models, while other datasets route to AI Director / recorded_results_v1.
3. Overflow pagination: Tables paginate across physical pages without row loss.
4. Long title failure: Unbudgeted title length causes SlideLayoutError in geometry resolution.
"""

import pytest
from app.db.database import get_connection
from app.services.presentation.slide_layout import resolve_slide, SlideLayoutError
from app.services.presentation.hr_report import build_hr_report
from app.services.presentation.grounded_review import build_grounded_review


def test_presentation_bypasses_upstream_executive_topic_and_visual_spec():
    """Characterization test: Presentation Studio deck specs do not ingest or preserve
    the upstream ExecutiveTopic identity, topic_id, evidence_ids, or VisualSpec hashes.
    """
    records = [
        {"Emp ID": "001", "Department": "Design", "1st to 5th July 2026": 0, "6th to 12th July 2026": 3,
         "Total Attendance": 3, "Approved Leaves": 2, "Final Attendance": 1},
        {"Emp ID": "002", "Department": "Operations", "1st to 5th July 2026": 2, "6th to 12th July 2026": 4,
         "Total Attendance": 6, "Approved Leaves": 1, "Final Attendance": 5},
    ]
    ctx = {
        "records": records,
        "columns": list(records[0]),
        "target_sheet": {"name": "July WFO", "original_name": "attendance.xlsx"},
        "snapshot_hash": "fixture_hash",
        "domain": "workforce"
    }
    deck = build_hr_report({}, ctx)
    assert deck is not None
    meta = deck.get("metadata", {})
    slides = deck.get("slides", [])

    # Upstream ExecutiveTopic fields must be absent in baseline presentation cards
    # (proving the architectural finding that Presentation Studio is uncoupled from Track 2)
    assert meta.get("content_contract") == "hr_attendance_v1"
    for s in slides:
        assert "topic_id" not in s
        assert "canonical_topic_hash" not in s


def test_workforce_routes_to_bespoke_hr_attendance_v1():
    """Characterization test: Workforce datasets with attendance aliases route
    to the bespoke hr_attendance_v1 builder without invoking AI models.
    """
    records = [
        {"Emp ID": "001", "Department": "Design", "1st to 5th July 2026": 0, "6th to 12th July 2026": 3,
         "Total Attendance": 3, "Approved Leaves": 2, "Final Attendance": 1},
    ]
    ctx = {
        "records": records,
        "columns": list(records[0]),
        "target_sheet": {"name": "July WFO", "original_name": "attendance.xlsx"},
        "snapshot_hash": "fixture_hash",
        "domain": "workforce"
    }
    deck = build_hr_report({}, ctx)
    assert deck is not None
    assert deck["metadata"]["content_contract"] == "hr_attendance_v1"
    assert len(deck["slides"]) >= 8
    assert deck["slides"][0]["title"] == "Office attendance review"
    assert deck["slides"][1]["title"] == "Attendance at a glance"


def test_retail_falls_back_to_recorded_results_v1():
    """Characterization test: Datasets without attendance aliases fall back to build_grounded_review
    generating column-by-column 'at a glance' cards when forced to deterministic builder.
    """
    records = [
        {"Store": 1, "Weekly_Sales": 24924.50, "Date": "2026-02-05", "Holiday_Flag": 0},
        {"Store": 1, "Weekly_Sales": 46039.49, "Date": "2026-02-12", "Holiday_Flag": 1},
    ]
    ctx = {
        "records": records,
        "columns": list(records[0]),
        "target_sheet": {"name": "Store Sales", "original_name": "retail.csv"},
        "snapshot_hash": "fixture_hash",
        "domain": "retail"
    }
    deck = build_grounded_review({}, ctx)
    assert deck is not None
    assert deck["metadata"]["content_contract"] == "recorded_results_v1"
    assert len(deck["slides"]) >= 7
    assert deck["slides"][0]["title"] == "Review of recorded results"
    slide_titles = [s["title"] for s in deck["slides"]]
    assert any("Store" in t for t in slide_titles)
    assert any("Weekly_Sales" in t for t in slide_titles)


def test_table_pagination_preserves_all_rows_across_pages():
    """Characterization test: A 25-row table paginates into multiple physical pages

    without truncating or dropping rows.
    """
    slide_table_25 = {
        "layout": "table_detail",
        "category": "Data Audit",
        "title": "Operational Headcount Distribution",
        "table": {
            "headers": ["Department", "Headcount", "Attendance Rate", "Variance"],
            "rows": [[f"Dept {i}", f"{100+i}", f"{90+i%5}%", f"{i%3}.2%"] for i in range(25)]
        }
    }
    res = resolve_slide(slide_table_25)
    assert res is not None
    assert "pages" in res
    assert len(res["pages"]) > 1, "25 rows must paginate across more than 1 page"

    # Count total table rows across all pages
    total_rendered_rows = 0
    for page_blocks in res["pages"]:
        for block in page_blocks:
            if block.get("kind") == "table":
                total_rendered_rows += len(block.get("rows", []))
    assert total_rendered_rows == 25, "All 25 rows must be rendered without loss"


def test_long_title_overflow_raises_slidelayout_error():
    """Characterization test: Titles exceeding the 155pt height threshold in resolve_slide

    trigger SlideLayoutError, formalizing the failure vector where unbudgeted upstream
    titles crash export rather than gracefully auto-fitting.
    """
    slide_long_title = {
        "layout": "chart_narrative",
        "category": "Strategic Executive Review",
        "title": (
            "Comprehensive Long-Term Strategic Operational Review Analyzing Cross-Functional "
            "Interdependencies Across Workforce Demographics, Longitudinal Attendance Trends, "
            "Regional Performance Variances, and Multi-Quarter Productivity Dynamics in High-Growth Environments"
        ),
        "chart": {
            "type": "bar",
            "title": "Test",
            "categories": ["A", "B"],
            "series": [{"name": "S1", "values": [10, 20]}]
        }
    }
    with pytest.raises(SlideLayoutError) as exc_info:
        resolve_slide(slide_long_title)
    assert "The slide title needs a shorter heading" in str(exc_info.value)
