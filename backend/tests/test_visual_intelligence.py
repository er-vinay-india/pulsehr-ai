"""Unit and integration tests for Autonomous AI Visual Intelligence Dashboard Engine."""

import json
import pytest
from app.db.database import get_connection
from app.services.visual_intelligence import (
    build_workspace_visual_dashboard,
    get_sheet_raw_projections,
    generate_comparative_insight,
    is_name_or_text_column,
    clean_file_label,
)


def test_is_name_or_text_column():
    assert is_name_or_text_column('Employee Name') is True
    assert is_name_or_text_column('candidate_name') is True
    assert is_name_or_text_column('notes') is True
    assert is_name_or_text_column('comments') is True
    assert is_name_or_text_column('Department') is False
    assert is_name_or_text_column('Performance Score') is False
    assert is_name_or_text_column('Risk Level') is False


def test_clean_file_label():
    assert clean_file_label('employee_performance_data.csv') == 'employee_performance_data'
    assert clean_file_label('test.xlsx') == 'test'
    long_name = 'very_long_employee_attendance_performance_dataset_name_2026.csv'
    assert len(clean_file_label(long_name)) <= 32


def test_comparative_insight_generation():
    items = [
        {'label': 'Engineering', 'val1': 92.0, 'val2': 1.5},
        {'label': 'Operations', 'val1': 76.0, 'val2': 4.5},
    ]
    comp_insight = generate_comparative_insight('Department', 'Performance Score', 'Absent Days', 'pts', 'days', items)
    assert 'Engineering' in comp_insight
    assert '92.0 pts' in comp_insight
    assert 'Operations' in comp_insight


def seed_test_datasets(conn):
    """Seeds two connected sheets into the test database."""
    # Dataset 1
    d1 = conn.execute(
        "INSERT INTO dataset_uploads(filename, original_name, file_type, row_count, col_count) VALUES (?,?,?,?,?)",
        ("perf.csv", "employee_performance.csv", "csv", 4, 4)
    ).lastrowid
    s1 = conn.execute(
        "INSERT INTO sheets(dataset_id, name, columns_json, profile_json, row_count) VALUES (?,?,?,?,?)",
        (d1, "Sheet1", json.dumps(["Employee ID", "Department", "Performance Score", "Risk Level", "Overtime Hours"]), json.dumps([]), 4)
    ).lastrowid

    p_rows = [
        {"Employee ID": "E1", "Department": "Tech", "Performance Score": 92.0, "Risk Level": "Low", "Overtime Hours": 10.0},
        {"Employee ID": "E2", "Department": "Tech", "Performance Score": 88.0, "Risk Level": "Medium", "Overtime Hours": 15.0},
        {"Employee ID": "E3", "Department": "Sales", "Performance Score": 78.0, "Risk Level": "High", "Overtime Hours": 5.0},
        {"Employee ID": "E4", "Department": "Sales", "Performance Score": 82.0, "Risk Level": "Low", "Overtime Hours": 8.0},
    ]
    for idx, r in enumerate(p_rows):
        conn.execute("INSERT INTO sheet_rows(sheet_id, row_index, data_json) VALUES (?,?,?)", (s1, idx, json.dumps(r)))

    # Dataset 2
    d2 = conn.execute(
        "INSERT INTO dataset_uploads(filename, original_name, file_type, row_count, col_count) VALUES (?,?,?,?,?)",
        ("absent.csv", "employee_absent.csv", "csv", 4, 3)
    ).lastrowid
    s2 = conn.execute(
        "INSERT INTO sheets(dataset_id, name, columns_json, profile_json, row_count) VALUES (?,?,?,?,?)",
        (d2, "Sheet1", json.dumps(["Employee ID", "Department", "Absent ( no of days )"]), json.dumps([]), 4)
    ).lastrowid

    a_rows = [
        {"Employee ID": "E1", "Department": "Tech", "Absent ( no of days )": 1.0},
        {"Employee ID": "E2", "Department": "Tech", "Absent ( no of days )": 2.0},
        {"Employee ID": "E3", "Department": "Sales", "Absent ( no of days )": 5.0},
        {"Employee ID": "E4", "Department": "Sales", "Absent ( no of days )": 4.0},
    ]
    for idx, r in enumerate(a_rows):
        conn.execute("INSERT INTO sheet_rows(sheet_id, row_index, data_json) VALUES (?,?,?)", (s2, idx, json.dumps(r)))

    # Relationship
    conn.execute(
        "INSERT INTO sheet_relationships(left_sheet, right_sheet, left_column, right_column, method, status, cardinality, matching_keys, matching_pairs, reason) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (s1, s2, "Employee ID", "Employee ID", "exact", "linked", "one-to-one", 4, 4, "Key match")
    )
    conn.commit()
    return s1, s2


def test_build_workspace_visual_dashboard_multi_sheet():
    conn = get_connection()
    try:
        s1, s2 = seed_test_datasets(conn)
        dash = build_workspace_visual_dashboard(conn)
        assert isinstance(dash, dict)
        assert dash['total_visualizations'] >= 3
        assert 'All' in dash['categories']
        assert 'Industrial People Analytics' in dash['categories']

        # Ensure Industrial Models exist
        types = [v['chart_type'] for v in dash['visualizations']]
        assert 'talent_9box' in types
        assert 'bradford_factor' in types

        # Ensure Cross-Sheet Comparative Chart exists
        cross_charts = [v for v in dash['visualizations'] if v['chart_type'] == 'comparative_bar']
        assert len(cross_charts) >= 1
        comp = cross_charts[0]
        assert comp['category'] == 'Cross-Sheet Intelligence'
        assert comp['sheet_ids'] == [s1, s2]
        assert len(comp['comparative_data']['items']) == 2
        assert 'ai_insight' in comp
    finally:
        conn.close()


def test_get_sheet_raw_projections_for_data_explorer():
    conn = get_connection()
    try:
        s1, s2 = seed_test_datasets(conn)
        proj = get_sheet_raw_projections(conn, s1)
        assert proj['available'] is True
        assert proj['sheet_id'] == s1
        assert len(proj['column_stats']) >= 4
        assert len(proj['projections']) >= 2

        # Verify bar charts exist for numeric measures
        bars = [p for p in proj['projections'] if p['type'] == 'bar']
        assert len(bars) >= 2
        titles = [b['title'] for b in bars]
        assert any('performance score' in t.lower() for t in titles)
        assert any('overtime hours' in t.lower() for t in titles)

        # Verify donut chart for Risk Level
        donuts = [p for p in proj['projections'] if p['type'] == 'donut']
        assert len(donuts) >= 1
    finally:
        conn.close()


def test_empty_workspace_returns_clean_structure():
    conn = get_connection()
    try:
        dash = build_workspace_visual_dashboard(conn)
        assert dash['total_visualizations'] == 0
        assert dash['visualizations'] == []
        assert dash['categories'] == ['All']
    finally:
        conn.close()
