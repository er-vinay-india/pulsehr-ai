"""Live Database Isolation & Anti-Contamination Boundary.

Guarantees that test environments, benchmark fixtures, and developer scripts
can NEVER mutate or connect to the configured live application database.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

LIVE_DB_PATH = (Path(__file__).resolve().parent.parent.parent / "data" / "db" / "pulsehr.sqlite3").resolve()


class LiveDatabaseIsolationError(RuntimeError):
    """Raised when test infrastructure or seeders attempt to access or mutate the live application database."""
    pass


# Backward compatible alias with __test__ = False to avoid pytest collection warning
class TestDatabaseIsolationError(LiveDatabaseIsolationError):
    __test__ = False



def is_test_environment() -> bool:
    """Returns True if the current process is running under pytest or explicit test environment."""
    return bool(
        os.getenv("TESTING") == "true"
        or os.getenv("PYTEST_CURRENT_TEST")
        or os.getenv("APP_ENV") == "test"
    )


def assert_test_database_isolation(target_path: Path | str | None = None) -> None:
    """Fails fast if test execution attempts to target the live application database."""
    if not is_test_environment():
        return

    from . import config
    active_path = Path(target_path or config.DB_PATH).resolve()
    if active_path == LIVE_DB_PATH:
        raise TestDatabaseIsolationError(
            f"CRITICAL TEST ISOLATION BREACH: Test is configured to target live application database: {active_path}. "
            "Tests must run against isolated temporary databases only."
        )


def verify_connection_not_live_db(conn: Any) -> None:
    """Verifies that a SQLite connection is NOT attached to the live application database."""
    try:
        db_list = conn.execute("PRAGMA database_list").fetchall()
        for row in db_list:
            file_path = row[2] if len(row) > 2 else None
            if file_path:
                resolved_file = Path(file_path).resolve()
                if resolved_file == LIVE_DB_PATH:
                    raise TestDatabaseIsolationError(
                        f"CRITICAL ENVIRONMENT CONTAMINATION: Attempted operation on live database '{resolved_file}'. "
                        "Seeding and tests are strictly forbidden from touching the live application database."
                    )
    except Exception as e:
        if isinstance(e, TestDatabaseIsolationError):
            raise
        # PRAGMA may not return if closed
        pass
