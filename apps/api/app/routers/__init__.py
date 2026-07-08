"""Shared dependencies for all routers."""
from ..db import get_db as _get_db
from ..services.auth import (
    csrf_header_key, enforce_csrf, require_admin, require_any_auth,
    require_auth, resolve_actor, resolve_current_user, resolve_role,
    session_account,
)
from ..services.permissions import can_write

def get_db():
    return _get_db()

__all__ = [
    "get_db", "require_admin", "require_any_auth", "require_auth",
    "resolve_current_user", "resolve_actor", "resolve_role",
    "csrf_header_key", "enforce_csrf", "can_write", "session_account",
]
