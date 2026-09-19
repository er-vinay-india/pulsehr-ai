from fastapi import APIRouter
from ..services.sheet_catalog import overview

router = APIRouter(prefix='/api/analytics', tags=['analytics'])

@router.get('/overview')
def get_analytics_overview():
    return overview()
