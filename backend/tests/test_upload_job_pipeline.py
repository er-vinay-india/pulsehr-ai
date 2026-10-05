import io
import time
from fastapi.testclient import TestClient

from app.main import app
from app.services.ingestion_job_manager import IngestionJobManager, ingestion_job_manager


def test_ingestion_job_manager_lifecycle():
    mgr = IngestionJobManager()
    jid = mgr.create_job(filename="test.csv", file_size_bytes=1024)
    assert jid is not None

    job = mgr.get_job(jid)
    assert job["status"] == "queued"
    assert job["filename"] == "test.csv"
    assert job["step"] == 0
    assert job["percentage"] == 0

    # Test subscriber queue
    sub_q = mgr.subscribe(jid)
    init_event = sub_q.get(timeout=1.0)
    assert init_event["job_id"] == jid

    mgr.update_progress(jid, step=3, message="Sanitizing data...")
    step3_event = sub_q.get(timeout=1.0)
    assert step3_event["step"] == 3
    assert step3_event["status"] == "running"
    assert step3_event["percentage"] == 30

    mgr.complete_job(jid, dataset_id=42, result={"test": "data"})
    done_event = sub_q.get(timeout=1.0)
    assert done_event["status"] == "completed"
    assert done_event["step"] == 10
    assert done_event["percentage"] == 100
    assert done_event["dataset_id"] == 42
    assert done_event["result"] == {"test": "data"}

    mgr.unsubscribe(jid, sub_q)

    # Test failure lifecycle
    jid_err = mgr.create_job(filename="bad.csv")
    mgr.fail_job(jid_err, "Corrupt file header")
    err_job = mgr.get_job(jid_err)
    assert err_job["status"] == "failed"
    assert "Corrupt file header" in err_job["error"]


def test_upload_file_sync_mode_backward_compatible():
    client = TestClient(app)
    csv_content = b"emp_id,full_name,department,salary\nE101,Alice,Engineering,$120000\nE102,Bob,Product,$110000\n"
    res = client.post(
        "/api/upload/file",
        files={"file": ("sync_test.csv", csv_content, "text/csv")},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "job_id" in data
    assert "dataset_id" in data
    assert data["total_rows"] == 2
    from app.db.database import get_connection
    with get_connection() as conn:
        sheets = conn.execute('SELECT id FROM sheets WHERE dataset_id=? ORDER BY id', (data['dataset_id'],)).fetchall()
    assert data['sheet_ids'] == [s['id'] for s in sheets]
    assert data['sheets']  # Existing sheet-name contract remains available.

    # Verify job manager was populated and finalized
    job = ingestion_job_manager.get_job(data["job_id"])
    assert job is not None
    assert job["status"] == "completed"
    assert job["step"] == 10


def test_upload_file_async_mode_and_polling():
    client = TestClient(app)
    csv_content = b"emp_id,full_name,department,salary\nE201,Carol,HR,$95000\nE202,Dave,Design,$90000\n"
    res = client.post(
        "/api/upload/file?async_mode=true",
        files={"file": ("async_test.csv", csv_content, "text/csv")},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "queued"
    assert "job_id" in data
    job_id = data["job_id"]

    # Poll job status until completed
    max_wait = 15.0
    start = time.time()
    final_job = None
    while time.time() - start < max_wait:
        poll_res = client.get(f"/api/upload/jobs/{job_id}")
        assert poll_res.status_code == 200
        job_data = poll_res.json()
        if job_data["status"] in ("completed", "failed"):
            final_job = job_data
            break
        time.sleep(0.1)

    assert final_job is not None
    assert final_job["status"] == "completed"
    assert final_job["step"] == 10
    assert final_job["percentage"] == 100
    assert final_job["result"] is not None
    assert final_job["result"]["total_rows"] == 2


def test_upload_job_nonexistent_returns_404():
    client = TestClient(app)
    res = client.get("/api/upload/jobs/nonexistent_id_12345")
    assert res.status_code == 404
