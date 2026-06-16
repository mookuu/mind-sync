import re
import sqlite3
from typing import Any

from ..config import settings
from .categories import category_sql_clause, classify_document, path_prefix_sql_clause, topic_sql_clause
from .indexer import snippet_from_content
from .chinese_tokenizer import has_chinese, tokenize_query

_TOKEN_SPLIT = re.compile(r"\s+")
_DEFAULT_WEIGHTS = {"source": 1.0, "summary": 1.2, "query": 1.1}


def parse_category_weights() -> dict[str, float]:
    raw = (settings.search_category_weights or "").strip()
    if not raw:
        return dict(_DEFAULT_WEIGHTS)
    weights = dict(_DEFAULT_WEIGHTS)
    for part in raw.split(","):
        chunk = part.strip()
        if not chunk or "=" not in chunk:
            continue
        key, val = chunk.split("=", 1)
        cat = key.strip().lower()
        try:
            weights[cat] = max(0.1, float(val.strip()))
        except ValueError:
            continue
    return weights


def _weights_active(weights: dict[str, float]) -> bool:
    return any(abs(weights.get(k, 1.0) - 1.0) > 1e-9 for k in _DEFAULT_WEIGHTS)


def _boost_title_match(items: list[dict[str, Any]], query: str) -> None:
    """Boost documents whose title/path contains query keywords (lower rank_score = better)."""
    keywords = [t.lower() for t in _TOKEN_SPLIT.split(query.strip()) if len(t) >= 2]
    if not keywords:
        return
    for item in items:
        title = (item.get("title") or "").lower()
        path = (item.get("rel_path") or "").lower()
        match_count = sum(1 for kw in keywords if kw in title or kw in path)
        if match_count > 0:
            boost = 1.0 - (match_count / (len(keywords) * 2))
            item["rank_score"] = float(item.get("rank_score", 0)) * max(boost, 0.3)


def _rank_with_weights(items: list[dict[str, Any]], weights: dict[str, float], query: str = "") -> list[dict[str, Any]]:
    """Lower effective rank is better (SQLite bm25: smaller = better match)."""
    for item in items:
        rank = float(item.get("rank_score", 0))
        cat = item.get("category") or classify_document(item.get("source_id", ""), item.get("rel_path", ""))
        weight = weights.get(cat, 1.0)
        item["rank_score"] = rank / weight
    if query:
        _boost_title_match(items, query)
    return sorted(items, key=lambda x: float(x.get("rank_score", 0)))


def _fts_fetch_limit(limit: int, sort: str, weights: dict[str, float]) -> int:
    if sort == "mtime_desc":
        return limit
    if _weights_active(weights):
        return min(max(limit * 3, limit), 200)
    return limit


def escape_fts_phrase(text: str) -> str:
    return text.replace('"', '""')


def _user_owner_filter(username: str | None = None, role: str | None = None) -> tuple[str, list[str]]:
    """Build SQL filter clause for source_owner based on user/role.

    Returns (sql_clause, args_list).
    - admin → no filter (access all)
    - member/logged-in → shared + own
    - anonymous → shared only
    """
    if role and role.strip().lower() == "admin":
        return "", []
    if not username:
        return "AND d.source_owner = ?", ["__shared__"]
    return "AND (d.source_owner = ? OR d.source_owner = ?)", ["__shared__", username]


def build_fts_match_query(raw: str) -> str:
    q = (raw or "").strip()
    if not q:
        return ""
    # Chinese query → use jieba tokenization
    if has_chinese(q):
        return tokenize_query(q, default_op="OR")
    # English/ASCII query → existing logic
    parts: list[str] = [f'"{escape_fts_phrase(q)}"']
    tokens = [t for t in _TOKEN_SPLIT.split(q) if len(t) >= 2]
    if len(tokens) > 1:
        token_expr = " OR ".join(f'"{escape_fts_phrase(t)}"' for t in tokens[:16])
        parts.append(f"({token_expr})")
    return " OR ".join(parts)


def _fts_rows(
    conn: sqlite3.Connection,
    fts_query: str,
    sql_suffix: str,
    args: tuple[Any, ...],
) -> list[sqlite3.Row]:
    if not fts_query:
        return []
    sql = f"""
        SELECT d.id, d.source_id, d.rel_path, d.title, d.content, d.lang, d.source_owner,
               snippet(documents_fts, 1, '<mark>', '</mark>', '...', 45) AS snippet,
               bm25(documents_fts) AS rank_score
        FROM documents_fts
        JOIN documents d ON d.id = documents_fts.rowid
        WHERE documents_fts MATCH ?
        {sql_suffix}
    """
    try:
        return conn.execute(sql, (fts_query, *args)).fetchall()
    except sqlite3.OperationalError:
        return []


def search_for_query(
    conn: sqlite3.Connection,
    question: str,
    limit: int = 8,
    username: str | None = None,
    role: str | None = None,
) -> list[dict[str, Any]]:
    weights = parse_category_weights()
    fetch_limit = _fts_fetch_limit(limit, "relevance", weights)
    fts_query = build_fts_match_query(question)
    owner_clause, owner_args = _user_owner_filter(username, role)
    fts_suffix = f"{owner_clause} ORDER BY bm25(documents_fts) LIMIT ?"
    rows = _fts_rows(
        conn,
        fts_query,
        fts_suffix,
        tuple(owner_args) + (fetch_limit,),
    )
    if rows:
        items = [dict(row) for row in rows]
        for item in items:
            item["category"] = classify_document(item["source_id"], item["rel_path"])
        if _weights_active(weights):
            items = _rank_with_weights(items, weights, question)
        return items[:limit]
    return _like_fallback(conn, question, limit=limit)


def _sort_items(items: list[dict[str, Any]], sort: str, conn: sqlite3.Connection) -> list[dict[str, Any]]:
    if sort != "mtime_desc" or not items:
        return items
    ids = [int(i["id"]) for i in items if i.get("id") is not None]
    if not ids:
        return items
    placeholders = ",".join("?" * len(ids))
    rows = conn.execute(
        f"SELECT id, mtime FROM documents WHERE id IN ({placeholders})",
        tuple(ids),
    ).fetchall()
    mtime_map = {int(r["id"]): float(r["mtime"]) for r in rows}
    return sorted(items, key=lambda x: mtime_map.get(int(x["id"]), 0), reverse=True)


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
    sort: str = "relevance",
    username: str | None = None,
    role: str | None = None,
) -> list[dict[str, Any]]:
    weights = parse_category_weights()
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
    owner_clause, owner_args = _user_owner_filter(username, role)
    filter_sql += owner_clause
    filter_args.extend(owner_args)

    fts_query = build_fts_match_query(q)
    fetch_limit = _fts_fetch_limit(limit, sort, weights)
    if sort == "mtime_desc":
        fts_suffix = filter_sql + " LIMIT ?"
    else:
        fts_suffix = filter_sql + " ORDER BY bm25(documents_fts) LIMIT ?"
    fts_rows = _fts_rows(conn, fts_query, fts_suffix, tuple(filter_args) + (fetch_limit,))

    items: list[dict[str, Any]] = []
    existing_ids: set[int] = set()
    for row in fts_rows:
        item = dict(row)
        item["category"] = classify_document(row["source_id"], row["rel_path"])
        if "snippet" not in item or not item["snippet"]:
            item["snippet"] = snippet_from_content(row["content"], q, window=30)
        items.append(item)
        existing_ids.add(int(row["id"]))

    if sort != "mtime_desc" and _weights_active(weights):
        items = _rank_with_weights(items, weights, q)

    if len(items) >= limit:
        trimmed = items[:limit]
        for item in trimmed:
            item.pop("rank_score", None)
        return _sort_items(trimmed, sort, conn)

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
    out = _sort_items(items[:limit], sort, conn)
    for item in out:
        item.pop("rank_score", None)
    return out


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
