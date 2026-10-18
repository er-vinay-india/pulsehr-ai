"""
HighView Ingestion V2 — Adaptive Table Reconstruction Contract
Stage 2: Adaptive Table Reconstruction (Bronze/Silver Boundary)
Boundary: Tabular structure identification. Header boundary detection and grid delimitation.
Zero semantic classification, zero type casting, zero relationship discovery.
"""

from enum import Enum
from pydantic import BaseModel, ConfigDict, Field
from app.services.ingestion_v2.contracts.base import IngestionContractBase


class ReconstructionStatus(str, Enum):
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FALLBACK = "FALLBACK"
    FAILED = "FAILED"


class PhysicalCellCoord(BaseModel):
    """
    Physical coordinates in source sheet.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    sheet_index: int
    row: int
    col: int


class LogicalColumnHeader(BaseModel):
    """
    Header cell identified for a logical column.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    column_id: str
    raw_header_text: str
    source_coord: PhysicalCellCoord
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class LogicalTable(BaseModel):
    """
    Reconstructed logical table with header boundaries and row slice.
    Includes EDA-0 physical reconstruction quality metrics.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    logical_table_id: str
    source_sheet_index: int
    source_sheet_name: str
    header_row_indices: list[int] = Field(default_factory=list)
    data_start_row: int
    data_end_row: int
    columns: list[LogicalColumnHeader] = Field(default_factory=list)
    total_rows: int
    total_cols: int
    reconstruction_status: ReconstructionStatus = ReconstructionStatus.SUCCESS

    # EDA-0 Physical Quality Metrics
    header_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    merged_cells_unmerged: int = 0
    split_records_stitched: int = 0
    empty_rows_dropped: int = 0
    jagged_rows_padded: int = 0


class ReconstructedDataset(IngestionContractBase):
    """
    Stage 2 Contract: Adaptive Table Reconstruction.
    """
    stage_name: str = "adaptive_table_reconstruction"

    tables: list[LogicalTable] = Field(default_factory=list)
    reconstruction_status: ReconstructionStatus = ReconstructionStatus.SUCCESS
