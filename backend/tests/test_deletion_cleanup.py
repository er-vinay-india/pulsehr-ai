"""Deletion safety and complete cleanup, using only the isolated workspace fixture."""
import json
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest
import sqlite_vec
from fastapi.testclient import TestClient

from app.main import app
from app.core import config
from app.db.database import get_connection
from app.services.dataset_deletion import retry_file_cleanup
from app.services.input_intelligence.snapshot_manager import SnapshotManager
from app.services.insight_registry import insight_registry

client = TestClient(app)


def seed_sources():
    conn = get_connection()
    with conn:
        for did, sid in [(7, 101), (20, 17)]:
            filename = f'source_{did}.csv'
            (config.UPLOADS_DIR / filename).write_text('amount\n10\n')
            conn.execute('INSERT INTO dataset_uploads(id,filename,original_name,file_type) VALUES (?,?,?,?)', (did, filename, filename, 'csv'))
            conn.execute('INSERT INTO sheets(id,dataset_id,name,columns_json,profile_json,row_count) VALUES (?,?,?,?,?,?)', (sid, did, 'Sheet1', '["amount"]', '[]', 1))
            conn.execute('INSERT INTO sheet_rows(sheet_id,row_index,data_json) VALUES (?,?,?)', (sid, 0, '{"amount":10}'))
            conn.execute('INSERT INTO sheet_curated_rows(sheet_id,row_index,data_json) VALUES (?,?,?)', (sid, 0, '{"amount":10}'))
            conn.execute('INSERT INTO sheet_cells(sheet_id,row_index,column_name,value_key) VALUES (?,?,?,?)', (sid, 0, 'amount', '10'))
            chunk_id = conn.execute('INSERT INTO tabular_chunks(dataset_id,chunk_text) VALUES (?,?)', (did, 'source value 10')).lastrowid
            conn.execute('INSERT INTO tabular_vectors(id,embedding) VALUES (?,?)', (chunk_id, sqlite_vec.serialize_float32([0.1] * config.EMBEDDING_DIM)))
        for dtid, name, sources, keys in [(201, 'deleted-source', [101], {}), (202, 'unrelated', [17], {}), (203, 'legacy-rollup', [7], {'type':'scientific_enrichment_rollup'}), (204, 'new-rollup', [101], {'type':'scientific_enrichment_rollup', 'source_kind':'sheet'})]:
            conn.execute('INSERT INTO derived_tables(id,name,display_name,source_sheets_json,join_keys_json,columns_json,row_count) VALUES (?,?,?,?,?,?,?)', (dtid,name,name,json.dumps(sources),json.dumps(keys),'["amount"]',1))
            conn.execute('INSERT INTO derived_table_rows(derived_table_id,row_index,data_json) VALUES (?,?,?)', (dtid,0,'{"amount":10}'))
        report = {'cross_sheet_intelligence': {'entity_links':[{'left_sheet_id':101,'left_column':'amount','right_sheet_id':17,'right_column':'amount'}], 'correlations':[]}}
        conn.execute('INSERT INTO eda_reports(sheet_id,dataset_id,health_score,report_json) VALUES (?,?,?,?)', (17,20,100,json.dumps(report)))
        for deck_id, did, sid in [('removed',7,101), ('kept',20,17), ('cross',20,17)]:
            spec = {'pptx_filename':f'presentation_{deck_id}.pptx', 'pdf_filename':f'presentation_{deck_id}.pdf'}
            if deck_id == 'cross': spec['evidence_ledger'] = [{'source_sheet_id':101}]
            conn.execute('INSERT INTO presentation_decks(id,title,dataset_id,sheet_id,spec_json,pptx_filename) VALUES (?,?,?,?,?,?)', (deck_id,deck_id,did,sid,json.dumps(spec),spec['pptx_filename']))
            for suffix in ('pptx','pdf'):
                (config.EXPORTS_DIR / f'presentation_{deck_id}.{suffix}').write_text('test export')
        conn.execute('INSERT INTO presentation_jobs(id,status,stage,stage_label,deck_id,scope_json) VALUES (?,?,?,?,?,?)', ('job-removed','ready','ready','ready','removed','{"sheet_id":101}'))
        conn.execute('INSERT INTO presentation_jobs(id,status,stage,stage_label,scope_json) VALUES (?,?,?,?,?)', ('job-running','in_progress','planning','planning','{"scope_type":"workspace"}'))
    conn.close()
    narration = config.EXPORTS_DIR / 'narration_removed'
    narration.mkdir()
    (narration / 'slide_1.mp3').write_text('test narration')
    memory = sqlite3.connect(config.PRESENTATION_MEMORY_DB_PATH)
    memory.execute('CREATE TABLE presentation_memories(memory_id TEXT, deck_id TEXT, dataset_id INTEGER, sheet_id INTEGER, provenance_json TEXT)')
    memory.executemany('INSERT INTO presentation_memories VALUES (?,?,?,?,?)', [('gone','removed',7,101,'{}'), ('live','kept',20,17,'{}'), ('cross','cross',20,17,'{}')])
    memory.enable_load_extension(True)
    sqlite_vec.load(memory)
    memory.enable_load_extension(False)
    memory.execute(f'CREATE VIRTUAL TABLE vec_presentation_memories USING vec0(memory_id TEXT PRIMARY KEY, embedding FLOAT[{config.EMBEDDING_DIM}])')
    for mid in ('gone', 'live', 'cross'):
        memory.execute('INSERT INTO vec_presentation_memories(memory_id,embedding) VALUES (?,?)', (mid,sqlite_vec.serialize_float32([0.1]*config.EMBEDDING_DIM)))
    memory.commit(); memory.close()


def remaining(table, column='id'):
    conn = get_connection()
    try: return [row[0] for row in conn.execute(f'SELECT {column} FROM {table} ORDER BY {column}')]
    finally: conn.close()


@pytest.mark.parametrize('url,payload', [('/api/upload/datasets/bulk-delete', {}), ('/api/upload/datasets/bulk-delete', {'dataset_ids':[]}), ('/api/upload/datasets/bulk-delete', {'dataset_ids':[-7]}), ('/api/upload/datasets/bulk-delete', {'dataset_ids':[True]}), ('/api/upload/datasets?ids=abc', None), ('/api/upload/datasets?ids=7,abc', None), ('/api/upload/datasets?ids=', None)])
def test_invalid_selection_never_deletes_anything(url,payload):
    seed_sources()
    res = client.post(url,json=payload) if payload is not None else client.delete(url)
    assert res.status_code in (400,422)
    assert remaining('dataset_uploads') == [7,20]
    assert remaining('derived_tables') == [201,202,203,204]
    assert (config.UPLOADS_DIR / 'source_7.csv').exists()


@pytest.mark.parametrize('bulk',[False,True])
def test_exact_dependencies_and_all_source_artifacts_are_removed(bulk, caplog):
    seed_sources()
    SnapshotManager._SNAPSHOT_CACHE['ws_7'] = object()
    insight_registry.set_cached_brief('old', {'amount':10})
    insight_registry.register_findings('old', [{'observation':'deleted data'}])
    with caplog.at_level('INFO'):
        res = client.post('/api/upload/datasets/bulk-delete',json={'dataset_ids':[7]}) if bulk else client.delete('/api/upload/datasets/7')
    assert res.status_code == 200 and not res.json()['cleanup_pending']
    assert remaining('dataset_uploads') == [20]
    assert remaining('sheets') == [17]
    for table in ('sheet_rows','sheet_curated_rows','sheet_cells'):
        assert remaining(table,'sheet_id') == [17]
    assert remaining('derived_tables') == [202]
    assert remaining('derived_table_rows','derived_table_id') == [202]
    assert remaining('presentation_decks') == ['kept']
    assert remaining('presentation_jobs') == []
    assert remaining('eda_reports') == []
    assert remaining('tabular_chunks','dataset_id') == [20]
    assert len(remaining('tabular_vectors')) == 1
    assert SnapshotManager.get_cached_context('ws_7') is None
    assert insight_registry.get_cached_brief('old') is None
    assert insight_registry.get_all_facts('old') == []
    assert not (config.UPLOADS_DIR / 'source_7.csv').exists()
    assert (config.UPLOADS_DIR / 'source_20.csv').exists()
    assert sorted(p.name for p in config.EXPORTS_DIR.iterdir()) == ['presentation_kept.pdf','presentation_kept.pptx']
    memory = sqlite3.connect(config.PRESENTATION_MEMORY_DB_PATH)
    memory.enable_load_extension(True); sqlite_vec.load(memory); memory.enable_load_extension(False)
    assert memory.execute('SELECT memory_id FROM presentation_memories').fetchall() == [('live',)]
    assert memory.execute('SELECT memory_id FROM vec_presentation_memories').fetchall() == [('live',)]
    memory.close()
    assert 'Dataset deletion complete' in caplog.text
    assert client.get('/api/eda/cross-sheet-correlations').json()['entity_links'] == []


def test_bulk_all_removes_data_and_generated_artifacts():
    seed_sources()
    res = client.post('/api/upload/datasets/bulk-delete',json={'dataset_ids':[7,20]})
    assert res.json()['deleted_count'] == 2
    for table in ('dataset_uploads','sheets','sheet_rows','sheet_cells','sheet_curated_rows','derived_tables','derived_table_rows','eda_reports','tabular_chunks','tabular_vectors','presentation_decks','presentation_jobs','deletion_file_cleanup'):
        conn = get_connection()
        assert conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] == 0
        conn.close()
    assert not list(config.UPLOADS_DIR.iterdir())
    assert not list(config.EXPORTS_DIR.iterdir())


def test_file_failure_is_visible_and_retryable_after_source_removal(caplog):
    seed_sources()
    bad_path = config.UPLOADS_DIR / 'source_7.csv'
    original = Path.unlink
    def fail_target(path,*args,**kwargs):
        if path == bad_path: raise PermissionError('simulated cleanup failure')
        return original(path,*args,**kwargs)
    with patch.object(Path,'unlink',fail_target):
        res = client.delete('/api/upload/datasets/7')
    assert res.status_code == 200 and res.json()['cleanup_pending']
    assert remaining('dataset_uploads') == [20]
    assert bad_path.exists()
    assert 'cleanup pending' in caplog.text
    retry = client.delete('/api/upload/datasets/7')
    assert not retry.json()['cleanup_pending']
    assert not bad_path.exists()
    assert remaining('deletion_file_cleanup','dataset_id') == []
    assert retry_file_cleanup() == 0
    assert client.delete('/api/upload/datasets/7').status_code == 200


def test_inflight_narration_cannot_recreate_deleted_exports(monkeypatch):
    import asyncio
    from app.services.presentation import narration_service
    seed_sources()
    (config.EXPORTS_DIR / 'narration_removed' / 'slide_1.mp3').unlink()
    conn = get_connection()
    with conn:
        conn.execute('UPDATE presentation_decks SET spec_json=? WHERE id=?',
                     (json.dumps({'slides':[{'order':1,'title':'Test','speaker_notes':'Test narration'}]}), 'removed'))
    conn.close()

    async def finish_after_deletion(text, voice, output):
        response = client.delete('/api/upload/datasets/7')
        assert response.status_code == 200
        output.write_bytes(b'test audio')

    monkeypatch.setattr(narration_service, '_synthesize_text_to_mp3', finish_after_deletion)
    with pytest.raises(ValueError, match='deleted during narration'):
        asyncio.run(narration_service.generate_deck_narration_async('removed'))
    assert not (config.EXPORTS_DIR / 'narration_removed').exists()
    assert narration_service.get_deck_narration_manifest('removed') is None
    assert not (config.EXPORTS_DIR / 'narration_removed').exists()


@pytest.mark.parametrize('endpoint', ['save', 'export-pptx', 'export-pdf'])
def test_stale_editor_cannot_restore_deleted_data(endpoint):
    seed_sources()
    stale_spec = {'id':'removed', 'metadata':{'dataset_id':7,'sheet_id':101,'title':'Old source'}, 'slides':[]}
    assert client.delete('/api/upload/datasets/7').status_code == 200
    response = (client.put('/api/presentations/decks/removed',json=stale_spec) if endpoint == 'save'
                else client.post('/api/presentations/'+endpoint,json={'deck_spec':stale_spec}))
    assert response.status_code == 409
    assert remaining('presentation_decks') == ['kept']
    assert not (config.EXPORTS_DIR/'presentation_removed.pptx').exists()
