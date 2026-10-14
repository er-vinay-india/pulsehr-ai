"""Source Data Loader for Adaptive Dashboard.

Encapsulates database access for resolving sheets, dataset uploads,
curated rows, derived tables, and EDA reports away from the dashboard engine.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from ...db.database import get_connection

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DashboardSourceContext:
    """Resolved dataset/sheet source context and records."""
    sheet_id: int
    target_dataset_id: int | None
    sheet_name: str
    display_name: str
    file_name: str
    columns: list[str] = field(default_factory=list)
    rows: list[dict[str, Any]] = field(default_factory=list)


def load_dashboard_source_context(
    sheet_id: int | None = None,
    dataset_id: int | None = None,
    conn: Any = None,
) -> tuple[DashboardSourceContext, Any]:
    """Resolves sheet metadata, dataset upload details, and parsed rows.

    Returns (context, connection). The caller must close the connection if conn was None.
    """
    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True

    try:
        # 1. Resolve sheet and dataset
        if dataset_id is not None:
            sheet_row = conn.execute(
                "SELECT id, dataset_id, name, display_name, columns_json FROM sheets WHERE dataset_id=? ORDER BY id ASC LIMIT 1",
                (dataset_id,),
            ).fetchone()
            if not sheet_row:
                raise ValueError(f"No uploaded sheet found for dataset_id {dataset_id}.")
        elif sheet_id is not None:
            sheet_row = conn.execute(
                "SELECT id, dataset_id, name, display_name, columns_json FROM sheets WHERE id=?",
                (sheet_id,),
            ).fetchone()
            if not sheet_row:
                raise ValueError(f"No uploaded sheet found for sheet_id {sheet_id}.")
        else:
            sheet_row = conn.execute(
                "SELECT id, dataset_id, name, display_name, columns_json FROM sheets ORDER BY id DESC LIMIT 1"
            ).fetchone()

        if not sheet_row:
            raise ValueError("No uploaded sheet found. Upload a dataset to view the adaptive dashboard.")

        sid, ds_id, sheet_name, display_name, cols_json = sheet_row
        target_dataset_id = dataset_id if dataset_id is not None else ds_id
        columns = json.loads(cols_json) if cols_json else []

        # Get original file name
        dataset_row = conn.execute(
            "SELECT original_name, display_name FROM dataset_uploads WHERE id=?",
            (target_dataset_id,),
        ).fetchone()
        file_name = dataset_row[0] if dataset_row else "dataset.csv"
        final_display_name = display_name or (dataset_row[1] if dataset_row else sheet_name)

        # 2. Fetch rows (prefer curated post-EDA rows, fallback to raw)
        row_records = conn.execute(
            "SELECT data_json FROM sheet_curated_rows WHERE sheet_id=? ORDER BY row_index",
            (sid,),
        ).fetchall()
        if not row_records:
            row_records = conn.execute(
                "SELECT data_json FROM sheet_rows WHERE sheet_id=? ORDER BY row_index",
                (sid,),
            ).fetchall()
        rows = [json.loads(r[0]) for r in row_records]

        context = DashboardSourceContext(
            sheet_id=sid,
            target_dataset_id=target_dataset_id,
            sheet_name=sheet_name,
            display_name=final_display_name,
            file_name=file_name,
            columns=columns,
            rows=rows,
        )
        return context, conn
    except Exception:
        if should_close and conn is not None:
            conn.close()
        raise


def load_eda_report_json(sheet_id: int, conn: Any) -> dict[str, Any] | None:
    """Loads EDA report json for the sheet if present."""
    try:
        eda_row = conn.execute(
            "SELECT report_json FROM eda_reports WHERE sheet_id=?",
            (sheet_id,),
        ).fetchone()
        return json.loads(eda_row[0]) if eda_row else None
    except Exception as e:
        logger.warning("Could not fetch EDA report for sheet %d: %s", sheet_id, e)
        return None


def load_sibling_sources(dataset_id: int | None, current_sheet_id: int, conn: Any) -> list[dict[str, Any]]:
    """Loads sibling sources for the dataset."""
    if not dataset_id:
        return []
    try:
        sibling_rows = conn.execute(
            "SELECT id, name, display_name FROM sheets WHERE dataset_id=? AND id != ?",
            (dataset_id, current_sheet_id),
        ).fetchall()
        return [{"sheet_id": r[0], "name": r[1], "display_name": r[2]} for r in sibling_rows]
    except Exception as e:
        logger.warning("Could not fetch sibling sources for dataset %s: %s", dataset_id, e)
        return []


def load_analytical_tables(
    sheet_id: int,
    dataset_id: int | None,
    conn: Any,
) -> list[dict[str, Any]]:
    """Loads synthesized derived analytical tables associated with sheet or dataset."""
    analytical_tables = []
    try:
        dt_rows = conn.execute(
            """
            SELECT id, name, display_name, description, columns_json, row_count, join_keys_json
            FROM derived_tables
            WHERE source_sheets_json LIKE ? OR source_sheets_json LIKE ?
            ORDER BY id ASC
            """,
            (f"%{sheet_id}%", f"%{dataset_id}%" if dataset_id else f"%{sheet_id}%"),
        ).fetchall()

        for dt in dt_rows:
            dt_id = dt[0]
            tbl_rows = conn.execute(
                "SELECT data_json FROM derived_table_rows WHERE derived_table_id=? ORDER BY row_index ASC LIMIT 100",
                (dt_id,),
            ).fetchall()
            row_records = [json.loads(tr[0]) for tr in tbl_rows]
            analytical_tables.append({
                "id": dt_id,
                "name": dt[1],
                "display_name": dt[2],
                "description": dt[3],
                "columns": json.loads(dt[4]),
                "row_count": dt[5],
                "join_keys": json.loads(dt[6]),
                "rows": row_records,
            })
    except Exception as dt_err:
        logger.warning("Could not fetch analytical tables for dashboard: %s", dt_err)
    return analytical_tables
