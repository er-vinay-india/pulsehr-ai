import copy
import datetime
import json
import logging
import os
import threading
import uuid
from typing import Any

from ...db.database import session_scope

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
        self._lock = threading.RLock()
        self._ensure_extra_column()

    def _ensure_extra_column(self):
        try:
            with session_scope() as conn:
                cols = [r[1] for r in conn.execute("PRAGMA table_info(presentation_jobs)").fetchall()]
                if "extra_json" not in cols:
                    conn.execute("ALTER TABLE presentation_jobs ADD COLUMN extra_json TEXT DEFAULT '{}'")
                if "worker_pid" not in cols:
                    conn.execute("ALTER TABLE presentation_jobs ADD COLUMN worker_pid INTEGER")
                if "recovery_attempts" not in cols:
                    conn.execute("ALTER TABLE presentation_jobs ADD COLUMN recovery_attempts INTEGER NOT NULL DEFAULT 0")
        except Exception as exc:
            logger.debug(f"Could not check/add extra_json column: {exc}")

    def recover_interrupted_jobs(self, job_id: str | None = None) -> list[dict[str, Any]]:
        """Claim orphaned work, preserving its ID and scope for a fresh pipeline run.

        Live owners are left alone. Legacy reload failures are recovered only when
        that particular job is requested, not as a bulk retry of historical jobs.
        """
        self._ensure_extra_column()
        recovered = []
        with self._lock, session_scope() as conn:
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
            "stage": "brief_setup",
            "stage_label": "Validating presentation brief and selected sources",
            "progress_pct": 3,
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
            with session_scope() as conn:
                conn.execute(
                    "INSERT INTO presentation_jobs (id, status, stage, stage_label, progress_pct, scope_json, created_at, updated_at, worker_pid) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (job_id, job["status"], job["stage"], job["stage_label"], job["progress_pct"], json.dumps(scope), now, now, os.getpid())
                )
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
        with session_scope() as conn:
            cancelled = conn.execute(
                "UPDATE presentation_jobs SET status='cancelled', stage='cancelled', "
                "stage_label='Generation cancelled by user', updated_at=? "
                "WHERE id=? AND status IN ('in_progress', 'pending')", (now, job_id),
            )
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
            if job.get("status") not in ("in_progress", "pending"):
                return
            now = datetime.datetime.now(datetime.timezone.utc).isoformat()
            if job.get("stage") != stage or not job.get("phase_started_at"):
                events = job.setdefault("phase_events", [])
                previous_start = job.get("phase_started_at")
                if previous_start:
                    events.append({"phase": job["stage"], "status": "failed" if error else "completed", "at": now,
                                   "elapsed_ms": round((datetime.datetime.fromisoformat(now) - datetime.datetime.fromisoformat(previous_start)).total_seconds()*1000)})
                if previous_start:
                    logger.info("presentation_phase job_id=%s phase=%s status=%s elapsed_ms=%s", job_id, job["stage"], events[-1]["status"], events[-1]["elapsed_ms"])
                events.append({"phase": stage, "status": "started", "at": now})
                job["phase_started_at"] = now
                job["phase_events"] = events[-80:]
                logger.info("presentation_phase job_id=%s dataset_id=%s sheet_id=%s phase=%s status=%s", job_id, job.get("scope", {}).get("dataset_id"), job.get("scope", {}).get("sheet_id"), stage, "failed" if error else "started")
            job["heartbeat_at"] = now
            job["dependency"] = None
            job["stage"] = stage
            job["stage_label"] = stage_label
            # Failure is terminal, not completed work. Preserve the last known
            # progress even when a producer reports failure with 100 percent.
            job["progress_pct"] = (
                min(99, max(0, job.get("progress_pct", 0))) if error
                else min(100 if stage == "ready" else 99, max(0, progress_pct))
            )
            progress_pct = job["progress_pct"]
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
                    "active_phase", "phase_started_at", "heartbeat_at", "dependency", "phase_events", "error_code"
                )
                if k in job
            }

        try:
            with session_scope() as conn:
                conn.execute(
                    "UPDATE presentation_jobs SET status=?, stage=?, stage_label=?, progress_pct=?, deck_id=?, error=?, extra_json=?, updated_at=? "
                    "WHERE id=? AND status IN ('in_progress', 'pending') AND worker_pid=?",
                    (job["status"], stage, stage_label, progress_pct, job.get("deck_id"), error, json.dumps(extra_to_save), now, job_id, os.getpid())
                )
        except Exception as exc:
            logger.exception("Presentation state persistence failed job_id=%s stage=%s", job_id, stage)
            raise RuntimeError("Could not save presentation progress. Please try again.") from exc

    def heartbeat(self, job_id: str, dependency: str):
        with self._lock, session_scope() as conn:
            row = conn.execute("SELECT extra_json FROM presentation_jobs WHERE id=? AND status IN ('in_progress','pending') AND worker_pid=?", (job_id, os.getpid())).fetchone()
            if not row:
                return
            extra = json.loads(row['extra_json'] or '{}')
            extra.update(heartbeat_at=datetime.datetime.now(datetime.timezone.utc).isoformat(), dependency=dependency)
            conn.execute("UPDATE presentation_jobs SET extra_json=? WHERE id=? AND status IN ('in_progress','pending') AND worker_pid=?", (json.dumps(extra), job_id, os.getpid()))
            if job_id in self._jobs:
                self._jobs[job_id].update(extra)

    def expire_phase(self, job_id: str, timeout: float) -> bool:
        with self._lock:
            job = self.get_job(job_id)
            if not job or job['status'] not in ('in_progress', 'pending'):
                return False
            started = job.get('phase_started_at') or job['updated_at']
            elapsed = (datetime.datetime.now(datetime.timezone.utc) - datetime.datetime.fromisoformat(started)).total_seconds()
            if elapsed < timeout:
                return False
            self.fail_job(job_id, 'PHASE_TIMEOUT', f"Presentation generation exceeded the {timeout:g}-second limit for its current phase. Check the local AI service, then try again.")
            return True

    def fail_job(self, job_id: str, code: str, message: str):
        with self._lock:
            try:
                self.update_stage(job_id, 'failed', message, 0, error=message, extra={'error_code': code})
            finally:
                self._cancel_flags[job_id] = True
            logger.error('presentation_failed job_id=%s error_code=%s', job_id, code)

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        # Persisted state also reflects cancellation by another API worker.
        try:
            with session_scope() as conn:
                r = conn.execute("SELECT * FROM presentation_jobs WHERE id=?", (job_id,)).fetchone()
                if r:
                    # A failed write must not make a known terminal failure look
                    # active. Repair it on the next successful DB connection.
                    with self._lock:
                        local = self._jobs.get(job_id)
                        terminal = copy.deepcopy(local) if local and local.get('status') == 'failed' else None
                    if terminal and r['status'] in ('in_progress', 'pending') and r['worker_pid'] == os.getpid():
                        conn.execute("UPDATE presentation_jobs SET status='failed', stage='failed', stage_label=?, error=?, extra_json=?, updated_at=? WHERE id=? AND status IN ('in_progress','pending') AND worker_pid=?",
                                     (terminal['stage_label'], terminal['error'], json.dumps({k: terminal[k] for k in ('phase_started_at', 'phase_events', 'heartbeat_at', 'error_code') if k in terminal}), terminal['updated_at'], job_id, os.getpid()))
                        return terminal
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
