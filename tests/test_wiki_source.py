"""Tests for wiki source helper and protected paths."""

from pathlib import Path

import pytest
from fastapi import HTTPException

from app.models import Source
from app.services.wiki_source import (
    assert_wiki_writable,
    fallback_wiki_source,
    get_wiki_source_or_fallback,
)


def test_fallback_wiki_source_has_url_none(wiki_dir: Path):
    src = fallback_wiki_source()
    assert src.url is None
    assert src.id == "wiki"


def test_assert_wiki_writable_blocks_system_pages():
    with pytest.raises(HTTPException) as exc:
        assert_wiki_writable("index.md")
    assert exc.value.status_code == 403


def test_assert_wiki_writable_allows_summary():
    assert_wiki_writable("summaries/demo/page.md") is None


def test_get_wiki_source_or_fallback_without_yaml(wiki_dir: Path, monkeypatch):
    monkeypatch.setattr("app.services.wiki_source.load_sources", lambda: [])
    src = get_wiki_source_or_fallback()
    assert src.id == "wiki"
    assert src.url is None
