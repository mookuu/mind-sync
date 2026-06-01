import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.auth import parse_api_keys


@pytest.fixture
def client(test_db, monkeypatch):
    monkeypatch.setattr("app.config.settings.auth_password", "test-pass")
    monkeypatch.setattr("app.config.settings.api_key", "test-api-key")
    monkeypatch.setattr("app.config.settings.secret_key", "test-secret-key-long-enough")
    with TestClient(app) as c:
        yield c


def test_health_includes_security_and_vault(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert "security_warnings" in body
    assert "vault" in body


def test_search_requires_auth(client):
    resp = client.get("/api/search", params={"q": "python"})
    assert resp.status_code == 401


def test_search_with_api_key(client):
    key = parse_api_keys()[0]
    resp = client.get("/api/search", params={"q": "test"}, headers={"x-api-key": key})
    assert resp.status_code == 200
    assert "items" in resp.json()


def test_classify_suggest(client):
    key = parse_api_keys()[0]
    resp = client.get("/api/classify-suggest", params={"q": "Python 装饰器"}, headers={"x-api-key": key})
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("recommended")
