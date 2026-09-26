import io
from fastapi.testclient import TestClient
from app.main import app
from app.db.database import get_connection

client = TestClient(app)

SAMPLE_CSV = b"""Employee ID,Employee Name,Department,Attendance Rate,Performance Score
EMP001,John Doe,Engineering,95.0,88.5
EMP002,Jane Smith,Marketing,92.0,84.0
EMP003,Bob Wilson,Engineering,89.5,78.0
"""


def test_delete_pipeline_cleans_up_narratives_and_overview():
    """Verify that deleting a dataset purges sheet narratives, global narratives, and leaves no residual references."""
    # 1. Upload a dataset
    files = {'file': ('test_delete_pipeline.csv', io.BytesIO(SAMPLE_CSV), 'text/csv')}
    upload_res = client.post('/api/upload/file', files=files)
    assert upload_res.status_code == 200
    dataset_id = upload_res.json()['dataset_id']

    # 2. Trigger story generation so it gets cached
    story_res = client.get('/api/analytics/overview/story')
    assert story_res.status_code == 200
    assert story_res.json().get('executive_story') is not None

    conn = get_connection()
    try:
        narrative_count = conn.execute('SELECT COUNT(*) FROM executive_narratives').fetchone()[0]
        assert narrative_count > 0, "Executive narrative should have been cached"
    finally:
        conn.close()

    # 3. Delete the dataset via DELETE /api/upload/datasets/{dataset_id}
    del_res = client.delete(f'/api/upload/datasets/{dataset_id}')
    assert del_res.status_code == 200

    # 4. Verify database is completely clean
    conn = get_connection()
    try:
        assert conn.execute('SELECT COUNT(*) FROM dataset_uploads WHERE id=?', (dataset_id,)).fetchone()[0] == 0
        assert conn.execute('SELECT COUNT(*) FROM sheets WHERE dataset_id=?', (dataset_id,)).fetchone()[0] == 0
        assert conn.execute('SELECT COUNT(*) FROM executive_narratives').fetchone()[0] == 0
    finally:
        conn.close()

    # 5. Verify overview endpoints return empty state without residual references
    story_after = client.get('/api/analytics/overview/story')
    assert story_after.status_code == 200
    assert story_after.json().get('executive_story') is None

    overview_after = client.get('/api/analytics/overview')
    assert overview_after.status_code == 200
    assert overview_after.json()['stats']['datasets'] == 0
    assert overview_after.json()['stats']['sheets'] == 0
    assert overview_after.json().get('executive_story') is None
    assert len(overview_after.json()['visual_dashboard']['visualizations']) == 0


def test_bulk_delete_all_datasets():
    """Verify DELETE /api/upload/datasets wipes everything."""
    files = {'file': ('test_bulk_delete.csv', io.BytesIO(SAMPLE_CSV), 'text/csv')}
    upload_res = client.post('/api/upload/file', files=files)
    assert upload_res.status_code == 200

    del_res = client.delete('/api/upload/datasets')
    assert del_res.status_code == 200

    conn = get_connection()
    try:
        assert conn.execute('SELECT COUNT(*) FROM dataset_uploads').fetchone()[0] == 0
        assert conn.execute('SELECT COUNT(*) FROM sheets').fetchone()[0] == 0
        assert conn.execute('SELECT COUNT(*) FROM executive_narratives').fetchone()[0] == 0
    finally:
        conn.close()


def test_selective_bulk_delete():
    """Verify selective bulk deletion of a subset of datasets."""
    # Upload dataset 1
    f1 = {'file': ('batch_ds_1.csv', io.BytesIO(SAMPLE_CSV), 'text/csv')}
    res1 = client.post('/api/upload/file', files=f1)
    assert res1.status_code == 200
    id1 = res1.json()['dataset_id']

    # Upload dataset 2
    f2 = {'file': ('batch_ds_2.csv', io.BytesIO(SAMPLE_CSV), 'text/csv')}
    res2 = client.post('/api/upload/file', files=f2)
    assert res2.status_code == 200
    id2 = res2.json()['dataset_id']

    # Upload dataset 3
    f3 = {'file': ('batch_ds_3.csv', io.BytesIO(SAMPLE_CSV), 'text/csv')}
    res3 = client.post('/api/upload/file', files=f3)
    assert res3.status_code == 200
    id3 = res3.json()['dataset_id']

    # Bulk delete id1 and id2 via POST
    del_res = client.post('/api/upload/datasets/bulk-delete', json={'dataset_ids': [id1, id2]})
    assert del_res.status_code == 200
    assert del_res.json()['deleted_count'] == 2

    conn = get_connection()
    try:
        assert conn.execute('SELECT COUNT(*) FROM dataset_uploads WHERE id IN (?, ?)', (id1, id2)).fetchone()[0] == 0
        # dataset 3 remains
        assert conn.execute('SELECT COUNT(*) FROM dataset_uploads WHERE id=?', (id3,)).fetchone()[0] == 1
    finally:
        conn.close()

    # Bulk delete id3 via DELETE query param
    del_q_res = client.delete(f'/api/upload/datasets?ids={id3}')
    assert del_q_res.status_code == 200
    assert del_q_res.json()['deleted_count'] == 1

    conn = get_connection()
    try:
        assert conn.execute('SELECT COUNT(*) FROM dataset_uploads WHERE id=?', (id3,)).fetchone()[0] == 0
    finally:
        conn.close()

