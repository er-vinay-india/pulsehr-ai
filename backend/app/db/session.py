"""
Database session provider & lifecycle management for HighView.
Guarantees clean connection disposal on request lifecycle exit.
"""
from __future__ import annotations

import sqlite3
from typing import Generator
from .database import session_scope


def get_db() -> Generator[sqlite3.Connection, None, None]:
    """FastAPI dependency yielding a managed SQLite connection that automatically commits and closes."""
    with session_scope() as conn:
        yield conn
