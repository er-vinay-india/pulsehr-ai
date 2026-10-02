"""Ingestion Job Manager.

Provides asynchronous orchestration, thread-safe state management,
granular progress tracking, and SSE streaming for spreadsheet ingestion.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import logging
import queue
import threading
import time
from typing import Any, Generator
from uuid import uuid4

logger = logging.getLogger(__name__)


# 10 canonical pipeline stages matching frontend visual progress card
STAGE_DEFINITIONS = [
    {
        "step": 1,
        "stage": "raw_ingestion",
        "title": "1. Raw Ingestion & Schema Extraction",
        "sub": "Validating file format (.csv, .xlsx, .xls), byte boundaries, and capturing raw immutable records",
        "default_pct": 10,
    },
    {
        "step": 2,
        "stage": "naming_and_profiling",
        "title": "2. AI Sheet Naming & Semantic Structural Profiling",
        "sub": "Decontaminating filenames, classifying business domain, and inferring column roles",
        "default_pct": 20,
    },
    {
        "step": 3,
        "stage": "cleansing_sanitization",
        "title": "3. Data Cleansing & Syntactic Sanitization",
        "sub": "Normalizing whitespace, stripping control characters, and standardizing nulls",
        "default_pct": 30,
    },
    {
        "step": 4,
        "stage": "metric_normalization",
        "title": "4. Metric & Unit Normalization",
        "sub": "Parsing currencies, rates, units, and numeric scales",
        "default_pct": 40,
    },
    {
        "step": 5,
        "stage": "semantic_enrichment",
        "title": "5. Controlled Semantic Enrichment & Scientific Discovery",
        "sub": "Graph clustering, dimensional transformations, and synthesized analytical rollups",
        "default_pct": 50,
    },
    {
        "step": 6,
        "stage": "missing_value_diagnostics",
        "title": "6. Missing Value Diagnostics & Smart Imputation",
        "sub": "Computing distribution-aware targets and preserving fidelity flags",
        "default_pct": 60,
    },
    {
        "step": 7,
        "stage": "eda_outlier_profiling",
        "title": "7. Statistical Exploratory Data Analysis (EDA) & Outlier Profiling",
        "sub": "Running Tukey IQR fences, Z-score diagnostics, and computing Data Health Score",
        "default_pct": 70,
    },
    {
        "step": 8,
        "stage": "multisheet_cross_correlation",
        "title": "8. Multi-Sheet Key Discovery & Cross-Correlation Matrix (N-Sheet EDA)",
        "sub": "Discovering entity linkages across sheets and materializing derived tables",
        "default_pct": 80,
    },
    {
        "step": 9,
        "stage": "vectorization_indexing",
        "title": "9. Semantic Vectorization & BM25 Hybrid Retrieval Indexing",
        "sub": "Batching normalized tokens and building hybrid vector & cell indices",
        "default_pct": 90,
    },
    {
        "step": 10,
        "stage": "catalog_readiness",
        "title": "10. Analytical Evidence Catalog & Dashboard Readiness",
        "sub": "Materializing Post-EDA curated views, linking cross-sheet intelligence, and finalizing",
        "default_pct": 100,
    },
]


@dataclass
class IngestionJob:
    job_id: str
    filename: str
    file_size_bytes: int = 0
    status: str = "queued"  # queued, running, completed, failed
    step: int = 0
    total_steps: int = 10
    percentage: int = 0
    stage: str = "queued"
    title: str = "Job Queued"
    message: str = "Spreadsheet upload registered. Initializing ingestion worker..."
    dataset_id: int | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        elapsed = round(max(0.0, time.time() - self.created_at), 2)
        return {
            "job_id": self.job_id,
            "filename": self.filename,
            "file_size_bytes": self.file_size_bytes,
            "status": self.status,
            "step": self.step,
            "total_steps": self.total_steps,
            "percentage": self.percentage,
            "stage": self.stage,
            "title": self.title,
            "message": self.message,
            "dataset_id": self.dataset_id,
            "result": self.result,
            "error": self.error,
            "elapsed_seconds": elapsed,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class IngestionJobManager:
    """Thread-safe registry for asynchronous spreadsheet ingestion jobs."""

    def __init__(self, max_history: int = 100) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, IngestionJob] = {}
        self._subscribers: dict[str, list[queue.Queue]] = {}
        self._max_history = max_history

    def create_job(self, filename: str, file_size_bytes: int = 0, job_id: str | None = None) -> str:
        with self._lock:
            jid = job_id or uuid4().hex
            job = IngestionJob(
                job_id=jid,
                filename=filename,
                file_size_bytes=file_size_bytes,
            )
            self._jobs[jid] = job
            self._prune_history_locked()
            return jid

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return job.to_dict() if job else None

    def list_jobs(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock:
            sorted_jobs = sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)
            return [j.to_dict() for j in sorted_jobs[:limit]]

    def update_progress(
        self,
        job_id: str,
        step: int,
        stage: str | None = None,
        title: str | None = None,
        message: str | None = None,
        percentage: int | None = None,
    ) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return

            stage_info = None
            if 1 <= step <= len(STAGE_DEFINITIONS):
                stage_info = STAGE_DEFINITIONS[step - 1]

            job.status = "running"
            job.step = step
            job.stage = stage or (stage_info["stage"] if stage_info else f"step_{step}")
            job.title = title or (stage_info["title"] if stage_info else f"Step {step}")
            job.message = message or (stage_info["sub"] if stage_info else "")
            job.percentage = (
                percentage
                if percentage is not None
                else (stage_info["default_pct"] if stage_info else int((step / job.total_steps) * 100))
            )
            job.updated_at = time.time()
            data = job.to_dict()

        self._notify_subscribers(job_id, data)

    def complete_job(self, job_id: str, dataset_id: int, result: dict[str, Any]) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            job.status = "completed"
            job.step = 10
            job.percentage = 100
            stage_10 = STAGE_DEFINITIONS[9]
            job.stage = stage_10["stage"]
            job.title = stage_10["title"]
            job.message = "Ingestion, statistical analysis, and vectorization complete."
            job.dataset_id = dataset_id
            job.result = result
            job.updated_at = time.time()
            data = job.to_dict()

        self._notify_subscribers(job_id, data)

    def fail_job(self, job_id: str, error_message: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            job.status = "failed"
            job.error = error_message
            job.message = f"Ingestion failed: {error_message}"
            job.updated_at = time.time()
            data = job.to_dict()

        self._notify_subscribers(job_id, data)

    def subscribe(self, job_id: str) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=100)
        with self._lock:
            if job_id not in self._subscribers:
                self._subscribers[job_id] = []
            self._subscribers[job_id].append(q)
            # Push current state immediately so listener gets current status
            if job_id in self._jobs:
                try:
                    q.put_nowait(self._jobs[job_id].to_dict())
                except queue.Full:
                    pass
        return q

    def unsubscribe(self, job_id: str, q: queue.Queue) -> None:
        with self._lock:
            if job_id in self._subscribers:
                try:
                    self._subscribers[job_id].remove(q)
                except ValueError:
                    pass
                if not self._subscribers[job_id]:
                    del self._subscribers[job_id]

    def _notify_subscribers(self, job_id: str, data: dict[str, Any]) -> None:
        subscribers = []
        with self._lock:
            subscribers = list(self._subscribers.get(job_id, []))
        for q in subscribers:
            try:
                q.put_nowait(data)
            except queue.Full:
                pass

    def _prune_history_locked(self) -> None:
        if len(self._jobs) > self._max_history:
            excess = len(self._jobs) - self._max_history
            oldest_keys = sorted(self._jobs.keys(), key=lambda k: self._jobs[k].created_at)[:excess]
            for k in oldest_keys:
                del self._jobs[k]
                self._subscribers.pop(k, None)


# Global singleton instance
ingestion_job_manager = IngestionJobManager()
