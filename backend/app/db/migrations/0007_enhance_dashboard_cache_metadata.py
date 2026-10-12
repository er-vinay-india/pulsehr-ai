"""
Migration 0007: Enhance dashboard_cache table with deterministic versioning and governance metadata.
"""
from __future__ import annotations

import sqlite3


def upgrade(conn: sqlite3.Connection) -> None:
    # Ensure dashboard_cache table exists
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

    # Check and add metadata columns
    cols = {r[1] for r in conn.execute("PRAGMA table_info(dashboard_cache)").fetchall()}

    columns_to_add = [
        ("dataset_version", "INTEGER DEFAULT 1"),
        ("content_hash", "TEXT"),
        ("semantic_schema_version", "TEXT"),
        ("context_version", "TEXT"),
        ("policy_version", "TEXT"),
        ("analytics_engine_version", "TEXT"),
        ("composition_engine_version", "TEXT"),
        ("filter_hash", "TEXT DEFAULT ''"),
        ("last_accessed_at", "TIMESTAMP"),
        ("hit_count", "INTEGER DEFAULT 0"),
        ("size_bytes", "INTEGER DEFAULT 0"),
    ]

    for col_name, col_def in columns_to_add:
        if col_name not in cols:
            conn.execute(f"ALTER TABLE dashboard_cache ADD COLUMN {col_name} {col_def}")

    conn.execute("CREATE INDEX IF NOT EXISTS idx_dash_cache_dataset ON dashboard_cache(dataset_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_dash_cache_hash ON dashboard_cache(content_hash)")
