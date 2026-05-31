from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.services.rate_limit import check_api_rate_limit


def _api_request(key: str = "test-key") -> MagicMock:
    req = MagicMock()
    req.headers = {"x-api-key": key}
    req.client = MagicMock()
    req.client.host = "127.0.0.1"
    return req


def test_rate_limit_allows_under_cap(test_db, monkeypatch):
    monkeypatch.setattr("app.config.settings.api_rate_limit_query_max", 3)
    monkeypatch.setattr("app.config.settings.api_rate_limit_window_seconds", 3600)
    req = _api_request()
    check_api_rate_limit(req, "query")
    check_api_rate_limit(req, "query")


def test_rate_limit_blocks_over_cap(test_db, monkeypatch):
    monkeypatch.setattr("app.config.settings.api_rate_limit_query_max", 2)
    monkeypatch.setattr("app.config.settings.api_rate_limit_window_seconds", 3600)
    req = _api_request("another-key")
    check_api_rate_limit(req, "query")
    check_api_rate_limit(req, "query")
    with pytest.raises(HTTPException) as exc:
        check_api_rate_limit(req, "query")
    assert exc.value.status_code == 429
    assert "Retry-After" in (exc.value.headers or {})
