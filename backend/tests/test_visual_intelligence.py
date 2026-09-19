"""Unit and integration tests for Autonomous AI Visual Intelligence Dashboard Engine."""

import json
import pytest
from app.db.database import get_connection
from app.services.visual_intelligence import (
    build_workspace_visual_dashboard,
    generate_comparative_insight,
    generate_bar_insight,
    generate_donut_insight,
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


def test_insights_generation():
    bars = [{'label': 'Engineering', 'value': 90.5}, {'label': 'Sales', 'value': 75.0}]
    bar_insight = generate_bar_insight('Department', 'Performance Score', 'pts', bars)
    assert 'Engineering' in bar_insight
    assert '90.5 pts' in bar_insight
    assert '**' in bar_insight

    slices = [
        {'label': 'Low Risk', 'count': 6, 'pct': 60.0, 'color': '#10b981'},
        {'label': 'High Risk', 'count': 4, 'pct': 40.0, 'color': '#f43f5e'},
    ]
    donut_insight = generate_donut_insight('Risk Level', slices, 10)
    assert 'Low Risk' in donut_insight
    assert '60.0%' in donut_insight

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
        (d1, "Sheet1", json.dumps(["Employee ID", "Department", "Performance Score", "Risk Level"]), json.dumps([]), 4)
    ).lastrowid

    p_rows = [
        {"Employee ID": "E1", "Department": "Tech", "Performance Score": 92.0, "Risk Level": "Low"},
        {"Employee ID": "E2", "Department": "Tech", "Performance Score": 88.0, "Risk Level": "Medium"},
        {"Employee ID": "E3", "Department": "Sales", "Performance Score": 78.0, "Risk Level": "High"},
        {"Employee ID": "E4", "Department": "Sales", "Performance Score": 82.0, "Risk Level": "Low"},
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
        assert dash['total_visualizations'] >= 4
        assert 'All' in dash['categories']
        assert 'Cross-Sheet Intelligence' in dash['categories']
        assert 'Performance & Talent' in dash['categories']
        assert 'Attendance & Leave' in dash['categories']

        # Ensure Cross-Sheet Comparative Chart exists
        cross_charts = [v for v in dash['visualizations'] if v['chart_type'] == 'comparative_bar']
        assert len(cross_charts) >= 1
        comp = cross_charts[0]
        assert comp['category'] == 'Cross-Sheet Intelligence'
        assert comp['sheet_ids'] == [s1, s2]
        assert len(comp['comparative_data']['items']) == 2
        assert 'ai_insight' in comp

        # Ensure Bar Chart exists
        bars = [v for v in dash['visualizations'] if v['chart_type'] == 'bar']
        assert len(bars) >= 2

        # Ensure Donut Chart exists
        donuts = [v for v in dash['visualizations'] if v['chart_type'] == 'donut']
        assert len(donuts) >= 1

        # Test sheet-specific filtering
        s1_dash = build_workspace_visual_dashboard(conn, sheet_id=s1)
        for v in s1_dash['visualizations']:
            assert s1 in v['sheet_ids']

        s2_dash = build_workspace_visual_dashboard(conn, sheet_id=s2)
        for v in s2_dash['visualizations']:
            assert s2 in v['sheet_ids']
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
