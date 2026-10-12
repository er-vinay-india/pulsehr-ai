"""
Migration 0006: Add Parquet storage paths, content hashes, and dashboard cache table.
"""
from __future__ import annotations

import sqlite3


def upgrade(conn: sqlite3.Connection) -> None:
    # Add parquet_path and content_hash to dataset_uploads
    du_cols = {r[1] for r in conn.execute("PRAGMA table_info(dataset_uploads)").fetchall()}
    if "parquet_path" not in du_cols:
        conn.execute("ALTER TABLE dataset_uploads ADD COLUMN parquet_path TEXT")
    if "content_hash" not in du_cols:
        conn.execute("ALTER TABLE dataset_uploads ADD COLUMN content_hash TEXT")

    # Add parquet_path and content_hash to sheets
    s_cols = {r[1] for r in conn.execute("PRAGMA table_info(sheets)").fetchall()}
    if "parquet_path" not in s_cols:
        conn.execute("ALTER TABLE sheets ADD COLUMN parquet_path TEXT")
    if "content_hash" not in s_cols:
        conn.execute("ALTER TABLE sheets ADD COLUMN content_hash TEXT")

    # Create deterministic dashboard cache table
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS dashboard_cache (
            cache_key TEXT PRIMARY KEY,
            dataset_id INTEGER NOT NULL,
            payload_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_dash_cache_dataset ON dashboard_cache(dataset_id)")
