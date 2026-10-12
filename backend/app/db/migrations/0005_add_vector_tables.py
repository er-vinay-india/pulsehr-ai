"""
Migration 0005: Add tabular vector virtual table using sqlite_vec.
"""
from __future__ import annotations

import sqlite3
from app.core import config


def upgrade(conn: sqlite3.Connection) -> None:
    has_vec = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='tabular_vectors'"
    ).fetchone()
    if not has_vec:
        conn.execute(
            f"""
            CREATE VIRTUAL TABLE tabular_vectors USING vec0(
                id INTEGER PRIMARY KEY,
                embedding FLOAT[{config.EMBEDDING_DIM}] distance_metric=cosine
            )
            """
        )
