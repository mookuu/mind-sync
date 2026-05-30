import re
from pathlib import Path
from typing import Any

LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:\|[^\]]+)?\]\]")


def _resolve_wiki_target(wiki_dir: Path, src_path: Path, raw: str) -> str | None:
    target = (raw or "").strip()
    if not target or target.startswith(("#", "http://", "https://", "mailto:")):
        return None
    if target.endswith(".md"):
        candidate = (src_path.parent / target).resolve()
    else:
        candidate = (src_path.parent / f"{target}.md").resolve()
    try:
        return str(candidate.relative_to(wiki_dir.resolve())).replace("\\", "/")
    except Exception:
        alt = (wiki_dir / f"{target}.md").resolve()
        if alt.exists():
            return str(alt.relative_to(wiki_dir.resolve())).replace("\\", "/")
        alt2 = (wiki_dir / target).resolve()
        try:
            return str(alt2.relative_to(wiki_dir.resolve())).replace("\\", "/")
        except Exception:
            return None


def analyze_wiki_graph(wiki_dir: Path) -> dict[str, Any]:
    wiki_dir.mkdir(parents=True, exist_ok=True)
    files = sorted([p for p in wiki_dir.rglob("*.md") if p.is_file()])
    node_ids = {str(p.relative_to(wiki_dir)).replace("\\", "/") for p in files}
    out_edges: dict[str, set[str]] = {nid: set() for nid in node_ids}
    in_edges: dict[str, set[str]] = {nid: set() for nid in node_ids}
    broken_links: list[dict[str, str]] = []

    for p in files:
        src = str(p.relative_to(wiki_dir)).replace("\\", "/")
        text = p.read_text(encoding="utf-8", errors="ignore")

        for raw in LINK_RE.findall(text):
            if raw.startswith(("http://", "https://", "#", "mailto:")):
                continue
            target = (p.parent / raw).resolve()
            try:
                rel = str(target.relative_to(wiki_dir.resolve())).replace("\\", "/")
            except Exception:
                broken_links.append({"source": src, "target": raw, "kind": "markdown"})
                continue
            if rel in node_ids:
                out_edges[src].add(rel)
                in_edges[rel].add(src)
            else:
                broken_links.append({"source": src, "target": raw, "kind": "markdown"})

        for raw in WIKILINK_RE.findall(text):
            rel = _resolve_wiki_target(wiki_dir, p, raw)
            if rel and rel in node_ids:
                out_edges[src].add(rel)
                in_edges[rel].add(src)
            else:
                broken_links.append({"source": src, "target": raw, "kind": "wikilink"})

    nodes = []
    for nid in sorted(node_ids):
        in_deg = len(in_edges[nid])
        out_deg = len(out_edges[nid])
        rp = nid.replace("\\", "/")
        doc_type = "summary" if rp.startswith("summaries/") else "query" if rp.startswith("queries/") else "wiki"
        nodes.append(
            {
                "id": nid,
                "in_degree": in_deg,
                "out_degree": out_deg,
                "is_orphan": in_deg == 0 and out_deg == 0,
                "is_hub": (in_deg + out_deg) >= 6,
                "doc_type": doc_type,
            }
        )

    edges = []
    for src, targets in out_edges.items():
        for tgt in sorted(targets):
            edges.append({"source": src, "target": tgt})

    orphans = [n["id"] for n in nodes if n["is_orphan"]]
    hubs = [n["id"] for n in nodes if n["is_hub"]]
    return {
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes": nodes,
        "edges": edges,
        "orphans": orphans,
        "hubs": hubs,
        "broken_links": broken_links,
    }
