"""Every test uses an isolated database, never the running application's data."""
from pathlib import Path
import sqlite3
import pandas as pd
import pytest
from app.core import config
from app.db.database import init_db
from app.services import sheet_catalog

@pytest.fixture(autouse=True)
def isolated_workspace(request, tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'DB_PATH', tmp_path / 'db' / 'test.sqlite3')
    monkeypatch.setattr(config, 'UPLOADS_DIR', tmp_path / 'uploads')
    monkeypatch.setattr(config, 'EXPORTS_DIR', tmp_path / 'exports')
    config.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    config.EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(sheet_catalog, 'model_embeddings', lambda texts: [])

    # If marked unit and not marked db, skip disk DB initialization for maximum velocity
    if request.node.get_closest_marker("unit") and not request.node.get_closest_marker("db"):
        return

    init_db()


@pytest.fixture
def hriday_test_env(tmp_path, monkeypatch):
    """Sets up a controlled SQLite database with HR attendance data including leading-zero IDs and ties."""
    db_path = tmp_path / "hriday_test.db"

    def connection():
        conn = sqlite3.connect(db_path)
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

