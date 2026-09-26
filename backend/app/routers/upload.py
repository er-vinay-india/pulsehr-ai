import csv
import io
import json
from pathlib import Path
import threading
from uuid import uuid4

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from ..core import config
from ..db.database import get_connection
from ..services.sheet_catalog import read_sheets, prepare_sheets, insert_sheets, rebuild_relationships, prepare_existing_column_vectors
from ..services.industrial_analytics import run_ingestion_industrial_pipeline
from ..services.sheet_naming_pipeline import generate_sheet_display_name

router = APIRouter(prefix='/api/upload', tags=['upload'])
_upload_lock = threading.Lock()


@router.post('/file')
def upload_file(
    file: UploadFile = File(...),
    user_objective: str = Form(default=""),
    business_context: str | None = Form(default=None)
):
    with _upload_lock:
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

            # Run AI Sheet Naming & Semantic Classification pipeline
            naming = generate_sheet_display_name(original, first['columns'], first['records'])
            display_name = naming['display_name']

            conn = get_connection()
            with conn:
                dataset_id = conn.execute('''INSERT INTO dataset_uploads(filename,original_name,display_name,file_type,sheet_count,row_count,col_count,columns_json,sample_preview_json,summary_insights)
                    VALUES (?,?,?,?,?,?,?,?,?,?)''', (path.name, original, display_name, suffix[1:], len(prepared), total, len(first['columns']), json.dumps(first['columns']), json.dumps(first['records'][:5]),
                    f'{len(prepared)} sheets and {total} rows. All original values retained.')).lastrowid
                for sid, profiles in column_updates:
                    conn.execute('UPDATE sheets SET profile_json=? WHERE id=?', (json.dumps(profiles), sid))
                insert_sheets(conn, dataset_id, prepared, display_name=display_name)
                rebuild_relationships(conn)
                from ..services.eda import run_eda_pipeline
                eda_res = run_eda_pipeline(conn=conn)
                industrial_res = run_ingestion_industrial_pipeline(conn, dataset_id)
                linked = conn.execute("SELECT COUNT(*) FROM sheet_relationships WHERE status='linked' AND (left_sheet IN (SELECT id FROM sheets WHERE dataset_id=?) OR right_sheet IN (SELECT id FROM sheets WHERE dataset_id=?))", (dataset_id, dataset_id)).fetchone()[0]

                # Immediate User Intent Reconciliation during Data Ingestion
                analysis_ctx_dict = None
                if user_objective and user_objective.strip():
                    import pandas as pd
                    from ..services.data_engine.semantic_classifier import SemanticClassifier
                    from ..services.data_engine.analysis_context import IntentDataReconciler

                    sheet_row = conn.execute('SELECT id, display_name, name FROM sheets WHERE dataset_id=? ORDER BY id ASC LIMIT 1', (dataset_id,)).fetchone()
                    sheet_id = sheet_row['id'] if sheet_row else None
                    df_first = pd.DataFrame(first['records'])
                    profile = SemanticClassifier.profile_dataset(df_first, dataset_name=display_name)
                    ctx = IntentDataReconciler.parse_and_reconcile(
                        raw_text=user_objective.strip(),
                        profile=profile,
                        dataset_id=dataset_id,
                        sheet_id=sheet_id,
                        business_context=business_context
                    )
                    ctx_json = ctx.model_dump_json()
                    conn.execute('UPDATE dataset_uploads SET analysis_context_json=? WHERE id=?', (ctx_json, dataset_id))
                    conn.execute('UPDATE sheets SET analysis_context_json=? WHERE dataset_id=?', (ctx_json, dataset_id))
                    analysis_ctx_dict = ctx.model_dump()

            return {'status': 'success', 'dataset_id': dataset_id, 'filename': original,
                    'display_name': display_name, 'domain': naming['domain'], 'description': naming['description'],
                    'sheets': list(frames), 'total_rows': total, 'columns': first['columns'], 'sample_preview': first['records'][:5],
                    'indexed_chunks': total, 'vector_chunks': sum(len(s['vectors']) for s in prepared), 'linked_relationships': linked,
                    'industrial_analytics': industrial_res,
                    'analysis_context': analysis_ctx_dict,
                    'user_objective': user_objective.strip() if user_objective else "",
                    'message': f'Indexed all {total} rows. Reconciled user intent into analytical evidence pipeline.' if analysis_ctx_dict else f'Indexed all {total} rows. Found {linked} exact key relationships and computed industrial analytics pipeline.'}
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
            ctx_str = item.pop('analysis_context_json', None)
            item['analysis_context'] = json.loads(ctx_str) if ctx_str else None
            item['sheets'] = [dict(s) for s in conn.execute('SELECT id,name,display_name,row_count FROM sheets WHERE dataset_id=?', (row['id'],))]
            datasets.append(item)
        return {'datasets': datasets}
    finally:
        conn.close()


@router.get('/datasets/{dataset_id}/download')
def download_dataset(dataset_id: int):
    conn = get_connection()
    try:
        row = conn.execute('SELECT * FROM dataset_uploads WHERE id=?', (dataset_id,)).fetchone()
        if row is None:
            raise HTTPException(404, 'Dataset not found')

        orig_name = (row['original_name'] or 'dataset').replace('"', '').replace('/', '_').replace('\\', '_')
        file_type = (row['file_type'] or 'csv').lower()
        if not orig_name.lower().endswith(f".{file_type}"):
            orig_name = f"{orig_name}.{file_type}"

        disk_path = (config.UPLOADS_DIR / row['filename']).resolve()
        if disk_path.is_file() and disk_path.is_relative_to(config.UPLOADS_DIR.resolve()):
            media = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' if file_type in ('xlsx', 'xls') else 'text/csv; charset=utf-8'
            return FileResponse(disk_path, filename=orig_name, media_type=media)

        # Fail-safe reconstruction from SQLite sheets and sheet_rows
        sheets = conn.execute('SELECT id, name, columns_json FROM sheets WHERE dataset_id=? ORDER BY id', (dataset_id,)).fetchall()
        if not sheets:
            raise HTTPException(404, 'No sheets found for dataset')

        if len(sheets) == 1 or file_type == 'csv':
            sheet = sheets[0]
            cols = json.loads(sheet['columns_json'] or '[]')
            rows = [json.loads(r['data_json']) for r in conn.execute('SELECT data_json FROM sheet_rows WHERE sheet_id=? ORDER BY row_index', (sheet['id'],))]
            buf = io.StringIO()
            writer = csv.DictWriter(buf, fieldnames=cols, extrasaction='ignore')
            writer.writeheader()
            for r in rows:
                writer.writerow(r)
            csv_bytes = buf.getvalue().encode('utf-8-sig')
            csv_name = orig_name if orig_name.lower().endswith('.csv') else f"{Path(orig_name).stem}.csv"
            return Response(
                content=csv_bytes,
                media_type='text/csv; charset=utf-8',
                headers={'Content-Disposition': f'attachment; filename="{csv_name}"'}
            )
        else:
            import pandas as pd
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='openpyxl') as writer:
                for sheet in sheets:
                    cols = json.loads(sheet['columns_json'] or '[]')
                    rows = [json.loads(r['data_json']) for r in conn.execute('SELECT data_json FROM sheet_rows WHERE sheet_id=? ORDER BY row_index', (sheet['id'],))]
                    df = pd.DataFrame(rows, columns=cols)
                    title = (sheet['name'] or 'Sheet')[:31]
                    df.to_excel(writer, sheet_name=title, index=False)
            xlsx_name = orig_name if orig_name.lower().endswith(('.xlsx', '.xls')) else f"{Path(orig_name).stem}.xlsx"
            return Response(
                content=buf.getvalue(),
                media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                headers={'Content-Disposition': f'attachment; filename="{xlsx_name}"'}
            )
    finally:
        conn.close()


@router.post('/reseed-kaggle')
def reseed_kaggle():
    raise HTTPException(410, 'Automatic demo seeding has been removed. Upload any CSV or Excel file through the upload control.')


class BulkDeleteRequest(BaseModel):
    dataset_ids: list[int] = []
    delete_all: bool = False


def perform_bulk_delete(dataset_ids: list[int] | None = None, delete_all: bool = False):
    conn = get_connection()
    try:
        if delete_all or not dataset_ids:
            rows = conn.execute('SELECT filename FROM dataset_uploads').fetchall()
            with conn:
                conn.execute('DELETE FROM executive_narratives')
                conn.execute('DELETE FROM hr_alerts')
                conn.execute('DELETE FROM tabular_vectors')
                conn.execute('DELETE FROM dataset_uploads')
                rebuild_relationships(conn)
            for row in rows:
                path = (config.UPLOADS_DIR / row['filename']).resolve()
                if path.is_relative_to(config.UPLOADS_DIR.resolve()):
                    path.unlink(missing_ok=True)
            return {'message': 'All datasets, sheets, rows, search entries, cached narratives and relationships completely cleared.', 'deleted_count': len(rows)}

        placeholders = ','.join('?' for _ in dataset_ids)
        rows = conn.execute(f'SELECT id, filename FROM dataset_uploads WHERE id IN ({placeholders})', dataset_ids).fetchall()
        if not rows:
            return {'message': 'No matching datasets found to delete.', 'deleted_count': 0}
        found_ids = [r['id'] for r in rows]
        id_placeholders = ','.join('?' for _ in found_ids)
        with conn:
            conn.execute(f'DELETE FROM executive_narratives WHERE target_type=\'sheet\' AND target_id IN (SELECT id FROM sheets WHERE dataset_id IN ({id_placeholders}))', found_ids)
            conn.execute('DELETE FROM executive_narratives WHERE target_type IN (\'global\', \'relationship\')')
            conn.execute(f'DELETE FROM tabular_vectors WHERE id IN (SELECT id FROM tabular_chunks WHERE dataset_id IN ({id_placeholders}))', found_ids)
            conn.execute(f'DELETE FROM dataset_uploads WHERE id IN ({id_placeholders})', found_ids)
            rebuild_relationships(conn)
            remaining = conn.execute('SELECT COUNT(*) FROM dataset_uploads').fetchone()[0]
            if remaining == 0:
                conn.execute('DELETE FROM executive_narratives')
                conn.execute('DELETE FROM hr_alerts')
        for row in rows:
            path = (config.UPLOADS_DIR / row['filename']).resolve()
            if path.is_relative_to(config.UPLOADS_DIR.resolve()):
                path.unlink(missing_ok=True)
        return {'message': f'Successfully deleted {len(found_ids)} dataset(s).', 'deleted_count': len(found_ids)}
    finally:
        conn.close()


@router.delete('/datasets/{dataset_id}')
def delete_dataset(dataset_id: int):
    conn = get_connection()
    try:
        row = conn.execute('SELECT filename FROM dataset_uploads WHERE id=?', (dataset_id,)).fetchone()
        if row is None:
            raise HTTPException(404, 'Dataset not found')
        with conn:
            # 1. Clean up sheet-level cached executive narratives for sheets in this dataset
            conn.execute('DELETE FROM executive_narratives WHERE target_type=\'sheet\' AND target_id IN (SELECT id FROM sheets WHERE dataset_id=?)', (dataset_id,))
            # 2. Invalidate global and relationship narratives since workspace composition has changed
            conn.execute('DELETE FROM executive_narratives WHERE target_type IN (\'global\', \'relationship\')')
            # 3. Clean up tabular vectors
            conn.execute('DELETE FROM tabular_vectors WHERE id IN (SELECT id FROM tabular_chunks WHERE dataset_id=?)', (dataset_id,))
            # 4. Delete dataset (cascades to sheets, sheet_rows, sheet_cells, tabular_chunks, sheet_relationships)
            conn.execute('DELETE FROM dataset_uploads WHERE id=?', (dataset_id,))
            rebuild_relationships(conn)
            # 5. If no datasets remain in workspace, complete purge of all narratives and alerts
            remaining = conn.execute('SELECT COUNT(*) FROM dataset_uploads').fetchone()[0]
            if remaining == 0:
                conn.execute('DELETE FROM executive_narratives')
                conn.execute('DELETE FROM hr_alerts')
        path = (config.UPLOADS_DIR / row['filename']).resolve()
        # Never delete external Kaggle caches or paths outside uploads.
        if path.is_relative_to(config.UPLOADS_DIR.resolve()):
            path.unlink(missing_ok=True)
        return {'message': 'Deleted dataset, sheets, rows, search entries, cached narratives and relationships.'}
    finally:
        conn.close()


@router.delete('/datasets')
def delete_all_datasets(ids: str | None = Query(None, description="Comma-separated dataset IDs to delete. If omitted or 'all', deletes all.")):
    """Bulk deletion: deletes specified dataset IDs or completely purges all datasets, sheets, narratives, relationships, and uploads."""
    if ids and ids.lower() != 'all':
        try:
            target_ids = [int(x.strip()) for x in ids.split(',') if x.strip().isdigit()]
        except Exception:
            raise HTTPException(400, "Invalid ids parameter format")
        return perform_bulk_delete(target_ids, delete_all=False)
    return perform_bulk_delete([], delete_all=True)


@router.post('/datasets/bulk-delete')
def bulk_delete_datasets(payload: BulkDeleteRequest):
    """Selective or full bulk deletion via JSON body."""
    return perform_bulk_delete(payload.dataset_ids, payload.delete_all)



class DatasetAnalysisBriefRequest(BaseModel):
    user_objective: str = ""
    business_context: str | None = None
    questions_to_answer: list[str] = []
    business_rules: list[dict] = []
    important_dimensions: list[str] = []
    important_metrics: list[str] = []
    preferred_output: str = "Executive report"


@router.post('/datasets/{dataset_id}/brief')
def submit_dataset_brief(dataset_id: int, req: DatasetAnalysisBriefRequest):
    """Submits or updates the user analysis brief and reconciles business intent."""
    import pandas as pd
    from ..services.data_engine.semantic_classifier import SemanticClassifier
    from ..services.data_engine.analysis_context import IntentDataReconciler, AnalysisContext

    conn = get_connection()
    try:
        row = conn.execute('SELECT * FROM dataset_uploads WHERE id=?', (dataset_id,)).fetchone()
        if not row:
            raise HTTPException(404, 'Dataset not found')

        sheet = conn.execute('SELECT * FROM sheets WHERE dataset_id=? ORDER BY id ASC LIMIT 1', (dataset_id,)).fetchone()
        if not sheet:
            raise HTTPException(404, 'No sheets found for dataset')

        rows = conn.execute('SELECT data_json FROM sheet_rows WHERE sheet_id=? ORDER BY row_index', (sheet['id'],)).fetchall()
        records = [json.loads(r['data_json']) for r in rows]
        df = pd.DataFrame(records)
        display_name = sheet['display_name'] or sheet['name']

        profile = SemanticClassifier.profile_dataset(df, dataset_name=display_name)
        ctx = IntentDataReconciler.parse_and_reconcile(
            raw_text=req.user_objective,
            profile=profile,
            dataset_id=dataset_id,
            sheet_id=sheet['id'],
            structured_rules=req.business_rules,
            important_dimensions=req.important_dimensions,
            important_metrics=req.important_metrics,
            preferred_output=req.preferred_output
        )

        ctx_json = ctx.model_dump_json()
        with conn:
            conn.execute('UPDATE dataset_uploads SET analysis_context_json=? WHERE id=?', (ctx_json, dataset_id))
            conn.execute('UPDATE sheets SET analysis_context_json=? WHERE dataset_id=?', (ctx_json, dataset_id))

        return ctx.model_dump()
    finally:
        conn.close()


@router.get('/datasets/{dataset_id}/brief')
def get_dataset_brief(dataset_id: int):
    """Retrieves the reconciled analysis context for a dataset."""
    conn = get_connection()
    try:
        row = conn.execute('SELECT analysis_context_json FROM dataset_uploads WHERE id=?', (dataset_id,)).fetchone()
        if not row:
            raise HTTPException(404, 'Dataset not found')
        ctx_json = row['analysis_context_json']
        if not ctx_json:
            return {'mode': 'DISCOVERY', 'provenance': 'SYSTEM_DEFAULT', 'user_objective': ''}
        return json.loads(ctx_json)
    finally:
        conn.close()

