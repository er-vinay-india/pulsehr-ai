"""
HighView Ingestion V2 — Provenance Contracts
Stage: Cross-Cutting Provenance & Evidence Binding
"""

from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class SourceCoordinateRef(BaseModel):
    """
    Exact coordinate reference pointing back to source file, sheet, row, and column.
    Fully compatible with HighView EvidenceGraph and EVID bindings.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    dataset_id: str
    sheet_id: str | int | None = None
    logical_table_id: str | None = None
    row_start: int | None = None
    row_end: int | None = None
    column_ids: list[str] = Field(default_factory=list)
    source_file_hash: str
    evidence_ref: str | None = None
