"""Hermetic Benchmark Dataset Seeder for PulseHR/HighView Test Suites.

Guarantees that benchmark datasets:
- 99770 (Workforce Attendance Summary, sheets 9967416, 9967417)
- 99771 (Walmart Store Sales, sheet 9967418)
- 99772 (CPCB Air Quality Report, sheet 9967419)

are always available in test connections, whether the physical pulsehr.sqlite3
database is fully populated, partially populated, or completely empty (zero-data state).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tests.test_phase_g5_characterization import RETAIL_RECORDS, ENVIRONMENTAL_RECORDS


FIXTURES_DIR = Path(__file__).resolve().parent / "benchmark_datasets"


def seed_workforce_from_fixture(conn) -> None:
    """Seeds Dataset 99770 and Sheets 9967416, 9967417 from WFO_July_2026_Test.xlsx."""
    from app.services.sheet_catalog import read_sheets, prepare_sheets

    wf_xlsx = FIXTURES_DIR / "WFO_July_2026_Test.xlsx"
    if not wf_xlsx.exists():
        # Fallback to Downloads if not yet in fixtures
        dl_xlsx = Path("/Users/vinayksharma/Downloads/WFO_July_2026_Test.xlsx")
        if dl_xlsx.exists():
            import shutil
            FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copy(dl_xlsx, wf_xlsx)

    if wf_xlsx.exists():
        frames = read_sheets(wf_xlsx)
        prepared = prepare_sheets(frames, "WFO_July_2026_Test.xlsx", embed=False)

        conn.execute(
            "INSERT OR REPLACE INTO dataset_uploads (id, filename, original_name, file_type, display_name, sheet_count, row_count, col_count, columns_json) "
            "VALUES (99770, 'WFO_July_2026_Test.xlsx', 'WFO_July_2026_Test.xlsx', 'xlsx', 'Employee Attendance Summary', 2, 470, 17, ?)",
            (json.dumps(prepared[0]["columns"]),)
        )

        s_map = {"Sheet1": 9967416, "Leave Calculation Check": 9967417}
        for s in prepared:
            sid = s_map.get(s["name"], 9967416)
            conn.execute(
                "INSERT OR REPLACE INTO sheets (id, dataset_id, name, display_name, columns_json, profile_json, row_count) "
                "VALUES (?, 99770, ?, 'Employee Attendance Summary', ?, ?, ?)",
                (sid, s["name"], json.dumps(s["columns"]), json.dumps(s["profiles"]), len(s["records"]))
            )
            for idx, r in enumerate(s["records"]):
                conn.execute(
                    "INSERT OR REPLACE INTO sheet_rows (sheet_id, row_index, data_json) VALUES (?, ?, ?)",
                    (sid, idx, json.dumps(r))
                )

        try:
            conn.execute(
                "INSERT OR REPLACE INTO sheet_relationships (left_sheet_id, right_sheet_id, left_column, right_column, match_score, relationship_type) "
                "VALUES (9967416, 9967417, 'ID', 'Employee ID', 1.0, 'many_to_one')"
            )
        except Exception:
            pass


def seed_retail_from_records(conn) -> None:
    """Seeds Dataset 99771 and Sheet 9967418 from canonical RETAIL_RECORDS."""
    ret_cols = list(RETAIL_RECORDS[0].keys())
    conn.execute(
        "INSERT OR REPLACE INTO dataset_uploads (id, filename, original_name, file_type, display_name, sheet_count, row_count, col_count, columns_json) "
        "VALUES (99771, 'walmart_eval.csv', 'walmart_eval.csv', 'csv', 'Walmart Store Sales', 1, ?, ?, ?)",
        (len(RETAIL_RECORDS), len(ret_cols), json.dumps(ret_cols))
    )
    conn.execute(
        "INSERT OR REPLACE INTO sheets (id, dataset_id, name, display_name, columns_json, profile_json, row_count) "
        "VALUES (9967418, 99771, 'Sales_Data', 'Walmart Store Sales', ?, '[]', ?)",
        (json.dumps(ret_cols), len(RETAIL_RECORDS))
    )
    for idx, r in enumerate(RETAIL_RECORDS):
        conn.execute(
            "INSERT OR REPLACE INTO sheet_rows (sheet_id, row_index, data_json) VALUES (9967418, ?, ?)",
            (idx, json.dumps(r))
        )


def seed_environmental_from_records(conn) -> None:
    """Seeds Dataset 99772 and Sheet 9967419 from canonical ENVIRONMENTAL_RECORDS."""
    env_cols = list(ENVIRONMENTAL_RECORDS[0].keys())
    conn.execute(
        "INSERT OR REPLACE INTO dataset_uploads (id, filename, original_name, file_type, display_name, sheet_count, row_count, col_count, columns_json) "
        "VALUES (99772, 'cpcb_eval.csv', 'cpcb_eval.csv', 'csv', 'CPCB Air Quality Report', 1, ?, ?, ?)",
        (len(ENVIRONMENTAL_RECORDS), len(env_cols), json.dumps(env_cols))
    )
    conn.execute(
        "INSERT OR REPLACE INTO sheets (id, dataset_id, name, display_name, columns_json, profile_json, row_count) "
        "VALUES (9967419, 99772, 'Location_data', 'CPCB Air Quality Report', ?, '[]', ?)",
        (json.dumps(env_cols), len(ENVIRONMENTAL_RECORDS))
    )
    for idx, r in enumerate(ENVIRONMENTAL_RECORDS):
        conn.execute(
            "INSERT OR REPLACE INTO sheet_rows (sheet_id, row_index, data_json) VALUES (9967419, ?, ?)",
            (idx, json.dumps(r))
        )


from app.core.db_isolation import verify_connection_not_live_db


def ensure_benchmark_datasets_seeded(conn) -> None:
    """Guarantees benchmark datasets 99770, 99771, 99772 exist hermetically in conn from fixture files/records."""
    verify_connection_not_live_db(conn)
    has_99770 = conn.execute("SELECT 1 FROM dataset_uploads WHERE id = 99770").fetchone()
    has_99771 = conn.execute("SELECT 1 FROM dataset_uploads WHERE id = 99771").fetchone()
    has_99772 = conn.execute("SELECT 1 FROM dataset_uploads WHERE id = 99772").fetchone()

    if has_99770 and has_99771 and has_99772:
        return

    if not has_99770:
        seed_workforce_from_fixture(conn)
    if not has_99771:
        seed_retail_from_records(conn)
    if not has_99772:
        seed_environmental_from_records(conn)
    conn.commit()

