from pathlib import Path

from app.models import Source
from app.services import source_health


def test_collect_source_warnings_missing_path(monkeypatch, tmp_path):
    missing = tmp_path / "missing-root"
    monkeypatch.setattr(
        source_health,
        "load_sources",
        lambda: [Source(id="demo", source_type="local", path=str(missing), url=None, include=["**/*.md"])],
    )
    monkeypatch.setattr(source_health, "resolve_source_root", lambda source: Path(source.path or ""))
    warnings = source_health.collect_source_warnings()
    assert any("missing" in w for w in warnings)
    assert source_health.source_health_status(warnings) == "degraded"


def test_source_health_status_ok_when_no_warnings():
    assert source_health.source_health_status([]) == "ok"
