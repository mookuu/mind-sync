"""Tests for wiki path validation."""

from pathlib import Path

import pytest
from fastapi import HTTPException

from app.services.wiki_util import safe_wiki_path


def test_safe_wiki_path_existing_file(wiki_dir: Path):
    target = wiki_dir / "summaries" / "a.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("# a", encoding="utf-8")

    resolved = safe_wiki_path("summaries/a.md", wiki_dir)
    assert resolved == target.resolve()


def test_safe_wiki_path_missing_file_raises_404(wiki_dir: Path):
    with pytest.raises(HTTPException) as exc:
        safe_wiki_path("summaries/missing.md", wiki_dir)
    assert exc.value.status_code == 404


def test_safe_wiki_path_must_exist_false_allows_missing(wiki_dir: Path):
    resolved = safe_wiki_path("summaries/new.md", wiki_dir, must_exist=False)
    assert resolved == (wiki_dir / "summaries" / "new.md").resolve()
    assert not resolved.exists()


def test_safe_wiki_path_rejects_traversal(wiki_dir: Path):
    with pytest.raises(HTTPException) as exc:
        safe_wiki_path("../etc/passwd.md", wiki_dir)
    assert exc.value.status_code == 400


def test_safe_wiki_path_requires_md_extension(wiki_dir: Path):
    with pytest.raises(HTTPException) as exc:
        safe_wiki_path("notes/readme.txt", wiki_dir, must_exist=False)
    assert exc.value.status_code == 400
