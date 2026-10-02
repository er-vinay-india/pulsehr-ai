"""Presentation reload recovery uses saved scopes and never retries real failures."""
import json
import os
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app.db.database import get_connection
from app.main import app
from app.services.presentation.job_manager import (
    PresentationJobManager,
    RELOAD_INTERRUPTION_ERROR,
)
from app.services.presentation import pipeline_orchestrator as pipeline
from app.routers import presentations


@pytest.fixture
def manager(monkeypatch):
    mgr = PresentationJobManager()
    monkeypatch.setattr(pipeline, 'job_manager', mgr)
    monkeypatch.setattr(presentations, 'job_manager', mgr)
    return mgr


def orphan(job_id):
    # An absent owner models a persisted job from the server that stopped.
    with get_connection() as conn:
        conn.execute('UPDATE presentation_jobs SET worker_pid=NULL WHERE id=?', (job_id,))
        conn.commit()


def test_new_manager_does_not_fail_live_generation(manager):
    job_id = manager.create_job({'objective': 'Existing live presentation'})
    other = PresentationJobManager()
    assert other.get_job(job_id)['status'] == 'in_progress'
    assert other.recover_interrupted_jobs() == []
    assert manager.get_job(job_id)['error'] is None


def test_recovery_preserves_id_and_exact_scope_and_resets_partial_progress(manager):
    scope = {
        'sheet_id': 123, 'sheet_ids': [123, 456], 'scope_type': 'custom_sheets',
        'objective': 'Quarterly performance', 'theme_id': 'clean_light',
        'target_length': 12, 'instructions': 'Compare the two sources',
        'content_preferences': {'include_appendix': True}, 'deliverable': 'pptx',
    }
    job_id = manager.create_job(scope)
    manager.update_stage(job_id, 'headlines', 'Building slides', 45, extra={
        'current_slide': 4, 'slide_status_list': [{'order': 1, 'status': 'complete'}],
    })
    orphan(job_id)
    restored_manager = PresentationJobManager()
    recovered = restored_manager.recover_interrupted_jobs()
    assert len(recovered) == 1
    job = recovered[0]
    assert job['id'] == job_id
    assert job['scope'] == scope
    assert job['status'] == 'in_progress'
    assert job['stage'] == 'recovering'
    assert job['progress_pct'] == 0
    assert job['current_slide'] == 0
    assert job['slide_status_list'] == []
    assert job['total_slides'] == 12
    assert job['error'] is None
    assert job['recovery_attempts'] == 1
    assert job['worker_pid'] == os.getpid()
    assert PresentationJobManager().recover_interrupted_jobs() == []


def test_recovery_dispatches_original_job_and_allows_completion(manager, monkeypatch):
    scope = {'objective': 'Rebuild from persisted settings', 'target_length': 4}
    job_id = manager.create_job(scope)
    orphan(job_id)
    calls = []

    def worker(recovered_id, recovered_scope):
        calls.append((recovered_id, recovered_scope))
        manager.update_stage(recovered_id, 'evidence_audit', 'Checking evidence', 18)
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO presentation_decks (id,title,theme_id,spec_json) VALUES (?,?,?,?)",
                ('recovered_deck', 'Recovered presentation', 'clean_light', '{"id":"recovered_deck"}'),
            )
            conn.commit()
        manager.update_stage(recovered_id, 'ready', 'Presentation ready', 100, deck_id='recovered_deck')

    monkeypatch.setattr(pipeline, '_launch_presentation_worker', worker)
    pipeline.recover_presentation_jobs()
    pipeline.recover_presentation_jobs()
    assert calls == [(job_id, scope)]
    client = TestClient(app)
    result = client.get(f'/api/presentations/jobs/{job_id}').json()
    assert result['status'] == 'ready'
    assert result['deck']['id'] == 'recovered_deck'
    assert result['error'] is None


def test_concurrent_recovery_claims_job_only_once(manager):
    job_id = manager.create_job({'objective': 'Concurrent recovery'})
    orphan(job_id)
    managers = [PresentationJobManager(), PresentationJobManager()]
    with ThreadPoolExecutor(max_workers=2) as workers:
        claims = list(workers.map(lambda mgr: mgr.recover_interrupted_jobs(job_id), managers))
    assert sum(len(claim) for claim in claims) == 1
    assert manager.get_job(job_id)['recovery_attempts'] == 1


def test_poll_recovers_existing_reload_failure_once_and_cancellation_survives(manager, monkeypatch):
    scope = {'objective': 'Previously interrupted presentation', 'theme_id': 'executive_dark'}
    job_id = manager.create_job(scope)
    with get_connection() as conn:
        conn.execute(
            "UPDATE presentation_jobs SET status='failed', stage='failed', error=?, worker_pid=NULL WHERE id=?",
            (RELOAD_INTERRUPTION_ERROR, job_id),
        )
        conn.commit()
    calls = []
    monkeypatch.setattr(pipeline, '_launch_presentation_worker', lambda jid, settings: calls.append((jid, settings)))
    # Startup does not resurrect historical failed jobs indiscriminately.
    pipeline.recover_presentation_jobs()
    assert calls == []
    client = TestClient(app)
    response = client.get(f'/api/presentations/jobs/{job_id}')
    assert response.status_code == 200
    assert response.json()['status'] == 'in_progress'
    assert response.json()['error'] is None
    client.get(f'/api/presentations/jobs/{job_id}')
    assert calls == [(job_id, scope)]
    assert client.post(f'/api/presentations/jobs/{job_id}/cancel').status_code == 200
    manager.update_stage(job_id, 'ready', 'Late update must not win', 100)
    assert manager.is_cancelled(job_id)
    assert client.get(f'/api/presentations/jobs/{job_id}').json()['status'] == 'cancelled'
    assert len(calls) == 1


@pytest.mark.parametrize('terminal', ['ready', 'cancelled', 'failed'])
def test_terminal_jobs_and_real_validation_failures_are_not_retried(manager, terminal):
    job_id = manager.create_job({'objective': 'Terminal presentation'})
    if terminal == 'cancelled':
        manager.cancel_job(job_id)
    elif terminal == 'failed':
        manager.update_stage(job_id, 'failed', 'Evidence validation failed', 100, error='Evidence discrepancy')
    else:
        manager.update_stage(job_id, 'ready', 'Ready', 100)
    orphan(job_id)
    assert manager.recover_interrupted_jobs(job_id) == []
    assert manager.get_job(job_id)['status'] == terminal


def test_repeated_reloads_stop_at_persisted_retry_limit(manager):
    job_id = manager.create_job({'objective': 'Repeated interruption'})
    for attempt in range(1, manager.MAX_RECOVERY_ATTEMPTS + 1):
        orphan(job_id)
        recovered = PresentationJobManager().recover_interrupted_jobs(job_id)
        assert recovered[0]['recovery_attempts'] == attempt
    orphan(job_id)
    assert PresentationJobManager().recover_interrupted_jobs(job_id) == []
    job = manager.get_job(job_id)
    assert job['status'] == 'failed'
    assert 'interrupted repeatedly' in job['error']
    assert manager.recover_interrupted_jobs(job_id) == []


def test_corrupt_saved_scope_fails_explicitly(manager):
    job_id = manager.create_job({'objective': 'Invalid saved scope'})
    with get_connection() as conn:
        conn.execute("UPDATE presentation_jobs SET scope_json='[]', worker_pid=NULL WHERE id=?", (job_id,))
        conn.commit()
    assert manager.recover_interrupted_jobs(job_id) == []
    with get_connection() as conn:
        row = conn.execute('SELECT status,error FROM presentation_jobs WHERE id=?', (job_id,)).fetchone()
    assert row['status'] == 'failed'
    assert 'settings are unavailable' in row['error']


def test_cancel_from_another_manager_blocks_inflight_stage_update(manager):
    job_id = manager.create_job({'objective': 'Shared cancellation'})
    assert PresentationJobManager().cancel_job(job_id)
    manager.update_stage(job_id, 'ready', 'Finished after cancellation', 100)
    assert manager.get_job(job_id)['status'] == 'cancelled'
    assert manager.is_cancelled(job_id)


def test_legacy_job_table_migrates_without_marking_jobs_failed():
    with get_connection() as conn:
        conn.execute('DROP TABLE presentation_jobs')
        conn.execute('''CREATE TABLE presentation_jobs (
            id TEXT PRIMARY KEY, status TEXT, stage TEXT, stage_label TEXT,
            progress_pct INTEGER, deck_id TEXT, error TEXT, scope_json TEXT,
            created_at TEXT, updated_at TEXT
        )''')
        conn.execute(
            'INSERT INTO presentation_jobs VALUES (?,?,?,?,?,?,?,?,?,?)',
            ('legacy_job', 'in_progress', 'headlines', 'Building slides', 18,
             None, None, json.dumps({'objective': 'Legacy scope'}), '2026-10-02', '2026-10-02'),
        )
        conn.commit()
    restored = PresentationJobManager()
    assert restored.get_job('legacy_job')['status'] == 'in_progress'
    recovered = restored.recover_interrupted_jobs()
    assert recovered[0]['id'] == 'legacy_job'
    assert recovered[0]['scope'] == {'objective': 'Legacy scope'}


def test_worker_launch_failure_is_reported_and_not_auto_retried(manager, monkeypatch):
    class BrokenThread:
        def __init__(self, **kwargs):
            pass

        def start(self):
            raise RuntimeError('Thread could not start')

    monkeypatch.setattr(pipeline.threading, 'Thread', BrokenThread)
    with pytest.raises(RuntimeError, match='Thread could not start'):
        pipeline.start_presentation_job({'objective': 'Worker failure'})
    job = manager.get_job(next(iter(manager._jobs)))
    assert job['status'] == 'failed'
    assert job['error'] == 'Thread could not start'
    assert manager.recover_interrupted_jobs(job['id']) == []

    # A failed relaunch must not take down application startup or status polling.
    interrupted_id = manager.create_job({'objective': 'Recovery worker failure'})
    orphan(interrupted_id)
    pipeline.recover_presentation_jobs()
    assert manager.get_job(interrupted_id)['status'] == 'failed'
