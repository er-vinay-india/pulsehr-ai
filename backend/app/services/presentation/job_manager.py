import copy
import datetime
import json
import logging
import threading
import uuid
from typing import Any

from ...db.database import get_connection

logger = logging.getLogger(__name__)


class PresentationJobManager:
    """Thread-safe background job pipeline coordinator."""

    def __init__(self):
        self._jobs: dict[str, dict[str, Any]] = {}
        self._cancel_flags: dict[str, bool] = {}
        self._lock = threading.Lock()
        self._ensure_extra_column()
        self.cleanup_stale_jobs()

    def _ensure_extra_column(self):
        try:
            with get_connection() as conn:
                cols = [r[1] for r in conn.execute("PRAGMA table_info(presentation_jobs)").fetchall()]
                if "extra_json" not in cols:
                    conn.execute("ALTER TABLE presentation_jobs ADD COLUMN extra_json TEXT DEFAULT '{}'")
                    conn.commit()
        except Exception as exc:
            logger.debug(f"Could not check/add extra_json column: {exc}")

    def cleanup_stale_jobs(self):
        """Marks any orphaned jobs as failed so clients are never stuck on crashed or interrupted runs."""
        with self._lock:
            for job in self._jobs.values():
                if job.get("status") in ("in_progress", "pending"):
                    job["status"] = "failed"
                    job["stage"] = "failed"
                    job["stage_label"] = "Generation interrupted by server reload"
                    job["error"] = "Generation was interrupted by server reload. Please click Generate Again to rebuild."
        try:
            with get_connection() as conn:
                conn.execute(
                    "UPDATE presentation_jobs SET status='failed', stage='failed', "
                    "stage_label='Generation interrupted by server reload', "
                    "error='Generation was interrupted by server reload. Please click Generate Again to rebuild.' "
                    "WHERE status IN ('in_progress', 'pending')"
                )
                conn.commit()
        except Exception as exc:
            logger.debug(f"Could not clean up stale jobs: {exc}")

    def create_job(self, scope: dict[str, Any]) -> str:
        job_id = f"pres_job_{uuid.uuid4().hex[:12]}"
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        job = {
            "id": job_id,
            "status": "in_progress",
            "stage": "reviewing_coverage",
            "stage_label": "Reviewing coverage, date boundaries & partial-year disclosure",
            "progress_pct": 15,
            "deck_id": None,
            "error": None,
            "scope": scope,
            "current_slide": 0,
            "total_slides": int(scope.get("target_length") or 8),
            "current_slide_title": "Initializing slide architecture",
            "slide_status_list": [],
            "created_at": now,
            "updated_at": now
        }
        with self._lock:
            self._jobs[job_id] = job
            self._cancel_flags[job_id] = False

        # Persist to database
        try:
            with get_connection() as conn:
                conn.execute(
                    "INSERT INTO presentation_jobs (id, status, stage, stage_label, progress_pct, scope_json, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (job_id, job["status"], job["stage"], job["stage_label"], job["progress_pct"], json.dumps(scope), now, now)
                )
                conn.commit()
        except Exception as exc:
            logger.warning(f"Could not persist presentation job to DB: {exc}")

        return job_id

    def is_cancelled(self, job_id: str) -> bool:
        with self._lock:
            return self._cancel_flags.get(job_id, False)

    def cancel_job(self, job_id: str) -> bool:
        with self._lock:
            if job_id not in self._jobs:
                return False
            self._cancel_flags[job_id] = True
            job = self._jobs[job_id]
            job["status"] = "cancelled"
            job["stage"] = "cancelled"
            job["stage_label"] = "Generation cancelled by user"
            now = datetime.datetime.now(datetime.timezone.utc).isoformat()
            job["updated_at"] = now

        try:
            with get_connection() as conn:
                conn.execute(
                    "UPDATE presentation_jobs SET status='cancelled', stage='cancelled', stage_label='Generation cancelled by user', updated_at=? WHERE id=?",
                    (now, job_id)
                )
                conn.commit()
        except Exception:
            pass
        return True

    def update_stage(
        self,
        job_id: str,
        stage: str,
        stage_label: str,
        progress_pct: int,
        deck_id: str | None = None,
        error: str | None = None,
        extra: dict[str, Any] | None = None
    ):
        with self._lock:
            if job_id not in self._jobs:
                return
            job = self._jobs[job_id]
            job["stage"] = stage
            job["stage_label"] = stage_label
            job["progress_pct"] = progress_pct
            now = datetime.datetime.now(datetime.timezone.utc).isoformat()
            job["updated_at"] = now
            if deck_id:
                job["deck_id"] = deck_id
            if error:
                job["status"] = "failed"
                job["error"] = error
            elif stage == "ready":
                job["status"] = "ready"
            if extra:
                job.update(extra)

            extra_to_save = {
                k: job[k] for k in (
                    "current_slide",
                    "total_slides",
                    "current_slide_title",
                    "current_slide_category",
                    "slide_status_list"
                )
                if k in job
            }

        try:
            with get_connection() as conn:
                conn.execute(
                    "UPDATE presentation_jobs SET status=?, stage=?, stage_label=?, progress_pct=?, deck_id=?, error=?, extra_json=?, updated_at=? WHERE id=?",
                    (job["status"], stage, stage_label, progress_pct, job.get("deck_id"), error, json.dumps(extra_to_save), now, job_id)
                )
                conn.commit()
        except Exception as exc:
            logger.debug(f"Could not update presentation_jobs in DB: {exc}")

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            if job_id in self._jobs:
                return copy.deepcopy(self._jobs[job_id])

        # Fallback to DB
        try:
            with get_connection() as conn:
                r = conn.execute("SELECT * FROM presentation_jobs WHERE id=?", (job_id,)).fetchone()
                if r:
                    res = {
                        "id": r["id"],
                        "status": r["status"],
                        "stage": r["stage"],
                        "stage_label": r["stage_label"],
                        "progress_pct": r["progress_pct"],
                        "deck_id": r["deck_id"],
                        "error": r["error"],
                        "scope": json.loads(r["scope_json"] or "{}"),
                        "created_at": r["created_at"],
                        "updated_at": r["updated_at"]
                    }
                    try:
                        if "extra_json" in r.keys() and r["extra_json"]:
                            extra_data = json.loads(r["extra_json"])
                            res.update(extra_data)
                    except Exception:
                        pass
                    return res
        except Exception as exc:
            logger.debug(f"Could not load presentation job from DB: {exc}")
        return None


# Global singleton instance
job_manager = PresentationJobManager()
