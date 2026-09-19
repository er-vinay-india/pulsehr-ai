import json
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, UploadFile, File, HTTPException

from ..core import config
from ..db.database import get_connection
from ..services.sheet_catalog import read_sheets, prepare_sheets, insert_sheets, rebuild_relationships, prepare_existing_column_vectors

router = APIRouter(prefix='/api/upload', tags=['upload'])


@router.post('/file')
def upload_file(file: UploadFile = File(...)):
    original = Path((file.filename or 'uploaded.csv').replace('\\', '/')).name
    suffix = Path(original).suffix.lower()
    if suffix not in ('.csv', '.xlsx', '.xls'):
        raise HTTPException(400, 'Upload a CSV or Excel file.')
    path = config.UPLOADS_DIR / f'{uuid4().hex}{suffix}'
    conn = None
    try:
        content = file.file.read(20 * 1024 * 1024 + 1)
        if len(content) > 20 * 1024 * 1024:
            raise ValueError('Maximum upload size is 20 MB.')
        path.write_bytes(content)
        frames = read_sheets(path)
        prepared = prepare_sheets(frames, original)
        total = sum(len(s['records']) for s in prepared)
        first = prepared[0]
        column_updates = prepare_existing_column_vectors()
        conn = get_connection()
        with conn:
            dataset_id = conn.execute('''INSERT INTO dataset_uploads(filename,original_name,file_type,sheet_count,row_count,col_count,columns_json,sample_preview_json,summary_insights)
                VALUES (?,?,?,?,?,?,?,?,?)''', (path.name, original, suffix[1:], len(prepared), total, len(first['columns']), json.dumps(first['columns']), json.dumps(first['records'][:5]),
                f'{len(prepared)} sheets and {total} rows. All original values retained.')).lastrowid
            for sid, profiles in column_updates:
                conn.execute('UPDATE sheets SET profile_json=? WHERE id=?', (json.dumps(profiles), sid))
            insert_sheets(conn, dataset_id, prepared)
            rebuild_relationships(conn)
            linked = conn.execute("SELECT COUNT(*) FROM sheet_relationships WHERE status='linked' AND (left_sheet IN (SELECT id FROM sheets WHERE dataset_id=?) OR right_sheet IN (SELECT id FROM sheets WHERE dataset_id=?))", (dataset_id, dataset_id)).fetchone()[0]
        return {'status': 'success', 'dataset_id': dataset_id, 'filename': original,
                'sheets': list(frames), 'total_rows': total, 'columns': first['columns'], 'sample_preview': first['records'][:5],
                'indexed_chunks': total, 'vector_chunks': sum(len(s['vectors']) for s in prepared), 'linked_relationships': linked,
                'message': f'Indexed all {total} rows. Found {linked} exact key relationships. Overview and explorer now include these sheets.'}
    except (ValueError, OSError, ImportError) as exc:
        path.unlink(missing_ok=True)
        raise HTTPException(400, str(exc)) from exc
    except Exception:
        path.unlink(missing_ok=True)
        raise
    finally:
        if conn:
            conn.close()


@router.get('/datasets')
def list_datasets():
    conn = get_connection()
    try:
        datasets = []
        for row in conn.execute('SELECT * FROM dataset_uploads ORDER BY id DESC'):
            item = dict(row)
            item['columns'] = json.loads(item.pop('columns_json') or '[]')
            item.pop('sample_preview_json', None)
            item['sheets'] = [dict(s) for s in conn.execute('SELECT id,name,row_count FROM sheets WHERE dataset_id=?', (row['id'],))]
            datasets.append(item)
        return {'datasets': datasets}
    finally:
        conn.close()


@router.post('/reseed-kaggle')
def reseed_kaggle():
    raise HTTPException(410, 'Automatic demo seeding has been removed. Upload any CSV or Excel file through the upload control.')


@router.delete('/datasets/{dataset_id}')
def delete_dataset(dataset_id: int):
    conn = get_connection()
    try:
        row = conn.execute('SELECT filename FROM dataset_uploads WHERE id=?', (dataset_id,)).fetchone()
        if row is None:
            raise HTTPException(404, 'Dataset not found')
        with conn:
            conn.execute('DELETE FROM tabular_vectors WHERE id IN (SELECT id FROM tabular_chunks WHERE dataset_id=?)', (dataset_id,))
            conn.execute('DELETE FROM dataset_uploads WHERE id=?', (dataset_id,))
            rebuild_relationships(conn)
        path = (config.UPLOADS_DIR / row['filename']).resolve()
        # Never delete external Kaggle caches or paths outside uploads.
        if path.is_relative_to(config.UPLOADS_DIR.resolve()):
            path.unlink(missing_ok=True)
        return {'message': 'Deleted dataset, sheets, rows, search entries and relationships.'}
    finally:
        conn.close()
