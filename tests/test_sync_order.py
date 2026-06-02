import pytest

from app.models import Source
from app.services.sync_settings import apply_source_order


def _src(source_id: str, order: int | None = None) -> Source:
    return Source(
        id=source_id,
        source_type="local",
        path=f"/sources/{source_id}",
        url=None,
        include=["**/*.md"],
        order=order,
    )


def test_apply_source_order_yaml_order_field():
    sources = [_src("wiki", 100), _src("obsidian", 20), _src("notes", 10)]
    ordered = apply_source_order(sources, {})
    assert [s.id for s in ordered] == ["notes", "obsidian", "wiki"]


def test_apply_source_order_manual_override():
    sources = [_src("wiki", 100), _src("obsidian", 20), _src("notes", 10)]
    settings = {"sync_source_order": '["wiki", "notes", "obsidian"]'}
    ordered = apply_source_order(sources, settings)
    assert [s.id for s in ordered] == ["wiki", "notes", "obsidian"]


def test_apply_source_order_appends_unknown_manual_ids():
    sources = [_src("a", 1), _src("b", 2)]
    settings = {"sync_source_order": '["b"]'}
    ordered = apply_source_order(sources, settings)
    assert [s.id for s in ordered] == ["b", "a"]
