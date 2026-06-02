from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.models import Source
from app.services import git_ops
from app.services.source_sync import sync_github_source


def test_pull_repo_not_git(tmp_path):
    result = git_ops.pull_repo(tmp_path)
    assert result["ok"] is False


def test_sync_github_missing_url():
    source = Source(id="x", source_type="github", path=None, url=None, include=["**/*.md"])
    result = sync_github_source(source)
    assert result["ok"] is False


def test_sync_github_calls_clone(monkeypatch):
    called = {}

    def fake_ensure_clone(url, dest, **kwargs):
        called["url"] = url
        called["dest"] = dest
        return {"ok": True, "action": "clone"}

    monkeypatch.setattr("app.services.source_sync.ensure_clone", fake_ensure_clone)
    source = Source(
        id="demo",
        source_type="github",
        path=None,
        url="https://github.com/org/repo.git",
        include=["**/*.md"],
        branch="main",
    )
    result = sync_github_source(source)
    assert result["ok"] is True
    assert called["url"] == "https://github.com/org/repo.git"
    assert called["dest"] == Path("/sources/demo")


def test_sync_github_uses_configured_path(monkeypatch):
    called = {}

    def fake_ensure_clone(url, dest, **kwargs):
        called["dest"] = dest
        return {"ok": True, "action": "clone"}

    monkeypatch.setattr("app.services.source_sync.ensure_clone", fake_ensure_clone)
    source = Source(
        id="demo",
        source_type="github",
        path="/sources/example_github",
        url="https://github.com/org/repo.git",
        include=["**/*.md"],
    )
    sync_github_source(source)
    assert called["dest"] == Path("/sources/example_github")
