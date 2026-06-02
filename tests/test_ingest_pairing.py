"""Tests for ingest de-duplication with github/local pairing."""

from app.models import Source
from app.services.source_pairing import resolve_ingest_sources


def _src(sid: str, stype: str, path: str) -> Source:
    return Source(
        id=sid,
        source_type=stype,
        path=path,
        url=f"https://github.com/you/{sid}.git" if stype == "github" else None,
        include=["**/*.md"],
    )


def test_ingest_skips_paired_local():
    sources = [
        _src("PythonBasic", "github", "/sources/PythonBasic"),
        _src("PythonBasic", "local", "/sources/PythonBasic"),
        _src("wiki", "local", "/data/wiki"),
    ]
    to_ingest, warnings = resolve_ingest_sources(sources)
    ids = {s.id for s in to_ingest}
    assert "PythonBasic" in ids
    assert sum(1 for s in to_ingest if s.id == "PythonBasic") == 1
    assert "wiki" in ids
    assert any("skipped paired local" in w for w in warnings)


def test_ingest_filter_paired_local_returns_empty():
    sources = [
        _src("PythonBasic", "github", "/sources/PythonBasic"),
        _src("PythonBasic", "local", "/sources/PythonBasic"),
    ]
    to_ingest, _ = resolve_ingest_sources(sources, source_id_filter="PythonBasic")
    assert len(to_ingest) == 1
    assert to_ingest[0].source_type == "github"
