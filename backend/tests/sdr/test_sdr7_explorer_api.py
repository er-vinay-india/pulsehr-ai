"""
SDR-7 Automated Certification Test Suite

Validates the Governed Semantic Refinery (SDR-1 through SDR-6) Explorer API:
1. /summary: dataset metadata, stages, counts.
2. /source-rows: exactness-first raw records, zero derived columns masquerading, pagination, search.
3. /semantics: entity hypothesis, plain English grain explanation, candidate keys, valid no-key state, GEO-1 resolutions.
4. /relationships: validated edges, join safety, plain English preaggregation explanations (no SQL), plain English unsafe join explanations (no DB jargon).
5. /analytical-views: views, freshness status, stale warnings blocking current truth serving, virtual materialization default.
6. /analytical-facts: exact values, units, denominators, compact step-by-step lineage path.
7. P0 Invariant: zero mutations to primary production SQLite DB.
"""

import hashlib
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
DATASET_ID = "sdr7_cert"


def test_explorer_summary_api():
    """Verify /summary returns metadata, stages availability, and object counts."""
    response = client.get(f"/api/datasets/{DATASET_ID}/explorer/summary")
    assert response.status_code == 200
    data = response.json()

    assert data["dataset_id"] == DATASET_ID
    assert data["total_sheets"] == 6
    assert data["total_rows"] == 20

    sheet_names = [s["name"] for s in data["sheets"]]
    assert "Employees" in sheet_names
    assert "AttendanceDaily" in sheet_names
    assert "EmployeeMonthly" in sheet_names
    assert "Stores" in sheet_names
    assert "Sales" in sheet_names
    assert "InventoryDaily" in sheet_names

    # All pipeline stages should be available
    stages = data.get("stages", {})
    assert stages.get("SDR_1_PROFILING") == "AVAILABLE"
    assert stages.get("SDR_2_GRAIN") == "AVAILABLE"
    assert stages.get("SDR_3_KEYS") == "AVAILABLE"
    assert stages.get("SDR_4_ENRICHMENT") == "AVAILABLE"
    assert stages.get("SDR_5_RELATIONSHIPS") == "AVAILABLE"
    assert stages.get("SDR_6_ANALYTICAL_VIEWS") == "AVAILABLE"


def test_explorer_source_rows_api_exactness():
    """Verify /source-rows delivers exact raw data without derived column masquerading."""
    response = client.get(f"/api/datasets/{DATASET_ID}/explorer/source-rows?sheet_id=Employees&page=1&page_size=25")
    assert response.status_code == 200
    data = response.json()

    assert data["sheet_id"] == "Employees"
    assert data["total_rows"] == 4
    assert data["derived_columns_count"] == 0
    assert data["is_source_truth"] is True

    # Check exact raw values (e.g. leading zero preserved, exact strings)
    rows = data["rows"]
    assert len(rows) == 4
    first_row = rows[0]
    assert first_row["employee_id"] == "0042"
    assert first_row["employee_name"] == "Alice Zhang"
    assert first_row["city"] == "Bengaluru"
    assert first_row["ssn_redacted"] == "***-**-1234"

    # Search filter
    search_resp = client.get(f"/api/datasets/{DATASET_ID}/explorer/source-rows?sheet_id=Employees&search=Bob")
    assert search_resp.status_code == 200
    search_data = search_resp.json()
    assert search_data["total_rows"] == 1
    assert search_data["rows"][0]["employee_name"] == "Bob Smith"


def test_explorer_semantics_api():
    """Verify /semantics provides entity hypothesis, grain explanation, candidate keys, and GEO-1 resolutions."""
    response = client.get(f"/api/datasets/{DATASET_ID}/explorer/semantics?sheet_id=Employees")
    assert response.status_code == 200
    data = response.json()

    # Columns metadata
    columns = data["columns"]
    assert len(columns) > 0
    col_map = {c["column_id"]: c for c in columns}
    assert "employee_id" in col_map
    assert "salary" in col_map
    assert "city" in col_map

    salary_col = col_map["salary"]
    assert salary_col["measure_class_raw"] == "FINANCIAL"
    assert salary_col["is_derived"] is False

    # Entities
    entities = data["entities"]
    assert len(entities) > 0
    emp_entity = next((e for e in entities if e.get("canonical_name") == "EMPLOYEE"), None)
    assert emp_entity is not None

    # Candidate keys
    candidate_keys = data["candidate_keys"]
    assert len(candidate_keys) > 0
    primary_key = candidate_keys[0]
    assert "employee_id" in primary_key["key_columns"]

    # Grains
    grains = data["grains"]
    assert len(grains) > 0
    emp_grain = next((g for g in grains if g["sheet_id"] == "Employees"), None)
    assert emp_grain is not None
    assert emp_grain["explanation"] is not None

    # GEO-1 resolutions
    geo_res = data["geo_resolutions"]
    assert len(geo_res) > 0
    first_geo = geo_res[0]
    assert first_geo["reference"] is not None
    assert "geo" in first_geo["reference"].lower()


def test_explorer_semantics_valid_no_key_state():
    """Verify /semantics correctly identifies and explains valid no-key tables (e.g. InventoryDaily)."""
    response = client.get(f"/api/datasets/{DATASET_ID}/explorer/semantics?sheet_id=InventoryDaily")
    assert response.status_code == 200
    data = response.json()

    assert data["has_candidate_keys"] is False
    assert data["no_key_message"] is not None
    assert "no reliable business key was identified" in data["no_key_message"].lower()


def test_explorer_relationships_api():
    """Verify /relationships returns validated edges, join safety, and plain English explanations without SQL/DB jargon."""
    response = client.get(f"/api/datasets/{DATASET_ID}/explorer/relationships")
    assert response.status_code == 200
    data = response.json()

    relationships = data["relationships"]
    assert len(relationships) >= 3

    # Check AttendanceDaily -> EmployeeMonthly
    att_monthly_rel = next(
        (r for r in relationships if r["left_sheet"] == "AttendanceDaily" and r["right_sheet"] == "EmployeeMonthly"),
        None,
    )
    assert att_monthly_rel is not None
    assert att_monthly_rel["cardinality_raw"] in ["MANY_TO_ONE", "ONE_TO_MANY"]
    assert att_monthly_rel["safety_status_raw"] == "SAFE_WITH_PREAGGREGATION"

    # Preaggregation explanation must NOT contain SQL keywords like SELECT, GROUP BY
    preagg_exp = att_monthly_rel["preaggregation_explanation"]
    assert preagg_exp is not None
    assert "aggregate" in preagg_exp.lower()
    assert "SELECT " not in preagg_exp
    assert "GROUP BY" not in preagg_exp

    # Check unsafe join explanation has no raw DB jargon
    emp_att_rel = next(
        (r for r in relationships if r["left_sheet"] == "Employees" and r["right_sheet"] == "AttendanceDaily"),
        None,
    )
    assert emp_att_rel is not None
    assert emp_att_rel["safety_status_raw"] == "UNSAFE"
    unsafe_exp = emp_att_rel["unsafe_join_explanation"]
    assert unsafe_exp is not None
    assert "repeat parent-level metrics" in unsafe_exp.lower()
    assert "INNER JOIN" not in unsafe_exp
    assert "CROSS JOIN" not in unsafe_exp


def test_explorer_analytical_views_api():
    """Verify /analytical-views provides views, freshness, stale warnings, and virtual default."""
    response = client.get(f"/api/datasets/{DATASET_ID}/explorer/analytical-views")
    assert response.status_code == 200
    data = response.json()

    views = data["views"]
    assert len(views) >= 2

    # Check current view
    active_view = next((v for v in views if v["view_id"] == "view_monthly_attendance_summary"), None)
    assert active_view is not None
    assert active_view["is_stale"] is False
    assert active_view["freshness"] == "Current"
    assert active_view["materialization_mode_raw"] == "VIRTUAL"

    # Check stale view handling
    stale_view = next((v for v in views if v["view_id"] == "view_stale_legacy_compensation"), None)
    assert stale_view is not None
    assert stale_view["is_stale"] is True
    assert "Stale" in stale_view["freshness"]


def test_explorer_analytical_facts_api_and_lineage():
    """Verify /analytical-facts returns exact facts, units, denominators, and compact lineage steps."""
    response = client.get(f"/api/datasets/{DATASET_ID}/explorer/analytical-facts")
    assert response.status_code == 200
    data = response.json()

    facts = data["facts"]
    assert len(facts) >= 2

    first_fact = facts[0]
    assert first_fact["metric"] == "aggregated_hours"
    assert first_fact["value"] == 168.0
    assert first_fact["unit"] == "hours"

    # Lineage path verification
    lineage = first_fact["lineage_path"]
    assert len(lineage) == 4
    stage_types = [step["type"] for step in lineage]
    assert "SOURCE" in stage_types
    assert "JOIN_PLAN" in stage_types
    assert "ANALYTICAL_VIEW" in stage_types
    assert "FACT" in stage_types


def test_sdr7_p0_database_invariant():
    """Verifies that pulsehr.sqlite3 file size and content remain completely unmutated."""
    db_path = Path(__file__).resolve().parent.parent.parent / "data" / "db" / "pulsehr.sqlite3"
    if db_path.exists():
        expected_size = 70385664
        expected_hash = "1561d64eeae26f4d30926371740d6ca9dc41eb6ea7c537281763b7d5aabd9496"
        actual_size = db_path.stat().st_size
        actual_hash = hashlib.sha256(db_path.read_bytes()).hexdigest()
        assert actual_size == expected_size, (
            f"P0 LIVE DATABASE MUTATION DETECTED! Expected size {expected_size}, got {actual_size} bytes."
        )
        assert actual_hash == expected_hash, (
            f"P0 LIVE DATABASE HASH MISMATCH! Expected SHA {expected_hash}, got {actual_hash}."
        )
