from pathlib import Path

from app.models import Source
from app.services.source_pairing import (
    build_sync_plan,
    github_repo_basename,
    resolve_index_source,
)


def _local(id_: str, path: str) -> Source:
    return Source(id=id_, source_type="local", path=path, url=None, include=["**/*.md"])


def _github(id_: str, path: str, url: str) -> Source:
    return Source(
        id=id_,
        source_type="github",
        path=path,
        url=url,
        include=["**/*.md"],
        branch="main",
    )


def test_github_repo_basename():
    assert github_repo_basename("https://github.com/you/PythonBasic.git") == "PythonBasic"


def test_pair_same_id():
    local = _local("PythonBasic", "/sources/PythonBasic")
    gh = _github("PythonBasic", "/sources/PythonBasic", "https://github.com/you/PythonBasic.git")
    plan = build_sync_plan([local, gh])
    assert len(plan.pairs) == 1
    assert plan.pairs[0].local is local
    assert plan.pairs[0].match_reason == "same_id"
    assert plan.standalone == []
    assert len(plan.skipped_locals) == 1


def test_pair_repo_name(tmp_path: Path):
    local_root = tmp_path / "PythonBasic"
    local_root.mkdir()
    (local_root / "note.md").write_text("hello", encoding="utf-8")
    gh_root = tmp_path / "github_clone"
    local = _local("PythonBasic", str(local_root))
    gh = _github("notes_remote", str(gh_root), "https://github.com/you/PythonBasic.git")
    plan = build_sync_plan([local, gh])
    assert len(plan.pairs) == 1
    assert plan.pairs[0].match_reason == "repo_name"


def test_resolve_index_fallback_to_local(tmp_path: Path):
    root = tmp_path / "PythonBasic"
    root.mkdir()
    (root / "note.md").write_text("hello", encoding="utf-8")
    local = _local("PythonBasic", str(root))
    gh = _github("PythonBasic", str(root), "https://github.com/you/PythonBasic.git")
    pair = build_sync_plan([local, gh]).pairs[0]
    pull = {"ok": False, "error": "network down"}
    index_source, warning, skip = resolve_index_source(pair, pull)
    assert index_source is local
    assert warning and "fallback" in warning
    assert skip is None


def test_resolve_index_github_success():
    local = _local("PythonBasic", "/sources/PythonBasic")
    gh = _github("PythonBasic", "/sources/PythonBasic", "https://github.com/you/PythonBasic.git")
    pair = build_sync_plan([local, gh]).pairs[0]
    index_source, warning, skip = resolve_index_source(pair, {"ok": True})
    assert index_source is gh
    assert warning is None
