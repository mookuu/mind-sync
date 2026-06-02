"""Integration tests for mind-sync API endpoints.

Uses isolated temporary data directory via test_data_dir (autouse in conftest).
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr("app.config.settings.auth_password", "test-pass")
    monkeypatch.setattr("app.config.settings.auth_users", "")
    monkeypatch.setattr("app.config.settings.api_key", "test-api-key")
    monkeypatch.setattr("app.config.settings.secret_key", "test-secret-key-long-enough-1234567890123456")
    from tests.auth_util import patch_session_serializer

    patch_session_serializer(monkeypatch, "test-secret-key-long-enough-1234567890123456")
    api_key_val = "test-api-key"
    monkeypatch.setattr("app.services.auth.parse_api_keys", lambda: {api_key_val})
    with TestClient(app) as c:
        yield c


def test_health_returns_status(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert "status" in body
    assert "source_warnings" in body
    assert "security_warnings" in body
    assert "vault" in body


def test_search_requires_auth(client):
    """Without any auth header, search should return 401."""
    resp = client.get("/api/search", params={"q": "python"})
    assert resp.status_code == 401


def test_search_with_api_key(client):
    """With valid x-api-key, search should work."""
    resp = client.get("/api/search", params={"q": "test"}, headers={"x-api-key": "test-api-key"})
    assert resp.status_code == 200
    assert "items" in resp.json()


def test_empty_search_returns_empty(client):
    resp = client.get("/api/search", params={"q": ""}, headers={"x-api-key": "test-api-key"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []


def test_classify_suggest(client):
    resp = client.get("/api/classify-suggest", params={"q": "Python decorator"}, headers={"x-api-key": "test-api-key"})
    assert resp.status_code == 200
    body = resp.json()
    # classify returns at minimum "recommended"/"alternatives" or an empty result
    assert isinstance(body, dict)


def test_auth_mode_no_api_key(client):
    """When api_key is empty, /api/auth-mode should report it disabled."""
    import app.config as cfg
    original = cfg.settings.api_key
    cfg.settings.api_key = ""
    try:
        # Login with password since api key is disabled
        resp = client.post("/api/login", json={"password": "test-pass"})
        assert resp.status_code == 200
        from tests.auth_util import attach_session_cookies

        attach_session_cookies(client, resp)
        am = client.get("/api/auth-mode")
        assert am.status_code == 200
        body = am.json()
        assert body.get("api_key_enabled") is False
    finally:
        cfg.settings.api_key = original


def test_login_invalid_password(client):
    resp = client.post("/api/login", json={"password": "wrong"})
    assert resp.status_code == 401
    assert "Invalid username or password" in resp.json().get("detail", "")


def test_categories_endpoint(client):
    resp = client.get("/api/categories", headers={"x-api-key": "test-api-key"})
    assert resp.status_code == 200
    body = resp.json()
    assert "categories" in body or "items" in body or isinstance(body, dict)


def test_sync_status(client):
    resp = client.get("/api/sync-status", headers={"x-api-key": "test-api-key"})
    assert resp.status_code == 200
    body = resp.json()
    assert "running" in body or "status" in body


def test_purpose_endpoint(client):
    resp = client.get("/api/purpose", headers={"x-api-key": "test-api-key"})
    assert resp.status_code == 200
    body = resp.json()
    assert "exists" in body or "content" in body


def test_wiki_content_path_traversal_rejected(client):
    """Verify directory traversal attacks are blocked in wiki endpoint."""
    resp = client.get(
        "/api/wiki-content",
        params={"path": "../../../etc/passwd"},
        headers={"x-api-key": "test-api-key"},
    )
    assert resp.status_code in (400, 404)


def test_wiki_content_backslash_path_traversal(client):
    """Verify backslash-based traversal (Windows) is blocked."""
    resp = client.get(
        "/api/wiki-content",
        params={"path": "..\\..\\etc\\passwd"},
        headers={"x-api-key": "test-api-key"},
    )
    assert resp.status_code in (400, 404)


def test_settings_get(client):
    resp = client.get("/api/settings", headers={"x-api-key": "test-api-key"})
    assert resp.status_code == 200


def test_audit_events(client):
    resp = client.get("/api/audit-events", headers={"x-api-key": "test-api-key"})
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body


def test_rebuild_index_starts(client):
    resp = client.post("/api/rebuild-index", json={"use_saved_defaults": True}, headers={"x-api-key": "test-api-key"})
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("mode") == "rebuild"
    assert "started" in body


@pytest.mark.parametrize("endpoint", [
    "/api/sources",
    "/api/sync-status",
    "/api/library",
    "/api/wiki-graph",
    "/api/vault-status",
])
def test_get_endpoints_require_auth(client, endpoint):
    """Protected GET endpoints should return 401 without credentials (/api/health is public)."""
    resp = client.get(endpoint)
    assert resp.status_code == 401, f"{endpoint} should require auth"
