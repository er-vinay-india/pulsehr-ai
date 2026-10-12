"""Unit and integration tests for Phase G1: Stability Foundation & DB Governance.

Tests:
1. Settings configuration & backward-compatible module exports.
2. CORS origin governance.
3. Database migration runner (schema_migrations, sequential execution, idempotency, checksums).
4. Connection lifecycle management via session_scope & get_db (commit, rollback, guaranteed close).
"""
import os
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch
import pytest

from app.core import config
from app.core.config import HighviewSettings
from app.db.database import get_connection, session_scope, init_db
from app.db.session import get_db
from app.db.migration_runner import (
    run_migrations,
    get_migration_files,
    get_applied_versions,
)


def test_highview_settings_defaults_and_exports():
    """Verify pydantic-settings defaults and module-level export compatibility."""
    settings = HighviewSettings()
    assert settings.PROJECT_NAME == "HighView"
    assert "http://localhost:5173" in settings.ALLOWED_ORIGINS
    assert "http://localhost:5175" in settings.ALLOWED_ORIGINS
    assert settings.PORT == 8020

    # Module-level exported attributes match settings
    assert config.PROJECT_NAME == settings.PROJECT_NAME
    assert config.ALLOWED_ORIGINS == settings.ALLOWED_ORIGINS
    assert settings.DB_PATH.name == "pulsehr.sqlite3"
    assert config.PARQUET_STORAGE_DIR == settings.PARQUET_STORAGE_DIR


def test_highview_settings_cors_env_parsing():
    """Verify custom comma-separated CORS origins from environment."""
    with patch.dict(os.environ, {"ALLOWED_ORIGINS": "https://example.com,https://app.highview.ai"}):
        custom_settings = HighviewSettings()
        assert "https://example.com" in custom_settings.ALLOWED_ORIGINS
        assert "https://app.highview.ai" in custom_settings.ALLOWED_ORIGINS


def test_migration_discovery():
    """Verify that all migrations 0001 through 0006 are discovered in order."""
    migrations = get_migration_files()
    assert len(migrations) >= 6
    versions = [m.version for m in migrations]
    assert versions[:6] == [1, 2, 3, 4, 5, 6]
    for m in migrations:
        assert m.checksum
        assert len(m.checksum) == 16


def test_migration_runner_on_clean_db():
    """Verify running migrations on a completely empty SQLite database."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        test_db = Path(tmp_dir) / "test_migration.db"
        conn = get_connection(test_db)
        try:
            applied = run_migrations(conn)
            assert applied >= 6

            # Verify schema_migrations table
            cur = conn.cursor()
            cur.execute("SELECT version, name FROM schema_migrations ORDER BY version ASC")
            rows = cur.fetchall()
            versions = [r[0] for r in rows]
            assert 1 in versions
            assert 6 in versions

            # Verify baseline tables exist
            tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
            assert "dataset_uploads" in tables
            assert "sheets" in tables
            assert "schema_migrations" in tables
            assert "dashboard_cache" in tables
            assert "derived_tables" in tables

            # Verify migration 0006 columns on sheets
            sheet_cols = [r[1] for r in cur.execute("PRAGMA table_info(sheets)").fetchall()]
            assert "parquet_path" in sheet_cols
            assert "content_hash" in sheet_cols

            # Verify idempotency: running again should apply 0 migrations
            applied_second = run_migrations(conn)
            assert applied_second == 0
        finally:
            conn.close()


def test_session_scope_lifecycle_commits_and_closes():
    """Verify session_scope commits changes and strictly closes connection handle."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        test_db = Path(tmp_dir) / "test_lifecycle.db"
        
        # Initialize schema
        init_db_conn = get_connection(test_db)
        try:
            run_migrations(init_db_conn)
        finally:
            init_db_conn.close()

        captured_conn = None
        with session_scope(test_db) as conn:
            captured_conn = conn
            conn.execute(
                "INSERT INTO dataset_uploads (filename, original_name, row_count, file_type) VALUES (?, ?, ?, ?)",
                ("test.csv", "Test", 10, "csv"),
            )

        # Connection must be closed
        assert captured_conn is not None
        with pytest.raises(sqlite3.ProgrammingError, match="Cannot operate on a closed database"):
            captured_conn.execute("SELECT 1")

        # Verify data persisted via new session
        with session_scope(test_db) as conn2:
            row = conn2.execute("SELECT filename FROM dataset_uploads WHERE filename = 'test.csv'").fetchone()
            assert row is not None
            assert row["filename"] == "test.csv"


def test_session_scope_lifecycle_rollback_on_exception():
    """Verify session_scope rolls back changes when exception occurs, and closes."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        test_db = Path(tmp_dir) / "test_rollback.db"
        
        init_db_conn = get_connection(test_db)
        try:
            run_migrations(init_db_conn)
        finally:
            init_db_conn.close()

        captured_conn = None
        with pytest.raises(RuntimeError, match="Simulated failure"):
            with session_scope(test_db) as conn:
                captured_conn = conn
                conn.execute(
                    "INSERT INTO dataset_uploads (filename, original_name, row_count, file_type) VALUES (?, ?, ?, ?)",
                    ("fail.csv", "Fail", 5, "csv"),
                )
                raise RuntimeError("Simulated failure")

        # Connection must be closed
        assert captured_conn is not None
        with pytest.raises(sqlite3.ProgrammingError, match="Cannot operate on a closed database"):
            captured_conn.execute("SELECT 1")

        # Verify row was NOT inserted due to rollback
        with session_scope(test_db) as conn2:
            row = conn2.execute("SELECT filename FROM dataset_uploads WHERE filename = 'fail.csv'").fetchone()
            assert row is None


def test_get_db_dependency_lifecycle():
    """Verify FastAPI get_db dependency yields connection and cleans up."""
    gen = get_db()
    conn = next(gen)
    assert isinstance(conn, sqlite3.Connection)
    # Perform a query
    res = conn.execute("SELECT 1").fetchone()
    assert res[0] == 1
    # Exhaust generator (simulates request exit)
    with pytest.raises(StopIteration):
        next(gen)
    # Connection should now be closed
    with pytest.raises(sqlite3.ProgrammingError, match="Cannot operate on a closed database"):
        conn.execute("SELECT 1")
