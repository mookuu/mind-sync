"""Pull remote sources (GitHub / web cache) before indexing."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import httpx

from ..config import settings
from ..db import DATA_DIR
from ..models import Source
from .git_ops import ensure_clone, pull_repo

logger = logging.getLogger("mind-sync.source_sync")


def github_repo_dir(source_id: str) -> Path:
    return DATA_DIR / "repos" / source_id


def web_cache_dir(source_id: str) -> Path:
    return DATA_DIR / "web-cache" / source_id


def sync_github_source(source: Source) -> dict[str, Any]:
    url = (source.url or "").strip()
    if not url:
        return {"source_id": source.id, "type": "github", "ok": False, "error": "missing url"}
    branch = (source.branch or "main").strip() or "main"
    dest = github_repo_dir(source.id)
    token = (settings.github_token or "").strip() or None
    if (dest / ".git").is_dir():
        result = pull_repo(dest, branch=branch, token=token)
    else:
        result = ensure_clone(url, dest, branch=branch, shallow=True, token=token)
    result["source_id"] = source.id
    result["type"] = "github"
    return result


def sync_web_source(source: Source) -> dict[str, Any]:
    url = (source.url or "").strip()
    if not url:
        return {"source_id": source.id, "type": "web", "ok": False, "error": "missing url"}
    cache = web_cache_dir(source.id)
    cache.mkdir(parents=True, exist_ok=True)
    index_path = cache / "index.md"
    try:
        with httpx.Client(timeout=60, follow_redirects=True) as client:
            resp = client.get(url)
        if resp.status_code >= 400:
            return {
                "source_id": source.id,
                "type": "web",
                "ok": False,
                "error": f"HTTP {resp.status_code}",
            }
        content_type = resp.headers.get("content-type", "")
        body = resp.text
        if "html" in content_type.lower():
            body = f"# Web snapshot\n\nSource: {url}\n\n```html\n{body[:50000]}\n```\n"
        index_path.write_text(body, encoding="utf-8")
        meta = cache / "meta.json"
        meta.write_text(f'{{"url": "{url}", "status": {resp.status_code}}}', encoding="utf-8")
        return {"source_id": source.id, "type": "web", "ok": True, "path": str(cache)}
    except Exception as exc:
        logger.warning("web source fetch failed %s: %s", source.id, exc)
        return {"source_id": source.id, "type": "web", "ok": False, "error": str(exc)}


def sync_all_sources(sources: list[Source]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for source in sources:
        st = (source.source_type or "local").lower()
        if st == "github":
            results.append(sync_github_source(source))
        elif st == "web":
            results.append(sync_web_source(source))
    return results
