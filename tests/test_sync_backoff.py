"""Tests for per-source sync failure backoff."""

import json
import time

from app.services.sync_backoff import (
    list_backoff_status,
    record_sync_failure,
    record_sync_success,
    should_skip_source,
)


def test_backoff_skip_and_clear(test_data_dir, monkeypatch):
    monkeypatch.setattr("app.config.settings.sync_backoff_enabled", True)
    monkeypatch.setattr("app.config.settings.sync_backoff_base_seconds", 300.0)
    monkeypatch.setattr("app.config.settings.sync_backoff_max_seconds", 3600.0)

    record_sync_failure("web-demo", "HTTP 503")
    skip, reason = should_skip_source("web-demo")
    assert skip is True
    assert reason and "backoff" in reason

    status = list_backoff_status()
    assert len(status) == 1
    assert status[0]["source_id"] == "web-demo"
    assert status[0]["in_backoff"] is True

    record_sync_success("web-demo")
    skip2, _ = should_skip_source("web-demo")
    assert skip2 is False
    assert list_backoff_status() == []


def test_expired_backoff_allows_retry(test_data_dir, monkeypatch):
    monkeypatch.setattr("app.config.settings.sync_backoff_enabled", True)
    record_sync_failure("gh-src", "timeout")
    from app.db import get_db

    conn = get_db()
    row = conn.execute("SELECT value FROM app_settings WHERE key = ?", ("source_sync_backoff",)).fetchone()
    state = json.loads(row["value"])
    state["gh-src"]["next_retry_at"] = time.time() - 1
    conn.execute(
        "UPDATE app_settings SET value = ? WHERE key = ?",
        (json.dumps(state), "source_sync_backoff"),
    )
    conn.commit()
    conn.close()

    skip, _ = should_skip_source("gh-src")
    assert skip is False
