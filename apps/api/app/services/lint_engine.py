import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .link_graph import analyze_wiki_graph


def run_lint_report(
    rows: list[Any],
    stale_days: int,
    report_dir: Path,
    wiki_dir: Path | None = None,
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
