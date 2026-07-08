import sqlite3
from typing import Any

CATEGORY_LABELS = {
    "all": "全部",
    "source": "原始素材",
    "summary": "学习摘要",
    "query": "问答沉淀",
}


def classify_document(source_id: str, rel_path: str) -> str:
    rp = (rel_path or "").replace("\\", "/")
    if rp.startswith("summaries/"):
        return "summary"
    if rp.startswith("queries/") or rp.startswith("insight_"):
        return "query"
    if source_id == "wiki":
        return "summary"
    return "source"


def category_sql_clause(category: str | None) -> tuple[str, list[Any]]:
    cat = (category or "").strip().lower()
    if not cat or cat == "all":
        return "", []
    if cat == "summary":
        return " AND (d.rel_path LIKE 'summaries/%' OR d.source_id = 'wiki')", []
    if cat == "query":
        return " AND (d.rel_path LIKE 'queries/%' OR d.rel_path LIKE 'insight_%')", []
    if cat == "source":
        return " AND d.source_id != 'wiki' AND d.rel_path NOT LIKE 'summaries/%' AND d.rel_path NOT LIKE 'queries/%' AND d.rel_path NOT LIKE 'insight_%'", []
    return "", []


def topic_sql_clause(topic: str | None) -> tuple[str, list[Any]]:
    t = (topic or "").strip().lower()
    if not t:
        return "", []
    prefix = f"summaries/{t}/%"
    return " AND d.rel_path LIKE ?", [prefix]


def path_prefix_sql_clause(path_prefix: str | None) -> tuple[str, list[Any]]:
    p = (path_prefix or "").strip().replace("\\", "/")
    if not p:
        return "", []
    if not p.endswith("%"):
        p = p.rstrip("/") + "/%"
    return " AND d.rel_path LIKE ?", [p]


def list_category_stats(conn: sqlite3.Connection, *, username: str | None = None, role: str | None = None) -> dict[str, Any]:
    # 权限过滤：与 browse_documents 一致
    if role and role.strip().lower() == "admin":
        rows = conn.execute("SELECT source_id, rel_path FROM documents").fetchall()
    elif not username:
        rows = conn.execute(
            "SELECT source_id, rel_path FROM documents WHERE source_owner = ?", ("__shared__",)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT source_id, rel_path FROM documents WHERE source_owner = ? OR source_owner = ?",
            ("__shared__", username),
        ).fetchall()
    counts: dict[str, int] = {"source": 0, "summary": 0, "query": 0}
    topic_counts: dict[str, int] = {}
    for row in rows:
        cat = classify_document(row["source_id"], row["rel_path"])
        counts[cat] = counts.get(cat, 0) + 1
        rp = (row["rel_path"] or "").replace("\\", "/")
        if rp.startswith("summaries/"):
            parts = rp.split("/")
            if len(parts) >= 2 and parts[1]:
                topic_counts[parts[1]] = topic_counts.get(parts[1], 0) + 1
    topics = [{"id": k, "label": k, "count": v} for k, v in sorted(topic_counts.items())]
    categories = [
        {"id": "all", "label": CATEGORY_LABELS["all"], "count": len(rows)},
        {"id": "source", "label": CATEGORY_LABELS["source"], "count": counts["source"]},
        {"id": "summary", "label": CATEGORY_LABELS["summary"], "count": counts["summary"]},
        {"id": "query", "label": CATEGORY_LABELS["query"], "count": counts["query"]},
    ]
    return {"categories": categories, "topics": topics}


def browse_documents(
    conn: sqlite3.Connection,
    *,
    category: str | None = None,
    topic: str | None = None,
    limit: int = 50,
    username: str | None = None,
    role: str | None = None,
) -> list[dict[str, Any]]:
    cap = max(1, min(int(limit), 200))
    sql = """
        SELECT id, source_id, rel_path, title, lang, updated_at
        FROM documents d
        WHERE 1=1
    """
    args: list[Any] = []

    # source_owner 权限过滤（与 fts.py _user_owner_filter 一致）
    if role and role.strip().lower() == "admin":
        pass  # admin 可浏览全部文档
    elif not username:
        sql += " AND d.source_owner = ?"
        args.append("__shared__")
    else:
        sql += " AND (d.source_owner = ? OR d.source_owner = ?)"
        args.extend(["__shared__", username])

    clause, cargs = category_sql_clause(category)
    sql += clause
    args.extend(cargs)
    clause, targs = topic_sql_clause(topic)
    sql += clause
    args.extend(targs)
    sql += " ORDER BY updated_at DESC LIMIT ?"
    args.append(cap)
    rows = conn.execute(sql, tuple(args)).fetchall()
    items = []
    for row in rows:
        item = dict(row)
        item["category"] = classify_document(row["source_id"], row["rel_path"])
        items.append(item)
    return items
