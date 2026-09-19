import json
import sqlite3

import pytest

from app.services import hybrid_retrieval as retrieval
from app.services import ai_copilot


@pytest.fixture
def database(tmp_path, monkeypatch):
    path = tmp_path / 'retrieval.db'
    def connect():
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        return conn
    conn = connect()
    from pathlib import Path
    conn.executescript((Path(__file__).parents[1] / 'app/db/schema.sql').read_text())
    conn.execute("INSERT INTO dataset_uploads(id,filename,original_name,file_type) VALUES (1,'absence.csv','absence.csv','csv')")
    for emp_id, name in [(1, 'Ann Lee'), (10, 'Jo Green')]:
        conn.execute("INSERT INTO employees(id,employee_code,name,department,role) VALUES (?,?,?,'HR','Analyst')", (emp_id, f'EMP-{emp_id}', name))
        conn.execute('INSERT INTO tabular_chunks(dataset_id,chunk_text,metadata_json) VALUES (1,?,?)',
                     (f'{name} EMP-{emp_id} absent days: {emp_id}', json.dumps({'employee_id': emp_id})))
    conn.commit()
    conn.close()
    monkeypatch.setattr(retrieval, 'get_connection', connect)
    monkeypatch.setattr(ai_copilot, 'get_connection', connect)
    return connect


def test_keyword_retrieves_exact_code_and_source(database):
    results = retrieval.keyword_search('EMP-10')
    assert len(results) == 1
    assert 'Jo Green' in results[0]['text']
    assert results[0]['source_file'] == 'absence.csv'


def test_unknown_and_empty_queries(database):
    assert retrieval.keyword_search('quasar') == []
    assert retrieval.keyword_search('What is 2 + 2?') == []
    assert retrieval.keyword_search('the of') == []
    conn = database()
    conn.execute('DELETE FROM tabular_chunks')
    conn.commit()
    conn.close()
    assert retrieval.keyword_search('absent') == []


def test_semantic_failure_keeps_keyword_results(database, monkeypatch):
    def unavailable(*args):
        raise RuntimeError('vector backend unavailable')
    monkeypatch.setattr(retrieval, 'semantic_search', unavailable)
    results = retrieval.hybrid_search('EMP-10')
    assert len(results) == 1
    assert results[0]['retrieval_methods'] == ['keyword']


def test_fusion_deduplicates_and_retains_source(database, monkeypatch):
    item = retrieval.keyword_search('EMP-10')[0]
    monkeypatch.setattr(retrieval, 'semantic_search', lambda *args: [{**item, 'relevance_score': 0.9}])
    results = retrieval.hybrid_search('EMP-10')
    assert len(results) == 1
    assert results[0]['retrieval_methods'] == ['keyword', 'semantic']
    assert results[0]['source_file'] == 'absence.csv'


def test_employee_code_tokens_do_not_match_prefixes(database):
    results = retrieval.keyword_search('EMP-1')
    assert len(results) == 1
    assert 'Ann Lee' in results[0]['text']


def test_copilot_uses_hybrid_evidence(database, monkeypatch):
    item = retrieval.keyword_search('absent')[0]
    monkeypatch.setattr(ai_copilot, 'hybrid_search', lambda *args, **kwargs: [{**item, 'retrieval_methods': ['keyword']}])
    monkeypatch.setattr(ai_copilot, 'get_aggregate_context', lambda: '')
    monkeypatch.setattr(ai_copilot, 'get_available_models', lambda: [])
    class OfflineClient:
        def __init__(self, **kwargs): pass
        def __enter__(self):
            import httpx
            raise httpx.ConnectError('offline')
        def __exit__(self, *args): pass
    monkeypatch.setattr(ai_copilot.httpx, 'Client', OfflineClient)
    result = ai_copilot.query_copilot('absent')
    assert result['citations'][0]['type'] == 'hybrid_search'
    assert result['citations'][0]['source_file'] == 'absence.csv'
    assert item['text'] in result['answer']
