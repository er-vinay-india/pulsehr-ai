"""Complete, source-preserving sheets and explainable cross-sheet relationships."""
import json
import logging
import math
import re
from pathlib import Path

import httpx
import numpy as np
import pandas as pd

from ..core import config
from ..db.database import get_connection
from .display_formatters import format_display_label

logger = logging.getLogger(__name__)
ALIASES = {
    'employeeid': 'employee_id', 'empid': 'employee_id', 'employeecode': 'employee_id', 'empcode': 'employee_id',
    'employeename': 'employee_name', 'staffname': 'employee_name', 'fullname': 'employee_name',
    'department': 'department', 'dept': 'department', 'departmentname': 'department',
    'departmentid': 'department_id', 'deptid': 'department_id',
    'email': 'email', 'emailaddress': 'email', 'workemail': 'email',
}


def canonical(column):
    key = re.sub(r'[^\w]', '', column.casefold()).replace('_', '')
    return ALIASES.get(key, key)


def value_key(value):
    # Preserve punctuation and leading zeroes; do not turn 001 into 1.
    return ' '.join(str(value).strip().casefold().split()) if value is not None else ''


def model_embeddings(texts):
    """One embedding space only. An offline model never produces fake vectors."""
    if not texts:
        return []
    try:
        with httpx.Client(timeout=15) as client:
            response = client.post(f'{config.OLLAMA_BASE_URL}/api/embed', json={
                'model': config.OLLAMA_EMBED_MODEL, 'input': texts, 'truncate': True})
            response.raise_for_status()
            vectors = response.json()['embeddings']
            if len(vectors) == len(texts) and all(len(v) == config.EMBEDDING_DIM and all(math.isfinite(x) for x in v) for v in vectors):
                return vectors
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        logger.info('Embeddings unavailable; exact links and keyword search remain active')
    return []


def read_sheets(path):
    if path.suffix.lower() == '.csv':
        for encoding in ('utf-8-sig', 'cp1252', 'latin1'):
            try:
                frames = {'Sheet1': pd.read_csv(path, dtype=str, encoding=encoding, keep_default_na=False)}
                break
            except UnicodeDecodeError:
                continue
    else:
        with pd.ExcelFile(path) as book:
            frames = {name: pd.read_excel(book, sheet_name=name, dtype=str, keep_default_na=False) for name in book.sheet_names}
    if sum(len(f) for f in frames.values()) > 20000:
        raise ValueError('Upload at most 20,000 rows per file. Split larger files before uploading.')
    for frame in frames.values():
        frame.columns = [str(c).strip() for c in frame.columns]
        if len(frame.columns) > 200 or frame.columns.duplicated().any() or any(not c for c in frame.columns):
            raise ValueError('Use unique, nonempty column names and at most 200 columns per sheet.')
    return frames


def numeric_values(raw, column):
    values = raw.replace(r'^\s*$', pd.NA, regex=True)
    present = values.dropna().astype(str).str.strip()
    unit = None
    if len(present) and present.str.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)\s*%').all():
        values = values.astype('string').str.strip().str.rstrip('%').str.strip()
        unit = '%'
    elif 'rating' in canonical(column) and len(present):
        fractions = present.str.extract(r'^([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*/\s*(\d+(?:\.\d*)?)$')
        if fractions.notna().all().all() and fractions[1].nunique() == 1:
            values = values.astype('string').str.split('/').str[0].str.strip()
            unit = 'out of ' + fractions[1].iloc[0]
    return pd.to_numeric(values, errors='coerce'), unit


def prepare_sheets(frames, source, embed=True):
    prepared = []
    for name, frame in frames.items():
        records = json.loads(frame.to_json(orient='records', date_format='iso'))
        profiles = []
        for column in frame.columns:
            values = [row[column] for row in records if value_key(row[column])]
            numeric, unit = numeric_values(pd.Series(values, dtype=object), column)
            profile = {'column': column, 'canonical': canonical(column), 'display_name': format_display_label(column), 'nonempty': len(values),
                       'missing': len(records) - len(values), 'distinct': len({value_key(v) for v in values})}
            # IDs, booleans and numeric-looking codes are not measures.
            identifier = canonical(column).endswith('id') or canonical(column).endswith('_id') or 'code' in canonical(column)
            if len(values) and not identifier and numeric.notna().all() and np.isfinite(numeric.astype(float)).all():
                profile['numeric'] = {k: float(getattr(numeric.astype(float), k)()) for k in ('min', 'max', 'mean', 'sum')}
                profile['unit'] = unit
                if unit or any(term in canonical(column) for term in ('rate', 'rating', 'percent')):
                    profile['numeric'].pop('sum', None)
            profiles.append(profile)
        vectors = model_embeddings([f"Column {p['column']} ({p['canonical']})" for p in profiles]) if embed else []
        for profile, vector in zip(profiles, vectors):
            profile['vector'] = vector
            profile['embedding_model'] = config.OLLAMA_EMBED_MODEL
        chunks = [f"Source: {source}; Sheet: {name}; Row: {i + 1}. " + '; '.join(f'{k}: {v}' for k, v in row.items() if value_key(v)) for i, row in enumerate(records)]
        row_vectors = []
        if vectors:  # A failed column batch avoids repeatedly contacting an offline model.
            for start in range(0, len(chunks), 64):
                batch = model_embeddings(chunks[start:start+64])
                if not batch:
                    break
                row_vectors.extend(batch)
        prepared.append({'name': name, 'columns': list(frame.columns), 'profiles': profiles, 'records': records, 'chunks': chunks, 'vectors': row_vectors})
    return prepared


def insert_sheets(conn, dataset_id, prepared):
    from .rag_service import pack_vector
    for sheet in prepared:
        sid = conn.execute('INSERT INTO sheets(dataset_id,name,columns_json,profile_json,row_count) VALUES (?,?,?,?,?)',
                           (dataset_id, sheet['name'], json.dumps(sheet['columns']), json.dumps(sheet['profiles']), len(sheet['records']))).lastrowid
        for i, record in enumerate(sheet['records']):
            conn.execute('INSERT INTO sheet_rows(sheet_id,row_index,data_json) VALUES (?,?,?)', (sid, i, json.dumps(record)))
            conn.executemany('INSERT INTO sheet_cells VALUES (?,?,?,?)', [(sid, i, col, value_key(value)) for col, value in record.items() if value_key(value)])
            metadata = {'dataset_id': dataset_id, 'sheet_id': sid, 'sheet_name': sheet['name'], 'row_index': i}
            if i < len(sheet['vectors']):
                metadata['embedding_model'] = config.OLLAMA_EMBED_MODEL
            chunk_id = conn.execute('INSERT INTO tabular_chunks(dataset_id,sheet_name,row_index,chunk_text,metadata_json) VALUES (?,?,?,?,?)',
                                    (dataset_id, sheet['name'], i, sheet['chunks'][i], json.dumps(metadata))).lastrowid
            if i < len(sheet['vectors']):
                conn.execute('INSERT INTO tabular_vectors(id,embedding) VALUES (?,?)', (chunk_id, pack_vector(sheet['vectors'][i])))


def prepare_existing_column_vectors():
    conn = get_connection()
    try:
        sheets = [(r['id'], json.loads(r['profile_json'])) for r in conn.execute('SELECT id,profile_json FROM sheets')]
    finally:
        conn.close()
    missing = [(sid, profile) for sid, profiles in sheets for profile in profiles if not profile.get('vector')]
    vectors = model_embeddings([f"Column {p['column']} ({p['canonical']})" for _, p in missing])
    for (_, profile), vector in zip(missing, vectors):
        profile['vector'] = vector
        profile['embedding_model'] = config.OLLAMA_EMBED_MODEL
    return sheets if vectors else []


def sync_catalog_metadata(conn):
    if not conn.execute("SELECT 1 FROM app_metadata WHERE key='sheet_profiles_v2'").fetchone():
        for sheet in conn.execute('SELECT * FROM sheets').fetchall():
            records = [json.loads(r['data_json']) for r in conn.execute('SELECT data_json FROM sheet_rows WHERE sheet_id=? ORDER BY row_index', (sheet['id'],))]
            frame = pd.DataFrame(records, columns=json.loads(sheet['columns_json']))
            profiles = prepare_sheets({sheet['name']: frame}, '', embed=False)[0]['profiles']
            previous = {p['column']: p for p in json.loads(sheet['profile_json'])}
            for profile in profiles:
                old = previous.get(profile['column'], {})
                if old.get('vector'):
                    profile.update(vector=old['vector'], embedding_model=old['embedding_model'])
            conn.execute('UPDATE sheets SET profile_json=? WHERE id=?', (json.dumps(profiles), sheet['id']))
        conn.execute("INSERT INTO app_metadata VALUES ('sheet_profiles_v2','complete')")
    for dataset in conn.execute('SELECT id FROM dataset_uploads').fetchall():
        sheets = conn.execute('SELECT columns_json,row_count FROM sheets WHERE dataset_id=? ORDER BY id', (dataset['id'],)).fetchall()
        if sheets:
            conn.execute('UPDATE dataset_uploads SET sheet_count=?,row_count=?,col_count=?,columns_json=? WHERE id=?',
                         (len(sheets), sum(s['row_count'] for s in sheets), len(json.loads(sheets[0]['columns_json'])), sheets[0]['columns_json'], dataset['id']))


def rebuild_relationships(conn):
    sheets = conn.execute('SELECT * FROM sheets ORDER BY id').fetchall()
    conn.execute('DELETE FROM sheet_relationships')
    counts = {}
    for row in conn.execute('SELECT sheet_id,column_name,value_key,COUNT(*) AS n FROM sheet_cells GROUP BY sheet_id,column_name,value_key'):
        counts.setdefault((row['sheet_id'], row['column_name']), {})[row['value_key']] = row['n']
    for idx, left in enumerate(sheets):
        for right in sheets[idx+1:]:
            for lp in json.loads(left['profile_json']):
                for rp in json.loads(right['profile_json']):
                    lc, rc = lp['column'], rp['column']
                    exact = canonical(lc) == canonical(rc)
                    similarity = None
                    if not exact and lp.get('embedding_model') == rp.get('embedding_model') and lp.get('vector') and rp.get('vector'):
                        a, b = np.array(lp['vector']), np.array(rp['vector'])
                        denom = np.linalg.norm(a) * np.linalg.norm(b)
                        similarity = float(a @ b / denom) if denom else 0
                    if not exact and (similarity is None or similarity < .85):
                        continue
                    lv, rv = counts.get((left['id'], lc), {}), counts.get((right['id'], rc), {})
                    overlap = lv.keys() & rv.keys()
                    if not overlap:
                        continue
                    lu, ru = all(v == 1 for v in lv.values()), all(v == 1 for v in rv.values())
                    cardinality = ('one' if lu else 'many') + '-to-' + ('one' if ru else 'many')
                    keylike = lp['canonical'] not in ('id', 'paid', 'valid') and (lp['canonical'] in ('employee_id', 'employee_name', 'department', 'department_id', 'email') or lp['canonical'].endswith('id') or lp['canonical'].endswith('code'))
                    status = 'linked' if exact and keylike and (lu or ru) else 'suggested'
                    method = ('exact' if lc.casefold() == rc.casefold() else 'alias') if exact else 'vector'
                    reason = 'Matching keys with a unique side; exact equality join.' if status == 'linked' else 'Review before use: similarity or shared values alone do not establish identity.'
                    conn.execute('''INSERT INTO sheet_relationships(left_sheet,right_sheet,left_column,right_column,method,status,cardinality,matching_keys,matching_pairs,similarity,reason)
                                    VALUES (?,?,?,?,?,?,?,?,?,?,?)''', (left['id'], right['id'], lc, rc, method, status, cardinality, len(overlap), sum(lv[k]*rv[k] for k in overlap), similarity, reason))


def catalogue(conn):
    output = []
    for row in conn.execute('SELECT s.*,d.original_name FROM sheets s JOIN dataset_uploads d ON d.id=s.dataset_id ORDER BY s.id'):
        entry = dict(row)
        entry['columns'] = json.loads(entry.pop('columns_json'))
        profiles = json.loads(entry.pop('profile_json') or '[]')
        for p in profiles:
            if 'display_name' not in p and 'column' in p:
                p['display_name'] = format_display_label(p['column'])
        entry['profiles'] = [{k: v for k, v in p.items() if k not in ('vector', 'embedding_model')} for p in profiles]
        entry['display_columns'] = {c: format_display_label(c) for c in entry['columns']}
        output.append(entry)
    return output


def backfill_display_names():
    """Lightweight migration: ensures existing stored sheet profiles include display_name."""
    conn = get_connection()
    try:
        rows = conn.execute("SELECT id, profile_json FROM sheets").fetchall()
        for r in rows:
            sid = r["id"]
            if not r["profile_json"]:
                continue
            profiles = json.loads(r["profile_json"])
            modified = False
            for p in profiles:
                if 'display_name' not in p and 'column' in p:
                    p['display_name'] = format_display_label(p['column'])
                    modified = True
            if modified:
                conn.execute("UPDATE sheets SET profile_json=? WHERE id=?", (json.dumps(profiles), sid))
        conn.commit()
    except Exception as e:
        logger.warning(f"Failed to backfill display names: {e}")
    finally:
        conn.close()


def relationships(conn):
    return [dict(row) for row in conn.execute('''SELECT r.*, l.name AS left_name, rr.name AS right_name,
        ld.original_name AS left_file, rd.original_name AS right_file FROM sheet_relationships r
        JOIN sheets l ON l.id=r.left_sheet JOIN sheets rr ON rr.id=r.right_sheet
        JOIN dataset_uploads ld ON ld.id=l.dataset_id JOIN dataset_uploads rd ON rd.id=rr.dataset_id ORDER BY r.id''')]


def overview():
    conn = get_connection()
    try:
        sheets = catalogue(conn)
        links = relationships(conn)
        sources = [dict(r) for r in conn.execute('SELECT id,original_name,filename,summary_insights,row_count,sheet_count FROM dataset_uploads ORDER BY id DESC')]
        return {'stats': {'datasets': len(sources), 'sheets': len(sheets), 'rows': sum(s['row_count'] for s in sheets),
                          'linked_relationships': sum(r['status'] == 'linked' for r in links)},
                'sheets': sheets, 'relationships': links, 'sources': sources,
                'note': 'Rows are source records, not unique employees. Metrics stay separate by sheet to avoid double counting joins.'}
    finally:
        conn.close()


def migrate_existing():
    """Import legacy original files once; archive old derived data before retiring it."""
    conn = get_connection()
    try:
        if conn.execute("SELECT 1 FROM app_metadata WHERE key='sheet_catalog_v1'").fetchone():
            sync_catalog_metadata(conn)
            conn.commit()
            return
        # A local recovery snapshot includes the legacy derived employee data.
        import sqlite3
        backup_path = config.DB_PATH.parent / 'before_sheet_catalog_v1.sqlite3'
        if not backup_path.exists():
            backup = sqlite3.connect(backup_path)
            try:
                conn.backup(backup)
            finally:
                backup.close()
        pending = []
        for dataset in conn.execute('SELECT * FROM dataset_uploads').fetchall():
            if conn.execute('SELECT 1 FROM sheets WHERE dataset_id=?', (dataset['id'],)).fetchone():
                continue
            path = (config.UPLOADS_DIR / dataset['filename']).resolve()
            if not path.is_relative_to(config.UPLOADS_DIR.resolve()):
                continue
            if not path.is_file() and dataset['filename'] == 'attendance_2023_2024.csv':
                path = config.KAGGLE_LOCAL_CACHE / dataset['filename']
            try:
                pending.append((dataset['id'], prepare_sheets(read_sheets(path), dataset['original_name'], embed=False)))
            except (OSError, ValueError, ImportError) as exc:
                logger.warning('Cannot migrate dataset %s: %s', dataset['id'], exc)
                pending.append((dataset['id'], None))
        with conn:
            conn.execute("DELETE FROM tabular_vectors WHERE id IN (SELECT id FROM tabular_chunks WHERE json_extract(metadata_json,'$.sheet_id') IS NULL)")
            conn.execute("DELETE FROM tabular_chunks WHERE json_extract(metadata_json,'$.sheet_id') IS NULL")
            conn.execute('DELETE FROM attendance_records')
            conn.execute('DELETE FROM hr_alerts')
            conn.execute('DELETE FROM employees')
            for dataset_id, prepared in pending:
                if prepared is not None:
                    insert_sheets(conn, dataset_id, prepared)
                    conn.execute('UPDATE dataset_uploads SET row_count=?,sheet_count=?,summary_insights=? WHERE id=?',
                                 (sum(len(s['records']) for s in prepared), len(prepared), 'Original sheet data imported. Demo employee synthesis has been retired.', dataset_id))
                else:
                    conn.execute('UPDATE dataset_uploads SET summary_insights=? WHERE id=?', ('Original file unavailable. Delete this entry or upload the file again.', dataset_id))
            sync_catalog_metadata(conn)
            rebuild_relationships(conn)
            conn.execute("INSERT INTO app_metadata VALUES ('sheet_catalog_v1','complete')")
    finally:
        conn.close()


def linked_evidence(results, limit=12):
    """Expand retrieved rows via explicit key equality, never vector similarity alone."""
    conn = get_connection()
    found, seen = [], {r['chunk_id'] for r in results}
    try:
        for result in results:
            meta = result.get('metadata', {})
            sid, index = meta.get('sheet_id'), meta.get('row_index')
            if sid is None or index is None:
                continue
            links = conn.execute("SELECT * FROM sheet_relationships WHERE status='linked' AND (left_sheet=? OR right_sheet=?)", (sid, sid)).fetchall()
            for link in links:
                forward = sid == link['left_sheet']
                target = link['right_sheet'] if forward else link['left_sheet']
                source_col = link['left_column'] if forward else link['right_column']
                target_col = link['right_column'] if forward else link['left_column']
                rows = conn.execute('''SELECT c.*,d.original_name FROM sheet_cells a JOIN sheet_cells b ON a.value_key=b.value_key
                    JOIN sheets s ON s.id=b.sheet_id JOIN dataset_uploads d ON d.id=s.dataset_id
                    JOIN tabular_chunks c ON c.dataset_id=s.dataset_id AND c.sheet_name=s.name AND c.row_index=b.row_index
                    WHERE a.sheet_id=? AND a.row_index=? AND a.column_name=? AND b.sheet_id=? AND b.column_name=? LIMIT ?''',
                    (sid, index, source_col, target, target_col, limit)).fetchall()
                for row in rows:
                    if row['id'] in seen:
                        continue
                    seen.add(row['id'])
                    found.append({'chunk_id': row['id'], 'text': row['chunk_text'], 'metadata': json.loads(row['metadata_json']),
                                  'source_file': row['original_name'], 'sheet_name': row['sheet_name'], 'row_index': row['row_index'],
                                  'relevance_score': 0, 'retrieval_methods': ['exact_join'], 'relationship_id': link['id']})
                    if len(found) >= limit:
                        return found
        return found
    finally:
        conn.close()
