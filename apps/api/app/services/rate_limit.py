import time

from fastapi import HTTPException, Request

from ..config import settings
from ..db import get_db
from .audit import cleanup_auth_meta
from .auth import client_ip, is_api_key_valid


def rate_limit_identity(request: Request) -> str:
    if is_api_key_valid(request):
        key = request.headers.get("x-api-key", "").strip()
        if not key:
            auth = request.headers.get("authorization", "").strip()
            if auth.lower().startswith("bearer "):
                key = auth[7:].strip()
        return f"key:{key[:24]}"
    return f"ip:{client_ip(request)}"


def check_api_rate_limit(request: Request, bucket: str) -> None:
    window = max(30, int(settings.api_rate_limit_window_seconds))
    limits = {
        "query": max(1, int(settings.api_rate_limit_query_max)),
        "sync": max(1, int(settings.api_rate_limit_sync_max)),
        "lint": max(1, int(settings.api_rate_limit_lint_max)),
    }
    limit = limits.get(bucket, 60)
    identity = rate_limit_identity(request)
    now = time.time()
    conn = get_db()
    try:
        cleanup_auth_meta(conn)
        cutoff = now - window
        row = conn.execute(
            "SELECT COUNT(1) AS c, MIN(created_at) AS first_at "
            "FROM api_usage WHERE identity = ? AND bucket = ? AND created_at >= ?",
            (identity, bucket, cutoff),
        ).fetchone()
        if row and int(row["c"] or 0) >= limit:
            retry_after = max(1, int(window - (now - float(row["first_at"]))))
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded for {bucket}, retry in {retry_after}s",
                headers={"Retry-After": str(retry_after)},
            )
        conn.execute(
            "INSERT INTO api_usage(identity, bucket, created_at) VALUES(?, ?, ?)",
            (identity, bucket, now),
        )
        conn.commit()
    finally:
        conn.close()
