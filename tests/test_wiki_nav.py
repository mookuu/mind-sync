import sqlite3
from pathlib import Path

from app.services.wiki_nav import append_wiki_log, rebuild_wiki_index, touch_wiki_nav


def test_append_wiki_log_and_rebuild_index(wiki_dir: Path):
    summaries = wiki_dir / "summaries" / "harness"
    summaries.mkdir(parents=True, exist_ok=True)
    (summaries / "demo.md").write_text(
        "---\ntype: summary\ntopic: harness\nupdated: 2026-06-01\n---\n\n# Demo\n\nPipeline stage notes.\n",
        encoding="utf-8",
    )
    append_wiki_log("sync", "indexed=1")
    index_text = rebuild_wiki_index().read_text(encoding="utf-8")
    log_text = (wiki_dir / "log.md").read_text(encoding="utf-8")
    assert "Demo" in index_text
    assert "summaries/harness/demo.md" in index_text
    assert "## [" in log_text and "sync" in log_text


def test_touch_wiki_nav(wiki_dir: Path):
    paths = touch_wiki_nav("lint", "issues=0")
    assert Path(paths["log_path"]).exists()
    assert Path(paths["index_path"]).exists()
