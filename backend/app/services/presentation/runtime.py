"""Bound presentation dependencies without waiting on an abandoned executor."""
import logging
import os
import queue
import threading
import time

logger = logging.getLogger(__name__)
# Writer fallback/identity attempts plus SQLite's 60s busy budget can exceed
# several minutes. These are total wall budgets, not HTTP inactivity timeouts.
EVIDENCE_TIMEOUT_SECONDS = float(os.getenv('PRESENTATION_EVIDENCE_TIMEOUT_SECONDS', '600'))
SCOPE_TIMEOUT_SECONDS = float(os.getenv('PRESENTATION_SCOPE_TIMEOUT_SECONDS', '120'))
MEMORY_TIMEOUT_SECONDS = float(os.getenv('PRESENTATION_MEMORY_TIMEOUT_SECONDS', '35'))
PHASE_TIMEOUT_SECONDS = float(os.getenv('PRESENTATION_PHASE_TIMEOUT_SECONDS', '900'))
HEARTBEAT_SECONDS = float(os.getenv('PRESENTATION_HEARTBEAT_SECONDS', '15'))
DEPENDENCY_LABELS = {
    'scope_validation': 'Source validation',
    'workspace_evidence': 'Data preparation',
    'historical_memory': 'Presentation history retrieval',
}


class PresentationDependencyTimeout(TimeoutError):
    pass


def run_dependency(manager, job_id, dependency, operation, timeout):
    """A hung daemon cannot hold the coordinator or publish late results."""
    result = queue.Queue(maxsize=1)
    started = time.monotonic()

    def work():
        try:
            result.put((True, operation()))
        except BaseException as exc:
            result.put((False, exc))

    threading.Thread(target=work, daemon=True, name=f'pres-dependency-{job_id}-{dependency}').start()
    manager.heartbeat(job_id, dependency)
    logger.info('presentation_dependency job_id=%s dependency=%s status=started', job_id, dependency)
    while True:
        remaining = timeout - (time.monotonic() - started)
        if remaining <= 0:
            logger.error('presentation_dependency job_id=%s dependency=%s status=failed error_code=DEPENDENCY_TIMEOUT elapsed_ms=%.0f', job_id, dependency, (time.monotonic()-started)*1000)
            raise PresentationDependencyTimeout(f'{DEPENDENCY_LABELS.get(dependency, "Presentation preparation")} timed out after {timeout:g} seconds. Check the local AI service, then try again.')
        if manager.is_cancelled(job_id):
            raise RuntimeError('Presentation generation was stopped.')
        try:
            ok, value = result.get(timeout=min(HEARTBEAT_SECONDS, remaining))
        except queue.Empty:
            manager.heartbeat(job_id, dependency)
            continue
        logger.info('presentation_dependency job_id=%s dependency=%s status=%s elapsed_ms=%.0f', job_id, dependency, 'completed' if ok else 'failed', (time.monotonic()-started)*1000)
        if not ok:
            raise value
        return value


def watch_job(manager, job_id, finished):
    """Independent of client polling and of the pipeline's blocked thread."""
    while not finished.wait(HEARTBEAT_SECONDS):
        if manager.expire_phase(job_id, PHASE_TIMEOUT_SECONDS):
            return
        job = manager.get_job(job_id)
        if not job or job['status'] not in ('in_progress', 'pending'):
            return
        manager.heartbeat(job_id, job.get('dependency') or job['stage'])
