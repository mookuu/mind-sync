"""Server-side session store backed by SQLite."""

import secrets
import time

from ..config import settings
from ..db import get_db

SESSION_ID_BYTES = 32


def _now() -> float:
    return time.time()


def create_session(
    username: str,
    role: str,
    ip: str = "",
    user_agent: str = "",
    remember_me: bool = False,
) -> str:
    session_id = secrets.token_hex(SESSION_ID_BYTES)
    now = _now()
    ttl = settings.session_ttl_seconds
    # Remember me: longer TTL (30d), short session default (1h if < 24h)
    if remember_me:
        ttl = max(ttl, 60 * 60 * 24 * 30)
    else:
        ttl = min(ttl, 60 * 60 * 24)  # Short session max 24h
    expires_at = now + ttl

    conn = get_db()
    try:
        conn.execute(
            """INSERT INTO sessions(session_id, username, role, ip, user_agent,
               created_at, last_active_at, expires_at, remember_me)
               VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (session_id, username, role, ip, user_agent, now, now, expires_at, 1 if remember_me else 0),
        )
        conn.commit()
    finally:
        conn.close()
    return session_id


def get_session(session_id: str) -> dict | None:
    now = _now()
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        if not row:
            return None
        sess = dict(row)
        # Check absolute expiry
        if sess["expires_at"] <= now:
            _delete_session(conn, session_id)
            return None
        # Check idle timeout (skip for remember_me sessions)
        if sess.get("remember_me", 0) != 1:
            idle_max = settings.session_idle_timeout_seconds
            if idle_max > 0 and (now - sess["last_active_at"]) > idle_max:
                _delete_session(conn, session_id)
                return None
        # Update last active
        conn.execute(
            "UPDATE sessions SET last_active_at = ? WHERE session_id = ?",
            (now, session_id),
        )
        conn.commit()
        return sess
    finally:
        conn.close()


def touch_session(session_id: str) -> None:
    """Update last_active_at without full session validation."""
    conn = get_db()
    try:
        conn.execute(
            "UPDATE sessions SET last_active_at = ? WHERE session_id = ?",
            (_now(), session_id),
        )
        conn.commit()
    finally:
        conn.close()


def delete_session(session_id: str) -> None:
    conn = get_db()
    try:
        _delete_session(conn, session_id)
        conn.commit()
    finally:
        conn.close()


def _delete_session(conn, session_id: str) -> None:
    conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))


def list_sessions(username: str) -> list[dict]:
    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT session_id, username, role, ip, user_agent,
               created_at, last_active_at, expires_at, remember_me
               FROM sessions WHERE username = ?
               ORDER BY last_active_at DESC""",
            (username,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def delete_other_sessions(username: str, exclude_sid: str) -> None:
    conn = get_db()
    try:
        conn.execute(
            "DELETE FROM sessions WHERE username = ? AND session_id != ?",
            (username, exclude_sid),
        )
        conn.commit()
    finally:
        conn.close()


def cleanup_expired_sessions() -> int:
    now = _now()
    conn = get_db()
    try:
        result = conn.execute(
            "DELETE FROM sessions WHERE expires_at <= ?", (now,)
        )
        conn.commit()
        return result.rowcount
    finally:
        conn.close()
