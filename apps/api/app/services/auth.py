"""Auth: server-side sessions via SQLite, API key, CSRF."""

import hashlib
import time

from fastapi import HTTPException, Request
from itsdangerous import BadSignature, URLSafeSerializer

from ..config import settings
from ..db import get_db
from .audit import cleanup_auth_meta
from .password_util import verify_password
from .permissions import AuthUser, Role, can_write
from .session_store import create_session, delete_session, get_session

serializer = URLSafeSerializer(settings.secret_key, salt="mind-sync")


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8", errors="ignore")).hexdigest()


# ── Password / DB user management ──────────────────────────────────


def is_user_locked(account: str) -> bool:
    """Check if account is currently locked due to too many login failures."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT locked_until FROM users WHERE username = ?", (account,)
        ).fetchone()
        if row and row["locked_until"] and row["locked_until"] > time.time():
            return True
        return False
    finally:
        conn.close()


def authenticate(username: str, password: str) -> AuthUser | None:
    """Check DB users first, then env users as fallback."""
    account = (username or "default").strip() or "default"
    supplied = password or ""

    # Check if account is locked
    if is_user_locked(account):
        raise HTTPException(
            status_code=423,
            detail="账户已锁定，请 5 分钟后再试",
        )

    # Check DB users
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT username, password_hash, role, locked_until FROM users WHERE username = ?",
            (account,),
        ).fetchone()
    finally:
        conn.close()

    if row:
        if verify_password(supplied, row["password_hash"]):
            role = Role.ADMIN if row["role"] == "admin" else Role.VIEWER
            return AuthUser(username=row["username"], password=row["password_hash"], role=role)

    # Fallback: env users
    from .permissions import load_auth_users as load_env_users

    for user in load_env_users():
        if user.username == account and verify_password(supplied, user.password):
            return user
    return None


def update_password(username: str, new_password_hash: str) -> bool:
    """Update password in DB. Returns False if user not found."""
    conn = get_db()
    try:
        cur = conn.execute(
            "UPDATE users SET password_hash = ? WHERE username = ?",
            (new_password_hash, username),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


# ── Session management ────────────────────────────────────────────

def login_user(
    username: str,
    password: str,
    request: Request,
    remember_me: bool = False,
) -> tuple[str, str, str]:
    """Authenticate and create a session. Returns (session_id, username, role)."""
    user = authenticate(username, password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    session_id = create_session(
        username=user.username,
        role=user.role.value,
        ip=client_ip(request),
        user_agent=request.headers.get("user-agent", ""),
        remember_me=remember_me,
    )
    return session_id, user.username, user.role.value


def logout_user(session_id: str) -> None:
    if session_id:
        delete_session(session_id)


# ── Request auth helpers ──────────────────────────────────────────

def _get_session_id(request: Request) -> str:
    sid = (request.cookies.get("ms_token") or "").strip()
    # Reject old-format signed tokens (not 64-char hex) — they're from pre-auth-rewrite
    if sid and (len(sid) != 64 or not all(c in "0123456789abcdef" for c in sid)):
        return ""  # treated as no session, caller will 401 with clear message
    return sid


def parse_api_keys() -> set[str]:
    raw = settings.api_key.strip()
    if not raw:
        return set()
    return {item.strip() for item in raw.split(",") if item.strip()}


def is_api_key_valid(request: Request) -> bool:
    expected_set = parse_api_keys()
    if not expected_set:
        return False
    header_key = request.headers.get("x-api-key", "").strip()
    auth_header = request.headers.get("authorization", "").strip()
    bearer_key = ""
    if auth_header.lower().startswith("bearer "):
        bearer_key = auth_header[7:].strip()
    return header_key in expected_set or bearer_key in expected_set


def require_auth(request: Request) -> None:
    if is_api_key_valid(request):
        return
    session_id = _get_session_id(request)
    if not session_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    sess = get_session(session_id)
    if not sess:
        raise HTTPException(status_code=401, detail="Session expired or revoked")


def require_any_auth(request: Request) -> None:
    if is_api_key_valid(request):
        return
    require_auth(request)
    enforce_csrf(request)


def resolve_role(request: Request) -> str:
    if is_api_key_valid(request):
        return Role.ADMIN.value
    session_id = _get_session_id(request)
    if not session_id:
        return Role.VIEWER.value
    sess = get_session(session_id)
    if not sess:
        return Role.VIEWER.value
    return (sess.get("role") or Role.ADMIN.value).strip().lower()


def require_admin(request: Request) -> None:
    require_any_auth(request)
    if not can_write(resolve_role(request)):
        raise HTTPException(status_code=403, detail="Admin permission required")


def resolve_current_user(request: Request) -> tuple[str | None, str | None]:
    """返回 (username, role)。API Key 认证时角色为 admin。"""
    if is_api_key_valid(request):
        return None, "admin"
    session_id = _get_session_id(request)
    if not session_id:
        return None, None
    sess = get_session(session_id)
    if not sess:
        return None, None
    username = sess.get("username")
    role = sess.get("role", "viewer")
    return username, (role or "viewer").strip().lower()


def require_own_source(source_id: str, request: Request) -> None:
    """Check if current user can access/modify a source.

    - admin → any source
    - member → only sources where owner == username or owner is None (shared)
    """
    username, role = resolve_current_user(request)
    if role == "admin":
        return
    if not username:
        raise HTTPException(status_code=401, detail="Not authenticated")
    from .indexer import load_sources

    sources = load_sources()
    for s in sources:
        if s.id == source_id or s.id == source_id.split(":")[0]:
            if s.owner is None or s.owner == username:
                return
            raise HTTPException(status_code=403, detail="无权操作此来源")
    raise HTTPException(status_code=404, detail=f"来源不存在：{source_id}")


def resolve_actor(request: Request) -> str:
    if is_api_key_valid(request):
        key = request.headers.get("x-api-key", "").strip()
        if not key:
            auth = request.headers.get("authorization", "").strip()
            if auth.lower().startswith("bearer "):
                key = auth[7:].strip()
        return f"api-key:{key[:8]}…" if key else "api-key"
    session_id = _get_session_id(request)
    if session_id:
        sess = get_session(session_id)
        if sess:
            return sess.get("username", "cookie-user")
    return "cookie-user"


def session_account(request: Request) -> str:
    session_id = _get_session_id(request)
    if not session_id:
        return ""
    sess = get_session(session_id)
    return sess.get("username", "") if sess else ""


# ── Rate limiting ─────────────────────────────────────────────────

def client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[0].strip() or "unknown"
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def check_login_rate_limit(request: Request, account: str) -> None:
    now = time.time()
    window = max(10, int(settings.login_rate_limit_window_seconds))
    limit = max(1, int(settings.login_rate_limit_max_attempts))
    ip = client_ip(request)
    account_key = account.lower()[:128]
    conn = get_db()
    try:
        cleanup_auth_meta(conn)
        cutoff = now - window
        row = conn.execute(
            "SELECT COUNT(1) AS c, MIN(failed_at) AS first_at "
            "FROM login_failures WHERE ip = ? AND account = ? AND failed_at >= ?",
            (ip, account_key, cutoff),
        ).fetchone()
        conn.commit()
    finally:
        conn.close()
    if row and int(row["c"] or 0) >= limit:
        retry_after = max(1, int(window - (now - float(row["first_at"]))))
        raise HTTPException(
            status_code=429,
            detail=f"Too many login attempts, retry in {retry_after}s",
            headers={"Retry-After": str(retry_after)},
        )


def mark_login_failure(request: Request, account: str) -> None:
    now = time.time()
    conn = get_db()
    try:
        cleanup_auth_meta(conn)
        conn.execute(
            "INSERT INTO login_failures(ip, account, failed_at) VALUES(?, ?, ?)",
            (client_ip(request), account.lower()[:128], now),
        )
        # 检查该账户在窗口内总失败次数，超过阈值则锁定 5 分钟
        window = max(10, int(settings.login_rate_limit_window_seconds))
        limit = max(1, int(settings.login_rate_limit_max_attempts))
        cutoff = now - window
        fail_row = conn.execute(
            "SELECT COUNT(1) AS c FROM login_failures WHERE account = ? AND failed_at > ?",
            (account.lower()[:128], cutoff),
        ).fetchone()
        if fail_row and int(fail_row["c"] or 0) >= limit:
            conn.execute(
                "UPDATE users SET locked_until = ? WHERE username = ?",
                (now + 300, account.lower()[:128]),
            )
        conn.commit()
    finally:
        conn.close()


def clear_login_failures(request: Request, account: str) -> None:
    ip = client_ip(request)
    account_key = account.lower()[:128]
    conn = get_db()
    try:
        conn.execute("DELETE FROM login_failures WHERE ip = ? AND account = ?", (ip, account_key))
        # 清除所有失败记录后，如果该账户失败总数为 0，解锁
        row = conn.execute(
            "SELECT COUNT(1) AS c FROM login_failures WHERE account = ?", (account_key,)
        ).fetchone()
        if row and int(row["c"] or 0) == 0:
            conn.execute(
                "UPDATE users SET locked_until = 0 WHERE username = ?", (account_key,)
            )
        conn.commit()
    finally:
        conn.close()


# ── CSRF ──────────────────────────────────────────────────────────

def csrf_header_key() -> str:
    return (settings.csrf_header_name or "x-csrf-token").strip().lower()


def csrf_cookie_token(request: Request) -> str:
    return request.cookies.get("ms_csrf", "").strip()


def enforce_csrf(request: Request) -> None:
    if request.method.upper() not in {"POST", "PUT", "PATCH", "DELETE"}:
        return
    if is_api_key_valid(request):
        return
    expected = csrf_cookie_token(request)
    provided = request.headers.get(csrf_header_key(), "").strip()
    if not expected or not provided or expected != provided:
        raise HTTPException(status_code=403, detail="CSRF validation failed")


