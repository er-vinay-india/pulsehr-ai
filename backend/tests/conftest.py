"""Every test uses an isolated database, never the running application's data."""
from pathlib import Path
import sqlite3
import socket
import pandas as pd
import pytest
from app.core import config
from app.db.database import init_db
from app.services import sheet_catalog

from app.core.db_isolation import assert_test_database_isolation, LIVE_DB_PATH

import os
import shutil
os.environ["TESTING"] = "true"
os.environ["APP_ENV"] = "test"
os.environ["HIGHVIEW_ENVIRONMENT"] = "test"

_LIVE_DB_SESSION_START_STATE = None

def get_live_db_state():
    if not LIVE_DB_PATH.exists():
        return None
    conn = sqlite3.connect(f"file:{LIVE_DB_PATH}?mode=ro", uri=True)
    try:
        try:
            import sqlite_vec
            conn.enable_load_extension(True)
            sqlite_vec.load(conn)
            conn.enable_load_extension(False)
        except Exception:
            pass

        tables = [
            r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'tabular_vectors%'"
            ).fetchall()
        ]
        tables.sort()
        state = {}
        for t in tables:
            rows = conn.execute(f"SELECT * FROM {t}").fetchall()
            state[t] = rows
        return state
    finally:
        conn.close()

def pytest_sessionstart(session):
    global _LIVE_DB_SESSION_START_STATE
    _LIVE_DB_SESSION_START_STATE = get_live_db_state()

@pytest.fixture(autouse=True)
def isolated_workspace(request, tmp_path, monkeypatch):
    test_db = tmp_path / 'db' / 'test.sqlite3'
    test_db.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(config, 'DB_PATH', test_db)
    monkeypatch.setattr(config.settings, 'DB_PATH', test_db)
    monkeypatch.setenv('DATABASE_PATH', str(test_db))
    monkeypatch.setenv('HIGHVIEW_DB_PATH', str(test_db))
    monkeypatch.setenv('TESTING', 'true')
    monkeypatch.setenv('APP_ENV', 'test')

    assert_test_database_isolation(test_db)
    assert test_db.resolve() != LIVE_DB_PATH, "CRITICAL: Test DB matches Live DB!"
    monkeypatch.setattr(config, 'UPLOADS_DIR', tmp_path / 'uploads')
    monkeypatch.setattr(config, 'EXPORTS_DIR', tmp_path / 'exports')
    monkeypatch.setattr(config, 'PRESENTATION_MEMORY_DB_PATH', tmp_path / 'db' / 'presentation_memory.sqlite3')
    config.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    config.EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(sheet_catalog, 'model_embeddings', lambda texts: [])

    # Hermetic test firewall: block unmocked connections to Ollama / model port 11434 in presentation & ingestion suites
    if "presentation" in request.node.nodeid or "ingestion" in request.node.nodeid:
        orig_connect = socket.socket.connect
        def guarded_connect(self, address):
            if isinstance(address, tuple) and len(address) >= 2 and address[1] == 11434:
                raise ConnectionRefusedError(
                    "HERMETIC TEST FIREWALL: Connection to port 11434 is blocked in test environment. "
                    "Tests must mock embedding/model HTTP requests."
                )
            return orig_connect(self, address)
        monkeypatch.setattr(socket.socket, "connect", guarded_connect)

    # If marked unit and not marked db, skip disk DB initialization for maximum velocity
    if request.node.get_closest_marker("unit") and not request.node.get_closest_marker("db"):
        return

    baseline_path = Path(__file__).resolve().parent.parent / "data" / "db_backups_safety" / "pulsehr.sqlite3.pristine_i8_3_baseline"
    if baseline_path.exists():
        shutil.copyfile(baseline_path, test_db)
    else:
        init_db()


@pytest.fixture
def hriday_test_env(tmp_path, monkeypatch):
    """Sets up a controlled SQLite database with HR attendance data including leading-zero IDs and ties."""
    db_path = tmp_path / "hriday_test.db"

    def connection(target_path=None):
        conn = sqlite3.connect(target_path or db_path)
        conn.row_factory = sqlite3.Row
        return conn

    conn = connection()
    conn.executescript((Path(__file__).parents[1] / "app/db/schema.sql").read_text())

    # Dataset 1: WFO July Attendance
    conn.execute(
        "INSERT INTO dataset_uploads(id, filename, original_name, file_type) VALUES (1, 'wfo_july.csv', 'wfo_july.csv', 'csv')"
    )
    # Dataset 2: Unrelated Sales dataset
    conn.execute(
        "INSERT INTO dataset_uploads(id, filename, original_name, file_type) VALUES (2, 'sales.csv', 'sales.csv', 'csv')"
    )
    conn.commit()
    conn.close()

    # Generate 15 employee records for Dataset 1
    # Include leading zero ID '0012', 0 attendance days, ties, missing attendance
    df_hr = pd.DataFrame({
        "Full Name": [f"Employee {i}" for i in range(1, 16)],
        "ID": ["0012", "0034", "LB101", "LB102", "LB103", "E06", "E07", "E08", "E09", "E10", "E11", "E12", "E13", "E14", "E15"],
        "Department": ["Engineering", "Engineering", "Operations", "Operations", "Sales", "Sales", "HR", "HR", "IT", "IT", "Support", "Support", "Finance", "Finance", "Legal"],
        "1st to 5th July": [0, 0, 1, 2, 3, 4, 4, 5, 2, 3, 4, 5, 1, 3, None],
        "Leaves(1st to 5th July)": [0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
        "6th to 12th July": [0, 1, 1, 1, 3, 4, 5, 5, 3, 3, 4, 5, 2, 4, None],
        "Total Attendance": [0, 1, 2, 3, 6, 8, 9, 10, 5, 6, 8, 10, 3, 7, None]
    })
    df_hr.to_csv(tmp_path / "wfo_july.csv", index=False)

    df_sales = pd.DataFrame({
        "Store": ["Store A", "Store B"],
        "Revenue": [1000, 2000]
    })
    df_sales.to_csv(tmp_path / "sales.csv", index=False)

    conn = connection()
    sheet_catalog.insert_sheets(
        conn,
        1,
        sheet_catalog.prepare_sheets(sheet_catalog.read_sheets(tmp_path / "wfo_july.csv"), "wfo_july.csv", embed=False)
    )
    sheet_catalog.insert_sheets(
        conn,
        2,
        sheet_catalog.prepare_sheets(sheet_catalog.read_sheets(tmp_path / "sales.csv"), "sales.csv", embed=False)
    )
    conn.commit()
    conn.close()

    from app.db import database
    from app.routers import copilot as copilot_router
    from app.services import copilot_query_planner as planner_service
    from app.services.copilot import council_evidence_service
    from app.services import rag_service
    from app.services import hybrid_retrieval

    monkeypatch.setattr(database, 'get_connection', connection)
    monkeypatch.setattr(sheet_catalog, 'get_connection', connection)
    monkeypatch.setattr(copilot_router, 'get_connection', connection)
    monkeypatch.setattr(planner_service, 'get_connection', connection)
    monkeypatch.setattr(council_evidence_service, 'get_connection', connection)
    monkeypatch.setattr(rag_service, 'get_connection', connection)
    monkeypatch.setattr(hybrid_retrieval, 'get_connection', connection)

    return {"db_path": db_path, "dataset_id": 1, "sheet_id": 1}
