"""
Background Job Repository for Phase G4.
Provides thread-safe persistence and retrieval of job records in SQLite.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

from app.db.database import session_scope
from .contracts import JobRecord, JobStatus, JobType

logger = logging.getLogger(__name__)


class BackgroundJobRepository:
    """SQLite repository for governed background jobs."""

    @classmethod
    def create_job(
        cls,
        job_id: str,
        job_type: JobType,
        payload: dict[str, Any],
        execution_id: str | None = None,
    ) -> JobRecord:
        with session_scope() as conn:
            conn.execute(
                """
                INSERT INTO background_jobs (
                    id, job_type, status, progress_pct, stage, stage_label,
                    payload_json, worker_pid, execution_id, created_at, updated_at
                ) VALUES (?, ?, ?, 0, 'QUEUED', 'Job queued', ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                (
                    job_id,
                    job_type.value,
                    JobStatus.PENDING.value,
                    json.dumps(payload),
                    os.getpid(),
                    execution_id,
                ),
            )
        return cls.get_job(job_id)  # type: ignore

    @classmethod
    def get_job(cls, job_id: str) -> JobRecord | None:
        with session_scope() as conn:
            row = conn.execute(
                """
                SELECT id, job_type, status, progress_pct, stage, stage_label,
                       payload_json, result_json, error, artifact_path, worker_pid,
                       execution_id, created_at, started_at, completed_at, updated_at
                FROM background_jobs
                WHERE id = ?
                """,
                (job_id,),
            ).fetchone()
            if not row:
                return None

            return JobRecord(
                id=row[0],
                job_type=JobType(row[1]),
                status=JobStatus(row[2]),
                progress_pct=row[3],
                stage=row[4],
                stage_label=row[5],
                payload=json.loads(row[6] or "{}"),
                result=json.loads(row[7] or "{}"),
                error=row[8],
                artifact_path=row[9],
                worker_pid=row[10],
                execution_id=row[11],
                created_at=str(row[12]) if row[12] else None,
                started_at=str(row[13]) if row[13] else None,
                completed_at=str(row[14]) if row[14] else None,
                updated_at=str(row[15]) if row[15] else None,
            )

    @classmethod
    def mark_running(cls, job_id: str, stage: str = "INITIALIZING", stage_label: str = "Job started") -> None:
        with session_scope() as conn:
            conn.execute(
                """
                UPDATE background_jobs
                SET status = ?, stage = ?, stage_label = ?, started_at = CURRENT_TIMESTAMP,
                    worker_pid = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (JobStatus.RUNNING.value, stage, stage_label, os.getpid(), job_id),
            )

    @classmethod
    def update_progress(cls, job_id: str, progress_pct: int, stage: str, stage_label: str) -> None:
        with session_scope() as conn:
            conn.execute(
                """
                UPDATE background_jobs
                SET progress_pct = ?, stage = ?, stage_label = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND status = ?
                """,
                (progress_pct, stage, stage_label, job_id, JobStatus.RUNNING.value),
            )

    @classmethod
    def mark_completed(
        cls,
        job_id: str,
        result: dict[str, Any] | None = None,
        artifact_path: str | None = None,
    ) -> None:
        with session_scope() as conn:
            conn.execute(
                """
                UPDATE background_jobs
                SET status = ?, progress_pct = 100, stage = 'COMPLETED',
                    stage_label = 'Job completed successfully',
                    result_json = ?, artifact_path = ?, completed_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    JobStatus.COMPLETED.value,
                    json.dumps(result or {}),
                    artifact_path,
                    job_id,
                ),
            )

    @classmethod
    def mark_failed(cls, job_id: str, error: str) -> None:
        with session_scope() as conn:
            conn.execute(
                """
                UPDATE background_jobs
                SET status = ?, stage = 'FAILED', stage_label = 'Job failed',
                    error = ?, completed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (JobStatus.FAILED.value, error, job_id),
            )

    @classmethod
    def mark_cancelled(cls, job_id: str) -> None:
        with session_scope() as conn:
            conn.execute(
                """
                UPDATE background_jobs
                SET status = ?, stage = 'CANCELLED', stage_label = 'Job cancelled by user',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (JobStatus.CANCELLED.value, job_id),
            )

    @classmethod
    def list_jobs(
        cls,
        job_type: JobType | None = None,
        status: JobStatus | None = None,
        limit: int = 20,
    ) -> list[JobRecord]:
        query = """
            SELECT id, job_type, status, progress_pct, stage, stage_label,
                   payload_json, result_json, error, artifact_path, worker_pid,
                   execution_id, created_at, started_at, completed_at, updated_at
            FROM background_jobs
        """
        where = []
        params = []
        if job_type:
            where.append("job_type = ?")
            params.append(job_type.value)
        if status:
            where.append("status = ?")
            params.append(status.value)
        if where:
            query += " WHERE " + " AND ".join(where)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with session_scope() as conn:
            rows = conn.execute(query, params).fetchall()
            return [
                JobRecord(
                    id=r[0],
                    job_type=JobType(r[1]),
                    status=JobStatus(r[2]),
                    progress_pct=r[3],
                    stage=r[4],
                    stage_label=r[5],
                    payload=json.loads(r[6] or "{}"),
                    result=json.loads(r[7] or "{}"),
                    error=r[8],
                    artifact_path=r[9],
                    worker_pid=r[10],
                    execution_id=r[11],
                    created_at=str(r[12]) if r[12] else None,
                    started_at=str(r[13]) if r[13] else None,
                    completed_at=str(r[14]) if r[14] else None,
                    updated_at=str(r[15]) if r[15] else None,
                )
                for r in rows
            ]

    @classmethod
    def recover_interrupted_jobs(cls) -> list[JobRecord]:
        """Recovers jobs that were left running when a process died."""
        current_pid = os.getpid()
        with session_scope() as conn:
            rows = conn.execute(
                """
                SELECT id FROM background_jobs
                WHERE status = 'RUNNING' AND (worker_pid != ? OR worker_pid IS NULL)
                """,
                (current_pid,),
            ).fetchall()
            interrupted_ids = [r[0] for r in rows]
            for jid in interrupted_ids:
                conn.execute(
                    """
                    UPDATE background_jobs
                    SET status = 'FAILED', error = 'Worker process terminated unexpectedly',
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (jid,),
                )
        return [cls.get_job(jid) for jid in interrupted_ids if cls.get_job(jid)]  # type: ignore
