"""
Jobs Router for Phase G4 Slow-Path Worker Plane.
Provides unified polling, status inspection, cancellation, and artifact download.
"""
from __future__ import annotations

import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from ..jobs import BackgroundJobRepository, JobRecord, JobStatus, JobType, worker_plane

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/jobs", tags=["background jobs"])


@router.get("/{job_id}", response_model=JobRecord)
def get_background_job_status(job_id: str):
    """Polls real-time lifecycle status, stage, and progress for any background job."""
    job = BackgroundJobRepository.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Background job '{job_id}' not found")
    return job


@router.get("")
def list_background_jobs(
    limit: int = Query(20, ge=1, le=100),
    job_type: JobType | None = Query(None),
    status: JobStatus | None = Query(None),
):
    """Lists recent background jobs with optional status/type filtering."""
    jobs = BackgroundJobRepository.list_jobs(job_type=job_type, status=status, limit=limit)
    return {"jobs": [j.model_dump() for j in jobs], "count": len(jobs)}


@router.post("/{job_id}/cancel")
def cancel_background_job(job_id: str):
    """Cancels a running or queued background job."""
    cancelled = worker_plane.cancel_job(job_id)
    if not cancelled:
        job = BackgroundJobRepository.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
        raise HTTPException(status_code=400, detail=f"Job '{job_id}' is in non-cancellable state: {job.status.value}")
    return {"job_id": job_id, "status": "CANCELLED", "message": "Job cancellation signaled successfully"}


@router.get("/{job_id}/download")
def download_job_artifact(job_id: str):
    """Downloads the completed artifact produced by a background export job."""
    job = BackgroundJobRepository.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Job '{job_id}' has not completed (current status: {job.status.value}, progress: {job.progress_pct}%)",
        )

    if not job.artifact_path:
        raise HTTPException(status_code=404, detail="Job has no generated file artifact")

    artifact_file = Path(job.artifact_path)
    if not artifact_file.exists():
        raise HTTPException(status_code=404, detail=f"Artifact file not found at {job.artifact_path}")

    media_type = "application/pdf" if artifact_file.suffix == ".pdf" else "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    return FileResponse(path=str(artifact_file), filename=artifact_file.name, media_type=media_type)
