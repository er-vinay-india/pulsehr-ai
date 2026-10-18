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
    """Verifies that the live application database has not been polluted with test or benchmark fixtures."""
    conn = sqlite3.connect(LIVE_DB_PATH)
    try:
        # Benchmark and test fixture IDs must NEVER leak into the live user database
        benchmark_ids = [99770, 99771, 99772]
        polluted_count = conn.execute(
            f"SELECT COUNT(*) FROM dataset_uploads WHERE id IN ({','.join(map(str, benchmark_ids))})"
        ).fetchone()[0]
        assert polluted_count == 0
    finally:
        conn.close()


def test_firewall_blocks_test_mutation_against_live_instance(monkeypatch):
    """TestEnvironmentFirewallMiddleware returns 403 when test mutation targets live instance."""
    from fastapi.testclient import TestClient
    from app.main import app

    # Simulate running on live instance (not test mode)
    monkeypatch.setattr(config, "ENVIRONMENT", "development")
    monkeypatch.setattr(config, "DB_PATH", LIVE_DB_PATH)

    client = TestClient(app)
    res = client.delete(
        "/api/upload/datasets",
        headers={"X-HighView-Test-Run": "probe-live-rejection"}
    )
    assert res.status_code == 403
    body = res.json()
    assert body["error"] == "FORBIDDEN_TEST_MUTATION_ON_LIVE_INSTANCE"


def test_firewall_allows_test_mutation_on_isolated_instance(monkeypatch, tmp_path):
    """TestEnvironmentFirewallMiddleware permits test mutations on isolated ephemeral test backend."""
    from fastapi.testclient import TestClient
    from app.main import app

    isolated_db = tmp_path / "firewall_test.sqlite3"
    monkeypatch.setattr(config, "ENVIRONMENT", "test")
    monkeypatch.setattr(config, "DB_PATH", isolated_db)

    # Schema and migrations must be present in isolated_db
    from app.db.database import get_connection, init_db
    conn = get_connection(isolated_db)
    init_db(conn)
    conn.close()

    client = TestClient(app)
    res = client.delete(
        "/api/upload/datasets",
        headers={"X-HighView-Test-Run": "probe-isolated-allowed"}
    )
    assert res.status_code == 200
    body = res.json()
    assert body["orphan_check"] == "PASS"

