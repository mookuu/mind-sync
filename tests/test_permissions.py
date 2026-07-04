"""Tests for role-based permissions (admin vs member)."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.auth_util import attach_session_cookies, patch_session_serializer


@pytest.fixture
def rbac_client(monkeypatch):
    monkeypatch.setattr("app.config.settings.auth_password", "legacy-admin-pass")
    monkeypatch.setattr(
        "app.config.settings.auth_users",
        "admin:adminpass:admin,member:memberpass:member",
    )
    monkeypatch.setattr("app.config.settings.api_key", "test-api-key")
    secret = "test-secret-key-long-enough-1234567890123456"
    monkeypatch.setattr("app.config.settings.secret_key", secret)
    patch_session_serializer(monkeypatch, secret)
    api_key_val = "test-api-key"
    monkeypatch.setattr("app.services.auth.parse_api_keys", lambda: {api_key_val})
    with TestClient(app) as c:
        yield c


def _login(client: TestClient, username: str, password: str) -> str:
    resp = client.post("/api/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    attach_session_cookies(client, resp)
    return resp.json()["csrf_token"]


def test_member_can_search_but_not_write_wiki(rbac_client: TestClient):
    csrf = _login(rbac_client, "member", "memberpass")
    search = rbac_client.get("/api/search", params={"q": "test"})
    assert search.status_code == 200

    auth = rbac_client.get("/api/auth-mode")
    assert auth.status_code == 200
    body = auth.json()
    assert body["role"] == "member"
    assert body["can_write"] is False

    write = rbac_client.put(
        "/api/wiki-content",
        json={"path": "summaries/test.md", "content": "# test"},
        headers={"x-csrf-token": csrf},
    )
    assert write.status_code == 403


def test_admin_can_write_wiki(rbac_client: TestClient):
    csrf = _login(rbac_client, "admin", "adminpass")
    write = rbac_client.put(
        "/api/wiki-content",
        json={"path": "summaries/test-admin.md", "content": "# admin"},
        headers={"x-csrf-token": csrf},
    )
    assert write.status_code == 200
    assert write.json().get("ok") is True


def test_member_cannot_sync(rbac_client: TestClient):
    csrf = _login(rbac_client, "member", "memberpass")
    resp = rbac_client.post("/api/sync", json={}, headers={"x-csrf-token": csrf})
    assert resp.status_code == 403


def test_api_key_remains_admin(rbac_client: TestClient):
    resp = rbac_client.put(
        "/api/wiki-content",
        json={"path": "summaries/api-key.md", "content": "# key"},
        headers={"x-api-key": "test-api-key"},
    )
    assert resp.status_code == 200


def test_legacy_single_password_is_admin(monkeypatch):
    from tests.auth_util import patch_session_serializer

    secret = "test-secret-key-long-enough-1234567890123456"
    monkeypatch.setattr("app.config.settings.auth_password", "test-pass")
    monkeypatch.setattr("app.config.settings.auth_users", "")
    monkeypatch.setattr("app.config.settings.secret_key", secret)
    patch_session_serializer(monkeypatch, secret)
    with TestClient(app) as client:
        resp = client.post("/api/login", json={"password": "test-pass"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "admin"
        assert data["can_write"] is True


def test_bcrypt_user_login(monkeypatch):
    from app.services.password_util import hash_password
    from tests.auth_util import patch_session_serializer

    secret = "test-secret-key-long-enough-1234567890123456"
    hashed = hash_password("bcrypt-pass")
    monkeypatch.setattr("app.config.settings.auth_password", "")
    monkeypatch.setattr("app.config.settings.auth_users", f"bcuser:{hashed}:admin")
    monkeypatch.setattr("app.config.settings.secret_key", secret)
    patch_session_serializer(monkeypatch, secret)
    with TestClient(app) as client:
        ok = client.post("/api/login", json={"username": "bcuser", "password": "bcrypt-pass"})
        assert ok.status_code == 200
        bad = client.post("/api/login", json={"username": "bcuser", "password": "wrong"})
        assert bad.status_code == 401
