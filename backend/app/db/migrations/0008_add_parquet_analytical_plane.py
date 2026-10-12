"""
Migration 0008: Add dataset_parquet_tables registry for columnar analytical plane.
"""
from __future__ import annotations

import sqlite3


def upgrade(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS dataset_parquet_tables (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dataset_id INTEGER NOT NULL,
            sheet_id INTEGER NOT NULL,
            dataset_version INTEGER NOT NULL DEFAULT 1,
            logical_table_id TEXT NOT NULL,
            parquet_path TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            schema_hash TEXT NOT NULL,
            row_count INTEGER NOT NULL DEFAULT 0,
            column_count INTEGER NOT NULL DEFAULT 0,
            uncompressed_bytes INTEGER NOT NULL DEFAULT 0,
            parquet_bytes INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'PARQUET_READY',
            schema_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(dataset_id, dataset_version, logical_table_id)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_parquet_tables_lookup ON dataset_parquet_tables(dataset_id, dataset_version)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_parquet_tables_sheet ON dataset_parquet_tables(sheet_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_parquet_tables_hash ON dataset_parquet_tables(content_hash)"
    )
