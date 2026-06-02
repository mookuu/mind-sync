"""Tests for web source sync (meta JSON, size limits)."""

import json
from unittest.mock import MagicMock

import app.config as cfg
from app.models import Source
from app.services.source_sync import sync_web_source


def test_sync_web_writes_valid_meta_json(tmp_path, monkeypatch):
    monkeypatch.setattr(cfg.settings, "web_fetch_respect_robots", False)
    monkeypatch.setattr(cfg.settings, "web_fetch_min_interval_seconds", 0)
    monkeypatch.setattr(cfg.settings, "web_fetch_max_bytes", 1_000_000)

    out = tmp_path / "snap"
    out.mkdir()
    source = Source(
        id="web1",
        source_type="web",
        path=str(out),
        url="https://example.com/doc",
        include=["**/*.md"],
        fetch_confirmed=True,
    )

    class Resp:
        status_code = 200
        encoding = "utf-8"
        headers = {"content-type": "text/html", "etag": 'W/"abc"', "last-modified": "Mon, 01 Jan 2024 00:00:00 GMT"}

        @property
        def text(self):
            return self.content.decode("utf-8")

        content = b"<html><head><title>T</title></head><body><p>Hi</p></body></html>"

    mock_client = MagicMock()
    mock_client.__enter__ = lambda s: mock_client
    mock_client.__exit__ = lambda *a: None
    mock_client.get.return_value = Resp()

    monkeypatch.setattr("app.services.source_sync.validate_web_fetch", lambda *a, **k: None)
    monkeypatch.setattr("app.services.source_sync.httpx.Client", lambda **k: mock_client)
    monkeypatch.setattr(
        "app.services.source_sync.build_web_snapshot_markdown",
        lambda **k: "# snap\n",
    )

    result = sync_web_source(source)
    assert result["ok"] is True
    meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    assert meta["url"] == "https://example.com/doc"
    assert meta["etag"] == 'W/"abc"'
