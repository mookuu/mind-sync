import sqlite3
from pathlib import Path

import pytest

from app.models import Source
from app.services.indexer import clear_source_index, index_single_source, index_single_source_force, upsert_document


@pytest.fixture
def mem_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id TEXT NOT NULL,
            rel_path TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            lang TEXT NOT NULL,
            mtime REAL NOT NULL,
            size INTEGER NOT NULL DEFAULT 0,
            sha1 TEXT NOT NULL,
            updated_at REAL NOT NULL,
            UNIQUE(source_id, rel_path)
        );
        CREATE VIRTUAL TABLE documents_fts USING fts5(title, content, rel_path, source_id);
        """
    )
    yield conn
    conn.close()


def test_clear_source_index_removes_rows(mem_conn):
    upsert_document(mem_conn, "wiki", "a.md", "hello", 1.0, 5, "abc", "markdown")
    assert mem_conn.execute("SELECT COUNT(1) FROM documents").fetchone()[0] == 1
    removed = clear_source_index(mem_conn, "wiki")
    assert removed == 1
    assert mem_conn.execute("SELECT COUNT(1) FROM documents").fetchone()[0] == 0
    assert mem_conn.execute("SELECT COUNT(1) FROM documents_fts").fetchone()[0] == 0


def test_index_single_source_force_reindexes_without_skip(mem_conn, tmp_path: Path):
    root = tmp_path / "notes"
    root.mkdir()
    f = root / "note.md"
    f.write_text("version-1", encoding="utf-8")

    source = Source(
        id="notes",
        source_type="local",
        path=str(root),
        url=None,
        include=["**/*.md"],
    )

    stat1 = index_single_source(mem_conn, source)
    assert stat1["indexed"] == 1
    assert stat1["skipped"] == 0

    stat2 = index_single_source(mem_conn, source)
    assert stat2["indexed"] == 0
    assert stat2["skipped"] == 1

    f.write_text("version-2", encoding="utf-8")
    stat3 = index_single_source_force(mem_conn, source)
    assert stat3["indexed"] == 1
    row = mem_conn.execute("SELECT content FROM documents WHERE source_id = ?", ("notes",)).fetchone()
    assert row["content"] == "version-2"
