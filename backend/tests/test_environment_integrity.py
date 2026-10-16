"""Tests for Live Database Isolation & Environment Integrity (Section 4, 5, 6, 24, 27).

Verifies that:
1. Test execution is strictly forbidden from writing to or attaching the live application database.
2. ensure_benchmark_datasets_seeded rejects connections to the live pulsehr.sqlite3 database with TestDatabaseIsolationError.
3. get_connection rejects live application database paths during test execution.
4. Seeding an isolated tmp_path database succeeds with 100% fidelity.
5. The live database remains strictly preserved and unmodified.
"""
import os
import sqlite3
import pytest
from pathlib import Path

from app.core import config
from app.core.db_isolation import (
    LIVE_DB_PATH,
    TestDatabaseIsolationError,
    assert_test_database_isolation,
    verify_connection_not_live_db,
    is_test_environment,
)
from app.db.database import get_connection
from tests.fixtures.benchmark_seeder import ensure_benchmark_datasets_seeded


def test_is_test_environment_active():
    """Confirms test environment detection is active during pytest."""
    assert is_test_environment() is True


def test_assert_test_database_isolation_rejects_live_path():
    """Fails fast if target path resolves to live application DB."""
    with pytest.raises(TestDatabaseIsolationError, match="CRITICAL TEST ISOLATION BREACH"):
        assert_test_database_isolation(LIVE_DB_PATH)


def test_get_connection_rejects_live_db_in_test_env():
    """get_connection fails fast if requested with the live DB path under test mode."""
    with pytest.raises(TestDatabaseIsolationError, match="CRITICAL TEST ISOLATION BREACH"):
        get_connection(db_path=LIVE_DB_PATH)


def test_seeder_blocks_mutation_of_live_db(tmp_path):
    """ensure_benchmark_datasets_seeded rejects live DB connection with TestDatabaseIsolationError."""
    # Create a connection directly pointing to LIVE_DB_PATH
    live_conn = sqlite3.connect(LIVE_DB_PATH)
    try:
        with pytest.raises(TestDatabaseIsolationError, match="CRITICAL ENVIRONMENT CONTAMINATION"):
            ensure_benchmark_datasets_seeded(live_conn)
    finally:
        live_conn.close()


def test_seeder_succeeds_on_isolated_tmp_db(tmp_path):
    """ensure_benchmark_datasets_seeded succeeds on an isolated temporary test database."""
    tmp_db_path = tmp_path / "hermetic_test.sqlite3"
    schema_path = Path(__file__).resolve().parents[1] / "app" / "db" / "schema.sql"

    conn = sqlite3.connect(tmp_db_path)
    try:
        conn.row_factory = sqlite3.Row
        conn.executescript(schema_path.read_text())

        # Verify not live DB
        verify_connection_not_live_db(conn)

        # Seed hermetically
        ensure_benchmark_datasets_seeded(conn)

        # Assert benchmark datasets 99770, 99771, 99772 are all present
        ds_ids = [r[0] for r in conn.execute("SELECT id FROM dataset_uploads ORDER BY id").fetchall()]
        assert ds_ids == [99770, 99771, 99772]

        sheets_count = conn.execute("SELECT COUNT(*) FROM sheets").fetchone()[0]
        assert sheets_count == 4

        rows_count = conn.execute("SELECT COUNT(*) FROM sheet_rows").fetchone()[0]
        assert rows_count > 400
    finally:
        conn.close()


def test_live_db_remains_unpolluted():
    """Verifies that the live application database has not been modified."""
    conn = sqlite3.connect(LIVE_DB_PATH)
    try:
        uploads_count = conn.execute("SELECT COUNT(*) FROM dataset_uploads").fetchone()[0]
        sheets_count = conn.execute("SELECT COUNT(*) FROM sheets").fetchone()[0]
        rows_count = conn.execute("SELECT COUNT(*) FROM sheet_rows").fetchone()[0]
        assert uploads_count == 0
        assert sheets_count == 0
        assert rows_count == 0
    finally:
        conn.close()
