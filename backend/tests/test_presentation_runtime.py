"""Presentation phase transitions and deadlines use persisted, poll-visible state."""
import datetime
import threading
import time

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import get_connection
from app.routers import presentations
from app.services.presentation import pipeline_orchestrator as pipeline, runtime
from app.services.presentation.job_manager import PresentationJobManager


@pytest.fixture
def manager(monkeypatch):
    mgr = PresentationJobManager()
    monkeypatch.setattr(presentations, 'job_manager', mgr)
    monkeypatch.setattr(pipeline, 'job_manager', mgr)
    monkeypatch.setattr(runtime, 'HEARTBEAT_SECONDS', 0.01)
    return mgr


def test_phase_one_completes_and_phase_two_is_poll_visible_before_evidence_returns(manager, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    monkeypatch.setattr(pipeline, 'preview_presentation_scope', lambda *_: {'eligible': True})

    def evidence(*_):
        entered.set()
        release.wait(2)
        raise ValueError('Controlled end of test')

    monkeypatch.setattr(pipeline, 'collect_workspace_evidence', evidence)
    jid = manager.create_job({'sheet_id': 1})
    worker = threading.Thread(target=pipeline.execute_presentation_pipeline_async, args=(jid, {'sheet_id': 1}, manager))
    worker.start()
    try:
        assert entered.wait(2)
        job = TestClient(app).get(f'/api/presentations/jobs/{jid}').json()
        assert job['stage'] == 'evidence_audit'
        assert job['status'] == 'in_progress'
        assert job['progress_pct'] == 10
        assert [(e['phase'], e['status']) for e in job['phase_events']] == [
            ('brief_setup', 'started'), ('brief_setup', 'completed'), ('evidence_audit', 'started')]
        assert job['phase_started_at'] and job['heartbeat_at']
    finally:
        release.set()
        worker.join(2)
    assert not worker.is_alive()


def test_initial_dependency_failure_is_persisted_and_retry_has_fresh_identity(manager, monkeypatch):
    def broken(*_):
        raise ValueError('Selected sheet is unavailable; select a sheet and try again.')
    monkeypatch.setattr(pipeline, 'preview_presentation_scope', broken)
    jid = manager.create_job({'sheet_id': 1})
    pipeline.execute_presentation_pipeline_async(jid, {'sheet_id': 1}, manager)
    job = TestClient(app).get(f'/api/presentations/jobs/{jid}').json()
    assert job['status'] == 'failed'
    assert job['error_code'] == 'PIPELINE_FAILED'
    assert 'select a sheet' in job['error']
    retry = manager.create_job({'sheet_id': 1})
    assert retry != jid
    assert manager.get_job(jid)['status'] == 'failed'


def test_never_returning_initial_dependency_times_out_and_late_result_cannot_revive(manager, monkeypatch):
    release = threading.Event()
    monkeypatch.setattr(runtime, 'SCOPE_TIMEOUT_SECONDS', 0.04)
    monkeypatch.setattr(pipeline, 'preview_presentation_scope', lambda *_: (release.wait(2), {'eligible': True})[1])
    jid = manager.create_job({'sheet_id': 1})
    started = time.monotonic()
    try:
        pipeline.execute_presentation_pipeline_async(jid, {'sheet_id': 1}, manager)
        job = TestClient(app).get(f'/api/presentations/jobs/{jid}').json()
        assert time.monotonic() - started < 1
        assert job['status'] == 'failed'
        assert job['error_code'] == 'DEPENDENCY_TIMEOUT'
        assert 'Source validation timed out' in job['error']
        manager.update_stage(jid, 'ready', 'Late result', 100)
        assert manager.get_job(jid)['status'] == 'failed'
    finally:
        release.set()


def test_heartbeat_reports_activity_without_fake_progress_or_resetting_deadline(manager):
    jid = manager.create_job({'sheet_id': 1})
    manager.update_stage(jid, 'brief_setup', 'Checking scope', 3)
    before = manager.get_job(jid)
    manager.heartbeat(jid, 'scope_validation')
    after = manager.get_job(jid)
    assert after['progress_pct'] == 3
    assert after['phase_started_at'] == before['phase_started_at']
    assert after['updated_at'] == before['updated_at']
    assert after['heartbeat_at'] >= before['heartbeat_at']
    assert after['dependency'] == 'scope_validation'


def test_watchdog_expires_blocked_phase_independently_of_polling(manager, monkeypatch):
    monkeypatch.setattr(runtime, 'PHASE_TIMEOUT_SECONDS', 0.01)
    jid = manager.create_job({'sheet_id': 1})
    manager.update_stage(jid, 'narrative_arc', 'Planning', 18)
    finished = threading.Event()
    watcher = threading.Thread(target=runtime.watch_job, args=(manager, jid, finished))
    watcher.start()
    watcher.join(1)
    assert not watcher.is_alive()
    job = manager.get_job(jid)
    assert job['status'] == 'failed'
    assert job['error_code'] == 'PHASE_TIMEOUT'
    assert manager.is_cancelled(jid)


def test_progress_persistence_failure_is_not_silently_swallowed(manager, monkeypatch):
    jid = manager.create_job({'sheet_id': 1})
    import importlib
    module = importlib.import_module("app.services.presentation.job_manager")
    from contextlib import contextmanager
    @contextmanager
    def broken():
        raise RuntimeError('Database unavailable')
        yield
    monkeypatch.setattr(module, 'session_scope', broken)
    with pytest.raises(RuntimeError, match='Could not save presentation progress'):
        manager.update_stage(jid, 'brief_setup', 'Validating', 3)


def test_failed_state_write_is_repaired_on_next_poll(manager, monkeypatch):
    import importlib
    module = importlib.import_module('app.services.presentation.job_manager')
    original = module.session_scope
    from contextlib import contextmanager
    @contextmanager
    def broken():
        raise RuntimeError('Temporary write failure')
        yield
    jid = manager.create_job({'sheet_id': 1})
    monkeypatch.setattr(module, 'session_scope', broken)
    with pytest.raises(RuntimeError):
        manager.fail_job(jid, 'PIPELINE_FAILED', 'Please try again.')
    monkeypatch.setattr(module, 'session_scope', original)
    assert manager.get_job(jid)['status'] == 'failed'
    assert PresentationJobManager().get_job(jid)['status'] == 'failed'
