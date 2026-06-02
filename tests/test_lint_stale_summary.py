import sqlite3
import time
from pathlib import Path

from app.services.lint_engine import check_stale_summaries


def test_stale_summary_detected(wiki_dir: Path):
    summary = wiki_dir / "summaries" / "harness" / "demo.md"
    summary.parent.mkdir(parents=True, exist_ok=True)
    summary.write_text(
        "---\ntype: summary\nupdated: 2020-01-01\nsources:\n  - notes/intro.md\n---\n\n# Demo\n",
        encoding="utf-8",
    )
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE documents (source_id TEXT, rel_path TEXT, mtime REAL)"
    )
    conn.execute(
        "INSERT INTO documents VALUES (?, ?, ?)",
        ("notes", "intro.md", time.time()),
    )
    issues = check_stale_summaries(wiki_dir, conn)
    conn.close()
    assert any(i["type"] == "stale-summary" for i in issues)
