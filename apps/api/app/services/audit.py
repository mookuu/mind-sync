import sqlite3
import time
from typing import Any

from fastapi import Request

from ..config import settings
from ..db import get_db


def cleanup_auth_meta(conn: sqlite3.Connection) -> None:
    now = time.time()
    window = max(10, int(settings.login_rate_limit_window_seconds))
    retain_days = max(1, int(settings.audit_retention_days))
    api_window = max(60, int(settings.api_rate_limit_window_seconds))
    conn.execute("DELETE FROM login_failures WHERE failed_at < ?", (now - window * 5,))
    conn.execute("DELETE FROM audit_events WHERE created_at < ?", (now - retain_days * 86400,))
    conn.execute("DELETE FROM api_usage WHERE created_at < ?", (now - api_window * 2,))


def add_audit_event_meta(event_type: str, actor: str, ip: str, detail: str) -> None:
    conn = get_db()
    try:
        cleanup_auth_meta(conn)
        conn.execute(
            "INSERT INTO audit_events(event_type, actor, ip, detail, created_at) VALUES(?, ?, ?, ?, ?)",
            (event_type, actor[:128], ip[:64], detail[:1000], time.time()),
        )
        conn.commit()
    finally:
        conn.close()


def add_audit_event(event_type: str, request: Request, actor: str, detail: str) -> None:
    from .auth import client_ip

    add_audit_event_meta(event_type, actor, client_ip(request), detail)


def fetch_audit_events(limit: int = 50) -> list[dict[str, Any]]:
    conn = get_db()
    try:
        cleanup_auth_meta(conn)
        cap = max(1, min(int(limit), 200))
        rows = conn.execute(
            "SELECT id, event_type, actor, ip, detail, created_at "
            "FROM audit_events ORDER BY id DESC LIMIT ?",
            (cap,),
        ).fetchall()
        conn.commit()
        return [dict(r) for r in rows]
    finally:
        conn.close()
