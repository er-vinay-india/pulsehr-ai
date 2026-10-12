"""
Parquet Dataset Backfill Service for Phase G3 Analytical Plane.
Idempotently scans existing SQLite sheets and materializes typed Parquet files
without requiring file re-upload.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from app.db.database import session_scope
from .contracts import TableParquetMetadata
from .parquet_materializer import ParquetMaterializer

logger = logging.getLogger(__name__)


class DatasetParquetBackfill:
    """Idempotent, restartable backfill coordinator for existing datasets."""

    @classmethod
    def backfill_dataset(cls, dataset_id: int, dataset_version: int = 1) -> list[TableParquetMetadata]:
        """Backfills all sheets belonging to a specific dataset."""
        logger.info("Starting Parquet backfill for dataset %d v%d...", dataset_id, dataset_version)
        materialized: list[TableParquetMetadata] = []

        with session_scope() as conn:
            sheet_rows = conn.execute(
                "SELECT id, name, columns_json FROM sheets WHERE dataset_id = ? ORDER BY id ASC",
                (dataset_id,),
            ).fetchall()

        if not sheet_rows:
            logger.warning("No sheets found to backfill for dataset %d", dataset_id)
            return []

        for s_id, s_name, cols_json in sheet_rows:
            with session_scope() as conn:
                raw_rows = conn.execute(
                    "SELECT row_index, data_json FROM sheet_rows WHERE sheet_id = ? ORDER BY row_index ASC",
                    (s_id,),
                ).fetchall()

            if not raw_rows:
                logger.warning("Sheet %d (%s) has no rows in sheet_rows; skipping", s_id, s_name)
                continue

            records: list[dict[str, Any]] = []
            for r_idx, d_json in raw_rows:
                try:
                    d = json.loads(d_json)
                    d["__source_sheet_id"] = s_id
                    d["__source_row_index"] = r_idx
                    records.append(d)
                except Exception as exc:
                    logger.warning("Corrupted json in sheet_rows for sheet %d row %d: %s", s_id, r_idx, exc)

            if not records:
                continue

            logical_table_id = f"sheet_{s_id}"
            try:
                meta = ParquetMaterializer.materialize_table(
                    dataset_id=dataset_id,
                    sheet_id=s_id,
                    logical_table_id=logical_table_id,
                    rows=records,
                    dataset_version=dataset_version,
                )
                materialized.append(meta)
            except Exception as e:
                logger.error("Failed backfilling Parquet for sheet %d (%s): %s", s_id, s_name, e)

        logger.info(
            "Backfill completed for dataset %d: %d Parquet tables materialized",
            dataset_id,
            len(materialized),
        )
        return materialized

    @classmethod
    def backfill_all_datasets(cls) -> dict[int, list[TableParquetMetadata]]:
        """Scans all registered datasets and materializes missing Parquet tables."""
        with session_scope() as conn:
            dataset_ids = [
                r[0] for r in conn.execute("SELECT id FROM dataset_uploads ORDER BY id ASC").fetchall()
            ]

        results: dict[int, list[TableParquetMetadata]] = {}
        for d_id in dataset_ids:
            results[d_id] = cls.backfill_dataset(d_id)

        return results
