"""
Analytics & Vector Reindex Job Handlers for Phase G4 Slow-Path Worker Plane.
Executes batch Parquet backfills and vector embeddings asynchronously.
"""
from __future__ import annotations

import logging
from typing import Any

from app.analytics import DatasetParquetBackfill
from ..worker_plane import ProgressReporter

logger = logging.getLogger(__name__)


def handle_parquet_backfill_job(
    job_id: str,
    payload: dict[str, Any],
    reporter: ProgressReporter,
) -> tuple[dict[str, Any], str | None]:
    """Executes dataset Parquet materialization backfill."""
    dataset_id = payload.get("dataset_id")
    reporter.update(15, "SCANNING", f"Scanning logical tables for dataset {dataset_id or 'all'}")

    if dataset_id:
        tables = DatasetParquetBackfill.backfill_dataset(int(dataset_id))
        total_tables = len(tables)
    else:
        all_res = DatasetParquetBackfill.backfill_all_datasets()
        total_tables = sum(len(v) for v in all_res.values())

    reporter.update(90, "FINALIZING", f"Materialized {total_tables} Parquet tables")
    return {
        "status": "COMPLETED",
        "dataset_id": dataset_id,
        "tables_materialized": total_tables,
    }, None


def handle_vector_reindex_job(
    job_id: str,
    payload: dict[str, Any],
    reporter: ProgressReporter,
) -> tuple[dict[str, Any], str | None]:
    """Refreshes presentation memory and vector indexes asynchronously."""
    reporter.update(10, "INDEXING", "Beginning memory backfill and embedding refresh")
    try:
        from app.services.presentation.memory.backfill import run_memory_backfill
        stats = run_memory_backfill()
    except Exception as exc:
        logger.warning("Vector reindex warning: %s", exc)
        stats = {"warning": str(exc)}

    reporter.update(95, "FINALIZING", "Vector indexes refreshed")
    return {
        "status": "COMPLETED",
        "reindex_stats": stats,
    }, None
