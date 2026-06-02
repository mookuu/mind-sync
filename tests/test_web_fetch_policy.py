"""Tests for web fetch compliance policy."""

from urllib.parse import urlparse

import httpx
import pytest

import app.config as cfg
from app.models import Source
from app.services.web_fetch_policy import (
    build_user_agent,
    check_allowlist,
    check_robots,
    reset_web_fetch_state_for_tests,
    validate_web_fetch,
    web_fetch_policy_summary,
)


@pytest.fixture(autouse=True)
def _reset_state():
    reset_web_fetch_state_for_tests()
    yield
    reset_web_fetch_state_for_tests()


def test_build_user_agent_with_contact(monkeypatch):
    monkeypatch.setattr(cfg.settings, "web_fetch_user_agent", "mind-sync/0.2")
    monkeypatch.setattr(cfg.settings, "web_fetch_contact", "ops@example.com")
    assert build_user_agent() == "mind-sync/0.2 (+mailto:ops@example.com)"


def test_check_allowlist_blocks_unknown_host(monkeypatch):
    monkeypatch.setattr(cfg.settings, "web_fetch_allowlist", "example.com")
    monkeypatch.setattr(cfg.settings, "web_fetch_require_allowlist", False)
    assert check_allowlist("https://example.com/page") is None
    assert "not in WEB_FETCH_ALLOWLIST" in (check_allowlist("https://other.com/") or "")


def test_require_opt_in_blocks_unconfirmed(monkeypatch):
    monkeypatch.setattr(cfg.settings, "web_fetch_require_opt_in", True)
    source = Source(
        id="web1",
        source_type="web",
        path="/tmp",
        url="https://example.com",
        include=["**/*.md"],
        fetch_confirmed=False,
    )
    with httpx.Client() as client:
        err = validate_web_fetch(source, source.url, client)
    assert err is not None
    assert "fetch_confirmed" in err


def test_opt_in_allows_confirmed_source(monkeypatch):
    monkeypatch.setattr(cfg.settings, "web_fetch_require_opt_in", True)
    monkeypatch.setattr(cfg.settings, "web_fetch_respect_robots", False)
    monkeypatch.setattr(cfg.settings, "web_fetch_min_interval_seconds", 0)
    source = Source(
        id="web1",
        source_type="web",
        path="/tmp",
        url="https://example.com",
        include=["**/*.md"],
        fetch_confirmed=True,
    )
    with httpx.Client() as client:
        assert validate_web_fetch(source, source.url, client) is None


def test_check_robots_disallows_blocked_path(monkeypatch):
    reset_web_fetch_state_for_tests()
    robots_body = "User-agent: *\nDisallow: /private\n"
    calls: list[str] = []

    class FakeResp:
        status_code = 200
        text = robots_body

    def fake_get(url, timeout=15):
        calls.append(url)
        return FakeResp()

    monkeypatch.setattr(cfg.settings, "web_fetch_user_agent", "mind-sync/0.1")
    with httpx.Client() as client:
        client.get = fake_get  # type: ignore[method-assign]
        assert check_robots("https://example.com/public", "mind-sync/0.1", client) is None
        err = check_robots("https://example.com/private/page", "mind-sync/0.1", client)
        assert err is not None
        assert "robots.txt disallows" in err


def test_web_fetch_disabled(monkeypatch):
    monkeypatch.setattr(cfg.settings, "web_fetch_enabled", False)
    source = Source(
        id="web1",
        source_type="web",
        path="/tmp",
        url="https://example.com",
        include=["**/*.md"],
    )
    with httpx.Client() as client:
        assert validate_web_fetch(source, source.url, client) == "WEB_FETCH_ENABLED=false"


def test_policy_summary_keys():
    summary = web_fetch_policy_summary()
    assert "enabled" in summary
    assert "user_agent" in summary
    assert "allowlist" in summary
