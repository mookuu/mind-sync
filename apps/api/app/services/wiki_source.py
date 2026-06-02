"""Wiki source resolution and protected system pages."""

from __future__ import annotations

from fastapi import HTTPException

from ..db import WIKI_DIR
from ..models import Source
from .indexer import load_sources

WIKI_PROTECTED_RELPATHS = frozenset({"index.md", "log.md", "SCHEMA.md"})


def fallback_wiki_source() -> Source:
    return Source(
        id="wiki",
        source_type="local",
        path=str(WIKI_DIR),
        url=None,
        include=["**/*.md"],
    )


def get_wiki_source() -> Source | None:
    for source in load_sources():
        if source.id == "wiki":
            return source
    return None


def get_wiki_source_or_fallback() -> Source:
    return get_wiki_source() or fallback_wiki_source()


def assert_wiki_writable(rel: str) -> None:
    norm = (rel or "").strip().replace("\\", "/")
    if norm in WIKI_PROTECTED_RELPATHS:
        raise HTTPException(
            status_code=403,
            detail=f"system wiki page '{norm}' is auto-maintained and cannot be edited via API",
        )
