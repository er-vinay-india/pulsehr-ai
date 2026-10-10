import csv
import io
import json
import logging
from pathlib import Path
import queue
import threading
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel, Field, StrictInt

from ..core import config
from ..db.database import get_connection
from ..services.sheet_catalog import read_sheets, prepare_sheets, insert_sheets, rebuild_relationships, prepare_existing_column_vectors
from ..services.industrial_analytics import run_ingestion_industrial_pipeline
from ..services.sheet_naming_pipeline import generate_sheet_display_name
from ..services.ingestion_job_manager import ingestion_job_manager
from ..services.dataset_deletion import delete_datasets
from ..services.data_lifecycle import data_lifecycle_lock

logger = logging.getLogger(__name__)

router = APIRouter(prefix='/api/upload', tags=['upload'])
_db_write_lock = data_lifecycle_lock


def execute_ingestion_job(
    job_id: str,
    path: Path,
    original: str,
    suffix: str,
    user_objective: str = "",
    business_context: str | None = None
) -> dict[str, Any]:
    """Executes the complete 10-stage ingestion pipeline with real-time stage tracking."""
    conn = None
    try:
        # Stage 1: Raw Ingestion & Schema Extraction
        ingestion_job_manager.update_progress(
            job_id, step=1,
            message=f"Extracting raw sheets and tabular structure from {original}..."
        )
        frames = read_sheets(path)
        prepared = prepare_sheets(frames, original)
        total = sum(len(s['records']) for s in prepared)
        first = prepared[0]
        column_updates = prepare_existing_column_vectors()

        # Stage 2: AI Sheet Naming & Semantic Structural Profiling
        ingestion_job_manager.update_progress(
            job_id, step=2,
            message="Decontaminating filename, classifying business domain, and inferring column roles..."
        )
        naming = generate_sheet_display_name(original, first['columns'], first['records'])
        display_name = naming['display_name']

        # Stage 3: Data Cleansing & Syntactic Sanitization
        ingestion_job_manager.update_progress(
            job_id, step=3,
            message=f"Sanitizing whitespace, sentinel nulls, and data types across {len(prepared)} sheet(s)..."
        )

        # Stage 4: Metric & Unit Normalization
        ingestion_job_manager.update_progress(
            job_id, step=4,
            message="Parsing currencies ($/€/£/¥/₹), rates, percentages, and units while preserving data fidelity..."
        )

        # Stage 5: Controlled Semantic Enrichment & Scientific Discovery across ALL sheets
        ingestion_job_manager.update_progress(
            job_id, step=5,
            message="Executing controlled feature discovery, graph clustering, and analytical rollup synthesis..."
        )
        all_enrichment_summaries = {}
        primary_enrichment_summary = None

        for s_idx, sheet_data in enumerate(prepared):
            try:
                import pandas as pd
                from ..services.enrichment import ControlledEnrichmentPipeline

                df_raw = pd.DataFrame(sheet_data['records'])
                if len(df_raw) > 0:
                    final_df, enriched_pkg = ControlledEnrichmentPipeline.enrich_dataset(
                        df=df_raw,
                        dataset_id=f"{original}_{sheet_data['name']}"
                    )
                    enriched_records = json.loads(final_df.to_json(orient="records"))
                    enriched_cols = list(final_df.columns)

                    # Preserve raw values for existing columns so leading zeroes ('001') are never lost
                    orig_cols_set = set(sheet_data['columns'])
                    new_cols = [c for c in enriched_cols if c not in orig_cols_set]
                    for idx_r, r in enumerate(sheet_data['records']):
                        if idx_r < len(enriched_records):
                            for c in new_cols:
                                r[c] = enriched_records[idx_r].get(c)
                    sheet_data['columns'] = list(sheet_data['columns']) + new_cols

                    # Update profiles and hints for enriched columns while preserving existing column embeddings
                    old_vectors = {p['column']: (p.get('vector'), p.get('embedding_model')) for p in sheet_data['profiles']}
                    enriched_frames = {sheet_data['name']: pd.DataFrame(sheet_data['records']).astype(str)}
                    enriched_prep = prepare_sheets(enriched_frames, original, embed=False)
                    if enriched_prep:
                        for p in enriched_prep[0]['profiles']:
                            if p['column'] in old_vectors and old_vectors[p['column']][0]:
                                p['vector'] = old_vectors[p['column']][0]
                                p['embedding_model'] = old_vectors[p['column']][1]
                        sheet_data['profiles'] = enriched_prep[0]['profiles']
                        sheet_data['decision_hints'] = enriched_prep[0]['decision_hints']

                    sheet_summary = {
                        "sheet_name": sheet_data['name'],
                        "original_col_count": enriched_pkg.original_col_count,
                        "enriched_col_count": enriched_pkg.enriched_col_count,
                        "derived_features_count": len(enriched_pkg.derived_features),
                        "derived_features": [f.model_dump() for f in enriched_pkg.derived_features],
                        "semantic_groups": [g.model_dump() for g in enriched_pkg.semantic_groups],
                        "analytical_tables_count": len(enriched_pkg.analytical_tables),
                        "analytical_tables": [t.model_dump() for t in enriched_pkg.analytical_tables],
                        "budget_summary": enriched_pkg.budget_summary
                    }
                    all_enrichment_summaries[sheet_data['name']] = sheet_summary
                    if s_idx == 0:
                        primary_enrichment_summary = sheet_summary
            except Exception as e:
                logger.warning(f"Enrichment pipeline non-blocking warning for sheet '{sheet_data['name']}': {e}")

        enrichment_summary = primary_enrichment_summary

        # Stage 6: Database Persistence & Storage
        ingestion_job_manager.update_progress(
            job_id, step=6,
            message="Persisting sheets, batched rows, cell indexes, and feature metadata to catalog..."
        )

        with _db_write_lock:
            conn = get_connection()
            try:
                with conn:
                    enrich_json_str = json.dumps(enrichment_summary) if enrichment_summary else None
                    dataset_id = conn.execute('''INSERT INTO dataset_uploads(filename,original_name,display_name,file_type,sheet_count,row_count,col_count,columns_json,sample_preview_json,summary_insights,enrichment_json)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?)''', (path.name, original, display_name, suffix[1:], len(prepared), total, len(first['columns']), json.dumps(first['columns']), json.dumps(first['records'][:5]),
                        f'{len(prepared)} sheets and {total} rows. All original values retained.', enrich_json_str)).lastrowid
                    for sid, profiles in column_updates:
                        conn.execute('UPDATE sheets SET profile_json=? WHERE id=?', (json.dumps(profiles), sid))
                    insert_sheets(conn, dataset_id, prepared, display_name=display_name)
                    persisted_rows = conn.execute(
                        'SELECT COUNT(*) FROM sheet_rows WHERE sheet_id IN (SELECT id FROM sheets WHERE dataset_id=?)',
                        (dataset_id,)
                    ).fetchone()[0]
                    recon_rows = sum(len(f) for f in frames.values())
                    if recon_rows != total or total != persisted_rows:
                        raise ValueError(
                            f"Hard Invariant Violation: reconstructed_row_count ({recon_rows}) != "
                            f"prepared_records ({total}) != persisted_rows ({persisted_rows})"
                        )
                    logger.info(
                        "Reconstruction-to-persistence invariant verified: %d == %d == %d",
                        recon_rows, total, persisted_rows
                    )
                    uploaded_sheet_ids = [row['id'] for row in conn.execute(
                        'SELECT id FROM sheets WHERE dataset_id=? ORDER BY id', (dataset_id,)
                    ).fetchall()]
                    # Persist per-sheet enrichment metadata across all tabs
                    for s_name, s_summary in all_enrichment_summaries.items():
                        conn.execute('UPDATE sheets SET enrichment_json=? WHERE dataset_id=? AND name=?', (json.dumps(s_summary), dataset_id, s_name))
                    if enrich_json_str and not all_enrichment_summaries:
                        conn.execute('UPDATE sheets SET enrichment_json=? WHERE dataset_id=?', (enrich_json_str, dataset_id))

                    # Stage 7: Statistical Exploratory Data Analysis (EDA) & Outlier Profiling
                    ingestion_job_manager.update_progress(
                        job_id, step=7,
                        message="Computing statistical distributions, Tukey IQR fences, and Data Health Score..."
                    )
                    from ..services.eda import run_eda_pipeline
                    eda_res = run_eda_pipeline(conn=conn)
                    industrial_res = run_ingestion_industrial_pipeline(conn, dataset_id)

                    # Stage 8: Multi-Sheet Key Discovery & Cross-Correlation Matrix
                    ingestion_job_manager.update_progress(
                        job_id, step=8,
                        message="Discovering cross-sheet entity relationships and materializing analytical rollup views..."
                    )
                    rebuild_relationships(conn)

                    # Materialize synthesized analytical tables across all sheets in derived_tables & derived_table_rows (runs after EDA)
                    for s_name, s_summary in all_enrichment_summaries.items():
                        if s_summary.get("analytical_tables"):
                            for atbl in s_summary["analytical_tables"]:
                                try:
                                    cur = conn.execute(
                                        """
                                        INSERT INTO derived_tables(name, display_name, description, source_sheets_json, join_keys_json, columns_json, row_count)
                                        VALUES (?, ?, ?, ?, ?, ?, ?)
                                        """,
                                        (
                                            atbl["table_id"],
                                            atbl["title"],
                                            atbl["description"],
                                            json.dumps([conn.execute("SELECT id FROM sheets WHERE dataset_id=? AND name=?", (dataset_id, s_name)).fetchone()[0]]),
                                            json.dumps({"type": "scientific_enrichment_rollup", "source_kind": "sheet", "sheet": s_name, "group_by": atbl.get("group_by_columns", [])}),
                                            json.dumps(atbl["columns"]),
                                            atbl["row_count"]
                                        )
                                    )
                                    dt_id = cur.lastrowid
                                    for r_idx, rec in enumerate(atbl.get("data_preview", [])):
                                        conn.execute(
                                            """
                                            INSERT INTO derived_table_rows(derived_table_id, row_index, data_json)
                                            VALUES (?, ?, ?)
                                            """,
                                            (dt_id, r_idx, json.dumps(rec))
                                        )
                                except Exception as dt_err:
                                    logger.warning(f"Error persisting analytical table: {dt_err}")
                    linked = conn.execute("SELECT COUNT(*) FROM sheet_relationships WHERE status='linked' AND (left_sheet IN (SELECT id FROM sheets WHERE dataset_id=?) OR right_sheet IN (SELECT id FROM sheets WHERE dataset_id=?))", (dataset_id, dataset_id)).fetchone()[0]

                    # Stage 9: Semantic Vectorization & BM25 Hybrid Retrieval Indexing
                    ingestion_job_manager.update_progress(
                        job_id, step=9,
                        message="Verifying vector chunks, tabular embeddings, and lexical indexing..."
                    )

                    # Stage 10: Canonical Input & Context Intelligence Ingestion
                    ingestion_job_manager.update_progress(
                        job_id, step=10,
                        message="Reconciling workspace context, pre-warming visuals, and activating evidence catalog..."
                    )
                    ws_ctx_dict = None
                    try:
                        from ..services.input_intelligence import InputIntelligenceService
                        files_or_data = []
                        for s in prepared:
                            files_or_data.append({
                                "id": str(s.get("sheet_id") or dataset_id),
                                "filename": s.get("name") or original,
                                "original_name": s.get("name") or original,
                                "records": s.get("records") or [],
                                "columns": s.get("columns") or []
                            })
                        ws_ctx = InputIntelligenceService.process_workspace_input(
                            workspace_id=str(dataset_id),
                            files_or_data=files_or_data,
                            user_instruction=user_objective.strip() if user_objective else ""
                        )
                        ws_ctx_dict = ws_ctx.model_dump()
                        ws_ctx_json = ws_ctx.model_dump_json()
                        conn.execute('UPDATE dataset_uploads SET analysis_context_json=? WHERE id=?', (ws_ctx_json, dataset_id))
                        conn.execute('UPDATE sheets SET analysis_context_json=? WHERE dataset_id=?', (ws_ctx_json, dataset_id))
                    except Exception as e:
                        logger.warning(f"InputIntelligenceService ingestion warning: {e}")

                    analysis_ctx_dict = ws_ctx_dict
            finally:
                conn.close()

        # Asynchronously pre-warm visual analytics, persona detection, and evidence ledger to eliminate PPT cold start
        def _prewarm_presentation_cache(ds_id: int):
            try:
                with get_connection() as warm_conn:
                    from ..services.visuals.workspace_visual_dashboard import build_workspace_visual_dashboard
                    from ..services.presentation.scope_detector import collect_workspace_evidence, capture_dataset_context
                    from ..services.presentation.persona_router import detect_dataset_persona

                    build_workspace_visual_dashboard(warm_conn)
                    ctx = capture_dataset_context(warm_conn, ds_id)
                    detect_dataset_persona(ctx, warm_conn)
                    scope = {"scope_type": "workspace", "sheet_id": ds_id}
                    collect_workspace_evidence(warm_conn, scope)
            except Exception as warm_err:
                logger.debug(f"Pre-warming presentation cache non-blocking notice: {warm_err}")

        threading.Thread(target=_prewarm_presentation_cache, args=(dataset_id,), daemon=True).start()

        result_payload = {
            'status': 'success',
            'job_id': job_id,
            'dataset_id': dataset_id,
            'filename': original,
            'display_name': display_name,
            'domain': (ws_ctx_dict.get('context_summary', {}).get('domain') if ws_ctx_dict else naming['domain']),
            'description': naming['description'],
            'sheets': list(frames),
            'sheet_ids': uploaded_sheet_ids,
            'total_rows': total,
            'columns': first['columns'],
            'sample_preview': first['records'][:5],
            'indexed_chunks': total,
            'vector_chunks': sum(len(s['vectors']) for s in prepared),
            'linked_relationships': linked,
            'industrial_analytics': industrial_res,
            'analysis_context': analysis_ctx_dict,
            'workspace_context': ws_ctx_dict,
            'enrichment': enrichment_summary,
            'user_objective': user_objective.strip() if user_objective else "",
            'message': f'Indexed all {total} rows with {enrichment_summary["derived_features_count"] if enrichment_summary else 0} scientifically derived features.' if enrichment_summary else (f'Indexed all {total} rows. Reconciled user intent into analytical evidence pipeline.' if analysis_ctx_dict else f'Indexed all {total} rows. Found {linked} exact key relationships and computed industrial analytics pipeline.')
        }

        with data_lifecycle_lock:
            with get_connection() as live_conn:
                if not live_conn.execute('SELECT 1 FROM dataset_uploads WHERE id=?', (dataset_id,)).fetchone():
                    raise ValueError('Workbook was deleted before ingestion finished.')
            ingestion_job_manager.complete_job(job_id, dataset_id, result_payload)
        return result_payload

    except Exception as exc:
        ingestion_job_manager.fail_job(job_id, str(exc))
        path.unlink(missing_ok=True)
        raise


@router.post('/file')
def upload_file(
    file: UploadFile = File(...),
    user_objective: str = Form(default=""),
    business_context: str | None = Form(default=None),
    async_mode: bool = Query(default=False),
):
    original = Path((file.filename or 'uploaded.csv').replace('\\', '/')).name
    suffix = Path(original).suffix.lower()
    if suffix not in ('.csv', '.tsv', '.xlsx', '.xls'):
        raise HTTPException(400, 'Upload a CSV, TSV, or Excel file.')
    path = config.UPLOADS_DIR / f'{uuid4().hex}{suffix}'
    try:
        content = file.file.read(20 * 1024 * 1024 + 1)
        if len(content) > 20 * 1024 * 1024:
            raise ValueError('Maximum upload size is 20 MB.')
        path.write_bytes(content)
    except Exception as exc:
        path.unlink(missing_ok=True)
        raise HTTPException(400, str(exc)) from exc

    job_id = ingestion_job_manager.create_job(filename=original, file_size_bytes=len(content))

    if async_mode:
        worker_thread = threading.Thread(
            target=execute_ingestion_job,
            args=(job_id, path, original, suffix, user_objective, business_context),
            daemon=True
        )
        worker_thread.start()
        return {
            'status': 'queued',
            'job_id': job_id,
            'filename': original,
            'message': 'Spreadsheet ingestion job started.'
        }

    try:
        return execute_ingestion_job(
            job_id, path, original, suffix, user_objective, business_context
        )
    except (ValueError, OSError, ImportError) as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(500, f"Ingestion error: {exc}") from exc


@router.get('/jobs')
def list_ingestion_jobs(limit: int = Query(default=20, ge=1, le=100)):
    return {"jobs": ingestion_job_manager.list_jobs(limit=limit)}


@router.get('/jobs/{job_id}')
def get_ingestion_job(job_id: str):
    job = ingestion_job_manager.get_job(job_id)
    if not job:
        raise HTTPException(404, f"Ingestion job '{job_id}' not found")
    return job


@router.get('/jobs/{job_id}/stream')
def stream_ingestion_job(job_id: str):
    job = ingestion_job_manager.get_job(job_id)
    if not job:
        raise HTTPException(404, f"Ingestion job '{job_id}' not found")

    def event_stream():
        q = ingestion_job_manager.subscribe(job_id)
        try:
            while True:
                try:
                    data = q.get(timeout=25.0)
                    yield f"data: {json.dumps(data)}\n\n"
                    if data.get("status") in ("completed", "failed"):
                        break
                except queue.Empty:
                    yield ": keep-alive\n\n"
        finally:
            ingestion_job_manager.unsubscribe(job_id, q)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


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
            enrich_str = item.pop('enrichment_json', None)
            item['enrichment'] = json.loads(enrich_str) if enrich_str else None
            item['sheets'] = [dict(s) for s in conn.execute('SELECT id,name,display_name,row_count FROM sheets WHERE dataset_id=?', (row['id'],))]
            datasets.append(item)
        return {'datasets': datasets}
    finally:
        conn.close()


@router.get('/datasets/{dataset_id}/enrichment')
def get_dataset_enrichment(dataset_id: int):
    conn = get_connection()
    try:
        row = conn.execute('SELECT enrichment_json FROM dataset_uploads WHERE id=?', (dataset_id,)).fetchone()
        if not row or not row['enrichment_json']:
            return {"enrichment": None, "message": "No enrichment data available for this dataset."}
        return {"enrichment": json.loads(row['enrichment_json'])}
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
    dataset_ids: list[StrictInt] = Field(default_factory=list)
    delete_all: bool = False


def perform_bulk_delete(dataset_ids: list[int] | None = None, delete_all: bool = False):
    return delete_datasets(dataset_ids, delete_all=delete_all)


@router.delete('/datasets/{dataset_id}')
def delete_dataset(dataset_id: int):
    result = delete_datasets([dataset_id])
    if not result['deleted_count'] and not result['cleanup_pending']:
        # A repeated DELETE is safe, including after a lost success response.
        result['message'] = 'Workbook is already removed; cleanup is complete.'
    return result


@router.delete('/datasets')
def delete_all_datasets(ids: str | None = Query(None, description="Comma-separated dataset IDs to delete. Omitted or 'all' explicitly clears the workspace.")):
    if ids is None or ids.lower() == 'all':
        return delete_datasets(delete_all=True)
    parts = ids.split(',')
    if not parts or any(not part.strip().isdigit() or int(part.strip()) <= 0 for part in parts):
        raise HTTPException(400, 'Invalid workbook IDs. Nothing was deleted.')
    return delete_datasets([int(part.strip()) for part in parts])


@router.post('/datasets/bulk-delete')
def bulk_delete_datasets(payload: BulkDeleteRequest):
    return delete_datasets(payload.dataset_ids, delete_all=payload.delete_all)


class DatasetAnalysisBriefRequest(BaseModel):
    sheet_id: int | None = None
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

        if req.sheet_id:
            sheet = conn.execute('SELECT * FROM sheets WHERE dataset_id=? AND id=?', (dataset_id, req.sheet_id)).fetchone()
        else:
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
