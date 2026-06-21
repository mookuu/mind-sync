import sqlite3

from typing import Any



from .categories import classify_document

from .sync_settings import LANG_LABELS, SOURCE_LABELS





def _new_dir(name: str, path: str) -> dict[str, Any]:

    return {"type": "dir", "name": name, "path": path, "dirs": {}, "files": []}





def _insert_doc(root: dict[str, Any], doc: dict[str, Any]) -> None:

    rel_path = (doc.get("rel_path") or "").replace("\\", "/")

    parts = [p for p in rel_path.split("/") if p]

    if not parts:

        return

    node = root

    for i, part in enumerate(parts):

        if i == len(parts) - 1:

            node["files"].append(

                {

                    "type": "file",

                    "name": part,

                    "path": rel_path,

                    "doc_id": doc["id"],

                    "title": doc.get("title") or part,

                    "lang": doc.get("lang"),

                }

            )

            return

        path = "/".join(parts[: i + 1])

        if part not in node["dirs"]:

            node["dirs"][part] = _new_dir(part, path)

        node = node["dirs"][part]





def _flatten_tree(node: dict[str, Any]) -> list[dict[str, Any]]:

    items: list[dict[str, Any]] = []

    for name in sorted(node.get("dirs", {}).keys(), key=str.lower):

        child = node["dirs"][name]

        items.append(

            {

                "type": "dir",

                "name": name,

                "path": child.get("path") or name,

                "children": _flatten_tree(child),

            }

        )

    for f in sorted(node.get("files", []), key=lambda x: x["name"].lower()):

        items.append(f)

    return items





def _build_lang_tree(docs: list[dict[str, Any]]) -> list[dict[str, Any]]:

    root = {"dirs": {}, "files": []}

    for doc in docs:

        _insert_doc(root, doc)

    return _flatten_tree(root)





def _build_lang_groups(docs: list[dict[str, Any]]) -> list[dict[str, Any]]:

    by_lang: dict[str, list[dict[str, Any]]] = {}

    for doc in docs:

        lang = doc.get("lang") or "unknown"

        by_lang.setdefault(lang, []).append(doc)

    lang_groups = []

    for lang in sorted(by_lang.keys(), key=lambda x: (x != "markdown", x)):

        lang_docs = by_lang[lang]

        lang_groups.append(

            {

                "id": lang,

                "label": LANG_LABELS.get(lang, lang),

                "count": len(lang_docs),

                "tree": _build_lang_tree(lang_docs),

            }

        )

    return lang_groups





def build_library_index(conn: sqlite3.Connection, *, category: str | None = "source", username: str | None = None, role: str | None = None) -> dict[str, Any]:

    rows = conn.execute(

        """

        SELECT id, source_id, rel_path, title, lang, updated_at

        FROM documents

        ORDER BY source_id, rel_path

        """

    ).fetchall()

    by_source: dict[str, list[dict[str, Any]]] = {}

    for row in rows:

        item = dict(row)

        cat = classify_document(row["source_id"], row["rel_path"])

        if category and category != "all" and cat != category:

            continue

        by_source.setdefault(row["source_id"], []).append(item)



    # 只保留当前用户已同步的源
    if username and role and role.strip().lower() != "admin":
        from .fts import _user_synced_sources
        synced = _user_synced_sources(username)
        if synced is not None:  # None = all synced
            synced_set = set(synced)
            by_source = {k: v for k, v in by_source.items() if k in synced_set}

    sections: list[dict[str, Any]] = []

    wiki_docs: list[dict[str, Any]] | None = None

    raw_blocks: list[dict[str, Any]] = []



    for source_id in sorted(by_source.keys(), key=str.lower):

        docs = by_source[source_id]

        if source_id == "wiki":

            wiki_docs = docs

            continue

        raw_blocks.append(

            {

                "id": source_id,

                "label": SOURCE_LABELS.get(source_id, source_id),

                "count": len(docs),

                "tree": _build_lang_tree(docs),

            }

        )



    if raw_blocks:

        sections.append({"id": "raw_sources", "label": "原始文档", "sources": raw_blocks})

    if wiki_docs is not None:

        sections.append(

            {

                "id": "wiki",

                "label": "Wiki 摘要与沉淀",

                "count": len(wiki_docs),

                "flat": True,

                "source_id": "wiki",

                "tree": _build_lang_tree(wiki_docs),

            }

        )



    # 生成 etag：源 ID + 文档数的指纹，前端用于缓存判断
    import hashlib
    import json
    etag_src = sorted((sid, len(dlist)) for sid, dlist in by_source.items())
    etag = hashlib.md5(json.dumps(etag_src, sort_keys=True).encode()).hexdigest()[:8]

    return {

        "sections": sections,

        "total_documents": sum(len(v) for v in by_source.values()),
        "etag": etag,

    }

