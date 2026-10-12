"""
Phase G4 Slow-Path Worker Plane Contracts.
Defines job types, lifecycle statuses, and data structures.
"""
from __future__ import annotations

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class JobType(str, Enum):
    PRESENTATION = "PRESENTATION"
    PDF_EXPORT = "PDF_EXPORT"
    PPTX_EXPORT = "PPTX_EXPORT"
    EDA = "EDA"
    VECTOR_REINDEX = "VECTOR_REINDEX"
    PARQUET_BACKFILL = "PARQUET_BACKFILL"


class JobStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class JobRecord(BaseModel):
    id: str
    job_type: JobType
    status: JobStatus = JobStatus.PENDING
    progress_pct: int = 0
    stage: str = "QUEUED"
    stage_label: str = "Job queued"
    payload: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    artifact_path: str | None = None
    worker_pid: int | None = None
    execution_id: str | None = None
    created_at: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    updated_at: str | None = None


class JobSubmitResponse(BaseModel):
    job_id: str
    job_type: JobType
    status: JobStatus
    stage: str
    progress_pct: int
    message: str
    poll_url: str
