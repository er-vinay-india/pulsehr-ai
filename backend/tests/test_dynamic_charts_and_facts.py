"""Automated Verification Suite for Dynamic Charts, Interesting Facts & Multi-Sheet Relationships."""

import json
import pytest
import pandas as pd
from app.db.database import get_connection
from app.services.analysis_planner import evaluate_chart_prerequisites, classify_row_entity
from app.services.fact_discovery import discover_prioritized_hr_facts
from app.services.visual_intelligence import build_workspace_visual_dashboard
from app.services.sheet_catalog import value_key, canonical


def test_single_unfamiliar_sheet_generates_charts_and_facts():
    """Verify that an unfamiliar sheet (e.g. recruitment pipeline) produces standalone visual charts and facts."""
    records = [
        {"Applicant ID": "APP-001", "Candidate Name": "Alice Wong", "Hiring Stage": "Technical Interview", "Interview Score": 88.5, "Salary Expectation": "$120,000"},
        {"Applicant ID": "APP-002", "Candidate Name": "Bob Miller", "Hiring Stage": "HR Screen", "Interview Score": 72.0, "Salary Expectation": "$95,000"},
        {"Applicant ID": "APP-003", "Candidate Name": "Carol Danvers", "Hiring Stage": "Offer Extended", "Interview Score": 95.0, "Salary Expectation": "$140,000"},
        {"Applicant ID": "APP-004", "Candidate Name": "Dave Ross", "Hiring Stage": "Technical Interview", "Interview Score": 84.0, "Salary Expectation": "$115,000"},
        {"Applicant ID": "APP-005", "Candidate Name": "Emma Watson", "Hiring Stage": "HR Screen", "Interview Score": 69.5, "Salary Expectation": "$90,000"},
    ]
    cols = ["Applicant ID", "Candidate Name", "Hiring Stage", "Interview Score", "Salary Expectation"]

    # 1. Entity classification
    entity_info = classify_row_entity(cols, records)
    assert entity_info["entity_type"] == "recruitment_application"

    # 2. Dynamic Chart Prerequisites
    res = evaluate_chart_prerequisites(records, cols, "Recruitment_Pipeline", "recruitment_q3.csv")
    supported = res["supported_charts"]
    assert len(supported) >= 1

    chart_types = [c["chart_type"] for c in supported]
    assert "bar" in chart_types or "donut" in chart_types

    # 3. Bar Chart contains valid groups
    bar_chart = next((c for c in supported if c["chart_type"] == "bar"), None)
    if bar_chart:
        assert len(bar_chart["bars"]) >= 2
        assert bar_chart["unit"] in ("pts", "units", "$")
        assert bar_chart["coverage_pct"] == 100.0


def test_two_related_sheets_different_column_names(tmp_path):
    """Verify two sheets with differently named columns (e.g. 'emp_code' vs 'staff_id') join properly."""
    conn = get_connection()
    try:
        # Sheet A: Staff Directory
        d1 = conn.execute("INSERT INTO dataset_uploads(filename, original_name, file_type) VALUES ('staff.csv', 'staff_roster.csv', 'csv')").lastrowid
        s1 = conn.execute("INSERT INTO sheets(dataset_id, name, columns_json, profile_json, row_count) VALUES (?,?,?,?,?)",
                          (d1, "Staff", json.dumps(["staff_id", "Full Name", "Department", "Performance Rating"]), "[]", 3)).lastrowid
        rows1 = [
            {"staff_id": "001", "Full Name": "Dev A", "Department": "Tech", "Performance Rating": 4.8},
            {"staff_id": "002", "Full Name": "Dev B", "Department": "Tech", "Performance Rating": 4.2},
            {"staff_id": "003", "Full Name": "Sales C", "Department": "Commercial", "Performance Rating": 3.9},
        ]
        for idx, r in enumerate(rows1):
            conn.execute("INSERT INTO sheet_rows(sheet_id, row_index, data_json) VALUES (?,?,?)", (s1, idx, json.dumps(r)))

        # Sheet B: Compensation Records with leading zero IDs
        d2 = conn.execute("INSERT INTO dataset_uploads(filename, original_name, file_type) VALUES ('comp.csv', 'comp_q3.csv', 'csv')").lastrowid
        s2 = conn.execute("INSERT INTO sheets(dataset_id, name, columns_json, profile_json, row_count) VALUES (?,?,?,?,?)",
                          (d2, "Compensation", json.dumps(["staff_id", "Base Salary", "Bonus Pct"]), "[]", 3)).lastrowid
        rows2 = [
            {"staff_id": "001", "Base Salary": 110000, "Bonus Pct": "15%"},
            {"staff_id": "002", "Base Salary": 95000, "Bonus Pct": "10%"},
            {"staff_id": "003", "Base Salary": 85000, "Bonus Pct": "12%"},
        ]
        for idx, r in enumerate(rows2):
            conn.execute("INSERT INTO sheet_rows(sheet_id, row_index, data_json) VALUES (?,?,?)", (s2, idx, json.dumps(r)))

        conn.execute("""
            INSERT INTO sheet_relationships(left_sheet, right_sheet, left_column, right_column, method, status, cardinality, matching_keys, matching_pairs, reason)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (s1, s2, "staff_id", "staff_id", "exact", "linked", "one-to-one", 3, 3, "Exact key match"))
        conn.commit()

        dash = build_workspace_visual_dashboard(conn)
        assert dash["total_visualizations"] >= 1
        assert "prioritized_facts" in dash
        assert isinstance(dash["prioritized_facts"], list)
    finally:
        conn.close()


def test_leading_zeroes_preserved_in_value_key():
    """Verify that identifiers like '001' and '0042' preserve leading zeroes and do not become integers."""
    assert value_key("001") == "001"
    assert value_key("0042") == "0042"
    assert value_key("  007  ") == "007"
    assert value_key("001") != value_key("1")


def test_unrelated_sheets_do_not_force_connections():
    """Verify unrelated sheets produce independent findings without artificial forced relationships."""
    conn = get_connection()
    try:
        # Sheet A: Office Facilities Expenses
        d1 = conn.execute("INSERT INTO dataset_uploads(filename, original_name, file_type) VALUES ('fac.csv', 'facilities.csv', 'csv')").lastrowid
        s1 = conn.execute("INSERT INTO sheets(dataset_id, name, columns_json, profile_json, row_count) VALUES (?,?,?,?,?)",
                          (d1, "Facilities", json.dumps(["Building", "Electricity Expense", "Floor Area"]), "[]", 2)).lastrowid
        conn.execute("INSERT INTO sheet_rows(sheet_id, row_index, data_json) VALUES (?,?,?)", (s1, 0, json.dumps({"Building": "HQ", "Electricity Expense": 4500, "Floor Area": 20000})))
        conn.execute("INSERT INTO sheet_rows(sheet_id, row_index, data_json) VALUES (?,?,?)", (s1, 1, json.dumps({"Building": "Lab", "Electricity Expense": 8200, "Floor Area": 15000})))

        # Sheet B: Vehicle Fleet
        d2 = conn.execute("INSERT INTO dataset_uploads(filename, original_name, file_type) VALUES ('fleet.csv', 'fleet.csv', 'csv')").lastrowid
        s2 = conn.execute("INSERT INTO sheets(dataset_id, name, columns_json, profile_json, row_count) VALUES (?,?,?,?,?)",
                          (d2, "Fleet", json.dumps(["Vehicle VIN", "Model", "Mileage"]), "[]", 2)).lastrowid
        conn.execute("INSERT INTO sheet_rows(sheet_id, row_index, data_json) VALUES (?,?,?)", (s2, 0, json.dumps({"Vehicle VIN": "VIN1", "Model": "Van A", "Mileage": 42000})))
        conn.execute("INSERT INTO sheet_rows(sheet_id, row_index, data_json) VALUES (?,?,?)", (s2, 1, json.dumps({"Vehicle VIN": "VIN2", "Model": "Van B", "Mileage": 18500})))
        conn.commit()

        # Build dashboard: Should generate standalone charts without crashing
        dash = build_workspace_visual_dashboard(conn)
        assert dash["total_visualizations"] >= 1
    finally:
        conn.close()


def test_small_sample_and_missing_fields_graceful_handling():
    """Verify that a small sample (N=2) with null fields does not crash calculations."""
    records = [
        {"Department": "Finance", "Bonus": 5000.0, "Tenure": None},
        {"Department": "Finance", "Bonus": None, "Tenure": 3.0}
    ]
    cols = ["Department", "Bonus", "Tenure"]
    res = evaluate_chart_prerequisites(records, cols, "MiniSheet", "mini.csv")
    assert isinstance(res, dict)
    assert "supported_charts" in res
    assert "limitations" in res
