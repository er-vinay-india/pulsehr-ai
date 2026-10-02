"""API routes for Exploratory Data Analysis (EDA) and Multi-Sheet Intelligence."""
from __future__ import annotations

import json
import math
from typing import Any
from fastapi import APIRouter, HTTPException, Query, Body

from ..db.database import get_connection
from ..services.eda import run_eda_pipeline

router = APIRouter(prefix="/api/eda", tags=["exploratory data analysis"])


@router.get("/reports/{sheet_id}")
def get_sheet_eda_report(sheet_id: int):
    """Returns the full EDA report & diagnostics for a specific sheet."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, sheet_id, dataset_id, health_score, report_json, created_at FROM eda_reports WHERE sheet_id=?",
            (sheet_id,)
        ).fetchone()
        if not row:
            # If not yet generated, attempt on-the-fly generation
            run_eda_pipeline(sheet_ids=[sheet_id], conn=conn)
            row = conn.execute(
                "SELECT id, sheet_id, dataset_id, health_score, report_json, created_at FROM eda_reports WHERE sheet_id=?",
                (sheet_id,)
            ).fetchone()

        if not row:
            raise HTTPException(404, f"No EDA report found for sheet {sheet_id}")

        report = json.loads(row["report_json"])
        report["created_at"] = row["created_at"]

        # Ensure summary completeness & type breakdown fields are always present
        summary = report.setdefault("summary", {})
        col_diags = report.get("column_diagnostics", {})
        if ("data_types_breakdown" not in summary or "columns_with_nulls" not in summary) and col_diags:
            type_counts = {"numeric": 0, "categorical": 0, "datetime": 0, "identifier": 0, "boolean": 0, "other": 0}
            cols_with_nulls = []
            for col, diag in col_diags.items():
                t = diag.get("inferred_type", "categorical")
                if t.startswith("numeric"):
                    type_counts["numeric"] += 1
                elif t in ("datetime", "date", "time"):
                    type_counts["datetime"] += 1
                elif t in ("identifier", "id"):
                    type_counts["identifier"] += 1
                elif t in ("boolean", "bool"):
                    type_counts["boolean"] += 1
                elif t == "categorical":
                    type_counts["categorical"] += 1
                else:
                    type_counts["other"] += 1
                if diag.get("null_count", 0) > 0:
                    cols_with_nulls.append({
                        "column": col,
                        "null_count": diag["null_count"],
                        "null_percentage": diag.get("null_percentage", 0.0),
                        "inferred_type": t
                    })
            summary.setdefault("data_types_breakdown", type_counts)
            summary.setdefault("columns_with_nulls", cols_with_nulls)
            summary.setdefault("columns_with_nulls_count", len(cols_with_nulls))
            t_rows = summary.get("total_rows", 0)
            t_cols = summary.get("total_columns", len(col_diags))
            t_cells = max(1, t_rows * t_cols)
            t_nulls = summary.get("total_null_cells", 0)
            summary.setdefault("total_cells", t_cells)
            summary.setdefault("null_cells_pct", round((t_nulls / t_cells) * 100, 2))
            summary.setdefault("completeness_pct", round(100.0 - ((t_nulls / t_cells) * 100), 2))
            summary.setdefault("is_incomplete", t_nulls > 0)
            if "incomplete_rows_count" not in summary:
                max_null_in_col = max((d.get("null_count", 0) for d in col_diags.values()), default=0)
                summary["incomplete_rows_count"] = min(t_rows, max_null_in_col)
                summary["incomplete_rows_pct"] = round((summary["incomplete_rows_count"] / max(1, t_rows)) * 100, 1)

        # Attach canonical WorkspaceContext via EDAContextAdapter if available
        try:
            from ..services.input_intelligence import SnapshotManager, EDAContextAdapter
            ws_id = str(row["dataset_id"])
            ws_ctx = SnapshotManager.get_cached_context(ws_id) or SnapshotManager.get_cached_context(f"ws_{ws_id}")
            if ws_ctx:
                eda_ctx = EDAContextAdapter.adapt(ws_ctx)
                report["eda_analysis_context"] = eda_ctx.model_dump()
                report["domain"] = eda_ctx.domain
                report["primary_dataset"] = eda_ctx.primary_dataset_name
                report["semantic_roles"] = eda_ctx.semantic_roles
                report["units"] = eda_ctx.units
                report["readiness_status"] = eda_ctx.readiness_status
                report["quality_warnings"] = eda_ctx.quality_warnings
        except Exception:
            pass

        return report
    finally:
        conn.close()


@router.get("/derived-tables")
def list_derived_tables():
    """Lists all synthesized cross-sheet derived tables with schema metadata."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, name, display_name, description, source_sheets_json, join_keys_json, columns_json, row_count, created_at FROM derived_tables ORDER BY id ASC"
        ).fetchall()
        tables = []
        for r in rows:
            tables.append({
                "id": r["id"],
                "name": r["name"],
                "display_name": r["display_name"],
                "description": r["description"],
                "source_sheets": json.loads(r["source_sheets_json"]),
                "join_keys": json.loads(r["join_keys_json"]),
                "columns": json.loads(r["columns_json"]),
                "row_count": r["row_count"],
                "created_at": r["created_at"]
            })
        return {"derived_tables": tables, "total": len(tables)}
    finally:
        conn.close()


@router.get("/derived-tables/{derived_id}/rows")
def get_derived_table_rows(
    derived_id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    search: str = Query("", max_length=200)
):
    """Fetches paginated rows from a synthesized cross-sheet derived table."""
    conn = get_connection()
    try:
        table_meta = conn.execute("SELECT * FROM derived_tables WHERE id=?", (derived_id,)).fetchone()
        if not table_meta:
            raise HTTPException(404, f"Derived table {derived_id} not found")

        clause = "derived_table_id=?"
        args: list[Any] = [derived_id]
        if search:
            clause += " AND EXISTS (SELECT 1 FROM json_each(derived_table_rows.data_json) WHERE instr(lower(CAST(value AS TEXT)), lower(?)) > 0)"
            args.append(search)

        total = conn.execute(f"SELECT COUNT(*) FROM derived_table_rows WHERE {clause}", args).fetchone()[0]
        rows = conn.execute(
            f"SELECT row_index, data_json FROM derived_table_rows WHERE {clause} ORDER BY row_index LIMIT ? OFFSET ?",
            (*args, limit, (page - 1) * limit)
        ).fetchall()

        return {
            "derived_id": derived_id,
            "name": table_meta["name"],
            "display_name": table_meta["display_name"],
            "description": table_meta["description"],
            "columns": json.loads(table_meta["columns_json"]),
            "rows": [
                {
                    "row_number": r["row_index"] + 1,
                    "values": json.loads(r["data_json"]),
                    "anomalies": []
                }
                for r in rows
            ],
            "total": total,
            "page": page,
            "pages": max(1, math.ceil(total / limit))
        }
    finally:
        conn.close()


@router.get("/cross-sheet-correlations")
def get_cross_sheet_correlations():
    """Returns cross-sheet entity linkages and statistically computed metric correlations."""
    conn = get_connection()
    try:
        # Load from all sheet eda reports
        rows = conn.execute("SELECT report_json FROM eda_reports ORDER BY id ASC").fetchall()
        all_links = []
        all_corrs = []
        seen_links = set()
        seen_corrs = set()

        for r in rows:
            rep = json.loads(r["report_json"])
            cs = rep.get("cross_sheet_intelligence", {})
            for link in cs.get("entity_links", []):
                key = (link["left_sheet_id"], link["left_column"], link["right_sheet_id"], link["right_column"])
                if key not in seen_links:
                    seen_links.add(key)
                    all_links.append(link)
            for corr in cs.get("correlations", []):
                key = (corr["left_sheet_id"], corr["left_metric"], corr["right_sheet_id"], corr["right_metric"])
                if key not in seen_corrs:
                    seen_corrs.add(key)
                    all_corrs.append(corr)

        return {
            "entity_links": all_links,
            "correlations": all_corrs,
            "total_links": len(all_links),
            "total_correlations": len(all_corrs)
        }
    finally:
        conn.close()


@router.post("/run")
def trigger_eda(sheet_ids: list[int] | None = Body(None)):
    """Triggers the EDA normalization and multi-sheet intelligence pipeline."""
    result = run_eda_pipeline(sheet_ids=sheet_ids)
    return result
