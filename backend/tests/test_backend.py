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


def test_dataset_and_sheet_download():
    assert client.get('/api/upload/datasets/999/download').status_code == 404
    assert client.get('/api/sheets/999/download').status_code == 404

    content = b"Employee ID,Name,Department,Salary\nEMP-01,Alice,Engineering,120000\nEMP-02,Bob,Product,110000\n"
    res = client.post('/api/upload/file', files={'file': ('salaries.csv', content, 'text/csv')})
    assert res.status_code == 200
    dataset_id = res.json()['dataset_id']

    dl_ds = client.get(f'/api/upload/datasets/{dataset_id}/download')
    assert dl_ds.status_code == 200
    assert 'attachment;' in dl_ds.headers.get('content-disposition', '')
    assert 'salaries.csv' in dl_ds.headers.get('content-disposition', '')
    assert b'EMP-01,Alice' in dl_ds.content

    sheets = client.get('/api/sheets').json()['sheets']
    sheet_id = sheets[0]['id']

    dl_sheet_csv = client.get(f'/api/sheets/{sheet_id}/download?format=csv')
    assert dl_sheet_csv.status_code == 200
    assert 'text/csv' in dl_sheet_csv.headers.get('content-type', '')
    assert 'attachment;' in dl_sheet_csv.headers.get('content-disposition', '')
    assert b'EMP-01,Alice,Engineering,120000' in dl_sheet_csv.content

    dl_sheet_xlsx = client.get(f'/api/sheets/{sheet_id}/download?format=xlsx')
    assert dl_sheet_xlsx.status_code == 200
    assert 'openxmlformats' in dl_sheet_xlsx.headers.get('content-type', '')
    assert dl_sheet_xlsx.content.startswith(b'PK')


def test_dataset_download_fallback_reconstruction():
    from app.core import config
    content = b"Code,Title,Level\nC1,Staff,5\nC2,Senior,4\n"
    res = client.post('/api/upload/file', files={'file': ('roles.csv', content, 'text/csv')})
    assert res.status_code == 200
    dataset_id = res.json()['dataset_id']

    datasets = client.get('/api/upload/datasets').json()['datasets']
    file_disk = config.UPLOADS_DIR / datasets[0]['filename']
    file_disk.unlink(missing_ok=True)

    dl_fallback = client.get(f'/api/upload/datasets/{dataset_id}/download')
    assert dl_fallback.status_code == 200
    assert 'attachment;' in dl_fallback.headers.get('content-disposition', '')
    assert b'Staff' in dl_fallback.content

