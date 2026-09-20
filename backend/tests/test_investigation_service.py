"""Tests for Universal Contextual Investigation Service."""

import json
import pytest
from app.db.database import get_connection
from app.services.investigation_service import run_contextual_investigation


def test_investigate_empty_workspace():
    conn = get_connection()
    try:
        # With empty sheets table
        conn.execute("DELETE FROM sheet_rows")
        conn.execute("DELETE FROM sheets")
        conn.commit()

        res = run_contextual_investigation(conn, entity_type="department", target_id="Engineering")
        assert res["available"] is False
        assert "No workspace sheets found" in res["message"]
    finally:
        conn.close()


def test_investigate_department_evidence():
    conn = get_connection()
    try:
        d_id = conn.execute(
            "INSERT INTO dataset_uploads(filename, original_name, file_type) VALUES ('dept_test.csv', 'dept_test.csv', 'csv')"
        ).lastrowid
        s_id = conn.execute(
            "INSERT INTO sheets(dataset_id, name, columns_json, profile_json, row_count) VALUES (?, ?, ?, ?, ?)",
            (d_id, "Department Roster", json.dumps(["Employee Name", "Department", "Overtime Hours"]), "[]", 4)
        ).lastrowid

        rows = [
            {"Employee Name": "Alice Smith", "Department": "Engineering", "Overtime Hours": 45.0},
            {"Employee Name": "Bob Jones", "Department": "Engineering", "Overtime Hours": 35.0},
            {"Employee Name": "Charlie Brown", "Department": "Marketing", "Overtime Hours": 10.0},
            {"Employee Name": "Dana White", "Department": "Marketing", "Overtime Hours": 15.0},
        ]
        for idx, r in enumerate(rows):
            conn.execute(
                "INSERT INTO sheet_rows(sheet_id, row_index, data_json) VALUES (?, ?, ?)",
                (s_id, idx, json.dumps(r))
            )
        conn.commit()

        # Run investigation for Engineering Overtime
        report = run_contextual_investigation(
            conn, entity_type="department", target_id="Engineering", metric="Overtime Hours", sheet_id=s_id
        )

        assert report["available"] is True
        assert report["investigation_type"] == "department"
        assert report["target"] == "Engineering"

        # Observation
        obs = report["observation"]
        assert "Engineering" in obs["headline"]
        assert "40.0 hrs" in obs["observed_value"]  # Mean of 45 and 35
        assert "2 recorded staff" in obs["population_count"]

        # Methodology
        meth = report["methodology"]
        assert "Mean(Overtime Hours)" in meth["formula"]
        assert len(meth["steps"]) >= 3

        # Breakdown
        breakdown = report["timelines_and_breakdowns"]
        assert breakdown["title"] == "Staff Breakdown within Engineering"
        assert len(breakdown["items"]) == 2
        assert breakdown["items"][0]["name"] == "Alice Smith"
        assert breakdown["items"][0]["value"] == 45.0

        # Source records
        assert len(report["source_records"]) == 2
        assert report["source_records"][0]["data"]["Department"] == "Engineering"

        # Practical HR questions
        assert len(report["practical_hr_questions"]) >= 2
        assert any("Engineering" in q for q in report["practical_hr_questions"])

        # Limitations
        assert len(report["limitations_and_uncertainty"]) >= 1
    finally:
        conn.close()


def test_investigate_individual_evidence_spells_and_continuity():
    conn = get_connection()
    try:
        d_id = conn.execute(
            "INSERT INTO dataset_uploads(filename, original_name, file_type) VALUES ('ind_test.csv', 'ind_test.csv', 'csv')"
        ).lastrowid
        s_id = conn.execute(
            "INSERT INTO sheets(dataset_id, name, columns_json, profile_json, row_count) VALUES (?, ?, ?, ?, ?)",
            (d_id, "Absence Summary", json.dumps(["Employee ID", "Employee Name", "Department", "Days Absent"]), "[]", 2)
        ).lastrowid

        rows = [
            {"Employee ID": "EMP-101", "Employee Name": "Elena Rostova", "Department": "Operations", "Days Absent": 12},
            {"Employee ID": "EMP-102", "Employee Name": "Frank Miller", "Department": "Operations", "Days Absent": 3},
        ]
        for idx, r in enumerate(rows):
            conn.execute(
                "INSERT INTO sheet_rows(sheet_id, row_index, data_json) VALUES (?, ?, ?)",
                (s_id, idx, json.dumps(r))
            )
        conn.commit()

        report = run_contextual_investigation(
            conn, entity_type="employee", target_id="Elena Rostova", metric="Days Absent", sheet_id=s_id
        )

        assert report["available"] is True
        assert report["investigation_type"] == "individual"
        assert report["target"] == "Elena Rostova"
        assert report["employee_code"] == "EMP-101"

        # Factual episode check: must state summary aggregate vs continuous without inventing habits
        breakdown = report["timelines_and_breakdowns"]
        assert "factual_context" in breakdown
        assert "summary aggregate totals per employee" in breakdown["factual_context"]
        assert "single continuous episode or multiple intermittent instances cannot be confirmed" in breakdown["factual_context"]

        # Limitations & uncertainty
        limitations = " ".join(report["limitations_and_uncertainty"])
        assert "No personal health, motivation, or private circumstances are assumed or inferred" in limitations

        # Raw record
        assert len(report["source_records"]) == 1
        assert report["source_records"][0]["data"]["Employee Name"] == "Elena Rostova"
    finally:
        conn.close()


def test_investigate_model_group_bradford_and_9box():
    conn = get_connection()
    try:
        d_id = conn.execute(
            "INSERT INTO dataset_uploads(filename, original_name, file_type) VALUES ('model_test.csv', 'model_test.csv', 'csv')"
        ).lastrowid
        s_id = conn.execute(
            "INSERT INTO sheets(dataset_id, name, columns_json, profile_json, row_count) VALUES (?, ?, ?, ?, ?)",
            (d_id, "Workforce", json.dumps(["Employee Name", "Department", "Absence Days"]), "[]", 2)
        ).lastrowid

        conn.execute("INSERT INTO sheet_rows(sheet_id, row_index, data_json) VALUES (?, ?, ?)",
                     (s_id, 0, json.dumps({"Employee Name": "User A", "Department": "Sales", "Absence Days": 5})))
        conn.execute("INSERT INTO sheet_rows(sheet_id, row_index, data_json) VALUES (?, ?, ?)",
                     (s_id, 1, json.dumps({"Employee Name": "User B", "Department": "Sales", "Absence Days": 8})))
        conn.commit()

        # Bradford Factor investigation
        bradford_rep = run_contextual_investigation(
            conn, entity_type="model_group", target_id="Bradford Factor Disruption", metric="Absence"
        )
        assert bradford_rep["available"] is True
        assert "Bradford" in bradford_rep["target"]
        assert "B = S² × D" in bradford_rep["methodology"]["formula"]
        assert any("200" in s for s in bradford_rep["methodology"]["steps"])

        # 9-Box investigation
        box_rep = run_contextual_investigation(
            conn, entity_type="model_group", target_id="9-Box Talent & Risk Cohort", metric="Performance"
        )
        assert box_rep["available"] is True
        assert "9-Box" in box_rep["target"]
        assert "Performance Score" in box_rep["methodology"]["formula"]
    finally:
        conn.close()


def test_investigate_connected_cross_sheet_evidence():
    conn = get_connection()
    try:
        # Sheet 1: Staff Directory
        d1 = conn.execute("INSERT INTO dataset_uploads(filename, original_name, file_type) VALUES ('s1.csv', 'staff_dir.csv', 'csv')").lastrowid
        s1 = conn.execute("INSERT INTO sheets(dataset_id, name, columns_json, profile_json, row_count) VALUES (?,?,?,?,?)",
                          (d1, "Staff", json.dumps(["staff_id", "Employee Name", "Department"]), "[]", 2)).lastrowid
        conn.execute("INSERT INTO sheet_rows(sheet_id, row_index, data_json) VALUES (?,?,?)",
                     (s1, 0, json.dumps({"staff_id": "E100", "Employee Name": "Sarah Connor", "Department": "Security"})))
        conn.execute("INSERT INTO sheet_rows(sheet_id, row_index, data_json) VALUES (?,?,?)",
                     (s1, 1, json.dumps({"staff_id": "E101", "Employee Name": "John Connor", "Department": "Leadership"})))

        # Sheet 2: Incident Logs
        d2 = conn.execute("INSERT INTO dataset_uploads(filename, original_name, file_type) VALUES ('s2.csv', 'incidents.csv', 'csv')").lastrowid
        s2 = conn.execute("INSERT INTO sheets(dataset_id, name, columns_json, profile_json, row_count) VALUES (?,?,?,?,?)",
                          (d2, "Incidents", json.dumps(["staff_id", "Incident Count", "Severity"]), "[]", 2)).lastrowid
        conn.execute("INSERT INTO sheet_rows(sheet_id, row_index, data_json) VALUES (?,?,?)",
                     (s2, 0, json.dumps({"staff_id": "E100", "Incident Count": 4, "Severity": "High"})))
        conn.execute("INSERT INTO sheet_rows(sheet_id, row_index, data_json) VALUES (?,?,?)",
                     (s2, 1, json.dumps({"staff_id": "E101", "Incident Count": 1, "Severity": "Low"})))

        conn.commit()

        # Investigate individual Sarah Connor
        rep = run_contextual_investigation(
            conn, entity_type="employee", target_id="Sarah Connor", sheet_id=s1
        )
        assert rep["available"] is True
        assert rep["target"] == "Sarah Connor"
        # Check connected evidence
        assert len(rep["connected_evidence"]) >= 1
        conn_sheet = rep["connected_evidence"][0]
        assert conn_sheet["related_sheet"] == "Incidents"
        assert len(conn_sheet["sample_rows"]) >= 1
        assert conn_sheet["sample_rows"][0]["Incident Count"] == 4
    finally:
        conn.close()
