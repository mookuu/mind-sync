"""Tests for id:type sync keys (duplicate source ids in yaml)."""

from app.models import Source
from app.services.source_sync_key import (
    expand_sync_keys,
    filter_sources_by_sync_keys,
    source_matches_sync_key,
    source_sync_key,
)


def _src(id_: str, stype: str) -> Source:
    return Source(id=id_, source_type=stype, path=f"/sources/{id_}", url=None, include=["**/*.md"])


def test_source_sync_key_includes_type():
    assert source_sync_key(_src("PythonBasic", "local")) == "PythonBasic:local"
    assert source_sync_key(_src("PythonBasic", "github")) == "PythonBasic:github"


def test_filter_local_only():
    local = _src("PythonBasic", "local")
    gh = _src("PythonBasic", "github")
    sources = [local, gh]
    out = filter_sources_by_sync_keys(sources, ["PythonBasic:local"])
    assert out == [local]


def test_legacy_bare_id_matches_both():
    local = _src("PythonBasic", "local")
    gh = _src("PythonBasic", "github")
    assert source_matches_sync_key(local, "PythonBasic")
    assert source_matches_sync_key(gh, "PythonBasic")


def test_expand_bare_id_to_typed_keys():
    local = _src("PythonBasic", "local")
    gh = _src("PythonBasic", "github")
    expanded = expand_sync_keys(["PythonBasic"], [local, gh])
    assert expanded == ["PythonBasic:local", "PythonBasic:github"]
