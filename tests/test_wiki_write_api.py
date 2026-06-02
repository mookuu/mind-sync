"""API tests for wiki write and protected paths."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.auth_util import attach_session_cookies, patch_session_serializer


@pytest.fixture
def admin_client(monkeypatch):
    monkeypatch.setattr("app.config.settings.auth_password", "test-pass")
    monkeypatch.setattr("app.config.settings.auth_users", "")
    secret = "test-secret-key-long-enough-1234567890123456"
    monkeypatch.setattr("app.config.settings.secret_key", secret)
    patch_session_serializer(monkeypatch, secret)
    with TestClient(app) as c:
        login = c.post("/api/login", json={"password": "test-pass"})
        attach_session_cookies(c, login)
        csrf = login.json()["csrf_token"]
        c.headers.update({"x-csrf-token": csrf})
        yield c


def test_wiki_write_without_wiki_source_in_yaml(admin_client: TestClient, wiki_dir, monkeypatch):
    monkeypatch.setattr("app.main.WIKI_DIR", wiki_dir)
    resp = admin_client.put(
        "/api/wiki-content",
        json={"path": "summaries/test/no-wiki-yaml.md", "content": "# hello"},
    )
    assert resp.status_code == 200, resp.text
    assert (wiki_dir / "summaries/test/no-wiki-yaml.md").is_file()


def test_wiki_write_blocks_system_pages(admin_client: TestClient):
    resp = admin_client.put(
        "/api/wiki-content",
        json={"path": "index.md", "content": "# hacked"},
    )
    assert resp.status_code == 403
