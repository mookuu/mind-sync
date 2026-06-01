import os
from pathlib import Path

import pytest

# Must run before test modules import app.* (default DATA_DIR=/data is not writable in CI).
os.environ.setdefault("DATA_DIR", str((Path.cwd() / ".pytest-data").resolve()))


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / "mind_sync.db"
    monkeypatch.setattr("app.db.DATA_DIR", data_dir)
    monkeypatch.setattr("app.db.DB_PATH", db_path)
    monkeypatch.setattr("app.db.WIKI_DIR", data_dir / "wiki")
    monkeypatch.setattr("app.db.LINT_DIR", data_dir / "lint-reports")
    monkeypatch.setattr("app.config.settings.data_dir", str(data_dir))
    from app.db import init_db

    init_db()
    return db_path
