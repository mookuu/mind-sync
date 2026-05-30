import hashlib
import time

from fastapi import HTTPException, Request
from itsdangerous import BadSignature, URLSafeSerializer

from ..config import settings
from ..db import get_db
from .audit import cleanup_auth_meta

serializer = URLSafeSerializer(settings.secret_key, salt="mind-sync")


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8", errors="ignore")).hexdigest()


def cleanup_expired_revocations(conn) -> None:
    conn.execute("DELETE FROM session_revocations WHERE expires_at <= ?", (time.time(),))


def is_token_revoked(conn, token: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM session_revocations WHERE token_hash = ? LIMIT 1",
        (token_hash(token),),
    ).fetchone()
    return bool(row)


def require_auth(request: Request) -> None:
    token = request.cookies.get("ms_token")
    if not token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        payload = serializer.loads(token)
        if payload.get("ok") is not True:
            raise HTTPException(status_code=401, detail="Unauthorized")
        expires_at = float(payload.get("expires_at", 0))
        now = time.time()
        if expires_at <= now:
            raise HTTPException(status_code=401, detail="Session expired")
        conn = get_db()
        try:
            cleanup_expired_revocations(conn)
            if is_token_revoked(conn, token):
                raise HTTPException(status_code=401, detail="Session revoked")
            conn.commit()
        finally:
            conn.close()
    except BadSignature as exc:
        raise HTTPException(status_code=401, detail="Unauthorized") from exc


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
    conn = get_db()
    try:
        cleanup_auth_meta(conn)
        conn.execute(
            "INSERT INTO login_failures(ip, account, failed_at) VALUES(?, ?, ?)",
            (client_ip(request), account.lower()[:128], time.time()),
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
        conn.commit()
    finally:
        conn.close()


def csrf_header_key() -> str:
    return (settings.csrf_header_name or "x-csrf-token").strip().lower()


def csrf_cookie_token(request: Request) -> str:
    return request.cookies.get("ms_csrf", "").strip()


def enforce_csrf(request: Request) -> None:
    if request.method.upper() not in {"POST", "PUT", "PATCH", "DELETE"}:
        return
    expected = csrf_cookie_token(request)
    provided = request.headers.get(csrf_header_key(), "").strip()
    if not expected or not provided or expected != provided:
        raise HTTPException(status_code=403, detail="CSRF validation failed")


def require_any_auth(request: Request) -> None:
    if is_api_key_valid(request):
        return
    require_auth(request)
    enforce_csrf(request)


def revoke_session_token(token: str) -> None:
    try:
        payload = serializer.loads(token)
        expires_at = float(payload.get("expires_at", time.time() + 60))
        conn = get_db()
        try:
            cleanup_expired_revocations(conn)
            conn.execute(
                "INSERT INTO session_revocations(token_hash, expires_at) VALUES(?, ?) "
                "ON CONFLICT(token_hash) DO UPDATE SET expires_at=excluded.expires_at",
                (token_hash(token), expires_at),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass
