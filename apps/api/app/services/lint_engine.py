import re
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from .link_graph import analyze_wiki_graph


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
    return (meta if isinstance(meta, dict) else {}), parts[2]


def _parse_updated_ts(value: Any, fallback: float) -> float:
    if isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return float(dt.timestamp())
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=timezone.utc).timestamp()
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value.strip():
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(value.strip(), fmt).replace(tzinfo=timezone.utc).timestamp()
            except ValueError:
                continue
    return fallback


def _source_mtime_map(conn: Any) -> dict[str, float]:
    rows = conn.execute("SELECT source_id, rel_path, mtime FROM documents").fetchall()
    return {f"{row['source_id']}/{row['rel_path']}": float(row["mtime"]) for row in rows}


def _normalize_source_ref(raw: str) -> str:
    ref = (raw or "").strip().replace("\\", "/").lstrip("/")
    return ref


def check_stale_summaries(wiki_dir: Path, conn: Any) -> list[dict[str, Any]]:
    """Flag summaries whose listed sources were updated after the summary."""
    if not wiki_dir.exists():
        return []
    mtime_map = _source_mtime_map(conn)
    issues: list[dict[str, Any]] = []
    for path in sorted(wiki_dir.glob("summaries/**/*.md")):
        if not path.is_file():
            continue
        rel = str(path.relative_to(wiki_dir)).replace("\\", "/")
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        meta, _ = _split_frontmatter(text)
        if meta.get("type") not in (None, "summary") and not rel.startswith("summaries/"):
            continue
        summary_ts = _parse_updated_ts(meta.get("updated"), path.stat().st_mtime)
        sources = meta.get("sources") or []
        if not isinstance(sources, list):
            continue
        stale_refs: list[str] = []
        for item in sources:
            ref = _normalize_source_ref(str(item))
            if not ref:
                continue
            src_mtime = mtime_map.get(ref)
            if src_mtime is not None and src_mtime > summary_ts + 1.0:
                stale_refs.append(ref)
        if stale_refs:
            issues.append(
                {
                    "type": "stale-summary",
                    "source_id": "wiki",
                    "rel_path": rel,
                    "detail": f"sources updated after summary: {', '.join(stale_refs[:5])}",
                }
            )
    return issues


def run_lint_report(
    rows: list[Any],
    stale_days: int,
    report_dir: Path,
    wiki_dir: Path | None = None,
    conn: Any | None = None,
) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    stale_threshold = time.time() - stale_days * 86400
    title_count: dict[str, int] = {}
    md_link_pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")

    for row in rows:
        title = row["title"]
        title_count[title] = title_count.get(title, 0) + 1
        content = row["content"] or ""
        if len(content.strip()) < 20:
            issues.append(
                {
                    "type": "thin-content",
                    "source_id": row["source_id"],
                    "rel_path": row["rel_path"],
                    "detail": "content too short (<20 chars)",
                }
            )
        if row["updated_at"] < stale_threshold:
            issues.append(
                {
                    "type": "stale-doc",
                    "source_id": row["source_id"],
                    "rel_path": row["rel_path"],
                    "detail": f"not updated in {stale_days}+ days",
                }
            )
        for link in md_link_pattern.findall(content):
            if link.startswith(("http://", "https://", "#", "mailto:")):
                continue
            if " " in link and not link.endswith(".md"):
                continue

    for row in rows:
        if title_count.get(row["title"], 0) > 1:
            issues.append(
                {
                    "type": "duplicate-title",
                    "source_id": row["source_id"],
                    "rel_path": row["rel_path"],
                    "detail": f"title '{row['title']}' appears multiple times",
                }
            )

    wiki_orphans: list[str] = []
    wiki_broken: list[dict[str, str]] = []
    if wiki_dir and wiki_dir.exists():
        graph = analyze_wiki_graph(wiki_dir)
        wiki_orphans = graph.get("orphans") or []
        wiki_broken = graph.get("broken_links") or []
        for path in wiki_orphans[:80]:
            issues.append(
                {
                    "type": "wiki-orphan",
                    "source_id": "wiki",
                    "rel_path": path,
                    "detail": "no incoming or outgoing wiki links",
                }
            )
        for item in wiki_broken[:80]:
            issues.append(
                {
                    "type": "wiki-broken-link",
                    "source_id": "wiki",
                    "rel_path": item.get("source", ""),
                    "detail": f"{item.get('kind', 'link')} -> {item.get('target', '')}",
                }
            )
        if conn is not None:
            issues.extend(check_stale_summaries(wiki_dir, conn))

    report_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    report_path = report_dir / f"lint_{ts}.md"
    report_lines = [
        "# mind-sync lint report",
        "",
        f"- Generated at: {datetime.now(timezone.utc).isoformat()}",
        f"- Total docs: {len(rows)}",
        f"- Total issues: {len(issues)}",
        f"- Wiki orphans: {len(wiki_orphans)}",
        f"- Wiki broken links: {len(wiki_broken)}",
        "",
        "## Issues",
    ]
    if not issues:
        report_lines.append("- No issues found.")
    else:
        for item in issues:
            report_lines.append(f"- [{item['type']}] `{item['source_id']}/{item['rel_path']}` - {item['detail']}")
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    return {
        "ok": True,
        "issue_count": len(issues),
        "issues": issues[:200],
        "wiki_orphans": wiki_orphans[:50],
        "wiki_broken_links": wiki_broken[:50],
        "report_path": str(report_path),
    }
