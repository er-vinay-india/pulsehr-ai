"""Every test uses an isolated database, never the running application's data."""
import pytest
from app.core import config
from app.db.database import init_db
from app.services import sheet_catalog

@pytest.fixture(autouse=True)
def isolated_workspace(request, tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'DB_PATH', tmp_path / 'db' / 'test.sqlite3')
    monkeypatch.setattr(config, 'UPLOADS_DIR', tmp_path / 'uploads')
    monkeypatch.setattr(config, 'EXPORTS_DIR', tmp_path / 'exports')
    config.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    config.EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(sheet_catalog, 'model_embeddings', lambda texts: [])

    # If marked unit and not marked db, skip disk DB initialization for maximum velocity
    if request.node.get_closest_marker("unit") and not request.node.get_closest_marker("db"):
        return

    init_db()
