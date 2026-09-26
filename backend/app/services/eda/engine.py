"""Orchestrator for the Exploratory Data Analysis (EDA) & Multi-Sheet Intelligence Pipeline."""
from __future__ import annotations

import json
import logging
import sqlite3
from typing import Any

from ...db.database import get_connection
from .normalizer import normalize_dataset
from .cross_correlator import (
    compute_cross_sheet_intelligence,
    compute_intra_sheet_correlations,
    compute_metric_distribution_histograms
)
from .temporal_analyzer import analyze_temporal_dynamics
from .predictive_models import generate_predictive_suite_for_sheet
from .derived_tables import synthesize_derived_tables
from .report_generator import build_sheet_eda_report

logger = logging.getLogger(__name__)


def run_eda_pipeline(sheet_ids: list[int] | None = None, conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    """Runs end-to-end EDA pipeline:
    1. Intra-sheet data cleansing & normalization -> writes sheet_curated_rows
    2. Multi-sheet cross-correlation & entity linkage discovery
    3. Cross-sheet derived table synthesis -> writes derived_tables
    4. Comprehensive EDA report generation -> writes eda_reports
    """
    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True

    try:
        # Load sheets metadata
        query = "SELECT id, dataset_id, name, display_name, columns_json, row_count FROM sheets"
        params = []
        if sheet_ids:
            query += f" WHERE id IN ({','.join(['?']*len(sheet_ids))})"
            params.extend(sheet_ids)
        query += " ORDER BY id ASC"

        sheet_records = conn.execute(query, params).fetchall()
        sheets: list[dict[str, Any]] = []
        for r in sheet_records:
            sheets.append({
                "id": r["id"],
                "dataset_id": r["dataset_id"],
                "name": r["name"],
                "display_name": r["display_name"] or r["name"],
                "columns": json.loads(r["columns_json"]),
                "row_count": r["row_count"]
            })

        if not sheets:
            return {"status": "skipped", "message": "No sheets to analyze."}

        curated_tables: dict[int, list[dict[str, Any]]] = {}
        normalization_results: dict[int, dict[str, Any]] = {}
        raw_records_by_sheet: dict[int, list[dict[str, Any]]] = {}

        # 1. Intra-Sheet Cleansing & Normalization
        for s in sheets:
            sid = s["id"]
            raw_rows_db = conn.execute(
                "SELECT row_index, data_json FROM sheet_rows WHERE sheet_id=? ORDER BY row_index ASC",
                (sid,)
            ).fetchall()
            raw_records = [json.loads(r["data_json"]) for r in raw_rows_db]
            raw_records_by_sheet[sid] = raw_records

            norm_res = normalize_dataset(
                sheet_id=sid,
                sheet_name=s.get("display_name") or s["name"],
                columns=s["columns"],
                raw_records=raw_records
            )
            normalization_results[sid] = norm_res
            curated_tables[sid] = norm_res["curated_records"]

            # Persist curated rows
            conn.execute("DELETE FROM sheet_curated_rows WHERE sheet_id=?", (sid,))
            for r_idx, rec in enumerate(norm_res["curated_records"]):
                anomalies = norm_res["anomalies_per_row"][r_idx]
                conn.execute(
                    """
                    INSERT INTO sheet_curated_rows(sheet_id, row_index, data_json, anomalies_json)
                    VALUES (?, ?, ?, ?)
                    """,
                    (sid, r_idx, json.dumps(rec), json.dumps(anomalies))
                )

        # 2. Multi-Sheet Cross-Correlation & Entity Discovery
        cross_intel = compute_cross_sheet_intelligence(
            sheets=sheets,
            curated_tables=curated_tables,
            diagnostics=normalization_results
        )

        # 3. Materialize Derived Tables
        derived_tables = synthesize_derived_tables(
            conn=conn,
            sheets=sheets,
            curated_tables=curated_tables,
            entity_links=cross_intel.get("entity_links", [])
        )

        # 4. Generate & Persist Structured EDA Reports
        reports_by_sheet: dict[int, dict[str, Any]] = {}
        eda_cols = [r[1] for r in conn.execute("PRAGMA table_info(eda_reports)").fetchall()]
        has_snapshot_col = "snapshot" in eda_cols

        for s in sheets:
            sid = s["id"]
            raw_rows = raw_records_by_sheet.get(sid, [])
            curated_rows = curated_tables.get(sid, [])
            norm_res = normalization_results[sid]
            diag = norm_res.get("column_diagnostics", {})

            # Compute intra-sheet correlations & distribution bins
            intra_corrs = compute_intra_sheet_correlations(curated_rows, s["columns"], diag)
            metric_dists = compute_metric_distribution_histograms(curated_rows, s["columns"], diag)

            # Compute temporal date-separated dynamics
            temporal_dyn = analyze_temporal_dynamics(curated_rows, s["columns"])

            # Compute predictive models (Linear & Logistic Regression)
            predictive_suite = generate_predictive_suite_for_sheet(curated_rows, s["columns"], diag)

            from ..adaptive_dashboard.engine import compute_source_snapshot
            snap = compute_source_snapshot(sid, s["columns"], raw_rows)

            report = build_sheet_eda_report(
                sheet_meta=s,
                norm_result=norm_res,
                cross_intel=cross_intel,
                derived_tables=derived_tables,
                intra_correlations=intra_corrs,
                metric_distributions=metric_dists,
                temporal_analysis=temporal_dyn,
                predictive_suite=predictive_suite,
                snapshot=snap
            )
            reports_by_sheet[sid] = report

            conn.execute("DELETE FROM eda_reports WHERE sheet_id=?", (sid,))
            if has_snapshot_col:
                conn.execute(
                    """
                    INSERT INTO eda_reports(sheet_id, dataset_id, health_score, report_json, snapshot)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (sid, s["dataset_id"], report["health_score"], json.dumps(report), snap)
                )
            else:
                conn.execute(
                    """
                    INSERT INTO eda_reports(sheet_id, dataset_id, health_score, report_json)
                    VALUES (?, ?, ?, ?)
                    """,
                    (sid, s["dataset_id"], report["health_score"], json.dumps(report))
                )

        conn.commit()


        logger.info(
            f"EDA pipeline successfully completed across {len(sheets)} sheets: "
            f"{len(cross_intel.get('entity_links', []))} links, "
            f"{len(cross_intel.get('cross_correlations', []))} correlations, "
            f"{len(derived_tables)} derived tables."
        )

        return {
            "status": "success",
            "sheets_analyzed": len(sheets),
            "cross_sheet_intelligence": cross_intel,
            "derived_tables": derived_tables,
            "reports_by_sheet": reports_by_sheet
        }

    finally:
        if should_close and conn:
            conn.close()
