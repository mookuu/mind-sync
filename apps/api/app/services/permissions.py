"""Role-based access: admin (read/write) vs viewer (read-only)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum

from ..config import settings
from .password_util import verify_password


class Role(str, Enum):
    ADMIN = "admin"
    VIEWER = "viewer"


@dataclass(frozen=True)
class AuthUser:
    username: str
    password: str
    role: Role


def _normalize_role(raw: str) -> Role | None:
    value = (raw or "").strip().lower()
    if value in {"admin", "administrator", "write", "editor"}:
        return Role.ADMIN
    if value in {"viewer", "read", "readonly", "read-only", "guest"}:
        return Role.VIEWER
    return None


def _parse_csv_users(raw: str) -> list[AuthUser]:
    users: list[AuthUser] = []
    for entry in raw.split(","):
        chunk = entry.strip()
        if not chunk:
            continue
        parts = chunk.split(":")
        if len(parts) < 3:
            continue
        username = parts[0].strip()
        role = _normalize_role(parts[-1])
        password = ":".join(parts[1:-1])
        if not username or not password or role is None:
            continue
        users.append(AuthUser(username=username, password=password, role=role))
    return users


def _parse_json_users(raw: str) -> list[AuthUser]:
    data = json.loads(raw)
    items = data if isinstance(data, list) else data.get("users", [])
    users: list[AuthUser] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        username = str(item.get("username") or item.get("user") or "").strip()
        password = str(item.get("password") or item.get("pass") or "")
        role = _normalize_role(str(item.get("role") or ""))
        if not username or not password or role is None:
            continue
        users.append(AuthUser(username=username, password=password, role=role))
    return users


def load_auth_users() -> list[AuthUser]:
    raw = (settings.auth_users or "").strip()
    if raw:
        try:
            if raw.startswith("[") or raw.startswith("{"):
                users = _parse_json_users(raw)
            else:
                users = _parse_csv_users(raw)
        except (json.JSONDecodeError, TypeError, ValueError):
            users = []
        if users:
            return users
    fallback = (settings.auth_password or "").strip()
    if fallback:
        return [AuthUser(username="default", password=fallback, role=Role.ADMIN)]
    return []


def authenticate(username: str, password: str) -> AuthUser | None:
    account = (username or "default").strip() or "default"
    supplied = password or ""
    for user in load_auth_users():
        if user.username != account:
            continue
        if verify_password(supplied, user.password):
            return user
    return None


def can_write(role: str | Role) -> bool:
    if isinstance(role, Role):
        return role == Role.ADMIN
    return (role or "").strip().lower() == Role.ADMIN.value
