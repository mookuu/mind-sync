"""pytest fixtures and configuration for mind-sync.

All tests get an isolated temporary data directory so they never write
to the production data/mind_sync.db.
"""
import os
import tempfile
from pathlib import Path
from typing import Generator

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db import get_db, init_db


@pytest.fixture(autouse=True)
def test_data_dir(monkeypatch: pytest.MonkeyPatch) -> Generator[Path, None, None]:
    """Create a temporary DATA_DIR for each test and reset it afterwards."""
    with tempfile.TemporaryDirectory(prefix="mind_sync_test_") as tmp:
        data_dir = Path(tmp)
        monkeypatch.setattr("app.config.settings.data_dir", str(data_dir))
        monkeypatch.setattr("app.db.DATA_DIR", data_dir)
        monkeypatch.setattr("app.db.DB_PATH", data_dir / "mind_sync.db")
        monkeypatch.setattr("app.db.WIKI_DIR", data_dir / "wiki")
        monkeypatch.setattr("app.db.LINT_DIR", data_dir / "lint-reports")
        # Re-initialize DB with fresh schema
        init_db()
        yield data_dir
        # Cleanup is handled by TemporaryDirectory


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """FastAPI TestClient with default dev API key auth."""
    with TestClient(app) as c:
        c.headers.update({"x-api-key": "mind-sync-dev-key"})
        yield c


@pytest.fixture
def db_conn():
    """Return a raw sqlite3 connection to the test database."""
    conn = get_db()
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture
def wiki_dir(test_data_dir: Path) -> Path:
    """Shortcut to the test wiki directory."""
    return test_data_dir / "wiki"
