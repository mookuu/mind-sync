"""Maintain wiki/index.md and wiki/log.md (Karpathy LLM Wiki navigation layer)."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from ..db import WIKI_DIR

_LOG_HEADER = "# mind-sync wiki log\n\nAppend-only timeline. Do not edit manually.\n\n"
_INDEX_HEADER = "# Wiki Index\n\nAuto-generated catalog of summaries and queries.\n\n"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    try:
        meta = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        meta = {}
    body = parts[2].lstrip("\n")
    return meta if isinstance(meta, dict) else {}, body


def _first_heading(body: str, fallback: str) -> str:
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def _one_line_summary(body: str, limit: int = 120) -> str:
    for line in body.splitlines():
        text = line.strip()
        if not text or text.startswith("#") or text.startswith(">"):
            continue
        if text.startswith("- ") or text.startswith("* "):
            text = text[2:].strip()
        text = re.sub(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", r"\1", text)
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
        if text:
            return text[:limit]
    return ""


def append_wiki_log(event: str, detail: str = "") -> Path:
    log_path = WIKI_DIR / "log.md"
    WIKI_DIR.mkdir(parents=True, exist_ok=True)
    if not log_path.exists():
        log_path.write_text(_LOG_HEADER, encoding="utf-8")
    ts = _utc_now_iso()
    line = f"## [{ts}] {event}"
    if detail.strip():
        line += f" | {detail.strip()}"
    existing = log_path.read_text(encoding="utf-8")
    log_path.write_text(existing.rstrip() + "\n" + line + "\n", encoding="utf-8")
    return log_path


def rebuild_wiki_index() -> Path:
    index_path = WIKI_DIR / "index.md"
    WIKI_DIR.mkdir(parents=True, exist_ok=True)

    summaries: dict[str, list[dict[str, str]]] = {}
    queries: list[dict[str, str]] = []

    for path in sorted(WIKI_DIR.rglob("*.md")):
        rel = str(path.relative_to(WIKI_DIR)).replace("\\", "/")
        if rel in {"index.md", "log.md", "SCHEMA.md"}:
            continue
        if rel.startswith("summaries/README"):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        meta, body = _split_frontmatter(text)
        title = _first_heading(body, path.stem)
        summary_line = _one_line_summary(body)
        entry = {"rel": rel, "title": title, "summary": summary_line}

        if rel.startswith("summaries/"):
            parts = rel.split("/")
            topic = parts[1] if len(parts) >= 2 else "general"
            summaries.setdefault(topic, []).append(entry)
        elif rel.startswith("queries/"):
            q = str(meta.get("question") or title)
            entry["title"] = q[:80]
            queries.append(entry)

    lines = [_INDEX_HEADER.rstrip(), "", f"_Updated: {_utc_now_iso()}_", ""]

    if summaries:
        lines.append("## Summaries")
        lines.append("")
        for topic in sorted(summaries.keys()):
            lines.append(f"### {topic}")
            lines.append("")
            for item in summaries[topic]:
                desc = f" — {item['summary']}" if item["summary"] else ""
                lines.append(f"- [{item['title']}]({item['rel']}){desc}")
            lines.append("")

    if queries:
        lines.append("## Queries")
        lines.append("")
        for item in sorted(queries, key=lambda x: x["rel"], reverse=True)[:80]:
            desc = f" — {item['summary']}" if item["summary"] else ""
            lines.append(f"- [{item['title']}]({item['rel']}){desc}")
        lines.append("")

    if not summaries and not queries:
        lines.append("_No summary or query pages yet._")
        lines.append("")

    index_path.write_text("\n".join(lines), encoding="utf-8")
    return index_path


def touch_wiki_nav(event: str, detail: str = "", *, rebuild_index: bool = True) -> dict[str, str]:
    log_path = append_wiki_log(event, detail)
    index_path = rebuild_wiki_index() if rebuild_index else WIKI_DIR / "index.md"
    _index_nav_pages()
    return {"log_path": str(log_path), "index_path": str(index_path)}


def _index_nav_pages() -> None:
    try:
        from ..db import get_db
        from .indexer import index_single_source
        from .wiki_source import get_wiki_source_or_fallback

        wiki_source = get_wiki_source_or_fallback()
        conn = get_db()
        try:
            for rel in ("index.md", "log.md"):
                if (WIKI_DIR / rel).exists():
                    index_single_source(conn, wiki_source, rel_path_filter=rel)
            conn.commit()
        finally:
            conn.close()
    except Exception as exc:
        import logging

        logging.getLogger("mind-sync.wiki_nav").warning("index nav pages failed: %s", exc)
        return
