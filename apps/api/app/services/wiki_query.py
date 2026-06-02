from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from ..db import WIKI_DIR, get_db
from .indexer import index_single_source
from .wiki_source import get_wiki_source_or_fallback


def build_query_page_body(
    *,
    question: str,
    answer: str,
    model_used: str,
    ts: str,
    evidences: list[dict[str, Any]],
) -> str:
    frontmatter = {
        "type": "query",
        "derived": True,
        "question": question,
        "model": model_used,
        "created": ts,
    }
    fm = yaml.safe_dump(frontmatter, allow_unicode=True, sort_keys=False).strip()
    ref_lines = "\n".join([f"- [{e['ref']}] `{e['source_id']}/{e['rel_path']}`" for e in evidences]) or "- (none)"
    return (
        f"---\n{fm}\n---\n\n"
        f"# Query: {question}\n\n"
        f"## Answer\n{answer}\n\n"
        f"## Citations\n{ref_lines}\n"
    )


def save_query_page(
    *,
    question: str,
    answer: str,
    model_used: str,
    evidences: list[dict[str, Any]],
    slug: str,
) -> tuple[str, dict[str, Any]]:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    queries_dir = WIKI_DIR / "queries"
    queries_dir.mkdir(parents=True, exist_ok=True)
    rel_name = f"queries/{ts}_{slug}.md"
    target = WIKI_DIR / rel_name
    target.write_text(
        build_query_page_body(
            question=question,
            answer=answer,
            model_used=model_used,
            ts=ts,
            evidences=evidences,
        ),
        encoding="utf-8",
    )

    index_stat: dict[str, Any] = {"indexed": 0, "status": "skipped"}
    wiki_source = get_wiki_source_or_fallback()
    conn = get_db()
    try:
        index_stat = index_single_source(conn, wiki_source, rel_path_filter=rel_name)
        conn.commit()
    finally:
        conn.close()
    return rel_name, index_stat


def save_query_page_with_nav(
    *,
    question: str,
    answer: str,
    model_used: str,
    evidences: list[dict[str, Any]],
    slug: str,
) -> tuple[str, dict[str, Any]]:
    rel_name, index_stat = save_query_page(
        question=question,
        answer=answer,
        model_used=model_used,
        evidences=evidences,
        slug=slug,
    )
    from .wiki_nav import touch_wiki_nav

    touch_wiki_nav("query", f"saved {rel_name}")
    return rel_name, index_stat
