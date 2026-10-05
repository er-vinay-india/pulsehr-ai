"""Loaded sources remain authoritative when retrieval has no text matches."""
import json
import sqlite3

import pandas as pd
from fastapi.testclient import TestClient

from app.core import config
from app.db.database import get_connection
from app.main import app
from app.services import ai_copilot, sheet_catalog
from app.services.copilot import council_coordinator


def store_sheet(filename, records):
    frame = pd.DataFrame(records)
    frame.to_csv(config.UPLOADS_DIR / filename, index=False)
    with get_connection() as conn:
        dataset = conn.execute(
            'INSERT INTO dataset_uploads(filename, original_name, file_type) VALUES (?,?,?)',
            (filename, filename, 'csv'),
        ).lastrowid
        sheet_catalog.insert_sheets(conn, dataset, sheet_catalog.prepare_sheets({'Sheet1': frame}, filename, embed=False))
        sid = conn.execute('SELECT id FROM sheets WHERE dataset_id=?', (dataset,)).fetchone()['id']
        conn.commit()
    return dataset, sid


def test_catalogue_uses_live_relationship_table_and_keeps_sheet_names():
    ds, sid = store_sheet('new.csv', [{'Department': 'Sales', 'attendance_rate': 96}])
    _, other = store_sheet('other.csv', [{'Department': 'Sales', 'attendance_rate': 90}])
    with get_connection() as conn:
        conn.execute(
            'INSERT INTO sheet_relationships(left_sheet,right_sheet,left_column,right_column,method,status,cardinality,matching_keys,matching_pairs,reason) VALUES (?,?,?,?,?,?,?,?,?,?)',
            (sid, other, 'Department', 'Department', 'exact', 'linked', 'one-to-one', 1, 1, 'Verified'),
        )
        conn.commit()
    context = ai_copilot.build_copilot_context(sheet_id=sid, dataset_id=ds)
    assert "[ACTIVE SHEET] 'Sheet1' (Source: 'new.csv', 1 rows)" in context
    assert 'VERIFIED RELATIONSHIPS BETWEEN SHEETS' in context
    assert 'Catalogue context summary:' not in context


def test_optional_relationship_failure_does_not_discard_catalogue(monkeypatch):
    ds, sid = store_sheet('loaded.csv', [{'Score': 75}])
    connection = get_connection

    class WithoutRelationships:
        def __enter__(self):
            self.conn = connection()
            return self

        def __exit__(self, *args):
            self.conn.close()

        def execute(self, sql, *args):
            if 'FROM sheet_relationships' in sql:
                raise sqlite3.OperationalError('optional relationship lookup failed')
            return self.conn.execute(sql, *args)

    monkeypatch.setattr(ai_copilot, 'get_connection', WithoutRelationships)
    context = ai_copilot.build_copilot_context(sheet_id=sid, dataset_id=ds)
    assert "Source: 'loaded.csv', 1 rows" in context
    assert '[ACTIVE SHEET]' in context


def test_delete_then_upload_answers_from_new_sheet_without_retrieval_or_model(monkeypatch):
    old_ds, old_sid = store_sheet('old_students.csv', [{'math_score': 66.09}])
    client = TestClient(app)
    deleted = client.delete(f'/api/upload/datasets/{old_ds}')
    assert deleted.status_code == 200
    new_ds, new_sid = store_sheet('new_attendance.csv',
        [{'Department': 'Support', 'attendance_rate': 80.0}] * 10
        + [{'Department': 'Sales', 'attendance_rate': 96.0}] * 10)

    def forbidden(*args, **kwargs):
        raise AssertionError('Dataset strengths must use the verified brief, not retrieval or model inference')

    monkeypatch.setattr(ai_copilot, 'hybrid_search', forbidden)
    monkeypatch.setattr(council_coordinator, 'query_copilot', forbidden)
    monkeypatch.setattr(council_coordinator, 'stream_copilot_generator', forbidden)
    payload = {'query': 'what is good about this data you have', 'dataset_id': new_ds, 'sheet_id': new_sid,
               'prior_context': {'dataset_id': old_ds, 'sheet_id': old_sid, 'metric': 'math_score'}}
    for endpoint in ('/api/copilot/query', '/api/copilot/query/stream'):
        response = client.post(endpoint, json=payload)
        assert response.status_code == 200
        if endpoint.endswith('/stream'):
            done = next(event for event in response.text.split('\n\n') if event.startswith('event: done'))
            result = json.loads(done.split('data: ', 1)[1])
        else:
            result = response.json()
        assert result['status'] == 'success'
        assert 'new_attendance.csv' in result['answer']
        assert '20 records' in result['answer']
        assert 'old_students.csv' not in result['answer']
        assert "Hello!" not in result['answer']
        assert result['evidence']['source_ids'] == [new_sid]
        assert result['prior_context']['sheet_id'] == new_sid
        assert result['timings']['is_deterministic'] is True


def test_empty_workspace_is_reported_only_when_sheet_is_actually_absent():
    result = TestClient(app).post('/api/copilot/query', json={'query': 'what is good about this data you have'}).json()
    assert result['status'] == 'source_unavailable'
    assert 'No spreadsheet datasets are currently uploaded' in result['answer']
