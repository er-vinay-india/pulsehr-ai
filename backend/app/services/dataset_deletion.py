"""Delete source data and its materializations; retain only unfinished file cleanup tasks."""
import json
import logging
import sys
from pathlib import Path

from fastapi import HTTPException

from ..core import config
from ..db.database import get_connection
from .data_lifecycle import data_lifecycle_lock
from .sheet_catalog import rebuild_relationships

logger = logging.getLogger(__name__)


def _json(value):
    try:
        return json.loads(value or '{}')
    except (TypeError, ValueError):
        return {}


def source_references(value):
    """Collect explicit source identities in scopes, manifests and evidence ledgers."""
    datasets, sheets = set(), set()
    if isinstance(value, dict):
        for key, item in value.items():
            target = datasets if key in {'dataset_id', 'dataset_ids', 'source_dataset_id'} else (
                sheets if key in {'sheet_id', 'sheet_ids', 'source_sheet_id', 'source_sheet_ids', 'target_sheet_ids'} else None)
            if target is not None:
                for identity in item if isinstance(item, list) else [item]:
                    if str(identity).isdigit():
                        target.add(int(identity))
            child_datasets, child_sheets = source_references(item)
            datasets.update(child_datasets)
            sheets.update(child_sheets)
    elif isinstance(value, list):
        for item in value:
            child_datasets, child_sheets = source_references(item)
            datasets.update(child_datasets)
            sheets.update(child_sheets)
    return datasets, sheets



def require_live_sources(deck_spec):
    """Reject a stale editor request that would republish data from removed sources."""
    datasets, sheets = source_references(deck_spec)
    with get_connection() as conn:
        for table, identities in (('dataset_uploads', datasets), ('sheets', sheets)):
            for identity in identities:
                if not conn.execute(f'SELECT 1 FROM {table} WHERE id=?', (identity,)).fetchone():
                    raise HTTPException(409, 'This presentation uses a deleted workbook. Refresh the workspace before saving or exporting.')

def _affected(value, dataset_ids, sheet_ids):
    datasets, sheets = source_references(value)
    return bool(datasets & dataset_ids or sheets & sheet_ids)


def _delete_ids(conn, table, column, identities):
    if identities:
        marks = ','.join('?' for _ in identities)
        conn.execute(f'DELETE FROM {table} WHERE {column} IN ({marks})', list(identities))


def _queue_file(conn, dataset_id, kind, filename):
    if not filename:
        return
    root = config.UPLOADS_DIR if kind == 'upload' else config.EXPORTS_DIR
    path = (root / filename).resolve()
    if not path.is_relative_to(root.resolve()):
        raise HTTPException(409, 'A stored file is outside managed storage; deletion was not performed.')
    conn.execute('INSERT OR IGNORE INTO deletion_file_cleanup(dataset_id, storage_kind, relative_path) VALUES (?,?,?)',
                 (dataset_id, kind, str(path.relative_to(root.resolve()))))


def retry_file_cleanup(dataset_ids=None):
    """Retryable physical cleanup. Tasks disappear when files are gone; this is not an audit log."""
    with data_lifecycle_lock:
        conn = get_connection()
        try:
            query = 'SELECT * FROM deletion_file_cleanup'
            args = []
            if dataset_ids is not None:
                if not dataset_ids:
                    return 0
                query += f" WHERE dataset_id IN ({','.join('?' for _ in dataset_ids)})"
                args = list(dataset_ids)
            tasks = conn.execute(query, args).fetchall()
            pending = 0
            for task in tasks:
                root = config.UPLOADS_DIR if task['storage_kind'] == 'upload' else config.EXPORTS_DIR
                path = (root / task['relative_path']).resolve()
                try:
                    if not path.is_relative_to(root.resolve()):
                        raise ValueError('Cleanup path is outside managed storage')
                    path.unlink(missing_ok=True)
                    parent = path.parent
                    while parent != root.resolve():
                        try:
                            parent.rmdir()
                        except OSError:
                            break
                        parent = parent.parent
                    with conn:
                        conn.execute('DELETE FROM deletion_file_cleanup WHERE dataset_id=? AND storage_kind=? AND relative_path=?',
                                     (task['dataset_id'], task['storage_kind'], task['relative_path']))
                except (OSError, ValueError):
                    pending += 1
                    logger.exception('Dataset deletion file cleanup pending: dataset_id=%s storage=%s', task['dataset_id'], task['storage_kind'])
            return pending
        finally:
            conn.close()


def delete_datasets(dataset_ids=None, *, delete_all=False):
    if not delete_all and (not dataset_ids or any(type(i) is not int or i <= 0 for i in dataset_ids)):
        raise HTTPException(400, 'Select at least one valid workbook to delete.')
    with data_lifecycle_lock:
        conn = get_connection()
        try:
            ids = set(dataset_ids or [])
            rows = conn.execute('SELECT * FROM dataset_uploads').fetchall()
            rows = [row for row in rows if delete_all or row['id'] in ids]
            if delete_all:
                ids = {row['id'] for row in rows}
                ids.update(row[0] for row in conn.execute('SELECT DISTINCT dataset_id FROM deletion_file_cleanup'))
            actual_ids = {row['id'] for row in rows}
            sheet_ids = {row['id'] for row in conn.execute('SELECT id,dataset_id FROM sheets') if row['dataset_id'] in actual_ids}
            derived_ids = set()
            for row in conn.execute('SELECT id, source_sheets_json, join_keys_json FROM derived_tables'):
                sources = set(_json(row['source_sheets_json']) or [])
                keys = _json(row['join_keys_json'])
                # Legacy enrichment rollups stored dataset IDs in this column; cross-sheet views store sheet IDs.
                legacy_rollup = keys.get('type') == 'scientific_enrichment_rollup' and keys.get('source_kind') != 'sheet'
                if delete_all or sources & (actual_ids if legacy_rollup else sheet_ids):
                    derived_ids.add(row['id'])

            all_decks = [dict(row) for row in conn.execute('SELECT * FROM presentation_decks')]
            decks = all_decks
            decks = [row for row in decks if delete_all or _affected(
                {'dataset_id': row['dataset_id'], 'sheet_id': row['sheet_id'], 'spec': _json(row['spec_json'])}, actual_ids, sheet_ids)]
            deck_ids = {row['id'] for row in decks}
            jobs = [dict(row) for row in conn.execute('SELECT * FROM presentation_jobs')]
            job_ids = {row['id'] for row in jobs if delete_all or row['deck_id'] in deck_ids or
                       _affected(_json(row['scope_json']), actual_ids, sheet_ids) or
                       (actual_ids and row['status'] in ('pending', 'in_progress') and _json(row['scope_json']).get('scope_type') == 'workspace')}

            cleanup_dirs = set()
            memory_attached = config.PRESENTATION_MEMORY_DB_PATH.is_file()
            if memory_attached:
                conn.execute('ATTACH DATABASE ? AS presentation_memory', (str(config.PRESENTATION_MEMORY_DB_PATH),))
            with conn:
                for row in rows:
                    _queue_file(conn, row['id'], 'upload', row['filename'])
                for row in decks:
                    spec = _json(row['spec_json'])
                    owner = row['dataset_id'] if row['dataset_id'] in actual_ids else next(iter(ids), 0)
                    for filename in {row['pptx_filename'], spec.get('pptx_filename'), spec.get('pdf_filename'),
                                     f"presentation_{row['id']}.pptx", f"presentation_{row['id']}.pdf"}:
                        _queue_file(conn, owner, 'export', filename)
                    for folder in (config.EXPORTS_DIR / f"narration_{row['id']}", config.EXPORTS_DIR / 'qa' / row['id']):
                        if folder.is_dir():
                            cleanup_dirs.add(folder)
                            cleanup_dirs.update(path for path in folder.rglob('*') if path.is_dir())
                            for path in folder.rglob('*'):
                                if path.is_file():
                                    _queue_file(conn, owner, 'export', str(path.relative_to(config.EXPORTS_DIR)))
                if rows or delete_all:
                    owner = next(iter(ids), 0)
                    ids.add(owner)
                    # Unsaved exports have no source manifest; invalidate these caches on any source change.
                    kept_exports = set()
                    for saved in all_decks:
                        if saved['id'] not in deck_ids:
                            spec = _json(saved['spec_json'])
                            kept_exports.update(filter(None, [saved['pptx_filename'], spec.get('pptx_filename'), spec.get('pdf_filename'),
                                                              f"presentation_{saved['id']}.pptx", f"presentation_{saved['id']}.pdf"]))
                    for path in config.EXPORTS_DIR.glob('presentation_*'):
                        if path.is_file() and path.name not in kept_exports:
                            _queue_file(conn, owner, 'export', path.name)
                    # Legacy workspace reports do not carry source IDs; any source change invalidates them.
                    for path in config.EXPORTS_DIR.glob('pulsehr_presentation_*.pptx'):
                        _queue_file(conn, owner, 'export', path.name)
                    if delete_all or len(rows) == conn.execute('SELECT COUNT(*) FROM dataset_uploads').fetchone()[0]:
                        for path in config.EXPORTS_DIR.rglob('*'):
                            if path.is_dir():
                                cleanup_dirs.add(path)
                            if path.is_file():
                                _queue_file(conn, owner, 'export', str(path.relative_to(config.EXPORTS_DIR)))
                _delete_ids(conn, 'presentation_jobs', 'id', job_ids)
                _delete_ids(conn, 'presentation_decks', 'id', deck_ids)
                _delete_ids(conn, 'derived_tables', 'id', derived_ids)  # Rows cascade; the generated table disappears too.
                _delete_ids(conn, 'executive_narratives', 'target_id', sheet_ids)
                if rows or delete_all:
                    conn.execute('DELETE FROM executive_narratives')
                    # Cross-sheet reports can embed values from deleted sources. Rebuild them lazily from live data.
                    conn.execute('DELETE FROM eda_reports')
                marks = ','.join('?' for _ in actual_ids)
                if actual_ids:
                    conn.execute(f'DELETE FROM tabular_vectors WHERE id IN (SELECT id FROM tabular_chunks WHERE dataset_id IN ({marks}))', list(actual_ids))
                    _delete_ids(conn, 'dataset_uploads', 'id', actual_ids)
                if delete_all or (rows and conn.execute('SELECT COUNT(*) FROM dataset_uploads').fetchone()[0] == 0):
                    for table in ('tabular_vectors', 'tabular_chunks', 'executive_narratives', 'hr_alerts', 'attendance_records', 'employees', 'derived_tables'):
                        conn.execute(f'DELETE FROM {table}')
                if rows or delete_all:
                    rebuild_relationships(conn)
                if memory_attached:
                    table_exists = conn.execute("SELECT 1 FROM presentation_memory.sqlite_master WHERE name='presentation_memories'").fetchone()
                    if table_exists:
                        memory_ids = []
                        for row in conn.execute('SELECT * FROM presentation_memory.presentation_memories'):
                            if delete_all or row['deck_id'] in deck_ids or _affected(
                                {'dataset_id': row['dataset_id'], 'sheet_id': row['sheet_id'], 'provenance': _json(row['provenance_json'])}, actual_ids, sheet_ids):
                                memory_ids.append(row['memory_id'])
                        if conn.execute("SELECT 1 FROM presentation_memory.sqlite_master WHERE name='vec_presentation_memories'").fetchone():
                            _delete_ids(conn, 'presentation_memory.vec_presentation_memories', 'memory_id', memory_ids)
                        _delete_ids(conn, 'presentation_memory.presentation_memories', 'memory_id', memory_ids)

            # No row data or persistent deletion history is logged.
            from .input_intelligence.snapshot_manager import SnapshotManager
            SnapshotManager._SNAPSHOT_CACHE.clear()
            workflow = sys.modules.get('app.services.reporting.workflow_orchestrator')
            if workflow:
                workflow._GENERIC_WORKFLOW_CACHE.clear()
            registry_module = sys.modules.get('app.services.insight_registry')
            if registry_module:
                registry_module.insight_registry.invalidate_cache()
                registry_module.insight_registry._facts_by_snapshot.clear()
            embeddings = sys.modules.get('app.services.presentation.memory.embedding_service')
            if embeddings:
                embeddings.embedding_service._memory_cache.clear()
            manager_module = sys.modules.get('app.services.presentation.job_manager')
            if manager_module:
                manager = manager_module.job_manager
                with manager._lock:
                    for job_id in job_ids:
                        manager._cancel_flags[job_id] = True
                        manager._jobs.pop(job_id, None)
            ingestion_module = sys.modules.get('app.services.ingestion_job_manager')
            if ingestion_module:
                ingestion = ingestion_module.ingestion_job_manager
                with ingestion._lock:
                    for job_id, job in list(ingestion._jobs.items()):
                        if job.dataset_id in actual_ids or (delete_all and job.status == 'completed'):
                            ingestion._jobs.pop(job_id, None)
                            for subscriber in ingestion._subscribers.pop(job_id, []):
                                while not subscriber.empty():
                                    try:
                                        subscriber.get_nowait()
                                    except Exception:
                                        break
                                subscriber.put_nowait({'status': 'failed', 'message': 'Workbook deleted', 'result': None})
            pending = retry_file_cleanup(ids)
            for folder in sorted(cleanup_dirs, key=lambda path: len(path.parts), reverse=True):
                try:
                    folder.rmdir()
                except FileNotFoundError:
                    pass
                except OSError:
                    # Nonempty folders still have queued file cleanup; leave them for that retry.
                    logger.debug('Dataset deletion directory cleanup deferred: %s', folder.name)
            logger.info('Dataset deletion complete: dataset_ids=%s sheets=%s derived_tables=%s decks=%s pending_files=%s',
                        sorted(actual_ids), len(sheet_ids), len(derived_ids), len(deck_ids), pending)
            return {'message': 'Workbooks and dependent data removed.' if not pending else 'Data removed; stored file cleanup needs a retry.',
                    'deleted_count': len(rows), 'deleted_ids': sorted(actual_ids), 'deleted_sheet_ids': sorted(sheet_ids),
                    'deleted_derived_ids': sorted(derived_ids), 'deleted_deck_ids': sorted(deck_ids),
                    'cleanup_pending': bool(pending), 'pending_files': pending}
        except Exception:
            logger.exception('Dataset deletion failed: dataset_ids=%s delete_all=%s', dataset_ids, delete_all)
            raise
        finally:
            conn.close()
