"""
Migration 0001: Baseline schema initialization.
Applies baseline tables from schema.sql if not already present.
"""
from __future__ import annotations

import sqlite3
from app.core import config


def upgrade(conn: sqlite3.Connection) -> None:
    # Check if baseline tables already exist
    has_du = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='dataset_uploads'"
    ).fetchone()

    if not has_du:
        conn.executescript(config.SCHEMA_PATH.read_text(encoding="utf-8"))
