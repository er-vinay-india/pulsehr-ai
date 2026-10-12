"""
Deterministic, versioned SQLite migration runner for HighView.
Tracks applied migrations in `schema_migrations`.
"""
from __future__ import annotations

import hashlib
import importlib.util
import logging
import sqlite3
from pathlib import Path
from typing import NamedTuple

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


class MigrationInfo(NamedTuple):
    version: int
    name: str
    path: Path
    checksum: str


def get_migration_files() -> list[MigrationInfo]:
    """Discovers and parses migration files sorted by version."""
    MIGRATIONS_DIR.mkdir(parents=True, exist_ok=True)
    migrations: list[MigrationInfo] = []
    for file in sorted(MIGRATIONS_DIR.iterdir()):
        if file.name.startswith(".") or file.name.startswith("__") or file.name == "__pycache__":
            continue
        if file.suffix in (".py", ".sql"):
            parts = file.stem.split("_", 1)
            if parts[0].isdigit():
                version = int(parts[0])
                name = parts[1] if len(parts) > 1 else file.stem
                checksum = hashlib.sha256(file.read_bytes()).hexdigest()[:16]
                migrations.append(MigrationInfo(version, name, file, checksum))
    return sorted(migrations, key=lambda m: m.version)


def init_migration_table(conn: sqlite3.Connection) -> None:
    """Ensures migration tracking table exists."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            checksum TEXT NOT NULL
        )
        """
    )


def get_applied_versions(conn: sqlite3.Connection) -> set[int]:
    """Returns set of applied migration version numbers."""
    init_migration_table(conn)
    rows = conn.execute("SELECT version FROM schema_migrations").fetchall()
    return {r[0] for r in rows}


def apply_migration(conn: sqlite3.Connection, migration: MigrationInfo) -> None:
    """Applies a single migration file and records it in schema_migrations."""
    logger.info("Applying migration %04d: %s...", migration.version, migration.name)
    if migration.path.suffix == ".sql":
        conn.executescript(migration.path.read_text(encoding="utf-8"))
    elif migration.path.suffix == ".py":
        spec = importlib.util.spec_from_file_location(f"migration_{migration.version}", migration.path)
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if hasattr(mod, "upgrade"):
                mod.upgrade(conn)
            else:
                raise AttributeError(f"Migration {migration.path.name} missing upgrade(conn) function")
    
    conn.execute(
        "INSERT INTO schema_migrations (version, name, checksum) VALUES (?, ?, ?)",
        (migration.version, migration.name, migration.checksum),
    )


def run_migrations(conn: sqlite3.Connection) -> int:
    """Executes all pending migrations in order within a managed transaction."""
    init_migration_table(conn)
    applied = get_applied_versions(conn)
    pending = [m for m in get_migration_files() if m.version not in applied]

    if not pending:
        logger.debug("Database schema is up to date.")
        return 0

    count = 0
    for migration in pending:
        apply_migration(conn, migration)
        count += 1

    logger.info("Successfully applied %d migration(s).", count)
    return count
