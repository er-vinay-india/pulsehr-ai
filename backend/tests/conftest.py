"""Every test uses an isolated database, never the running application's data."""
import pytest
from app.core import config
from app.db.database import init_db
from app.services import sheet_catalog

@pytest.fixture(autouse=True)
def isolated_workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'DB_PATH', tmp_path / 'db' / 'test.sqlite3')
    monkeypatch.setattr(config, 'UPLOADS_DIR', tmp_path / 'uploads')
    monkeypatch.setattr(config, 'EXPORTS_DIR', tmp_path / 'exports')
    config.UPLOADS_DIR.mkdir()
    config.EXPORTS_DIR.mkdir()
    monkeypatch.setattr(sheet_catalog, 'model_embeddings', lambda texts: [])
    init_db()
