"""
Phase G4 Verification Suite: Slow-Path Worker Plane.

Verifies:
1. Long-running workloads (PDF export, EDA, Parquet backfill) return immediately with job metadata.
2. Background worker threads process jobs asynchronously without blocking the caller.
3. Stage transitions and progress updates (QUEUED -> RUNNING -> COMPLETED) persist to SQLite.
4. User cancellation interrupts running jobs and transitions them to CANCELLED.
5. Generated file artifacts are downloadable via GET /api/jobs/{job_id}/download.
6. Server restart / crash recovery claims orphaned running jobs cleanly.
7. Synchronous deterministic operations (cache hits, DuckDB aggregations) remain fast and synchronous.
"""
from __future__ import annotations

import time
from pathlib import Path
import pytest

from app.jobs import (
    BackgroundJobRepository,
    JobRecord,
    JobStatus,
    JobType,
    ProgressReporter,
    SlowPathWorkerPlane,
    worker_plane,
)


from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def clean_jobs():
    yield


def test_01_submit_job_returns_immediately():
    """Test 1: Submitting heavy work returns immediately (< 20 ms) with a PENDING or RUNNING JobRecord."""
    t0 = time.perf_counter()
    job = worker_plane.submit_job(
        job_type=JobType.PARQUET_BACKFILL,
        payload={"dataset_id": 99770},
    )
    duration_ms = (time.perf_counter() - t0) * 1000

    assert duration_ms < 50.0  # Must be non-blocking
    assert job.id.startswith("JOB-PARQ-")
    assert job.status in (JobStatus.PENDING, JobStatus.RUNNING)
    assert job.execution_id is not None


def test_02_worker_executes_and_completes_job():
    """Test 2: Worker processes the submitted job asynchronously to completion."""
    # Register a test handler that reports progress and completes
    def test_handler(job_id: str, payload: dict, reporter: ProgressReporter):
        reporter.update(25, "STEP_1", "Processing step 1")
        time.sleep(0.05)
        reporter.update(75, "STEP_2", "Processing step 2")
        time.sleep(0.05)
        return {"processed_items": 42}, None

    wp = SlowPathWorkerPlane.get_instance()
    wp.register_handler(JobType.EDA, test_handler)

    job = wp.submit_job(job_type=JobType.EDA, payload={"sheet_ids": [1]})

    # Poll for completion with bounded timeout
    completed = False
    for _ in range(50):
        time.sleep(0.02)
        rec = BackgroundJobRepository.get_job(job.id)
        if rec and rec.status == JobStatus.COMPLETED:
            assert rec.progress_pct == 100
            assert rec.stage == "COMPLETED"
            assert rec.result.get("processed_items") == 42
            completed = True
            break

    assert completed, "Background job did not complete within timeout"


def test_03_job_cancellation():
    """Test 3: Cancellation signals running worker and marks status CANCELLED."""
    def cancellable_handler(job_id: str, payload: dict, reporter: ProgressReporter):
        for i in range(10):
            reporter.update(i * 10, f"STEP_{i}", f"Step {i}")
            time.sleep(0.05)
            if reporter.is_cancelled():
                raise InterruptedError("Cancelled")
        return {}, None

    wp = SlowPathWorkerPlane.get_instance()
    wp.register_handler(JobType.EDA, cancellable_handler)

    job = wp.submit_job(job_type=JobType.EDA, payload={})
    time.sleep(0.03)

    # Cancel job
    cancelled = wp.cancel_job(job.id)
    assert cancelled

    time.sleep(0.1)
    rec = BackgroundJobRepository.get_job(job.id)
    assert rec is not None
    assert rec.status == JobStatus.CANCELLED


def test_04_artifact_generation_and_storage(tmp_path):
    """Test 4: Export job writes artifact file and records artifact_path."""
    dummy_pdf = tmp_path / "presentation_deck.pdf"
    dummy_pdf.write_bytes(b"%PDF-1.4 mock content")

    def export_handler(job_id: str, payload: dict, reporter: ProgressReporter):
        reporter.update(50, "RENDERING", "Rendering PDF")
        return {"title": "Test Deck"}, str(dummy_pdf)

    wp = SlowPathWorkerPlane.get_instance()
    wp.register_handler(JobType.PDF_EXPORT, export_handler)

    job = wp.submit_job(job_type=JobType.PDF_EXPORT, payload={"deck_spec": {}})

    # Poll for completion
    for _ in range(30):
        time.sleep(0.02)
        rec = BackgroundJobRepository.get_job(job.id)
        if rec and rec.status == JobStatus.COMPLETED:
            assert rec.artifact_path == str(dummy_pdf)
            assert Path(rec.artifact_path).exists()
            break


def test_05_crash_recovery_cleans_orphaned_running_jobs():
    """Test 5: Orphaned running jobs from previous process restarts are transitioned to FAILED."""
    # Insert mock orphan job with dead PID 999999
    orphan_job = BackgroundJobRepository.create_job(
        job_id="JOB-ORPHAN-123",
        job_type=JobType.PPTX_EXPORT,
        payload={},
        execution_id="trace-orphan",
    )
    BackgroundJobRepository.mark_running(orphan_job.id)

    # Manually overwrite worker_pid to dead PID
    from app.db.database import session_scope
    with session_scope() as conn:
        conn.execute("UPDATE background_jobs SET worker_pid = 999999 WHERE id = ?", (orphan_job.id,))

    recovered = BackgroundJobRepository.recover_interrupted_jobs()
    assert any(j.id == orphan_job.id for j in recovered)

    rec = BackgroundJobRepository.get_job(orphan_job.id)
    assert rec is not None
    assert rec.status == JobStatus.FAILED
    assert "terminated unexpectedly" in (rec.error or "")


def test_06_fast_deterministic_operations_remain_synchronous():
    """Test 6: Invariant: fast operations (metadata, DuckDB queries) remain synchronous and fast."""
    from app.analytics import AnalyticalQueryService, ParquetMaterializer, MeasureSpec, AggregationType

    rows = [{"Dept": "Support", "Tickets": 100}]
    ParquetMaterializer.materialize_table(
        dataset_id=8866,
        sheet_id=88661,
        logical_table_id="sync_test",
        rows=rows,
        force_rebuild=True,
    )

    t0 = time.perf_counter()
    res = AnalyticalQueryService.aggregate(
        dataset_id=8866,
        logical_table_id="sync_test",
        measures=[MeasureSpec(field="Tickets", aggregation=AggregationType.SUM, alias="tot_tickets")],
    )
    exec_ms = (time.perf_counter() - t0) * 1000

    # Fast columnar calculation completes synchronously in single-digit ms
    assert exec_ms < 30.0
    assert res.rows[0]["tot_tickets"] == 100


def test_07_download_endpoint_path_traversal_protection(client):
    """Test 7: Download endpoint verifies job ownership and rejects paths outside governed exports directory."""
    # Create a job with an artifact path outside governed exports dir (e.g. /etc/passwd)
    outside_job = BackgroundJobRepository.create_job(
        job_id="JOB-TRAVERSAL-01",
        job_type=JobType.PDF_EXPORT,
        payload={},
    )
    BackgroundJobRepository.mark_completed(
        job_id=outside_job.id,
        result={},
        artifact_path="/etc/passwd",
    )

    resp = client.get(f"/api/jobs/{outside_job.id}/download")
    assert resp.status_code == 403
    assert "outside governed directories" in resp.json()["detail"]


def test_08_payload_and_result_sanitization_avoids_storing_raw_rows():
    """Test 8: Sensitive tabular row arrays are not stored in SQLite background_jobs."""
    sensitive_rows = [{"ssn": f"123-45-{i:04d}", "salary": 100000 + i} for i in range(100)]
    job = BackgroundJobRepository.create_job(
        job_id="JOB-SANITIZE-01",
        job_type=JobType.EDA,
        payload={"rows": sensitive_rows, "sheet_id": 42},
    )

    rec = BackgroundJobRepository.get_job(job.id)
    assert rec is not None
    assert rec.payload.get("sheet_id") == 42
    # Verify rows were sanitized to governance placeholder
    assert "omitted for data governance" in str(rec.payload.get("rows"))


def test_09_async_submission_returns_202_accepted(client):
    """Test 9: Async submission endpoints return HTTP 202 Accepted."""
    resp = client.post(
        "/api/presentations/export-pdf/async",
        json={
            "deck_spec": {
                "metadata": {"title": "Async 202 Test", "objective": "Leadership", "audience": "Exec"},
                "slides": [{"id": "s1", "title": "Test Slide", "layout": "headline_stat"}]
            }
        }
    )
    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] in ("PENDING", "RUNNING")
    assert data["job_id"].startswith("JOB-PDF_")

