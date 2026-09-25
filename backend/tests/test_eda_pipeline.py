"""Tests for the Exploratory Data Analysis (EDA) & Multi-Sheet Intelligence Pipeline."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import get_connection
from app.services.eda.normalizer import (
    parse_percentage,
    parse_currency,
    parse_rating_fraction,
    parse_iso_date,
    normalize_dataset,
)
from app.services.eda.cross_correlator import compute_cross_sheet_intelligence
from app.services.eda.derived_tables import synthesize_derived_tables
from app.services.eda.engine import run_eda_pipeline


@pytest.fixture
def client():
    return TestClient(app)


def test_normalizer_primitives():
    # Percentage
    val, ok = parse_percentage("79.7%")
    assert ok and val == 79.7
    val, ok = parse_percentage("  -12.5 % ")
    assert ok and val == -12.5
    _, ok = parse_percentage("invalid")
    assert not ok

    # Currency
    val, ok = parse_currency("$1,250.75")
    assert ok and val == 1250.75
    val, ok = parse_currency("-$300")
    assert ok and val == -300.0

    # Rating
    num, denom, ok = parse_rating_fraction("4.7/5.0")
    assert ok and num == 4.7 and denom == 5.0
    num, denom, ok = parse_rating_fraction("9/10")
    assert ok and num == 9.0 and denom == 10.0

    # Date
    dt, ok = parse_iso_date("2026-09-25")
    assert ok and dt == "2026-09-25"
    dt, ok = parse_iso_date("09/25/2026")
    assert ok and dt == "2026-09-25"
    # Clock interval should NOT be parsed as date
    _, ok = parse_iso_date("08:43-16:42")
    assert not ok


def test_normalize_dataset_statistical_profiling():
    columns = ["EmpID", "Attendance", "Rating", "Salary", "Notes"]
    raw_records = [
        {"EmpID": "E1", "Attendance": "95%", "Rating": "4.5/5.0", "Salary": "$1,000", "Notes": "Good"},
        {"EmpID": "E2", "Attendance": "94%", "Rating": "4.6/5.0", "Salary": "$1,050", "Notes": "Good"},
        {"EmpID": "E3", "Attendance": "96%", "Rating": "4.8/5.0", "Salary": "$1,100", "Notes": "Good"},
        {"EmpID": "E4", "Attendance": "95%", "Rating": "4.5/5.0", "Salary": "$1,020", "Notes": "Good"},
        {"EmpID": "E5", "Attendance": "50%", "Rating": "2.0/5.0", "Salary": "$1,010", "Notes": "Outlier"},
    ]

    res = normalize_dataset(sheet_id=1, sheet_name="Test", columns=columns, raw_records=raw_records)
    assert res["health_score"] > 0
    assert res["total_rows"] == 5
    assert len(res["curated_records"]) == 5

    # Check normalized values
    assert res["curated_records"][0]["Attendance"] == 95.0
    assert res["curated_records"][0]["Rating"] == 4.5
    assert res["curated_records"][0]["Salary"] == 1000.0

    # Check outlier detected for 50%
    diag = res["column_diagnostics"]["Attendance"]
    assert diag["inferred_type"] == "numeric_percentage"
    assert diag["outlier_count"] >= 1
    assert any(o["value"] == 50.0 for o in diag["outliers"])


def test_cross_sheet_correlation_and_derived_tables():
    sheets = [
        {"id": 101, "name": "Performance", "display_name": "Performance", "columns": ["EmpID", "Score", "Rate"]},
        {"id": 102, "name": "Absence", "display_name": "Absence", "columns": ["EmpID", "DaysAbsent"]},
    ]
    curated_tables = {
        101: [
            {"EmpID": "E1", "Score": 9.0, "Rate": 98.0},
            {"EmpID": "E2", "Score": 8.5, "Rate": 95.0},
            {"EmpID": "E3", "Score": 7.0, "Rate": 85.0},
            {"EmpID": "E4", "Score": 6.0, "Rate": 75.0},
        ],
        102: [
            {"EmpID": "E1", "DaysAbsent": 1},
            {"EmpID": "E2", "DaysAbsent": 2},
            {"EmpID": "E3", "DaysAbsent": 5},
            {"EmpID": "E4", "DaysAbsent": 8},
        ]
    }
    diagnostics = {
        101: {
            "column_diagnostics": {
                "EmpID": {"inferred_type": "identifier"},
                "Score": {"inferred_type": "numeric"},
                "Rate": {"inferred_type": "numeric_percentage"}
            }
        },
        102: {
            "column_diagnostics": {
                "EmpID": {"inferred_type": "identifier"},
                "DaysAbsent": {"inferred_type": "numeric"}
            }
        }
    }

    intel = compute_cross_sheet_intelligence(sheets, curated_tables, diagnostics)
    assert len(intel["entity_links"]) >= 1
    assert intel["entity_links"][0]["left_column"] == "EmpID"
    assert intel["entity_links"][0]["right_column"] == "EmpID"

    # Correlations should be strongly negative: higher absence -> lower score/rate
    assert len(intel["cross_correlations"]) >= 1
    top_corr = intel["cross_correlations"][0]
    assert top_corr["pearson_r"] < -0.80
    assert top_corr["direction"] == "negative"


def test_api_eda_endpoints(client):
    # Seed a test sheet in the isolated test database
    import json
    from app.db.database import get_connection
    conn = get_connection()
    with conn:
        ds_id = conn.execute(
            "INSERT INTO dataset_uploads(filename, original_name, file_type) VALUES ('test.csv', 'test.csv', 'csv')"
        ).lastrowid
        sid = conn.execute(
            "INSERT INTO sheets(dataset_id, name, display_name, columns_json, profile_json, row_count) VALUES (?, ?, ?, ?, ?, ?)",
            (ds_id, "Sheet1", "Test Sheet", json.dumps(["EmpID", "Rate"]), json.dumps([]), 2)
        ).lastrowid
        conn.execute(
            "INSERT INTO sheet_rows(sheet_id, row_index, data_json) VALUES (?, ?, ?)",
            (sid, 0, json.dumps({"EmpID": "E1", "Rate": "95%"}))
        )
        conn.execute(
            "INSERT INTO sheet_rows(sheet_id, row_index, data_json) VALUES (?, ?, ?)",
            (sid, 1, json.dumps({"EmpID": "E2", "Rate": "80%"}))
        )
        conn.execute(
            "INSERT INTO sheet_curated_rows(sheet_id, row_index, data_json, anomalies_json) VALUES (?, ?, ?, ?)",
            (sid, 0, json.dumps({"EmpID": "E1", "Rate": 95.0}), json.dumps([]))
        )
        conn.execute(
            "INSERT INTO sheet_curated_rows(sheet_id, row_index, data_json, anomalies_json) VALUES (?, ?, ?, ?)",
            (sid, 1, json.dumps({"EmpID": "E2", "Rate": 80.0}), json.dumps([]))
        )

    # Test derived tables endpoint
    res = client.get("/api/eda/derived-tables")
    assert res.status_code == 200
    data = res.json()
    assert "derived_tables" in data

    # Test cross-sheet correlations endpoint
    corrs_res = client.get("/api/eda/cross-sheet-correlations")
    assert corrs_res.status_code == 200
    corrs_data = corrs_res.json()
    assert "correlations" in corrs_data

    # Dual version test on seeded sheet
    raw_res = client.get(f"/api/sheets/{sid}/rows?version=raw")
    cur_res = client.get(f"/api/sheets/{sid}/rows?version=curated")
    assert raw_res.status_code == 200
    assert cur_res.status_code == 200
    assert raw_res.json()["version"] == "raw"
    assert cur_res.json()["version"] == "curated"
    assert raw_res.json()["rows"][0]["values"]["Rate"] == "95%"
    assert cur_res.json()["rows"][0]["values"]["Rate"] == 95.0


def test_adaptive_dashboard_cross_sheet_cohort_comparator():
    from app.services.adaptive_dashboard.engine import run_adaptive_dashboard
    from app.db.database import get_connection
    import json

    conn = get_connection()
    with conn:
        ds_id = conn.execute(
            "INSERT INTO dataset_uploads(filename, original_name, file_type) VALUES ('perf.csv', 'perf.csv', 'csv')"
        ).lastrowid
        sid = conn.execute(
            "INSERT INTO sheets(dataset_id, name, display_name, columns_json, profile_json, row_count) VALUES (?, ?, ?, ?, ?, ?)",
            (ds_id, "PerfSheet", "Performance", json.dumps(["EmpID", "Overtime Hours"]), json.dumps([]), 4)
        ).lastrowid
        conn.execute(
            "INSERT INTO sheet_curated_rows(sheet_id, row_index, data_json, anomalies_json) VALUES (?, ?, ?, ?)",
            (sid, 0, json.dumps({"EmpID": "E1", "Overtime Hours": 10.0}), json.dumps([]))
        )
        conn.execute(
            "INSERT INTO sheet_curated_rows(sheet_id, row_index, data_json, anomalies_json) VALUES (?, ?, ?, ?)",
            (sid, 1, json.dumps({"EmpID": "E2", "Overtime Hours": 0.0}), json.dumps([]))
        )
        # Create derived table
        dt_id = conn.execute(
            "INSERT INTO derived_tables(name, display_name, description, source_sheets_json, join_keys_json, columns_json, row_count) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("derived_test", "Test Derived", "Test description", json.dumps([sid, sid + 1]), json.dumps({}), json.dumps(["EmpID", "Overtime Hours", "Absent"]), 4)
        ).lastrowid
        conn.execute(
            "INSERT INTO derived_table_rows(derived_table_id, row_index, data_json) VALUES (?, ?, ?)",
            (dt_id, 0, json.dumps({"EmpID": "E1", "Overtime Hours": 10.0, "Absent": 2.0}))
        )
        conn.execute(
            "INSERT INTO derived_table_rows(derived_table_id, row_index, data_json) VALUES (?, ?, ?)",
            (dt_id, 1, json.dumps({"EmpID": "E2", "Overtime Hours": 15.0, "Absent": 2.0}))
        )
        conn.execute(
            "INSERT INTO derived_table_rows(derived_table_id, row_index, data_json) VALUES (?, ?, ?)",
            (dt_id, 2, json.dumps({"EmpID": "E3", "Overtime Hours": 0.0, "Absent": 5.0}))
        )
        conn.execute(
            "INSERT INTO derived_table_rows(derived_table_id, row_index, data_json) VALUES (?, ?, ?)",
            (dt_id, 3, json.dumps({"EmpID": "E4", "Overtime Hours": 0.0, "Absent": 5.0}))
        )
        # Insert eda report
        conn.execute(
            "INSERT INTO eda_reports(sheet_id, dataset_id, health_score, report_json) VALUES (?, ?, ?, ?)",
            (sid, ds_id, 100, json.dumps({
                "cross_sheet_intelligence": {
                    "correlations": [{
                        "left_sheet_id": sid,
                        "left_metric": "Overtime Hours",
                        "right_sheet_id": sid + 1,
                        "right_metric": "Absent",
                        "pearson_r": -0.85
                    }]
                }
            }))
        )

    resp = run_adaptive_dashboard(sid)
    assert resp.quaternary_element is not None
    assert resp.quaternary_element.kind == "cohort_comparator"
    assert "Overtime Hours" in resp.quaternary_element.title
    assert "Absent" in resp.quaternary_element.title
    assert resp.quaternary_element.glance.value == -60.0
