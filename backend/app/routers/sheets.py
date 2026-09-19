import json
import math

from fastapi import APIRouter, HTTPException, Query
from ..db.database import get_connection
from ..services.sheet_catalog import catalogue, relationships

router = APIRouter(prefix='/api/sheets', tags=['sheets'])


@router.get('')
def list_sheets():
    conn = get_connection()
    try:
        return {'sheets': catalogue(conn), 'relationships': relationships(conn)}
    finally:
        conn.close()


@router.get('/relationships/{relationship_id}/rows')
def joined_rows(relationship_id: int, page: int = Query(1, ge=1), limit: int = Query(25, ge=1, le=100)):
    conn = get_connection()
    try:
        relation = conn.execute('SELECT * FROM sheet_relationships WHERE id=?', (relationship_id,)).fetchone()
        if relation is None:
            raise HTTPException(404, 'Relationship not found. Refresh the sheets list.')
        if relation['status'] != 'linked':
            raise HTTPException(409, 'This relationship is a suggestion, not a verified key join.')
        sql = '''FROM sheet_cells a JOIN sheet_cells b ON a.value_key=b.value_key
                 JOIN sheet_rows l ON l.sheet_id=a.sheet_id AND l.row_index=a.row_index
                 JOIN sheet_rows r ON r.sheet_id=b.sheet_id AND r.row_index=b.row_index
                 WHERE a.sheet_id=? AND a.column_name=? AND b.sheet_id=? AND b.column_name=?'''
        args = (relation['left_sheet'], relation['left_column'], relation['right_sheet'], relation['right_column'])
        rows = conn.execute('SELECT l.row_index AS left_row,r.row_index AS right_row,l.data_json AS left_data,r.data_json AS right_data ' + sql + ' ORDER BY l.row_index,r.row_index LIMIT ? OFFSET ?', (*args, limit, (page-1)*limit)).fetchall()
        return {'relationship': dict(relation), 'total': relation['matching_pairs'], 'page': page,
                'pages': max(1, math.ceil(relation['matching_pairs']/limit)),
                'rows': [{'left_row': r['left_row']+1, 'right_row': r['right_row']+1, 'left': json.loads(r['left_data']), 'right': json.loads(r['right_data'])} for r in rows]}
    finally:
        conn.close()


@router.get('/{sheet_id}/rows')
def sheet_rows(sheet_id: int, page: int = Query(1, ge=1), limit: int = Query(25, ge=1, le=100), search: str = Query('', max_length=200)):
    conn = get_connection()
    try:
        sheet = conn.execute('SELECT * FROM sheets WHERE id=?', (sheet_id,)).fetchone()
        if sheet is None:
            raise HTTPException(404, 'Sheet not found')
        clause, args = 'sheet_id=?', [sheet_id]
        if search:
            clause += ' AND EXISTS (SELECT 1 FROM json_each(sheet_rows.data_json) WHERE instr(lower(CAST(value AS TEXT)),lower(?)) > 0)'
            args.append(search)
        total = conn.execute('SELECT COUNT(*) FROM sheet_rows WHERE ' + clause, args).fetchone()[0]
        rows = conn.execute('SELECT row_index,data_json FROM sheet_rows WHERE ' + clause + ' ORDER BY row_index LIMIT ? OFFSET ?', (*args, limit, (page-1)*limit)).fetchall()
        return {'sheet_id': sheet_id, 'columns': json.loads(sheet['columns_json']), 'rows': [{'row_number': r['row_index']+1, 'values': json.loads(r['data_json'])} for r in rows], 'total': total, 'page': page, 'pages': max(1, math.ceil(total/limit))}
    finally:
        conn.close()
