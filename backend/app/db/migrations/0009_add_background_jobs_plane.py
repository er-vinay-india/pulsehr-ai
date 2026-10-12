"""
Migration 0009: Add background_jobs table for Phase G4 Slow-Path Worker Plane.
"""
from __future__ import annotations

import sqlite3


def upgrade(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS background_jobs (
            id TEXT PRIMARY KEY,
            job_type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDING',
            progress_pct INTEGER NOT NULL DEFAULT 0,
            stage TEXT NOT NULL DEFAULT 'QUEUED',
            stage_label TEXT NOT NULL DEFAULT 'Job queued',
            payload_json TEXT NOT NULL DEFAULT '{}',
            result_json TEXT DEFAULT '{}',
            error TEXT,
            artifact_path TEXT,
            worker_pid INTEGER,
            execution_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_bg_jobs_status ON background_jobs(status)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_bg_jobs_type ON background_jobs(job_type)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_bg_jobs_created ON background_jobs(created_at)"
    )
