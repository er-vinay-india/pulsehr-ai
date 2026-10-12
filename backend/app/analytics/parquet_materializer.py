"""
Parquet Materializer for Phase G3 Analytical Plane.
Converts validated logical table rows into typed, columnar, compressed Parquet files
with preserved provenance (__source_sheet_id, __source_row_index, __logical_row_index)
and governed sentinel handling.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import os
from pathlib import Path
import re
from typing import Any, Sequence

import pyarrow as pa
import pyarrow.parquet as pq

from app.core.config import settings
from app.db.database import get_connection, session_scope
from .contracts import AnalyticalStatus, TableParquetMetadata
from .storage_integrity import AnalyticalStorageIsolationIntegrity

logger = logging.getLogger(__name__)

STANDARD_SENTINELS = {
    "N/A", "NA", "BDL", "NR", "NM", "-", "--", "*", "**", "#N/A",
    "NONE", "NULL", "NAN", "", "NOT APPLICABLE", "NOT REPORTED", "NOT MONITORED"
}


class ParquetMaterializer:
    """Materializes validated logical tables into canonical Parquet files."""

    @classmethod
    def materialize_table(
        cls,
        dataset_id: int,
        sheet_id: int,
        logical_table_id: str,
        rows: Sequence[dict[str, Any]],
        dataset_version: int = 1,
        known_sentinels: Sequence[str] | None = None,
        force_rebuild: bool = False,
    ) -> TableParquetMetadata:
        """Converts in-memory row dictionaries into a typed, verified Parquet file."""
        if not rows:
            raise ValueError(f"Cannot materialize empty row set for {logical_table_id}")

        target_path = AnalyticalStorageIsolationIntegrity.build_canonical_path(
            dataset_id=dataset_id,
            dataset_version=dataset_version,
            logical_table_id=logical_table_id,
        )

        sentinel_set = set(STANDARD_SENTINELS)
        if known_sentinels:
            for s in known_sentinels:
                sentinel_set.add(str(s).strip().upper())

        # Extract column names (excluding internal provenance if already present)
        first_row = rows[0]
        col_names = [c for c in first_row.keys() if not c.startswith("__")]

        # Content-addressed hashing
        raw_repr = json.dumps(rows, sort_keys=True, default=str)
        content_hash = hashlib.sha256(raw_repr.encode("utf-8")).hexdigest()
        schema_hash = hashlib.sha256(json.dumps(sorted(col_names)).encode("utf-8")).hexdigest()

        # Check existing metadata and file
        if not force_rebuild and target_path.exists():
            existing = cls._get_stored_metadata(dataset_id, dataset_version, logical_table_id)
            if existing and existing.content_hash == content_hash and existing.schema_hash == schema_hash:
                logger.info(
                    "Parquet cache hit for %s (hash %s). Skipping rebuild.",
                    logical_table_id,
                    content_hash[:8],
                )
                return existing

        # Type inference across rows
        col_types = cls._infer_column_types(rows, col_names, sentinel_set)

        # Prepare typed data and provenance
        cleaned_rows: list[dict[str, Any]] = []
        for l_idx, r in enumerate(rows):
            clean: dict[str, Any] = {}
            for col in col_names:
                raw_val = r.get(col)
                clean[col] = cls._coerce_value(raw_val, col_types[col], sentinel_set)

            # Preserve provenance
            clean["__source_sheet_id"] = int(r.get("__source_sheet_id", sheet_id))
            clean["__source_row_index"] = int(r.get("__source_row_index", l_idx))
            clean["__logical_row_index"] = l_idx
            cleaned_rows.append(clean)

        # Build PyArrow schema
        fields = []
        for col in col_names:
            t = col_types[col]
            if t == "int":
                pa_type = pa.int64()
            elif t == "float":
                pa_type = pa.float64()
            elif t == "bool":
                pa_type = pa.bool_()
            else:
                pa_type = pa.string()
            fields.append(pa.field(col, pa_type, nullable=True))

        # Add provenance fields
        fields.append(pa.field("__source_sheet_id", pa.int64(), nullable=False))
        fields.append(pa.field("__source_row_index", pa.int64(), nullable=False))
        fields.append(pa.field("__logical_row_index", pa.int64(), nullable=False))

        schema = pa.schema(fields)
        table = pa.Table.from_pylist(cleaned_rows, schema=schema)

        # Atomic write via temporary file
        target_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = target_path.with_suffix(".tmp.parquet")
        try:
            pq.write_table(
                table,
                tmp_path,
                compression=getattr(settings, "PARQUET_COMPRESSION", "snappy"),
            )
            tmp_path.replace(target_path)
        except Exception as exc:
            if tmp_path.exists():
                tmp_path.unlink()
            logger.error("Failed materializing Parquet file at %s: %s", target_path, exc)
            cls._record_failure(dataset_id, sheet_id, dataset_version, logical_table_id, str(target_path), exc)
            raise

        uncompressed_bytes = table.nbytes
        parquet_bytes = target_path.stat().st_size
        schema_dict = {f.name: str(f.type) for f in schema}

        metadata = TableParquetMetadata(
            dataset_id=dataset_id,
            sheet_id=sheet_id,
            dataset_version=dataset_version,
            logical_table_id=logical_table_id,
            parquet_path=str(target_path),
            content_hash=content_hash,
            schema_hash=schema_hash,
            row_count=len(cleaned_rows),
            column_count=len(col_names),
            uncompressed_bytes=uncompressed_bytes,
            parquet_bytes=parquet_bytes,
            status=AnalyticalStatus.PARQUET_READY,
            schema_json=json.dumps(schema_dict),
        )

        cls._persist_metadata(metadata)
        logger.info(
            "Materialized Parquet for %s: %d rows, %d cols, %d -> %d bytes (%.1fx compression)",
            logical_table_id,
            metadata.row_count,
            metadata.column_count,
            uncompressed_bytes,
            parquet_bytes,
            (uncompressed_bytes / max(1, parquet_bytes)),
        )
        return metadata

    @classmethod
    def _infer_column_types(
        cls,
        rows: Sequence[dict[str, Any]],
        col_names: list[str],
        sentinel_set: set[str],
    ) -> dict[str, str]:
        """Infers appropriate column types (int, float, bool, string) while respecting sentinels."""
        types: dict[str, str] = {}
        for col in col_names:
            non_null = []
            for r in rows:
                v = r.get(col)
                if v is None:
                    continue
                s = str(v).strip()
                if s.upper() in sentinel_set:
                    continue
                non_null.append(v)

            if not non_null:
                types[col] = "string"
                continue

            # Check bool
            is_bool = all(
                isinstance(v, bool) or str(v).strip().lower() in ("true", "false")
                for v in non_null
            )
            if is_bool:
                types[col] = "bool"
                continue

            # Check int
            is_int = True
            for v in non_null:
                s = str(v).replace(",", "").replace("$", "").replace("%", "").strip()
                try:
                    iv = int(s)
                    if float(s) != iv:
                        is_int = False
                        break
                except (ValueError, TypeError):
                    is_int = False
                    break
            if is_int:
                types[col] = "int"
                continue

            # Check float
            is_float = True
            for v in non_null:
                s = str(v).replace(",", "").replace("$", "").replace("%", "").strip()
                try:
                    float(s)
                except (ValueError, TypeError):
                    is_float = False
                    break
            if is_float:
                types[col] = "float"
                continue

            types[col] = "string"

        return types

    @classmethod
    def _coerce_value(cls, val: Any, target_type: str, sentinel_set: set[str]) -> Any:
        """Coerces a single value to target type, converting sentinels to None."""
        if val is None:
            return None
        s = str(val).strip()
        if s.upper() in sentinel_set:
            return None

        try:
            if target_type == "int":
                clean_s = s.replace(",", "").replace("$", "").replace("%", "").strip()
                return int(float(clean_s))
            elif target_type == "float":
                clean_s = s.replace(",", "").replace("$", "").replace("%", "").strip()
                f = float(clean_s)
                return None if math.isnan(f) or math.isinf(f) else f
            elif target_type == "bool":
                if isinstance(val, bool):
                    return val
                return s.lower() in ("true", "1", "yes")
            else:
                return str(val)
        except (ValueError, TypeError):
            return None if target_type in ("int", "float") else str(val)

    @classmethod
    def _persist_metadata(cls, meta: TableParquetMetadata) -> None:
        """Writes metadata to SQLite dataset_parquet_tables."""
        with session_scope() as conn:
            conn.execute(
                """
                INSERT INTO dataset_parquet_tables (
                    dataset_id, sheet_id, dataset_version, logical_table_id,
                    parquet_path, content_hash, schema_hash, row_count, column_count,
                    uncompressed_bytes, parquet_bytes, status, schema_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(dataset_id, dataset_version, logical_table_id) DO UPDATE SET
                    parquet_path = excluded.parquet_path,
                    content_hash = excluded.content_hash,
                    schema_hash = excluded.schema_hash,
                    row_count = excluded.row_count,
                    column_count = excluded.column_count,
                    uncompressed_bytes = excluded.uncompressed_bytes,
                    parquet_bytes = excluded.parquet_bytes,
                    status = excluded.status,
                    schema_json = excluded.schema_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    meta.dataset_id,
                    meta.sheet_id,
                    meta.dataset_version,
                    meta.logical_table_id,
                    meta.parquet_path,
                    meta.content_hash,
                    meta.schema_hash,
                    meta.row_count,
                    meta.column_count,
                    meta.uncompressed_bytes,
                    meta.parquet_bytes,
                    meta.status.value,
                    meta.schema_json,
                ),
            )
            # Update sheet and dataset_upload pointers
            conn.execute(
                "UPDATE sheets SET parquet_path = ?, content_hash = ? WHERE id = ?",
                (meta.parquet_path, meta.content_hash, meta.sheet_id),
            )
            conn.execute(
                "UPDATE dataset_uploads SET parquet_path = ?, content_hash = ? WHERE id = ?",
                (meta.parquet_path, meta.content_hash, meta.dataset_id),
            )

    @classmethod
    def _record_failure(
        cls,
        dataset_id: int,
        sheet_id: int,
        dataset_version: int,
        logical_table_id: str,
        path: str,
        exc: Exception,
    ) -> None:
        try:
            with session_scope() as conn:
                conn.execute(
                    """
                    INSERT INTO dataset_parquet_tables (
                        dataset_id, sheet_id, dataset_version, logical_table_id,
                        parquet_path, content_hash, schema_hash, status, schema_json, updated_at
                    ) VALUES (?, ?, ?, ?, ?, '', '', ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(dataset_id, dataset_version, logical_table_id) DO UPDATE SET
                        status = excluded.status,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (
                        dataset_id,
                        sheet_id,
                        dataset_version,
                        logical_table_id,
                        path,
                        AnalyticalStatus.PARQUET_FAILED.value,
                        str(exc),
                    ),
                )
        except Exception as e:
            logger.error("Failed recording parquet failure to DB: %s", e)

    @classmethod
    def _get_stored_metadata(
        cls,
        dataset_id: int,
        dataset_version: int,
        logical_table_id: str,
    ) -> TableParquetMetadata | None:
        """Retrieves stored TableParquetMetadata from SQLite."""
        with session_scope() as conn:
            row = conn.execute(
                """
                SELECT dataset_id, sheet_id, dataset_version, logical_table_id,
                       parquet_path, content_hash, schema_hash, row_count, column_count,
                       uncompressed_bytes, parquet_bytes, status, schema_json
                FROM dataset_parquet_tables
                WHERE dataset_id = ? AND dataset_version = ? AND logical_table_id = ?
                """,
                (dataset_id, dataset_version, logical_table_id),
            ).fetchone()
            if not row:
                return None
            return TableParquetMetadata(
                dataset_id=row[0],
                sheet_id=row[1],
                dataset_version=row[2],
                logical_table_id=row[3],
                parquet_path=row[4],
                content_hash=row[5],
                schema_hash=row[6],
                row_count=row[7],
                column_count=row[8],
                uncompressed_bytes=row[9],
                parquet_bytes=row[10],
                status=AnalyticalStatus(row[11]),
                schema_json=row[12],
            )
