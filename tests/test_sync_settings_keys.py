"""Tests for custom sync selection with duplicate source ids."""

from app.models import Source
from app.services.sync_settings import read_sync_settings, resolve_sync_source_ids


def _src(id_: str, stype: str, order: int) -> Source:
    return Source(
        id=id_,
        source_type=stype,
        path=f"/sources/{id_}",
        url="https://github.com/x/y.git" if stype == "github" else None,
        include=["**/*.md"],
        order=order,
    )


def test_custom_preset_local_only(monkeypatch):
    sources = [
        _src("PythonBasic", "local", 40),
        _src("PythonBasic", "github", 45),
        _src("wiki", "local", 100),
    ]
    monkeypatch.setattr("app.services.sync_settings.load_sources", lambda: sources)

    settings = {
        "sync_preset": "custom",
        "sync_source_ids": '["PythonBasic:local"]',
    }
    meta = read_sync_settings(settings)
    assert meta["sync_selected_keys"] == ["PythonBasic:local"]
    assert meta["sync_selected_source_ids"] == ["PythonBasic (local)"]

    resolved = resolve_sync_source_ids(settings)
    assert resolved == ["PythonBasic:local"]
