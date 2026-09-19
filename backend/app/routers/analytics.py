from fastapi import APIRouter, Query
from ..db.database import get_connection
from ..services.sheet_catalog import overview
from ..services.executive_story import get_or_generate_executive_story, compute_relational_story

router = APIRouter(prefix='/api/analytics', tags=['analytics'])


@router.get('/overview')
def get_analytics_overview(sheet_id: int | None = Query(None)):
    clean_sheet_id = int(sheet_id) if sheet_id is not None and not hasattr(sheet_id, 'default') else None
    data = overview()
    conn = get_connection()
    try:
        story_res = get_or_generate_executive_story(sheet_id=clean_sheet_id, force_refresh=False)
        relational_res = compute_relational_story(conn)
        data['executive_story'] = story_res.get('narrative')
        data['evaluation'] = story_res.get('evaluation')
        data['charts'] = story_res.get('charts')
        data['forecast'] = story_res.get('forecast')
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
        return {
            'status': 'success',
            'executive_story': story_res.get('narrative'),
            'evaluation': story_res.get('evaluation'),
            'charts': story_res.get('charts'),
            'forecast': story_res.get('forecast'),
            'relational_story': relational_res,
            'story_meta': {
                'model': story_res.get('model_used'),
                'cached': False,
                'sheet_id': story_res.get('sheet_id')
            }
        }
    finally:
        conn.close()

