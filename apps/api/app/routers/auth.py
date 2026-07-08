"""Auth router: login, logout, sessions, API keys."""
from typing import Any
import secrets, time
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from ..config import settings
from ..db import get_db
from ..responses import HealthResponse, AuthModeResponse
from ..services.auth import (
    check_login_rate_limit, clear_login_failures, csrf_header_key,
    enforce_csrf, login_user, logout_user, resolve_actor,
    resolve_current_user, require_admin, require_any_auth,
    _get_session_id,
)
from ..services.session_store import delete_session, list_sessions as list_sessions_for_user
from ..services.audit import add_audit_event

router = APIRouter(tags=["auth"])

@router.get("/api/health", response_model=HealthResponse)
def health():
    from ..services.source_health import source_health_status as _shs, collect_source_warnings
    from ..services.security import collect_security_warnings
    return {
        "status": "ok",
        "source_warnings": collect_source_warnings(),
        "health": _shs(),
        "security": collect_security_warnings(),
    }

@router.get("/api/auth-mode", response_model=AuthModeResponse)
def auth_mode(request: Request, _: Any = Depends(require_any_auth)):
    import secrets as secmod
    role = resolve_current_user(request)[1] or "member"
    from ..services.auth import session_account
    username = session_account(request) or None
    csrf_token = request.cookies.get("ms_csrf", "")
    if not csrf_token:
        csrf_token = secmod.token_urlsafe(24)
    display_name = username
    if username:
        conn = get_db()
        try:
            row = conn.execute("SELECT display_name FROM users WHERE username = ?", (username,)).fetchone()
            if row and row["display_name"]:
                display_name = row["display_name"]
        finally:
            conn.close()
    from ..services.permissions import can_write
    return {
        "cookie_enabled": True,
        "api_key_enabled": bool(parse_api_keys() or get_db().execute("SELECT COUNT(1) FROM api_keys").fetchone()[0]),
        "csrf_header": csrf_header_key(),
        "role": role,
        "can_write": can_write(role),
        "username": username,
        "display_name": display_name,
        "authenticated": True,
        "csrf_token": csrf_token,
    }

@router.post("/api/change-password")
def change_password(payload: dict[str, str], request: Request, _: Any = Depends(require_any_auth)):
    enforce_csrf(request)
    username, _ = resolve_current_user(request)
    if not username:
        raise HTTPException(status_code=401, detail="Not authenticated")
    from ..services.auth import authenticate as _auth, update_password
    user = _auth(username, payload.get("current_password", ""))
    if not user:
        raise HTTPException(status_code=403, detail="当前密码错误")
    new_pw = (payload.get("new_password") or "").strip()
    if len(new_pw) < 4:
        raise HTTPException(status_code=400, detail="密码至少 4 位")
    conn = get_db()
    try:
        from ..services.auth import update_password as _up
        _up(username, new_pw)
        conn.commit()
    finally:
        conn.close()
    add_audit_event("password_reset", request, actor=resolve_actor(request), detail=f"user={username}")
    return {"ok": True}

@router.get("/api/sessions")
def list_sessions(request: Request, _: Any = Depends(require_any_auth)):
    username, _ = resolve_current_user(request)
    if not username:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {"sessions": list_sessions_for_user(username)}

@router.delete("/api/sessions/{session_id}")
def delete_user_session(request: Request, session_id: str, _: Any = Depends(require_any_auth)):
    enforce_csrf(request)
    username, _ = resolve_current_user(request)
    if not username:
        raise HTTPException(status_code=401, detail="Not authenticated")
    sessions = list_sessions_for_user(username)
    sids = [s["session_id"] for s in sessions]
    if session_id not in sids:
        raise HTTPException(status_code=404, detail="Session not found")
    delete_session(session_id)
    return {"ok": True, "deleted": session_id}

@router.get("/api/api-keys")
def list_api_keys(_: Any = Depends(require_admin)):
    conn = get_db()
    try:
        rows = conn.execute("SELECT id, key_value, label, username, created_at, last_used_at FROM api_keys ORDER BY created_at DESC").fetchall()
        from ..services.auth import parse_api_keys
        return {"keys": [dict(r) for r in rows], "env_keys": list(parse_api_keys())}
    finally:
        conn.close()

@router.post("/api/api-keys/rotate")
def rotate_api_key(payload: dict[str, Any], request: Request, _: Any = Depends(require_admin)):
    enforce_csrf(request)
    username, _ = resolve_current_user(request)
    new_key = f"msk-{secrets.token_urlsafe(32)}"
    conn = get_db()
    try:
        conn.execute("INSERT INTO api_keys(key_value, label, username, created_at) VALUES(?, ?, ?, ?)",
                     (new_key, payload.get("label", "default"), username or "", time.time()))
        conn.commit()
    finally:
        conn.close()
    add_audit_event("api_key_rotated", request, actor=resolve_actor(request), detail="new API key generated")
    return {"key": new_key}

@router.delete("/api/api-keys/{key_id}")
def delete_api_key(key_id: int, request: Request, _: Any = Depends(require_admin)):
    enforce_csrf(request)
    conn = get_db()
    try:
        cur = conn.execute("DELETE FROM api_keys WHERE id = ?", (key_id,))
        conn.commit()
        deleted = cur.rowcount > 0
    finally:
        conn.close()
    if not deleted:
        raise HTTPException(status_code=404, detail="API key not found")
    add_audit_event("api_key_deleted", request, actor=resolve_actor(request), detail=f"id={key_id}")
    return {"ok": True, "deleted": key_id}
