"""
Slow-Path Worker Plane Coordinator for Phase G4.
Executes long-running asynchronous jobs (PDF export, heavy EDA, vector re-indexing,
large Parquet backfill) outside the HTTP request path with cancellation and progress reporting.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import logging
import threading
import uuid
from typing import Any, Callable

from .contracts import JobRecord, JobStatus, JobSubmitResponse, JobType
from .repository import BackgroundJobRepository

logger = logging.getLogger(__name__)


class ProgressReporter:
    """Scoped progress reporter passed to worker functions."""

    def __init__(self, job_id: str, cancel_event: threading.Event):
        self.job_id = job_id
        self._cancel_event = cancel_event

    def update(self, progress_pct: int, stage: str, stage_label: str) -> None:
        if self.is_cancelled():
            raise InterruptedError(f"Job {self.job_id} was cancelled by user.")
        BackgroundJobRepository.update_progress(
            job_id=self.job_id,
            progress_pct=min(99, max(0, progress_pct)),
            stage=stage,
            stage_label=stage_label,
        )

    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()


class SlowPathWorkerPlane:
    """Coordinates asynchronous background jobs across worker threads."""

    _instance: SlowPathWorkerPlane | None = None
    _lock = threading.Lock()

    def __init__(self, max_workers: int = 4):
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="slow-worker")
        self._cancel_events: dict[str, threading.Event] = {}
        self._handlers: dict[JobType, Callable[[str, dict[str, Any], ProgressReporter], tuple[dict[str, Any], str | None]]] = {}

    @classmethod
    def get_instance(cls) -> SlowPathWorkerPlane:
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
                cls._instance.register_default_handlers()
            return cls._instance

    def register_handler(
        self,
        job_type: JobType,
        handler: Callable[[str, dict[str, Any], ProgressReporter], tuple[dict[str, Any], str | None]],
    ) -> None:
        self._handlers[job_type] = handler

    def submit_job(
        self,
        job_type: JobType,
        payload: dict[str, Any],
        execution_id: str | None = None,
        job_id: str | None = None,
    ) -> JobRecord:
        """Enqueues heavy workload and returns immediately with job tracking metadata."""
        if not job_id:
            tag = job_type.value[:4].upper()
            job_id = f"JOB-{tag}-{uuid.uuid4().hex[:8]}"

        if not execution_id:
            execution_id = f"trace-{uuid.uuid4().hex[:8]}"

        cancel_ev = threading.Event()
        self._cancel_events[job_id] = cancel_ev

        job_record = BackgroundJobRepository.create_job(
            job_id=job_id,
            job_type=job_type,
            payload=payload,
            execution_id=execution_id,
        )

        # Enqueue to background worker pool
        self._executor.submit(self._run_job_wrapper, job_id, job_type, payload, cancel_ev)

        logger.info(
            "Submitted background job %s (type=%s, execution_id=%s) to worker plane",
            job_id,
            job_type.value,
            execution_id,
        )
        return job_record

    def cancel_job(self, job_id: str) -> bool:
        """Signals cancellation to running or pending job."""
        ev = self._cancel_events.get(job_id)
        if ev:
            ev.set()
        job = BackgroundJobRepository.get_job(job_id)
        if job and job.status in (JobStatus.PENDING, JobStatus.RUNNING):
            BackgroundJobRepository.mark_cancelled(job_id)
            return True
        return False

    def _run_job_wrapper(
        self,
        job_id: str,
        job_type: JobType,
        payload: dict[str, Any],
        cancel_ev: threading.Event,
    ) -> None:
        """Worker thread entrypoint."""
        reporter = ProgressReporter(job_id, cancel_ev)
        BackgroundJobRepository.mark_running(job_id, stage="PROCESSING", stage_label="Worker picked up job")

        handler = self._handlers.get(job_type)
        if not handler:
            BackgroundJobRepository.mark_failed(job_id, f"No handler registered for job type {job_type.value}")
            return

        try:
            result_dict, artifact_path = handler(job_id, payload, reporter)
            if reporter.is_cancelled():
                BackgroundJobRepository.mark_cancelled(job_id)
            else:
                BackgroundJobRepository.mark_completed(job_id, result=result_dict, artifact_path=artifact_path)
                logger.info("Job %s completed successfully (artifact=%s)", job_id, artifact_path)
        except InterruptedError:
            BackgroundJobRepository.mark_cancelled(job_id)
            logger.info("Job %s was cancelled during execution", job_id)
        except Exception as exc:
            logger.exception("Job %s failed with exception: %s", job_id, exc)
            BackgroundJobRepository.mark_failed(job_id, str(exc))
        finally:
            self._cancel_events.pop(job_id, None)

    def register_default_handlers(self) -> None:
        """Wires standard Slow-Path handlers."""
        from .handlers.export_handler import handle_pdf_export_job, handle_pptx_export_job
        from .handlers.eda_handler import handle_eda_job
        from .handlers.analytics_handler import handle_parquet_backfill_job, handle_vector_reindex_job

        self.register_handler(JobType.PDF_EXPORT, handle_pdf_export_job)
        self.register_handler(JobType.PPTX_EXPORT, handle_pptx_export_job)
        self.register_handler(JobType.EDA, handle_eda_job)
        self.register_handler(JobType.PARQUET_BACKFILL, handle_parquet_backfill_job)
        self.register_handler(JobType.VECTOR_REINDEX, handle_vector_reindex_job)


worker_plane = SlowPathWorkerPlane.get_instance()
