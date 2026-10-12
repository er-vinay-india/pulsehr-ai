"""
Migration 0003: Add curated rows, derived tables, and EDA report tables.
"""
from __future__ import annotations

import sqlite3


def upgrade(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sheet_curated_rows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sheet_id INTEGER NOT NULL REFERENCES sheets(id) ON DELETE CASCADE,
            row_index INTEGER NOT NULL,
            data_json TEXT NOT NULL,
            anomalies_json TEXT DEFAULT '[]',
            UNIQUE(sheet_id, row_index)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS derived_tables (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            display_name TEXT NOT NULL,
            description TEXT,
            source_sheets_json TEXT NOT NULL,
            join_keys_json TEXT NOT NULL,
            columns_json TEXT NOT NULL,
            row_count INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS derived_table_rows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            derived_table_id INTEGER NOT NULL REFERENCES derived_tables(id) ON DELETE CASCADE,
            row_index INTEGER NOT NULL,
            data_json TEXT NOT NULL,
            UNIQUE(derived_table_id, row_index)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS eda_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sheet_id INTEGER REFERENCES sheets(id) ON DELETE CASCADE,
            dataset_id INTEGER REFERENCES dataset_uploads(id) ON DELETE CASCADE,
            health_score INTEGER NOT NULL,
            report_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    eda_cols = {r[1] for r in conn.execute("PRAGMA table_info(eda_reports)").fetchall()}
    if "snapshot" not in eda_cols:
        conn.execute("ALTER TABLE eda_reports ADD COLUMN snapshot TEXT")
