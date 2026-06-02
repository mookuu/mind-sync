"""Test helpers for session cookie auth."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from itsdangerous import URLSafeSerializer


def patch_session_serializer(monkeypatch: pytest.MonkeyPatch, secret_key: str) -> None:
    import app.main as main_module
    from app.services import auth

    ser = URLSafeSerializer(secret_key, salt="mind-sync")
    monkeypatch.setattr(auth, "serializer", ser)
    monkeypatch.setattr(main_module, "serializer", ser)


def attach_session_cookies(client: TestClient, login_response) -> None:
    token = login_response.cookies.get("ms_token")
    csrf = login_response.cookies.get("ms_csrf")
    if token:
        parts = [f"ms_token={token}"]
        if csrf:
            parts.append(f"ms_csrf={csrf}")
        client.headers.update({"Cookie": "; ".join(parts)})
