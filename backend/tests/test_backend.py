from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_check():
    data = client.get('/api/health').json()
    assert data['status'] == 'online'
    assert data['database']['employees'] == 0
    assert data['database']['sheets'] == 0


def test_empty_overview_has_no_demo_values():
    data = client.get('/api/analytics/overview').json()
    assert data['stats'] == {'datasets': 0, 'sheets': 0, 'rows': 0, 'linked_relationships': 0}
    assert data['sheets'] == []
    assert client.get('/api/employees').json()['total'] == 0
    assert client.get('/api/employees/0').status_code == 404


def test_copilot_suggestions():
    assert len(client.get('/api/copilot/suggestions').json()['suggestions']) >= 3


def test_report_uses_uploaded_sources():
    assert client.post('/api/reports/presentation').status_code == 400
    response = client.post('/api/upload/file', files={'file': ('roster.csv', b'Employee ID,Name,Score\nE1,Ana,4\n', 'text/csv')})
    assert response.status_code == 200
    assert client.post('/api/reports/presentation').status_code == 200
    text = client.get('/api/reports/executive-html').text
    assert 'roster.csv' in text and 'Kaggle' not in text


def test_unrelated_query_no_citation_flood():
    response = client.post('/api/copilot/query', json={'query': 'What is 2 + 2?'})
    assert response.json()['citations'] == []
