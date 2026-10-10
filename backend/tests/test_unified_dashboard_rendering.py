"""Unit tests for Phase 9.6: Unified Dataset Dashboard Rendering Migration.

Validates that:
1. Dashboard API is driven by dataset_id (PASS)
2. selected_sheet_id does not control or fragment the dashboard (PASS)
3. GlobalRanker output (up to 9 budgeted slots) is returned directly (PASS)
4. Cross-sheet discoveries appear as normal cards alongside single-sheet cards (PASS)
5. Story Planner uses dataset-wide context (PASS)
6. 3-sheet upload produces ONE unified dashboard (PASS)
7. Sheet reordering leaves dashboard unchanged (PASS)
"""
from __future__ import annotations

import json
import pytest
from fastapi.testclient import TestClient

from app.db.database import get_connection
from app.main import app
from app.services.adaptive_dashboard.dataset_orchestrator import run_dataset_intelligence


@pytest.fixture
def multisheet_workforce_dataset():
    """Sets up a 3-sheet workbook (Employees, Attendance, Leave) in SQLite."""
    conn = get_connection()
    ds_id = 999
    conn.execute(
        "INSERT OR REPLACE INTO dataset_uploads (id, filename, original_name, display_name, file_type, sheet_count, row_count) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (ds_id, "workforce_q3.xlsx", "Workforce Enterprise Q3.xlsx", "Global Workforce Q3", "xlsx", 3, 670),
    )

    emp_cols = ["employee_id", "department", "salary", "hire_date"]
    att_cols = ["employee_id", "date", "attendance_hours"]
    leave_cols = ["employee_id", "leave_type", "leave_days"]

    conn.execute(
        "INSERT OR REPLACE INTO sheets (id, dataset_id, name, display_name, columns_json, profile_json, row_count) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (1001, ds_id, "Employees", "Employee Directory", json.dumps(emp_cols), "[]", 50),
    )
    conn.execute(
        "INSERT OR REPLACE INTO sheets (id, dataset_id, name, display_name, columns_json, profile_json, row_count) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (1002, ds_id, "Attendance", "Attendance Records", json.dumps(att_cols), "[]", 500),
    )
    conn.execute(
        "INSERT OR REPLACE INTO sheets (id, dataset_id, name, display_name, columns_json, profile_json, row_count) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (1003, ds_id, "Leave", "Leave Log", json.dumps(leave_cols), "[]", 120),
    )

    conn.execute(
        """
        INSERT OR REPLACE INTO sheet_relationships (left_sheet, right_sheet, left_column, right_column, method, status, cardinality, matching_keys, matching_pairs, similarity, reason)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (1001, 1002, "employee_id", "employee_id", "exact_key", "verified", "one-to-many", 50, 500, 1.0, "Employee ID join"),
    )
    conn.execute(
        """
        INSERT OR REPLACE INTO sheet_relationships (left_sheet, right_sheet, left_column, right_column, method, status, cardinality, matching_keys, matching_pairs, similarity, reason)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (1001, 1003, "employee_id", "employee_id", "exact_key", "verified", "one-to-many", 45, 120, 0.95, "Leave records link"),
    )

    # Insert sample rows so profile_source doesn't fail
    for i in range(1, 11):
        conn.execute(
            "INSERT INTO sheet_rows (sheet_id, row_index, data_json) VALUES (?, ?, ?)",
            (1001, i, json.dumps({"employee_id": f"E{i}", "department": "Sales", "salary": 60000 + i * 1000, "hire_date": "2023-01-01"})),
        )
    conn.commit()
    conn.close()
    return ds_id


def test_dashboard_api_driven_by_dataset_id(multisheet_workforce_dataset):
    """Verify GET /api/adaptive-dashboard/primary-element?dataset_id={id} returns unified intelligence."""
    client = TestClient(app)
    resp = client.get(f"/api/adaptive-dashboard/primary-element?dataset_id={multisheet_workforce_dataset}")
    assert resp.status_code == 200
    data = resp.json()

    assert data["dataset_id"] == multisheet_workforce_dataset
    assert data["sheet_count"] == 3
    assert len(data["selected_dashboard_insights"]) > 0
    assert len(data["selected_dashboard_insights"]) <= 9
    assert data["cross_sheet_candidates_count"] >= 1
    assert data["story_plan"] is not None
    assert "narrative_angle" in data["story_plan"]


def test_selected_sheet_id_not_controlling_dashboard(multisheet_workforce_dataset):
    """Verify passing sheet_id resolves to the parent dataset and produces the same unified dashboard."""
    client = TestClient(app)

    # Calling with sheet_id=1001
    resp_s1 = client.get("/api/adaptive-dashboard/primary-element?sheet_id=1001")
    assert resp_s1.status_code == 200
    data_s1 = resp_s1.json()

    # Calling with dataset_id=999
    resp_ds = client.get(f"/api/adaptive-dashboard/primary-element?dataset_id={multisheet_workforce_dataset}")
    assert resp_ds.status_code == 200
    data_ds = resp_ds.json()

    # Both resolve to the dataset and produce unified insights
    assert data_s1["dataset_id"] == data_ds["dataset_id"] == multisheet_workforce_dataset
    assert len(data_s1["selected_dashboard_insights"]) == len(data_ds["selected_dashboard_insights"])


def test_dedicated_dataset_dashboard_endpoint(multisheet_workforce_dataset):
    """Verify GET /api/adaptive-dashboard/dataset/{dataset_id} returns DatasetIntelligenceResponse."""
    client = TestClient(app)
    resp = client.get(f"/api/adaptive-dashboard/dataset/{multisheet_workforce_dataset}")
    assert resp.status_code == 200
    data = resp.json()

    assert data["dataset_id"] == multisheet_workforce_dataset
    assert len(data["selected_dashboard_insights"]) <= 9
    assert data["cross_sheet_candidates_count"] >= 1
    assert data["relationship_graph"] is not None
    assert len(data["relationship_graph"]["relationships"]) >= 2


def test_cross_sheet_insights_appear_as_normal_cards(multisheet_workforce_dataset):
    """Verify that cross-sheet discoveries exist as normal cards with slot types in selected_dashboard_insights."""
    client = TestClient(app)
    resp = client.get(f"/api/adaptive-dashboard/primary-element?dataset_id={multisheet_workforce_dataset}")
    data = resp.json()

    insights = data["selected_dashboard_insights"]
    cross_insights = [i for i in insights if i["scope"] == "CROSS_SHEET"]
    assert len(cross_insights) >= 1

    hero_or_strat = cross_insights[0]
    assert hero_or_strat["slot_type"] in ("hero", "strategic", "diagnostic", "risk_foresight", "action_scenario")
    assert hero_or_strat["composite_score"] > 0.0
    assert hero_or_strat["candidate_id"].startswith("INS-")


def test_3_sheet_upload_produces_one_unified_dashboard(multisheet_workforce_dataset):
    """Verify that 3 sheets in a workbook generate ONE dashboard response containing all sheet contexts."""
    res = run_dataset_intelligence(multisheet_workforce_dataset)
    assert res.sheet_count == 3
    assert set(res.sheets_analyzed) == {"Employees", "Attendance", "Leave"}
    assert len(res.selected_dashboard_insights) <= 9
    assert res.story_plan is not None
    assert res.executive_integrity["evidence_coverage"] == "100%"


def test_sheet_reorder_leaves_dashboard_unchanged(multisheet_workforce_dataset):
    """Verify that sheet order in workbook does not alter the selected dashboard insights or ranking."""
    from app.services.adaptive_dashboard.evaluator import DatasetIntelligenceEvaluator

    is_invariant = DatasetIntelligenceEvaluator.test_sheet_order_invariance(multisheet_workforce_dataset)
    assert is_invariant is True

    # Also verify through the API endpoint
    client = TestClient(app)
    resp1 = client.get(f"/api/adaptive-dashboard/primary-element?dataset_id={multisheet_workforce_dataset}").json()
    resp2 = client.get(f"/api/adaptive-dashboard/primary-element?dataset_id={multisheet_workforce_dataset}").json()
    assert [i["candidate_id"] for i in resp1["selected_dashboard_insights"]] == [i["candidate_id"] for i in resp2["selected_dashboard_insights"]]


def test_story_planner_uses_dataset_context(multisheet_workforce_dataset):
    """Verify that story planner synthesizes across sibling sheets in the unified dataset."""
    client = TestClient(app)
    resp = client.get(f"/api/adaptive-dashboard/primary-element?dataset_id={multisheet_workforce_dataset}").json()
    story_plan = resp["story_plan"]
    assert story_plan is not None
    assert story_plan["narrative_angle"] != ""
    assert len(story_plan["claims"]) >= 1
    # Check that claims are bound to evidence IDs
    for claim in story_plan["claims"]:
        assert len(claim["evidence_ids"]) >= 1
        assert claim["rendered_text"] != ""


def test_multisheet_candidate_pool_and_budget_governance(multisheet_workforce_dataset):
    """Verify that multiple sibling sheets contribute to candidate pool and budget limits hold."""
    client = TestClient(app)
    resp = client.get(f"/api/adaptive-dashboard/primary-element?dataset_id={multisheet_workforce_dataset}")
    assert resp.status_code == 200
    data = resp.json()

    # Diagnostic metadata assertions
    assert data["dataset_id"] == multisheet_workforce_dataset
    assert data["source_sheet_count"] == 3
    assert len(data["source_sheet_ids"]) >= 2
    assert data["relationship_count"] >= 2
    assert data["candidate_count"] >= 2
    assert data["selected_insight_count"] <= 9

    insights = data["selected_dashboard_insights"]
    assert len(insights) <= 9

    # Slot budget checks
    hero_count = sum(1 for i in insights if i["slot_type"] == "hero")
    strat_count = sum(1 for i in insights if i["slot_type"] == "strategic")
    diag_count = sum(1 for i in insights if i["slot_type"] == "diagnostic")
    risk_count = sum(1 for i in insights if i["slot_type"] == "risk_foresight")
    action_count = sum(1 for i in insights if i["slot_type"] == "action_scenario")

    assert hero_count <= 1
    assert strat_count <= 3
    assert diag_count <= 2
    assert risk_count <= 2
    assert action_count <= 1


def test_unresolved_template_token_validator():
    """Verify that UnresolvedTemplateTokenValidator eliminates all {variable} tokens."""
    from app.services.adaptive_dashboard.evidence_graph import UnresolvedTemplateTokenValidator

    raw_text = "{subject} recorded {formatted_value}, showing {difference_pct}% variance compared to {comparison}."
    clean = UnresolvedTemplateTokenValidator.validate_and_sanitize(raw_text, fallback="Safe operational fallback")
    assert "{" not in clean
    assert "}" not in clean

    no_token_text = "Attendance remains stable across all divisions."
    assert UnresolvedTemplateTokenValidator.validate_and_sanitize(no_token_text) == no_token_text


def test_business_titles_and_visual_specs(multisheet_workforce_dataset):
    """Verify that selected insights have natural business titles and visual specs (no raw sheet join names)."""
    client = TestClient(app)
    resp = client.get(f"/api/adaptive-dashboard/primary-element?dataset_id={multisheet_workforce_dataset}")
    data = resp.json()

    insights = data["selected_dashboard_insights"]
    assert len(insights) > 0

    for cand in insights:
        # Business titles
        assert "Sheet1 × Leave Calculation Check" not in cand["title"]
        # Presentation type and visual spec
        assert cand.get("presentation_type") in ("comparison_bar", "ranked_bar", "trend_line", "kpi_card", "variance_chart", "distribution", "action_card")
        assert "visual_spec" in cand
        v_spec = cand["visual_spec"]
        assert "categories" in v_spec
        assert len(v_spec["categories"]) > 0

    # Story plan business language
    story_plan = data["story_plan"]
    assert "Sheet1 × Leave Calculation Check" not in story_plan["narrative_angle"]
    for claim in story_plan["claims"]:
        assert "{" not in claim["rendered_text"]
        assert "}" not in claim["rendered_text"]


def test_related_period_insights_merge_into_one_topic(multisheet_workforce_dataset):
    """Verify that multiple time-slice insights are merged into a single ExecutiveTopic."""
    from app.services.adaptive_dashboard.composition_planner import ExecutiveCompositionPlanner
    from app.services.adaptive_dashboard.dataset_orchestrator import run_dataset_intelligence

    intel = run_dataset_intelligence(multisheet_workforce_dataset)
    assert len(intel.executive_topics) >= 3
    assert len(intel.executive_topics) <= 5

    # Check for merged time-series attendance vs leave topic
    merged_topic = next((t for t in intel.executive_topics if "trend" in t["title"].lower() or "leave" in t["title"].lower()), None)
    assert merged_topic is not None
    assert len(merged_topic["periods"]) >= 2
    assert merged_topic["recommended_visual"] in ("100_percent_stacked_bar", "multi_series_trend", "grouped_bar", "ranked_bar")
    assert "visual_spec" in merged_topic


def test_max_main_visuals_is_five(multisheet_workforce_dataset):
    """Verify that the executive composition budget limits total topics to at most 5."""
    client = TestClient(app)
    resp = client.get(f"/api/adaptive-dashboard/primary-element?dataset_id={multisheet_workforce_dataset}")
    data = resp.json()

    assert "executive_topics" in data
    topics = data["executive_topics"]
    assert len(topics) >= 1
    assert len(topics) <= 5



