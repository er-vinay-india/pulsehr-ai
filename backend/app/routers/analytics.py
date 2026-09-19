import json
from fastapi import APIRouter, Query
from ..db.database import get_connection
from ..services.sheet_catalog import overview
from ..services.executive_story import get_or_generate_executive_story, compute_relational_story, detect_sheet_domain
from ..services.visual_intelligence import build_workspace_visual_dashboard

router = APIRouter(prefix='/api/analytics', tags=['analytics'])


def get_base_overview() -> dict:
    """Fast database catalog extraction (< 20ms) for instant initial page rendering."""
    data = overview()
    conn = get_connection()
    try:
        sheets_rows = conn.execute(
            'SELECT s.id, s.name, s.row_count, s.columns_json, d.original_name '
            'FROM sheets s JOIN dataset_uploads d ON d.id=s.dataset_id ORDER BY s.id ASC'
        ).fetchall()
        sheets_list = []
        for r in sheets_rows:
            cols = json.loads(r['columns_json']) if r['columns_json'] else []
            domain, _ = detect_sheet_domain(cols)
            sheets_list.append({
                'id': r['id'],
                'name': r['name'],
                'original_name': r['original_name'],
                'row_count': r['row_count'],
                'col_count': len(cols),
                'domain': domain
            })
        data['sheets_list'] = sheets_list
        return data
    finally:
        conn.close()


@router.get('/overview/base')
def api_overview_base():
    """Returns core catalog metrics, sheets list, and connection links instantly."""
    return get_base_overview()


@router.get('/overview/visuals')
def api_overview_visuals(sheet_id: int | None = Query(None)):
    """Computes and returns the Industrial People Analytics & Visual Intelligence Dashboard."""
    clean_sheet_id = int(sheet_id) if sheet_id is not None and not hasattr(sheet_id, 'default') else None
    conn = get_connection()
    try:
        visual_dashboard_res = build_workspace_visual_dashboard(conn, sheet_id=clean_sheet_id)
        return {
            'visual_dashboard': visual_dashboard_res,
            'sheet_id': clean_sheet_id
        }
    finally:
        conn.close()


@router.get('/overview/story')
def api_overview_story(sheet_id: int | None = Query(None), force_refresh: bool = Query(False), model: str | None = Query(None)):
    """Fetches or generates the AI Executive Story, forecast, and verification audit."""
    clean_sheet_id = int(sheet_id) if sheet_id is not None and not hasattr(sheet_id, 'default') else None
    clean_model = str(model) if model is not None and not hasattr(model, 'default') else None
    story_res = get_or_generate_executive_story(sheet_id=clean_sheet_id, force_refresh=force_refresh, model=clean_model)
    return {
        'executive_story': story_res.get('narrative'),
        'evaluation': story_res.get('evaluation'),
        'charts': story_res.get('charts'),
        'forecast': story_res.get('forecast'),
        'story_meta': {
            'model': story_res.get('model_used'),
            'cached': story_res.get('cached', False),
            'sheet_id': story_res.get('sheet_id')
        }
    }


@router.get('/overview/relational')
def api_overview_relational(model: str | None = Query(None)):
    """Computes cross-sheet relational dynamics and talent quadrants."""
    clean_model = str(model) if model is not None and not hasattr(model, 'default') else None
    conn = get_connection()
    try:
        relational_res = compute_relational_story(conn, model=clean_model)
        return {
            'relational_story': relational_res
        }
    finally:
        conn.close()


@router.get('/overview')
def get_analytics_overview(sheet_id: int | None = Query(None), chunk: str | None = Query(None)):
    clean_sheet_id = int(sheet_id) if sheet_id is not None and not hasattr(sheet_id, 'default') else None
    if chunk == 'base':
        return api_overview_base()
    if chunk == 'visuals':
        return api_overview_visuals(sheet_id=clean_sheet_id)
    if chunk == 'story':
        return api_overview_story(sheet_id=clean_sheet_id)
    if chunk == 'relational':
        return api_overview_relational()

    # Monolithic fallback for backward compatibility
    data = get_base_overview()
    conn = get_connection()
    try:
        story_res = get_or_generate_executive_story(sheet_id=clean_sheet_id, force_refresh=False)
        relational_res = compute_relational_story(conn)
        visual_dashboard_res = build_workspace_visual_dashboard(conn, sheet_id=clean_sheet_id)

        data['executive_story'] = story_res.get('narrative')
        data['evaluation'] = story_res.get('evaluation')
        data['charts'] = story_res.get('charts')
        data['forecast'] = story_res.get('forecast')
        data['visual_dashboard'] = visual_dashboard_res
        data['relational_story'] = relational_res
        data['story_meta'] = {
            'model': story_res.get('model_used'),
            'cached': story_res.get('cached', False),
            'sheet_id': story_res.get('sheet_id')
        }
        return data
    finally:
        conn.close()


@router.post('/overview/refresh-story')
def refresh_analytics_story(sheet_id: int | None = Query(None), model: str | None = Query(None)):
    clean_sheet_id = int(sheet_id) if sheet_id is not None and not hasattr(sheet_id, 'default') else None
    clean_model = str(model) if model is not None and not hasattr(model, 'default') else None
    conn = get_connection()
    try:
        story_res = get_or_generate_executive_story(sheet_id=clean_sheet_id, force_refresh=True, model=clean_model)
        relational_res = compute_relational_story(conn, model=clean_model)
        visual_dashboard_res = build_workspace_visual_dashboard(conn, sheet_id=clean_sheet_id, model=clean_model)
        return {
            'status': 'success',
            'executive_story': story_res.get('narrative'),
            'evaluation': story_res.get('evaluation'),
            'charts': story_res.get('charts'),
            'forecast': story_res.get('forecast'),
            'visual_dashboard': visual_dashboard_res,
            'relational_story': relational_res,
            'story_meta': {
                'model': story_res.get('model_used'),
                'cached': False,
                'sheet_id': story_res.get('sheet_id')
            }
        }
    finally:
        conn.close()



