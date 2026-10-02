import copy
import datetime
import json
import logging
import os
import threading
import uuid
from typing import Any

from ...db.database import get_connection

logger = logging.getLogger(__name__)
RELOAD_INTERRUPTION_ERROR = "Generation was interrupted by server reload. Please click Generate Again to rebuild."


def _process_is_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class PresentationJobManager:
    """Thread-safe background job pipeline coordinator."""

    MAX_RECOVERY_ATTEMPTS = 3

    def __init__(self):
        self._jobs: dict[str, dict[str, Any]] = {}
        self._cancel_flags: dict[str, bool] = {}
        self._lock = threading.Lock()
        self._ensure_extra_column()

    def _ensure_extra_column(self):
        try:
            with get_connection() as conn:
                cols = [r[1] for r in conn.execute("PRAGMA table_info(presentation_jobs)").fetchall()]
                if "extra_json" not in cols:
                    conn.execute("ALTER TABLE presentation_jobs ADD COLUMN extra_json TEXT DEFAULT '{}'")
                if "worker_pid" not in cols:
                    conn.execute("ALTER TABLE presentation_jobs ADD COLUMN worker_pid INTEGER")
                if "recovery_attempts" not in cols:
                    conn.execute("ALTER TABLE presentation_jobs ADD COLUMN recovery_attempts INTEGER NOT NULL DEFAULT 0")
                conn.commit()
        except Exception as exc:
            logger.debug(f"Could not check/add extra_json column: {exc}")

    def recover_interrupted_jobs(self, job_id: str | None = None) -> list[dict[str, Any]]:
        """Claim orphaned work, preserving its ID and scope for a fresh pipeline run.

        Live owners are left alone. Legacy reload failures are recovered only when
        that particular job is requested, not as a bulk retry of historical jobs.
        """
        self._ensure_extra_column()
        recovered = []
        with self._lock, get_connection() as conn:
            if job_id is None:
                rows = conn.execute(
                    "SELECT * FROM presentation_jobs WHERE status IN ('in_progress', 'pending')"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM presentation_jobs WHERE id=? AND "
                    "(status IN ('in_progress', 'pending') OR (status='failed' AND error=?))",
                    (job_id, RELOAD_INTERRUPTION_ERROR),
                ).fetchall()
            for row in rows:
                if _process_is_alive(row['worker_pid']):
                    continue
                now = datetime.datetime.now(datetime.timezone.utc).isoformat()
                predicate = "WHERE id=? AND status=? AND worker_pid IS ? AND updated_at=?"
                identity = (row['id'], row['status'], row['worker_pid'], row['updated_at'])
                attempts = row['recovery_attempts']
                try:
                    scope = json.loads(row['scope_json'])
                    if not isinstance(scope, dict) or not scope:
                        raise ValueError("Saved presentation settings are unavailable. Please start a new generation.")
                    total_slides = int(scope.get('target_length') or 8)
                    if attempts >= self.MAX_RECOVERY_ATTEMPTS:
                        raise ValueError("Generation was interrupted repeatedly. Wait until the server is stable, then try again.")
                except (ValueError, TypeError) as exc:
                    conn.execute(
                        "UPDATE presentation_jobs SET status='failed', stage='failed', stage_label='Unable to recover generation', "
                        "error=?, updated_at=? " + predicate, (str(exc), now, *identity),
                    )
                    continue
                extra = {
                    'current_slide': 0, 'total_slides': total_slides,
                    'current_slide_title': 'Rebuilding presentation from saved settings',
                    'slide_status_list': [], 'active_phase': 'brief_setup',
                }
                claimed = conn.execute(
                    "UPDATE presentation_jobs SET status='in_progress', stage='recovering', "
                    "stage_label='Server reconnected. Rebuilding your presentation automatically…', "
                    "progress_pct=0, deck_id=NULL, error=NULL, extra_json=?, worker_pid=?, "
                    "recovery_attempts=?, updated_at=? " + predicate,
                    (json.dumps(extra), os.getpid(), attempts + 1, now, *identity),
                )
                if claimed.rowcount != 1:
                    continue
                job = dict(row)
                job.pop('scope_json', None)
                job.pop('extra_json', None)
                job.update(
                    scope=scope, status='in_progress', stage='recovering',
                    stage_label='Server reconnected. Rebuilding your presentation automatically…',
                    progress_pct=0, deck_id=None, error=None, worker_pid=os.getpid(),
                    recovery_attempts=attempts + 1, updated_at=now, **extra,
                )
                self._jobs[job['id']] = job
                self._cancel_flags[job['id']] = False
                recovered.append(copy.deepcopy(job))
            conn.commit()
        return recovered

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
        job['worker_pid'] = os.getpid()
        job['recovery_attempts'] = 0
        with self._lock:
            self._jobs[job_id] = job
            self._cancel_flags[job_id] = False

        # Persist to database
        try:
            with get_connection() as conn:
                conn.execute(
                    "INSERT INTO presentation_jobs (id, status, stage, stage_label, progress_pct, scope_json, created_at, updated_at, worker_pid) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (job_id, job["status"], job["stage"], job["stage_label"], job["progress_pct"], json.dumps(scope), now, now, os.getpid())
                )
                conn.commit()
        except Exception as exc:
            with self._lock:
                self._jobs.pop(job_id, None)
                self._cancel_flags.pop(job_id, None)
            raise RuntimeError("Could not save presentation generation settings. Please retry.") from exc

        return job_id

    def is_cancelled(self, job_id: str) -> bool:
        with self._lock:
            if self._cancel_flags.get(job_id, False):
                return True
        job = self.get_job(job_id)
        return bool(job and (job['status'] in ('cancelled', 'failed') or job.get('worker_pid') not in (None, os.getpid())))

    def cancel_job(self, job_id: str) -> bool:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with get_connection() as conn:
            cancelled = conn.execute(
                "UPDATE presentation_jobs SET status='cancelled', stage='cancelled', "
                "stage_label='Generation cancelled by user', updated_at=? "
                "WHERE id=? AND status IN ('in_progress', 'pending')", (now, job_id),
            )
            conn.commit()
            if cancelled.rowcount != 1:
                return False
        with self._lock:
            self._cancel_flags[job_id] = True
            self._jobs.pop(job_id, None)
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
            if job_id not in self._jobs or self._cancel_flags.get(job_id):
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
            job = copy.deepcopy(job)

            extra_to_save = {
                k: job[k] for k in (
                    "current_slide",
                    "total_slides",
                    "current_slide_title",
                    "current_slide_category",
                    "slide_status_list",
                    "observer_note",
                    "observer_context",
                    "active_phase"
                )
                if k in job
            }

        try:
            with get_connection() as conn:
                conn.execute(
                    "UPDATE presentation_jobs SET status=?, stage=?, stage_label=?, progress_pct=?, deck_id=?, error=?, extra_json=?, updated_at=? "
                    "WHERE id=? AND status IN ('in_progress', 'pending') AND worker_pid=?",
                    (job["status"], stage, stage_label, progress_pct, job.get("deck_id"), error, json.dumps(extra_to_save), now, job_id, os.getpid())
                )
                conn.commit()
        except Exception as exc:
            logger.debug(f"Could not update presentation_jobs in DB: {exc}")

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        # Persisted state also reflects cancellation by another API worker.
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
                    res['worker_pid'] = r['worker_pid']
                    res['recovery_attempts'] = r['recovery_attempts']
                    try:
                        if "extra_json" in r.keys() and r["extra_json"]:
                            extra_data = json.loads(r["extra_json"])
                            res.update(extra_data)
                    except Exception:
                        pass
                    return res
        except Exception as exc:
            logger.debug(f"Could not load presentation job from DB: {exc}")
            with self._lock:
                if job_id in self._jobs:
                    return copy.deepcopy(self._jobs[job_id])
        return None


# Global singleton instance
job_manager = PresentationJobManager()
