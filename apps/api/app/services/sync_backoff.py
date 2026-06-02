"""Per-source exponential backoff after sync failures."""

from __future__ import annotations

import json
import random
import time
from typing import Any

from ..config import settings
from ..db import get_db

_BACKOFF_KEY = "source_sync_backoff"


def _load_state() -> dict[str, dict[str, Any]]:
    if not settings.sync_backoff_enabled:
        return {}
    conn = get_db()
    try:
        row = conn.execute("SELECT value FROM app_settings WHERE key = ?", (_BACKOFF_KEY,)).fetchone()
        if not row:
            return {}
        data = json.loads(row["value"])
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}
    finally:
        conn.close()


def _save_state(state: dict[str, dict[str, Any]]) -> None:
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO app_settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (_BACKOFF_KEY, json.dumps(state, ensure_ascii=False)),
        )
        conn.commit()
    finally:
        conn.close()


def _backoff_delay(fail_count: int) -> float:
    base = max(1.0, float(settings.sync_backoff_base_seconds))
    cap = max(base, float(settings.sync_backoff_max_seconds))
    delay = min(cap, base * (2 ** max(0, fail_count - 1)))
    jitter = random.uniform(0, min(30.0, delay * 0.1))
    return delay + jitter


def should_skip_source(source_id: str) -> tuple[bool, str | None]:
    if not settings.sync_backoff_enabled:
        return False, None
    entry = _load_state().get(source_id)
    if not entry:
        return False, None
    next_retry = float(entry.get("next_retry_at") or 0)
    if next_retry <= 0 or time.time() >= next_retry:
        return False, None
    remaining = int(next_retry - time.time())
    last_error = (entry.get("last_error") or "previous failure")[:120]
    return True, f"backoff {remaining}s remaining after: {last_error}"


def record_sync_success(source_id: str) -> None:
    if not settings.sync_backoff_enabled:
        return
    state = _load_state()
    if source_id in state:
        state.pop(source_id, None)
        _save_state(state)


def record_sync_failure(source_id: str, error: str) -> None:
    if not settings.sync_backoff_enabled:
        return
    state = _load_state()
    entry = state.get(source_id) or {}
    fail_count = int(entry.get("fail_count") or 0) + 1
    delay = _backoff_delay(fail_count)
    state[source_id] = {
        "fail_count": fail_count,
        "next_retry_at": time.time() + delay,
        "last_error": (error or "sync failed")[:500],
        "updated_at": time.time(),
    }
    _save_state(state)


def list_backoff_status() -> list[dict[str, Any]]:
    if not settings.sync_backoff_enabled:
        return []
    now = time.time()
    items: list[dict[str, Any]] = []
    for source_id, entry in sorted(_load_state().items()):
        next_retry = float(entry.get("next_retry_at") or 0)
        items.append(
            {
                "source_id": source_id,
                "fail_count": int(entry.get("fail_count") or 0),
                "next_retry_at": next_retry,
                "seconds_remaining": max(0, int(next_retry - now)) if next_retry > now else 0,
                "in_backoff": next_retry > now,
                "last_error": entry.get("last_error"),
            }
        )
    return items
