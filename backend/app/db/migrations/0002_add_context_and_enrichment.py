"""
Migration 0002: Add analysis context, display name, enrichment, and geometry columns.
"""
from __future__ import annotations

import sqlite3


def upgrade(conn: sqlite3.Connection) -> None:
    du_cols = {r[1] for r in conn.execute("PRAGMA table_info(dataset_uploads)").fetchall()}
    if "display_name" not in du_cols:
        conn.execute("ALTER TABLE dataset_uploads ADD COLUMN display_name TEXT")
    if "analysis_context_json" not in du_cols:
        conn.execute("ALTER TABLE dataset_uploads ADD COLUMN analysis_context_json TEXT")
    if "enrichment_json" not in du_cols:
        conn.execute("ALTER TABLE dataset_uploads ADD COLUMN enrichment_json TEXT")

    s_cols = {r[1] for r in conn.execute("PRAGMA table_info(sheets)").fetchall()}
    if "display_name" not in s_cols:
        conn.execute("ALTER TABLE sheets ADD COLUMN display_name TEXT")
    if "analysis_context_json" not in s_cols:
        conn.execute("ALTER TABLE sheets ADD COLUMN analysis_context_json TEXT")
    if "enrichment_json" not in s_cols:
        conn.execute("ALTER TABLE sheets ADD COLUMN enrichment_json TEXT")
    if "header_geometry_json" not in s_cols:
        conn.execute("ALTER TABLE sheets ADD COLUMN header_geometry_json TEXT")
