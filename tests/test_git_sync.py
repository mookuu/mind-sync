from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.models import Source
from app.services import git_ops
from app.services.source_sync import sync_github_source


def test_pull_repo_not_git(tmp_path):
    result = git_ops.pull_repo(tmp_path)
    assert result["ok"] is False


def test_sync_github_missing_url(test_db, monkeypatch, tmp_path):
    monkeypatch.setattr("app.services.source_sync.DATA_DIR", tmp_path)
    source = Source(id="x", source_type="github", path=None, url=None, include=["**/*.md"])
    result = sync_github_source(source)
    assert result["ok"] is False


def test_sync_github_calls_clone(monkeypatch, tmp_path):
    monkeypatch.setattr("app.services.source_sync.DATA_DIR", tmp_path)
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
