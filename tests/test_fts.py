import sqlite3

import pytest

from app.services.fts import build_fts_match_query, escape_fts_phrase, search_for_query


def test_escape_fts_phrase():
    assert escape_fts_phrase('say "hello"') == 'say ""hello""'


def test_build_fts_match_query_quotes_special():
    q = build_fts_match_query('foo "bar" OR test')
    assert q.startswith('"')
    assert '""' in q or "bar" in q


def test_search_for_query_like_fallback():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE documents (
            id INTEGER PRIMARY KEY,
            source_id TEXT, rel_path TEXT, title TEXT,
            content TEXT, lang TEXT
        );
        CREATE VIRTUAL TABLE documents_fts USING fts5(title, content, rel_path, source_id);
        """
    )
    conn.execute(
        "INSERT INTO documents(id, source_id, rel_path, title, content, lang) VALUES (1, 'wiki', 'a.md', 'a', 'Reflection 范式说明', 'markdown')"
    )
    conn.execute(
        "INSERT INTO documents_fts(rowid, title, content, rel_path, source_id) VALUES (1, 'a', 'Reflection 范式说明', 'a.md', 'wiki')"
    )
    rows = search_for_query(conn, "Reflection", limit=5)
    assert len(rows) >= 1
    assert rows[0]["source_id"] == "wiki"
    conn.close()
