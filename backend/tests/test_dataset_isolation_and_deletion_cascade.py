"""End-to-End Dataset Isolation and Bidirectional Deletion Cascade Regression Test.

Verifies:
1. CPCB -> Analyze -> Delete CPCB -> Attendance -> Assert zero CPCB tokens in Attendance dashboard.
2. Attendance -> Analyze -> Delete Attendance -> CPCB -> Assert zero Attendance tokens in CPCB dashboard.
3. Co-existence: When both datasets are loaded, sheet_relationships strictly isolates sheets within the same dataset.
4. Transactional deletion cascades all descendants and passes orphan verification with "PASS".
"""
import io
import json
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import get_connection
from app.services.dataset_deletion import delete_datasets, DatasetDeletionResult
from app.services.adaptive_dashboard.dataset_isolation_integrity import DatasetIsolationIntegrity

client = TestClient(app)

CPCB_CSV = b"""Stn Code,Sampling Date,State,City/Town/Village/Area,Location of Monitoring Station,Agency,SO2,NO2,PM10
101,2022-01-01,Jharkhand,Jharia,CPCB Station A,CPCB,15.2,28.4,140.5
102,2022-01-01,Meghalaya,Brynihat,CPCB Station B,CPCB,18.6,32.1,195.0
103,2022-01-01,Maharashtra,Mumbai,CPCB Station C,CPCB,12.0,22.0,85.0
104,2022-01-01,Delhi,Delhi,CPCB Station D,CPCB,22.1,45.3,210.0
"""

ATTENDANCE_CSV = b"""Employee ID,Employee Name,Department,Total Attendance,Approved Leaves
EMP001,John Doe,Engineering,22,2
EMP002,Jane Smith,Marketing,20,4
EMP003,Bob Wilson,Engineering,18,5
EMP004,Alice Brown,Sales,21,1
EMP005,Charlie Day,HR,19,3
EMP006,Eve Adams,Finance,23,0
"""

ENVIRONMENTAL_TOKENS = {"SO2", "NO2", "PM10", "PM2.5", "Jharia", "Brynihat", "CPCB", "AQMN"}
WORKFORCE_TOKENS = {"Attendance", "Department", "Approved Leave", "Employee", "WFO", "Policy Compliance"}


def test_cascade_delete_and_cpcb_to_attendance_isolation():
    """Test 1: Upload CPCB -> Analyze -> Delete CPCB -> Upload Attendance -> Assert zero CPCB leakage."""
    # 1. Upload CPCB dataset
    files = {"file": ("Location_data_2022.csv", io.BytesIO(CPCB_CSV), "text/csv")}
    upload_res = client.post("/api/upload/file", files=files)
    assert upload_res.status_code == 200, upload_res.text
    cpcb_id = upload_res.json()["dataset_id"]

    # 2. Run CPCB dashboard analysis
    dash_cpcb = client.get(f"/api/adaptive-dashboard/primary-element?dataset_id={cpcb_id}")
    assert dash_cpcb.status_code == 200, dash_cpcb.text
    cpcb_json_str = json.dumps(dash_cpcb.json())
    assert "SO2" in cpcb_json_str or "NO2" in cpcb_json_str, "CPCB dashboard should contain environmental metrics"

    # 3. Transactionally delete CPCB dataset
    del_result: DatasetDeletionResult = delete_datasets([cpcb_id])
    assert del_result["orphan_check"] == "PASS"
    assert del_result["deleted_count"] == 1
    assert cpcb_id in del_result["dataset_ids"]
    assert del_result["sheets_deleted"] > 0
    assert del_result["rows_deleted"] > 0

    # 4. Verify post-deletion zero orphans in database
    conn = get_connection()
    try:
        assert conn.execute("SELECT COUNT(*) FROM dataset_uploads WHERE id=?", (cpcb_id,)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM sheets WHERE dataset_id=?", (cpcb_id,)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM tabular_chunks WHERE dataset_id=?", (cpcb_id,)).fetchone()[0] == 0
    finally:
        conn.close()

    # 5. Upload Attendance dataset
    files_att = {"file": ("Attendance_Summary_Report.csv", io.BytesIO(ATTENDANCE_CSV), "text/csv")}
    upload_att = client.post("/api/upload/file", files=files_att)
    assert upload_att.status_code == 200, upload_att.text
    att_id = upload_att.json()["dataset_id"]

    # 6. Run Attendance dashboard analysis
    dash_att = client.get(f"/api/adaptive-dashboard/primary-element?dataset_id={att_id}")
    assert dash_att.status_code == 200, dash_att.text
    att_payload = dash_att.json()
    att_json_str = json.dumps(att_payload)

    # 7. Assert complete zero-token leakage of CPCB tokens
    for token in ENVIRONMENTAL_TOKENS:
        assert token not in att_json_str, f"Forbidden environmental token '{token}' leaked into Attendance dashboard"


def test_cascade_delete_and_attendance_to_cpcb_isolation():
    """Test 2: Upload Attendance -> Analyze -> Delete Attendance -> Upload CPCB -> Assert zero Attendance leakage."""
    # 1. Upload Attendance dataset
    files_att = {"file": ("Attendance_Summary_Report.csv", io.BytesIO(ATTENDANCE_CSV), "text/csv")}
    upload_att = client.post("/api/upload/file", files=files_att)
    assert upload_att.status_code == 200, upload_att.text
    att_id = upload_att.json()["dataset_id"]

    # 2. Run Attendance dashboard analysis
    dash_att = client.get(f"/api/adaptive-dashboard/primary-element?dataset_id={att_id}")
    assert dash_att.status_code == 200, dash_att.text
    att_json_str = json.dumps(dash_att.json())
    assert "Attendance" in att_json_str or "Department" in att_json_str

    # 3. Transactionally delete Attendance dataset
    del_result: DatasetDeletionResult = delete_datasets([att_id])
    assert del_result["orphan_check"] == "PASS"
    assert del_result["deleted_count"] == 1
    assert att_id in del_result["dataset_ids"]
    assert del_result["sheets_deleted"] > 0
    assert del_result["rows_deleted"] > 0

    # 4. Verify post-deletion zero orphans in database
    conn = get_connection()
    try:
        assert conn.execute("SELECT COUNT(*) FROM dataset_uploads WHERE id=?", (att_id,)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM sheets WHERE dataset_id=?", (att_id,)).fetchone()[0] == 0
    finally:
        conn.close()

    # 5. Upload CPCB dataset
    files = {"file": ("Location_data_2022.csv", io.BytesIO(CPCB_CSV), "text/csv")}
    upload_res = client.post("/api/upload/file", files=files)
    assert upload_res.status_code == 200, upload_res.text
    cpcb_id = upload_res.json()["dataset_id"]

    # 6. Run CPCB dashboard analysis
    dash_cpcb = client.get(f"/api/adaptive-dashboard/primary-element?dataset_id={cpcb_id}")
    assert dash_cpcb.status_code == 200, dash_cpcb.text
    cpcb_payload = dash_cpcb.json()
    cpcb_json_str = json.dumps(cpcb_payload)

    # 7. Assert complete zero-token leakage of Workforce tokens
    for token in WORKFORCE_TOKENS:
        assert token not in cpcb_json_str, f"Forbidden workforce token '{token}' leaked into CPCB dashboard"


def test_coexisting_datasets_relationship_isolation():
    """Test 3: Both datasets co-exist in the database. Verify sheet_relationships never cross dataset boundaries."""
    # 1. Upload both datasets
    upload_cpcb = client.post("/api/upload/file", files={"file": ("Location_data_2022.csv", io.BytesIO(CPCB_CSV), "text/csv")})
    upload_att = client.post("/api/upload/file", files={"file": ("Attendance_Summary_Report.csv", io.BytesIO(ATTENDANCE_CSV), "text/csv")})
    assert upload_cpcb.status_code == 200
    assert upload_att.status_code == 200
    cpcb_id = upload_cpcb.json()["dataset_id"]
    att_id = upload_att.json()["dataset_id"]

    conn = get_connection()
    try:
        # Check all relationships in DB
        rels = conn.execute("""
            SELECT r.id, s1.dataset_id AS left_ds, s2.dataset_id AS right_ds
            FROM sheet_relationships r
            JOIN sheets s1 ON r.left_sheet = s1.id
            JOIN sheets s2 ON r.right_sheet = s2.id
        """).fetchall()

        for r in rels:
            assert r["left_ds"] == r["right_ds"], f"Cross-dataset relationship detected: left_ds={r['left_ds']} right_ds={r['right_ds']}"

        # Test DatasetIsolationIntegrity filter directly
        mock_rels = [
            {"left_sheet_id": 1, "right_sheet_id": 2, "left_dataset_id": cpcb_id, "right_dataset_id": cpcb_id},
            {"left_sheet_id": 1, "right_sheet_id": 3, "left_dataset_id": cpcb_id, "right_dataset_id": att_id},
            {"left_sheet_id": 3, "right_sheet_id": 4, "left_dataset_id": att_id, "right_dataset_id": att_id},
        ]
        clean_cpcb_rels = DatasetIsolationIntegrity.validate_relationships(mock_rels, active_dataset_id=cpcb_id)
        assert len(clean_cpcb_rels) == 1
        assert clean_cpcb_rels[0]["left_dataset_id"] == cpcb_id and clean_cpcb_rels[0]["right_dataset_id"] == cpcb_id

        # Story purity validator rejects cross-domain vocabulary
        dirty_story = {"narrative": "Attendance dropped in Jharia due to high SO2"}
        is_valid_wf, _ = DatasetIsolationIntegrity.validate_story_purity(dirty_story, active_domain="workforce")
        assert not is_valid_wf
        is_valid_env, _ = DatasetIsolationIntegrity.validate_story_purity(dirty_story, active_domain="environmental")
        assert not is_valid_env
        clean_env_story = {"narrative": "High levels observed across monitoring stations"}
        is_valid_clean, _ = DatasetIsolationIntegrity.validate_story_purity(clean_env_story, active_domain="environmental")
        assert is_valid_clean
    finally:
        conn.close()
