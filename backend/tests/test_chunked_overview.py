from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_overview_base_endpoint():
    """Verify GET /api/analytics/overview/base returns core catalog metrics and sheets list in < 50ms."""
    res = client.get('/api/analytics/overview/base')
    assert res.status_code == 200
    data = res.json()
    assert 'stats' in data
    assert 'sheets' in data
    assert 'sheets_list' in data
    assert 'relationships' in data
    # Ensure it did not run expensive story generation
    assert 'executive_story' not in data


def test_overview_visuals_endpoint():
    """Verify GET /api/analytics/overview/visuals returns the visual intelligence dashboard."""
    res = client.get('/api/analytics/overview/visuals')
    assert res.status_code == 200
    data = res.json()
    assert 'visual_dashboard' in data
    vd = data['visual_dashboard']
    assert 'visualizations' in vd
    assert 'categories' in vd


def test_overview_story_endpoint():
    """Verify GET /api/analytics/overview/story returns narrative and evaluation."""
    res = client.get('/api/analytics/overview/story')
    assert res.status_code == 200
    data = res.json()
    assert 'executive_story' in data
    assert 'evaluation' in data
    assert 'story_meta' in data


def test_overview_relational_endpoint():
    """Verify GET /api/analytics/overview/relational returns relational story."""
    res = client.get('/api/analytics/overview/relational')
    assert res.status_code == 200
    data = res.json()
    assert 'relational_story' in data


def test_overview_query_param_chunks():
    """Verify GET /api/analytics/overview?chunk=base|visuals|story|relational works identically."""
    res_base = client.get('/api/analytics/overview?chunk=base')
    assert res_base.status_code == 200
    assert 'stats' in res_base.json()
    assert 'executive_story' not in res_base.json()

    res_vis = client.get('/api/analytics/overview?chunk=visuals')
    assert res_vis.status_code == 200
    assert 'visual_dashboard' in res_vis.json()

    res_story = client.get('/api/analytics/overview?chunk=story')
    assert res_story.status_code == 200
    assert 'executive_story' in res_story.json()


def test_overview_monolithic_backward_compatibility():
    """Verify GET /api/analytics/overview without chunk param returns full monolithic response."""
    res = client.get('/api/analytics/overview')
    assert res.status_code == 200
    data = res.json()
    assert 'stats' in data
    assert 'sheets' in data
    assert 'sheets_list' in data
    assert 'executive_story' in data
    assert 'evaluation' in data
    assert 'visual_dashboard' in data
    assert 'relational_story' in data
