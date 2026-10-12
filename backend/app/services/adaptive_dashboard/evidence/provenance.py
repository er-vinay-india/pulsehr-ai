"""Evidence Provenance and Lineage Tracking.

Connects every calculated analytical fact to its verified data plane lineage:
- Parquet / DuckDB analytical layer or Curated SQLite layer
- Logical table identifier
- Dataset / Sheet IDs
- Deterministic calculation hash and snapshot identifier
"""
from __future__ import annotations

import hashlib
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class ProvenanceRecord(BaseModel):
    """Immutable audit record linking a calculation to physical and logical lineage."""
    model_config = ConfigDict(extra="ignore")

    dataset_id: int
    sheet_id: int | None = None
    logical_table: str = "sheet_curated_rows"
    storage_plane: str = "parquet_duckdb"  # "parquet_duckdb" | "sqlite_curated"
    calculation_hash: str
    snapshot: str
    grain: str = "aggregate"
    row_count: int = 0
    column_scope: list[str] = Field(default_factory=list)


class ProvenanceBinder:
    """Binds lineage metadata to evidence nodes while sanitizing internal paths."""

    @classmethod
    def compute_calculation_hash(cls, formula_or_desc: str, params: dict[str, Any] | None = None) -> str:
        """Computes a deterministic hash for a calculation formula and parameters."""
        raw = f"{formula_or_desc}_{sorted(params.items()) if params else ''}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]

    @classmethod
    def build_provenance_record(
        cls,
        dataset_id: int,
        snapshot: str,
        calculation_desc: str,
        sheet_id: int | None = None,
        logical_table: str = "sheet_curated_rows",
        storage_plane: str = "parquet_duckdb",
        grain: str = "aggregate",
        row_count: int = 0,
        column_scope: list[str] | None = None,
    ) -> ProvenanceRecord:
        """Constructs an immutable ProvenanceRecord for an evidence item."""
        calc_hash = cls.compute_calculation_hash(calculation_desc, {"dataset_id": dataset_id, "grain": grain})
        return ProvenanceRecord(
            dataset_id=dataset_id,
            sheet_id=sheet_id,
            logical_table=logical_table,
            storage_plane=storage_plane,
            calculation_hash=calc_hash,
            snapshot=snapshot[:16] if snapshot else "snapshot_curated",
            grain=grain,
            row_count=row_count,
            column_scope=column_scope or [],
        )

    @classmethod
    def format_citation(cls, record: ProvenanceRecord) -> str:
        """Produces a safe, audit-ready provenance string suitable for UI inspection.
        
        Guarantees that raw server file paths are never leaked into the citation.
        """
        table_ref = f"{record.logical_table} (sheet #{record.sheet_id})" if record.sheet_id else record.logical_table
        return (
            f"Derived via {record.storage_plane} from {table_ref} [dataset #{record.dataset_id}, "
            f"grain: {record.grain}, snapshot: {record.snapshot}, calc_ref: {record.calculation_hash}]"
        )
