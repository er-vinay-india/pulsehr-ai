"""
HighView Ingestion V2 — Raw Ingestion Contract
Stage 1: Raw Fidelity Ingestion (Bronze Layer)
Boundary: Source file fidelity only. Zero inference, zero type coercion, zero semantic assumptions.
"""

from pydantic import BaseModel, ConfigDict, Field
from app.services.ingestion_v2.contracts.base import IngestionContractBase


class PhysicalSheet(BaseModel):
    """
    Physical sheet metadata representing raw unparsed sheets/streams.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    sheet_index: int
    raw_sheet_name: str
    total_physical_rows: int
    total_physical_columns: int
    has_merged_cells: bool = False
    merged_cell_ranges: list[str] = Field(default_factory=list)
    raw_fingerprint: str


class RawIngestionResult(IngestionContractBase):
    """
    Stage 1 Contract: Raw Fidelity Ingestion.
    Contains raw file metadata and exact source representations.
    """
    stage_name: str = "raw_ingestion"

    original_file_name: str
    file_size_bytes: int
    file_mime_type: str
    source_file_sha256: str
    sheets: list[PhysicalSheet] = Field(default_factory=list)
    storage_path: str
