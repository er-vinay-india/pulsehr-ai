"""Tests for Empty Data Scenarios (Zero-Data State).

Validates that when the workspace has zero uploaded sheets/datasets:
1. Endpoints return clean HTTP status codes (200, 404) with clear user copy.
2. No unhandled 500 crashes, stack traces, or corrupted state occur.
3. Query planner and copilot return 'source_unavailable' with graceful explanations.
4. Presentation scope detection handles zero-data with clear, governed guidance.
5. Deletion/bulk-deletion on empty database is idempotent and returns 200.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import get_connection
from app.services.copilot_query_planner import AnalyticalQueryPlan, execute_analytical_plan
from app.services.presentation.scope_detector import (
    capture_dataset_context,
    collect_workspace_evidence,
    preview_presentation_scope,
)
from app.services.adaptive_dashboard.source_data_loader import (
    load_dashboard_source_context,
    load_analytical_tables,
    load_sibling_sources,
)
from app.services.adaptive_dashboard.findings import get_shared_findings_for_sheet


@pytest.fixture
def client():
    return TestClient(app)


def test_empty_datasets_list(client):
    """GET /api/upload/datasets returns 200 and an empty list when no data is uploaded."""
    resp = client.get("/api/upload/datasets")
    assert resp.status_code == 200
    data = resp.json()
    assert "datasets" in data
    assert data["datasets"] == []


def test_empty_sheets_list(client):
    """GET /api/sheets returns 200 and an empty list when no sheets exist."""
    resp = client.get("/api/sheets")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, (list, dict))
    if isinstance(data, dict):
        assert data.get("sheets", []) == [] or data.get("data", []) == []


def test_empty_adaptive_dashboard_primary_element_no_params(client):
    """GET /api/adaptive-dashboard/primary-element with no params returns 404 with clean message."""
    resp = client.get("/api/adaptive-dashboard/primary-element")
    assert resp.status_code == 404
    detail = resp.json().get("detail", "")
    assert "No uploaded sheet found" in detail


def test_empty_adaptive_dashboard_primary_element_with_stale_dataset_id(client):
    """GET /api/adaptive-dashboard/primary-element?dataset_id=99770 returns 404 with dataset-specific detail."""
    resp = client.get("/api/adaptive-dashboard/primary-element?dataset_id=99770")
    assert resp.status_code == 404
    detail = resp.json().get("detail", "")
    assert "99770" in detail
    assert "No uploaded sheet found" in detail


def test_empty_adaptive_dashboard_primary_element_with_stale_sheet_id(client):
    """GET /api/adaptive-dashboard/primary-element?sheet_id=12345 returns 404 with sheet-specific detail."""
    resp = client.get("/api/adaptive-dashboard/primary-element?sheet_id=12345")
    assert resp.status_code == 404
    detail = resp.json().get("detail", "")
    assert "12345" in detail
    assert "No uploaded sheet found" in detail


def test_empty_source_data_loader_raises_value_error():
    """load_dashboard_source_context raises ValueError with clean message when database is empty."""
    with pytest.raises(ValueError, match="No uploaded sheet found"):
        load_dashboard_source_context()

    with pytest.raises(ValueError, match="No uploaded sheet found for dataset_id 99770"):
        load_dashboard_source_context(dataset_id=99770)

    with pytest.raises(ValueError, match="No uploaded sheet found for sheet_id 999"):
        load_dashboard_source_context(sheet_id=999)


def test_empty_analytical_tables_and_findings():
    """Helper loaders return empty collections or raise clear ValueErrors without crashing."""
    with get_connection() as conn:
        tables = load_analytical_tables(sheet_id=1, dataset_id=1, conn=conn)
        assert tables == {} or tables == []

        siblings = load_sibling_sources(dataset_id=1, current_sheet_id=1, conn=conn)
        assert siblings == []

    # Requesting findings for a nonexistent sheet in an empty database cleanly raises ValueError
    with pytest.raises(ValueError, match="No uploaded sheet found"):
        get_shared_findings_for_sheet(sheet_id=1)


def test_empty_capture_dataset_context_raises_value_error():
    """capture_dataset_context raises ValueError when no sheets exist."""
    with get_connection() as conn:
        with pytest.raises(ValueError, match="No uploaded sheets found"):
            capture_dataset_context(conn)

        with pytest.raises(ValueError, match="No uploaded sheets found"):
            capture_dataset_context(conn, dataset_id=99770)


def test_empty_presentation_scope_handling():
    """preview_presentation_scope and collect_workspace_evidence handle empty databases safely."""
    with get_connection() as conn:
        preview = preview_presentation_scope(conn, {"scope_type": "workspace"})
        assert preview["eligible"] is False
        assert preview["included_sheets"] == []

        with pytest.raises(ValueError, match="No eligible datasets in presentation scope"):
            collect_workspace_evidence(conn, {"scope_type": "workspace", "deck_style": "standard"})


def test_empty_copilot_analytical_plan_execution():
    """execute_analytical_plan returns source_unavailable status and user-friendly explanation."""
    plan = AnalyticalQueryPlan(
        intent="ranking",
        metric="attendance_rate",
        dataset_id=99770,
        sheet_id=None,
    )
    with get_connection() as conn:
        res = execute_analytical_plan(plan, conn=conn)
        assert res["status"] == "source_unavailable"
        assert "no longer available" in res["answer"] or "No spreadsheet datasets are currently uploaded" in res["answer"]


def test_empty_workspace_delete_all_is_idempotent(client):
    """Deleting datasets when already empty returns clean 200 without error."""
    resp = client.delete("/api/upload/datasets?ids=all")
    assert resp.status_code == 200
    data = resp.json()
    assert "deleted_count" in data or "success" in data or "deleted_dataset_ids" in data


def test_empty_context_documents(client):
    """GET /api/context/documents returns clean 200 list without 500 errors."""
    resp = client.get("/api/context/documents")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


def test_empty_workspace_context_not_found(client):
    """GET /api/workspace/99999/context returns clean 404 when workspace does not exist."""
    resp = client.get("/api/workspace/99999/context")
    assert resp.status_code == 404
    detail = resp.json().get("detail", "")
    assert "not found" in detail.lower()

