"""Universal Contextual Investigation Service for Evidence-Based HR Analytics.

Produces comprehensive, reproducible investigation payloads for any chart element,
department, employee/candidate, or interesting fact.

Covers:
1. What was observed (exact value, comparison, population, period).
2. Calculation, comparison, or statistical rule supporting it.
3. Relevant timelines, episodes, and breakdowns.
4. Supporting raw source records from SQLite.
5. Related evidence from reliably connected sheets.
6. Missing context, uncertainty, and alternative explanations.
7. Practical, objective questions HR can investigate next.
"""

import json
import logging
import re
from typing import Any
import pandas as pd

from .investigation import (
    clean_val,
    find_connected_evidence,
    find_individual_connected_evidence,
    build_store_investigation,
    build_time_series_investigation,
    build_dimension_investigation,
    build_department_investigation,
    build_individual_investigation,
    build_general_investigation,
    build_model_group_investigation,
)

logger = logging.getLogger(__name__)

# Expose all builders for backward compatibility
__all__ = [
    "clean_val",
    "run_contextual_investigation",
    "find_connected_evidence",
    "find_individual_connected_evidence",
    "build_store_investigation",
    "build_time_series_investigation",
    "build_dimension_investigation",
    "build_department_investigation",
    "build_individual_investigation",
    "build_general_investigation",
    "build_model_group_investigation",
]


def run_contextual_investigation(
    conn,
    entity_type: str,
    target_id: str | None = None,
    metric: str | None = None,
    sheet_id: int | None = None,
    chart_id: str | None = None
) -> dict:
    """Dispatches and compiles the deep contextual investigation report."""
    target_clean = str(target_id or "").strip()
    metric_clean = str(metric or "Metric").strip()

    # Retrieve all sheets and rows for investigation context
    sheet_query = (
        "SELECT s.id, s.name, s.columns_json, s.row_count, d.original_name, d.filename "
        "FROM sheets s JOIN dataset_uploads d ON d.id=s.dataset_id ORDER BY s.id ASC"
    )
    all_sheets = [dict(r) for r in conn.execute(sheet_query).fetchall()]
    if not all_sheets:
        return {
            "available": False,
            "message": "No workspace sheets found for investigation."
        }

    # Load records for sheets
    sheet_records = {}
    for s in all_sheets:
        sid = s["id"]
        rows = conn.execute("SELECT row_index, data_json FROM sheet_rows WHERE sheet_id=? ORDER BY row_index", (sid,)).fetchall()
        sheet_records[sid] = [
            {"__row_index": r["row_index"] + 1, **json.loads(r["data_json"])}
            for r in rows
        ]

    # Target sheet determination
    target_sheet = None
    if sheet_id:
        target_sheet = next((s for s in all_sheets if s["id"] == sheet_id), None)
    if not target_sheet:
        # Search for sheet containing the metric or target
        for s in all_sheets:
            cols = json.loads(s["columns_json"] or "[]")
            if any(metric_clean.lower() in c.lower() for c in cols):
                target_sheet = s
                break
    if not target_sheet:
        target_sheet = all_sheets[0]

    records = sheet_records.get(target_sheet["id"], [])
    df = pd.DataFrame(records) if records else pd.DataFrame()

    # Identify primary columns
    dept_col = None
    name_col = None
    id_col = None
    date_col = None
    store_col = None
    holiday_col = None

    if not df.empty:
        for c in df.columns:
            if c.startswith("__"):
                continue
            cl = str(c).lower().replace('_', '').replace(' ', '')
            if not dept_col and any(k in cl for k in ('dept', 'department', 'team', 'division')):
                dept_col = c
            if not name_col and any(k in cl for k in ('name', 'employeename', 'full_name', 'candidate', 'person')):
                name_col = c
            if not id_col and (cl in ('id', 'employeeid', 'empid', 'code', 'candidateid') or cl.endswith('id') or cl.endswith('code')):
                id_col = c
            if not date_col and any(k in cl for k in ('date', 'timestamp', 'datetime', 'day', 'week')):
                date_col = c
            if not store_col and any(k in cl for k in ('store', 'location', 'branch', 'outlet', 'facility', 'shop')):
                store_col = c
            if not holiday_col and any(k in cl for k in ('holiday', 'holidayflag', 'season')):
                holiday_col = c

    # Match metric column
    metric_col = None
    if not df.empty and metric_clean:
        for c in df.columns:
            if c.startswith("__"):
                continue
            if metric_clean.lower() in str(c).lower() or str(c).lower() in metric_clean.lower():
                metric_col = c
                break

    # Build investigation payload based on entity_type & target
    # 1. Store / Location investigation
    is_store_target = (
        entity_type in ("store", "location", "branch", "outlet")
        or target_clean.lower().startswith("store")
        or (store_col and (
            target_clean in df[store_col].astype(str).str.replace('.0', '', regex=False).values
            or (re.search(r'\b\d+\b', target_clean) and re.search(r'\b\d+\b', target_clean).group(0) in df[store_col].astype(str).str.replace('.0', '', regex=False).values)
        ))
    )
    if is_store_target and store_col:
        return build_store_investigation(
            conn, all_sheets, sheet_records, target_sheet, store_col, target_clean, metric_col or metric_clean, date_col, holiday_col
        )

    # 2. Time-series / Date investigation
    is_date_target = (
        entity_type in ("time_series", "date", "period")
        or (date_col and bool(re.search(r'\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{4}', target_clean)))
    )
    if is_date_target and date_col:
        return build_time_series_investigation(
            conn, all_sheets, sheet_records, target_sheet, date_col, target_clean, metric_col or metric_clean, store_col, holiday_col
        )

    # 3. Dimension / Holiday cohort investigation
    is_holiday_target = (
        entity_type in ("dimension", "cohort")
        or target_clean in ("Holiday Weeks", "Regular Weeks", "Holiday", "Non-Holiday")
        or (holiday_col and target_clean in ("0", "1", "Holiday Weeks", "Regular Weeks"))
    )
    if is_holiday_target and holiday_col:
        return build_dimension_investigation(
            conn, all_sheets, sheet_records, target_sheet, holiday_col, target_clean, metric_col or metric_clean
        )

    # 4. Department-level investigation
    if entity_type == "department" or (dept_col and target_clean in df[dept_col].astype(str).values):
        return build_department_investigation(
            conn, all_sheets, sheet_records, target_sheet, dept_col, target_clean, metric_col or metric_clean
        )
    # 5. Individual employee investigation
    elif entity_type in ("employee", "person", "candidate") or (name_col and target_clean in df[name_col].astype(str).values):
        return build_individual_investigation(
            conn, all_sheets, sheet_records, target_sheet, name_col, id_col, target_clean, metric_col or metric_clean
        )
    # 6. Model group investigation
    elif entity_type == "model_group":
        return build_model_group_investigation(
            conn, all_sheets, sheet_records, target_sheet, target_clean, metric_clean
        )
    # 7. General investigation fallback
    else:
        return build_general_investigation(
            conn, all_sheets, sheet_records, target_sheet, target_clean, metric_col or metric_clean
        )
