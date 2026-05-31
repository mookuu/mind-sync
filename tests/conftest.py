import pytest


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / "mind_sync.db"
    monkeypatch.setattr("app.db.DB_PATH", db_path)
    monkeypatch.setattr("app.config.settings.data_dir", str(data_dir))
    from app.db import init_db

    init_db()
    return db_path
