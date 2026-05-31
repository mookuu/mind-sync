import re
import sqlite3
from typing import Any

from .categories import category_sql_clause, classify_document, path_prefix_sql_clause, topic_sql_clause
from .indexer import snippet_from_content

_TOKEN_SPLIT = re.compile(r"\s+")


def escape_fts_phrase(text: str) -> str:
    return text.replace('"', '""')


def build_fts_match_query(raw: str) -> str:
    q = (raw or "").strip()
    if not q:
        return ""
    parts: list[str] = [f'"{escape_fts_phrase(q)}"']
    tokens = [t for t in _TOKEN_SPLIT.split(q) if len(t) >= 2]
    if len(tokens) > 1:
        token_expr = " OR ".join(f'"{escape_fts_phrase(t)}"' for t in tokens[:16])
        parts.append(f"({token_expr})")
    return " OR ".join(parts)


def _fts_rows(conn: sqlite3.Connection, fts_query: str, sql_suffix: str, args: tuple[Any, ...]) -> list[sqlite3.Row]:
    if not fts_query:
        return []
    sql = f"""
        SELECT d.id, d.source_id, d.rel_path, d.title, d.content, d.lang,
               snippet(documents_fts, 1, '<mark>', '</mark>', '...', 45) AS snippet
        FROM documents_fts
        JOIN documents d ON d.id = documents_fts.rowid
        WHERE documents_fts MATCH ?
        {sql_suffix}
    """
    try:
        return conn.execute(sql, (fts_query, *args)).fetchall()
    except sqlite3.OperationalError:
        return []


def search_for_query(conn: sqlite3.Connection, question: str, limit: int = 8) -> list[dict[str, Any]]:
    fts_query = build_fts_match_query(question)
    rows = _fts_rows(conn, fts_query, "LIMIT ?", (limit,))
    if rows:
        return [dict(row) for row in rows]
    return _like_fallback(conn, question, limit=limit)


def search_documents(
    conn: sqlite3.Connection,
    q: str,
    *,
    limit: int = 30,
    source_id: str | None = None,
    file_type: str | None = None,
    category: str | None = None,
    topic: str | None = None,
    path_prefix: str | None = None,
) -> list[dict[str, Any]]:
    cat_clause, cat_args = category_sql_clause(category)
    topic_clause, topic_args = topic_sql_clause(topic)
    prefix_clause, prefix_args = path_prefix_sql_clause(path_prefix)
    filter_sql = ""
    filter_args: list[Any] = []
    if source_id:
        filter_sql += " AND d.source_id = ?"
        filter_args.append(source_id)
    if file_type:
        filter_sql += " AND d.lang = ?"
        filter_args.append(file_type)
    filter_sql += cat_clause + topic_clause + prefix_clause
    filter_args.extend(cat_args)
    filter_args.extend(topic_args)
    filter_args.extend(prefix_args)

    fts_query = build_fts_match_query(q)
    fts_rows = _fts_rows(conn, fts_query, filter_sql + " LIMIT ?", tuple(filter_args) + (limit,))

    items: list[dict[str, Any]] = []
    existing_ids: set[int] = set()
    for row in fts_rows:
        item = dict(row)
        item["category"] = classify_document(row["source_id"], row["rel_path"])
        if "snippet" not in item or not item["snippet"]:
            item["snippet"] = snippet_from_content(row["content"], q, window=30)
        items.append(item)
        existing_ids.add(int(row["id"]))

    if len(items) >= limit:
        return items[:limit]

    like_sql = """
        SELECT id, source_id, rel_path, lang, content, title
        FROM documents d
        WHERE (title LIKE ? OR rel_path LIKE ? OR content LIKE ?)
          AND (? IS NULL OR source_id = ?)
          AND (? IS NULL OR lang = ?)
    """
    like_args: list[Any] = [
        f"%{q}%",
        f"%{q}%",
        f"%{q}%",
        source_id,
        source_id,
        file_type,
        file_type,
    ]
    like_sql += cat_clause + topic_clause + prefix_clause
    like_args.extend(cat_args)
    like_args.extend(topic_args)
    like_args.extend(prefix_args)
    like_sql += " LIMIT ?"
    like_args.append(limit * 5)
    like_rows = conn.execute(like_sql, tuple(like_args)).fetchall()
    for row in like_rows:
        row_id = int(row["id"])
        if row_id in existing_ids:
            continue
        items.append(
            {
                "id": row_id,
                "source_id": row["source_id"],
                "rel_path": row["rel_path"],
                "lang": row["lang"],
                "snippet": snippet_from_content(row["content"], q),
                "category": classify_document(row["source_id"], row["rel_path"]),
            }
        )
        existing_ids.add(row_id)
        if len(items) >= limit:
            break
    return items


def _like_fallback(conn: sqlite3.Connection, question: str, limit: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT id, source_id, rel_path, title, content, lang
        FROM documents
        WHERE title LIKE ? OR rel_path LIKE ? OR content LIKE ?
        LIMIT ?
        """,
        (f"%{question}%", f"%{question}%", f"%{question}%", limit),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["snippet"] = snippet_from_content(row["content"], question, window=45)
        out.append(item)
    return out
