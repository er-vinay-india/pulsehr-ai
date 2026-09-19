import io
import json

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import get_connection
from app.services import sheet_catalog, hybrid_retrieval, copilot_tools

client = TestClient(app)


def upload(name, content):
    response = client.post('/api/upload/file', files={'file': (name, content, 'application/octet-stream')})
    assert response.status_code == 200, response.text
    return response.json()


def test_shared_key_join_updates_overview_and_copilot():
    first = upload('roster.csv', b'Employee ID,Employee Name,Department\n001,Ana,HR\n002,Ben,IT\n')
    second = upload('absence.csv', b'Emp ID,Absent days\n001,2\n001,3\n002,0\n')
    overview = client.get('/api/analytics/overview').json()
    assert overview['stats'] == {'datasets': 2, 'sheets': 2, 'rows': 5, 'linked_relationships': 1}
    relation = overview['relationships'][0]
    assert relation['method'] == 'alias'
    assert relation['cardinality'] == 'one-to-many'
    assert relation['matching_pairs'] == 3
    joined = client.get(f"/api/sheets/relationships/{relation['id']}/rows").json()
    assert joined['rows'][0]['left']['Employee ID'] == '001'
    assert joined['rows'][0]['right']['Absent days'] == '2'
    evidence = hybrid_retrieval.keyword_search('Ana')
    expanded = sheet_catalog.linked_evidence(evidence)
    assert len(expanded) == 2
    assert all(r['source_file'] == 'absence.csv' for r in expanded)
    result = copilot_tools.calculate(copilot_tools.CalculationRequest(relationship_id=relation['id'], operation='sum', column='right.Absent days', group_by='left.Department'))
    assert {r['group']: r['value'] for r in result['results']} == {'HR': 5, 'IT': 0}
    assert client.delete(f"/api/upload/datasets/{second['dataset_id']}").status_code == 200
    assert sheet_catalog.overview()['stats']['rows'] == 2
    assert sheet_catalog.overview()['relationships'] == []
    assert sheet_catalog.linked_evidence(evidence) == []
    assert not hybrid_retrieval.keyword_search('Absent')
    assert client.delete(f"/api/upload/datasets/{first['dataset_id']}").status_code == 200
    assert sheet_catalog.overview()['stats']['rows'] == 0


def test_multisheet_complete_rows_and_pagination():
    stream = io.BytesIO()
    with pd.ExcelWriter(stream, engine='openpyxl') as writer:
        pd.DataFrame({'Employee ID': [f'E{i}' for i in range(351)], 'Hours': [2] * 351}).to_excel(writer, sheet_name='Hours', index=False)
        pd.DataFrame({'Emp ID': ['E350'], 'Team': ['Support']}).to_excel(writer, sheet_name='Teams', index=False)
    dataset = upload('book.xlsx', stream.getvalue())
    assert dataset['total_rows'] == 352
    sheets = client.get('/api/sheets').json()['sheets']
    assert len(sheets) == 2
    page = client.get(f"/api/sheets/{sheets[0]['id']}/rows?page=15&limit=25").json()
    assert page['rows'][0]['row_number'] == 351
    assert page['rows'][0]['values']['Employee ID'] == 'E350'
    assert hybrid_retrieval.keyword_search('E350')
    result = copilot_tools.calculate(copilot_tools.CalculationRequest(dataset_id=dataset['dataset_id'], sheet='Hours', column='Hours', operation='sum'))
    assert result['results'][0]['value'] == 702


def test_duplicate_keys_and_measures_are_not_automatic_joins():
    upload('first.csv', b'Employee ID,Rating\nE1,5\nE1,4\n')
    upload('second.csv', b'Employee ID,Rating\nE1,5\nE1,4\n')
    relations = sheet_catalog.overview()['relationships']
    assert relations and all(r['status'] == 'suggested' for r in relations)
    assert client.get(f"/api/sheets/relationships/{relations[0]['id']}/rows").status_code == 409


def test_leading_zeroes_and_nulls_do_not_join():
    upload('first.csv', b'Employee ID,Name\n001,Ana\n,Unknown\n')
    upload('second.csv', b'Emp ID,Hours\n1,8\n,2\n')
    assert sheet_catalog.overview()['relationships'] == []


def test_vector_column_match_is_only_a_suggestion(monkeypatch):
    monkeypatch.setattr(sheet_catalog, 'model_embeddings', lambda texts: [[1.] + [0.] * 767 for _ in texts])
    upload('first.csv', b'WorkerNumber\nE1\n')
    upload('second.csv', b'StaffReference\nE1\n')
    relation = sheet_catalog.overview()['relationships'][0]
    assert relation['method'] == 'vector'
    assert relation['status'] == 'suggested'
    assert relation['similarity'] == pytest.approx(1)


def test_same_filename_keeps_separate_sources_and_failed_upload_rolls_back():
    first = upload('same.csv', b'Employee ID,Hours\nE1,2\n')
    second = upload('same.csv', b'Employee ID,Hours\nE2,3\n')
    assert first['dataset_id'] != second['dataset_id']
    before = sheet_catalog.overview()
    response = client.post('/api/upload/file', files={'file': ('bad.xlsx', b'not excel')})
    assert response.status_code == 400
    assert sheet_catalog.overview() == before


def test_restart_does_not_reseed_deleted_demo():
    demo = upload('attendance_2023_2024.csv', b'Date,Hours\n2026-09-01,8\n')
    assert client.delete(f"/api/upload/datasets/{demo['dataset_id']}").status_code == 200
    with TestClient(app) as running:
        assert running.get('/api/analytics/overview').json()['stats']['datasets'] == 0
    with TestClient(app) as running:
        assert running.get('/api/health').json()['database']['employees'] == 0
        assert running.get('/api/sheets').json()['sheets'] == []
    assert client.post('/api/upload/reseed-kaggle').status_code == 410


def test_migration_preserves_original_and_backs_up_legacy(tmp_path):
    from app.core import config
    (config.UPLOADS_DIR / 'legacy.csv').write_text('Employee ID,Hours\nE1,0\n')
    conn = get_connection()
    conn.execute("INSERT INTO dataset_uploads(filename,original_name,file_type) VALUES ('legacy.csv','legacy.csv','csv')")
    conn.execute("INSERT INTO employees(employee_code,name,department,role) VALUES ('DEMO','Fake','Demo','Demo')")
    conn.commit()
    conn.close()
    sheet_catalog.migrate_existing()
    assert (config.DB_PATH.parent / 'before_sheet_catalog_v1.sqlite3').exists()
    assert sheet_catalog.overview()['sheets'][0]['profiles'][1]['numeric']['mean'] == 0
    assert client.get('/api/health').json()['database']['employees'] == 0
    sheet_catalog.migrate_existing()
    assert sheet_catalog.overview()['stats']['sheets'] == 1


def test_percent_and_rating_units_are_preserved():
    dataset = upload('scores.csv', b'Employee ID,Attendance Rate,Rating\n01,0%,4/5\n02,100%,5/5\n')
    profiles = sheet_catalog.overview()['sheets'][0]['profiles']
    assert profiles[1]['numeric']['mean'] == 50
    assert profiles[1]['unit'] == '%'
    assert 'sum' not in profiles[1]['numeric']
    result = copilot_tools.calculate(copilot_tools.CalculationRequest(dataset_id=dataset['dataset_id'], column='Rating', operation='mean'))
    assert result['results'][0]['value'] == 4.5
    assert result['unit'] == 'out of 5'


def test_generic_ids_are_suggestions_not_identity():
    upload('employees.csv', b'ID,Name\n1,Ana\n')
    upload('departments.csv', b'ID,Name\n1,Engineering\n')
    relations = sheet_catalog.overview()['relationships']
    assert relations and all(r['status'] == 'suggested' for r in relations)
