"""Tests for admin sources reload API."""

from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from app.main import app
from tests.auth_util import attach_session_cookies, patch_session_serializer


def test_admin_can_reload_sources(tmp_path, monkeypatch):
    src = tmp_path / "sources.yaml"
    src.write_text(
        yaml.safe_dump({"sources": [{"id": "demo", "type": "local", "path": str(tmp_path)}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr("app.config.settings.sources_file", str(src))
    monkeypatch.setattr("app.config.settings.auth_password", "admin-pass")
    monkeypatch.setattr("app.config.settings.auth_users", "")
    monkeypatch.setattr("app.config.settings.secret_key", "test-secret-key-long-enough-1234567890123456")
    patch_session_serializer(monkeypatch, "test-secret-key-long-enough-1234567890123456")

    with TestClient(app) as client:
        login = client.post("/api/login", json={"password": "admin-pass"})
        assert login.status_code == 200
        attach_session_cookies(client, login)
        csrf = login.json()["csrf_token"]

        src.write_text(
            yaml.safe_dump({"sources": [{"id": "demo2", "type": "local", "path": str(tmp_path)}]}),
            encoding="utf-8",
        )
        resp = client.post("/api/admin/sources/reload", headers={"x-csrf-token": csrf})
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert any(s["id"] == "demo2" for s in body["sources"])


def test_viewer_cannot_reload_sources(monkeypatch):
    monkeypatch.setattr("app.config.settings.auth_users", "viewer:vpass:viewer")
    secret = "test-secret-key-long-enough-1234567890123456"
    monkeypatch.setattr("app.config.settings.secret_key", secret)
    patch_session_serializer(monkeypatch, secret)
    with TestClient(app) as client:
        login = client.post("/api/login", json={"username": "viewer", "password": "vpass"})
        attach_session_cookies(client, login)
        csrf = login.json()["csrf_token"]
        resp = client.post("/api/admin/sources/reload", headers={"x-csrf-token": csrf})
        assert resp.status_code == 403
