from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.services.auth import enforce_csrf, resolve_actor, serializer


def _request(method: str, *, csrf_cookie: str = "", csrf_header: str = "") -> MagicMock:
    req = MagicMock()
    req.method = method
    req.cookies = {"ms_csrf": csrf_cookie}
    req.headers = {"x-csrf-token": csrf_header}
    req.client = MagicMock()
    req.client.host = "127.0.0.1"
    return req


def test_enforce_csrf_rejects_missing_header():
    req = _request("POST", csrf_cookie="abc")
    with pytest.raises(HTTPException) as exc:
        enforce_csrf(req)
    assert exc.value.status_code == 403


def test_enforce_csrf_accepts_matching_token():
    req = _request("POST", csrf_cookie="abc", csrf_header="abc")
    enforce_csrf(req)


def test_resolve_actor_reads_session_account():
    token = serializer.dumps({"ok": True, "account": "alice", "expires_at": 9999999999.0})
    req = _request("POST")
    req.cookies = {"ms_token": token}
    assert resolve_actor(req) == "alice"
