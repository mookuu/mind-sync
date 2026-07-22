"""Pull remote sources (GitHub / web cache) before indexing."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from ..config import settings
from ..models import Source
from .git_ops import ensure_clone, pull_repo
from .source_pairing import SourcePair, SyncPlan, build_sync_plan, resolve_index_source
from .source_spec_util import source_to_spec
from .source_adapters.github_repo import resolve_github_clone_dir
from .sync_backoff import record_sync_failure, record_sync_success, should_skip_source
from .web_extract import build_web_snapshot_markdown
from .web_fetch_policy import build_user_agent, validate_web_fetch

logger = logging.getLogger("mind-sync.source_sync")


def sync_github_source(source: Source) -> dict[str, Any]:
    skip, reason = should_skip_source(source.id)
    if skip:
        return {
            "source_id": source.id,
            "type": "github",
            "ok": False,
            "error": reason,
            "skipped_backoff": True,
        }
    url = (source.url or "").strip()
    if not url:
        return {"source_id": source.id, "type": "github", "ok": False, "error": "missing url"}
    branch = (source.branch or "main").strip() or "main"
    dest = resolve_github_clone_dir(source_to_spec(source))
    token = (settings.github_token or "").strip() or None
    try:
        if (dest / ".git").is_dir():
            result = pull_repo(dest, branch=branch, token=token)
        else:
            result = ensure_clone(url, dest, branch=branch, shallow=True, token=token)
    except Exception as exc:
        logger.warning("github sync exception %s: %s", source.id, exc)
        result = {"ok": False, "action": "pull", "path": str(dest), "error": str(exc)}
    result["source_id"] = source.id
    result["type"] = "github"
    result["path"] = str(dest)
    if not result.get("ok"):
        logger.warning("github sync failed %s: %s", source.id, result.get("error"))
        record_sync_failure(source.id, str(result.get("error") or "github sync failed"))
    else:
        record_sync_success(source.id)
    return result


def _load_web_meta(meta_path) -> dict[str, Any]:
    if not meta_path.is_file():
        return {}
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("invalid web meta %s: %s", meta_path, exc)
        return {}


def _conditional_headers(meta: dict[str, Any]) -> dict[str, str]:
    headers: dict[str, str] = {}
    etag = (meta.get("etag") or "").strip()
    if etag:
        headers["If-None-Match"] = etag
    last_modified = (meta.get("last_modified") or "").strip()
    if last_modified:
        headers["If-Modified-Since"] = last_modified
    return headers


def _read_body_limited(resp: httpx.Response, max_bytes: int) -> bytes:
    content_length = resp.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > max_bytes:
                raise ValueError(f"response too large ({content_length} bytes > {max_bytes})")
        except ValueError as exc:
            if "too large" in str(exc):
                raise
    data = resp.content
    if len(data) > max_bytes:
        raise ValueError(f"response too large ({len(data)} bytes > {max_bytes})")
    return data


def sync_web_source(source: Source) -> dict[str, Any]:
    skip, reason = should_skip_source(source.id)
    if skip:
        return {
            "source_id": source.id,
            "type": "web",
            "ok": False,
            "error": reason,
            "skipped_backoff": True,
        }
    result = _sync_web_source_fetch(source)
    if result.get("ok"):
        record_sync_success(source.id)
    else:
        record_sync_failure(source.id, str(result.get("error") or "web sync failed"))
    return result


def _sync_web_source_fetch(source: Source) -> dict[str, Any]:
    url = (source.url or "").strip()
    if not url:
        return {"source_id": source.id, "type": "web", "ok": False, "error": "missing url"}
    from .source_adapters.web_page import resolve_web_output_dir
    import hashlib

    url_hash = hashlib.sha256(url.encode()).hexdigest()[:12]
    out_dir = resolve_web_output_dir(source_to_spec(source))
    out_dir.mkdir(parents=True, exist_ok=True)
    index_name = f"{url_hash}.md"
    meta_name = f"{url_hash}.json"
    index_path = out_dir / index_name
    meta_path = out_dir / meta_name
    prior_meta = _load_web_meta(meta_path)
    max_bytes = max(64_000, int(settings.web_fetch_max_bytes))
    base_headers = {"User-Agent": build_user_agent()}
    try:
        with httpx.Client(timeout=60, follow_redirects=True, headers=base_headers) as client:
            blocked = validate_web_fetch(source, url, client)
            if blocked:
                logger.warning("web fetch blocked %s: %s", source.id, blocked)
                return {
                    "source_id": source.id,
                    "type": "web",
                    "ok": False,
                    "error": blocked,
                    "blocked": True,
                }
            req_headers = {**base_headers, **_conditional_headers(prior_meta)}
            resp = client.get(url, headers=req_headers)
        if resp.status_code == 304:
            return {
                "source_id": source.id,
                "type": "web",
                "ok": True,
                "path": str(out_dir),
                "snapshot": str(index_path),
                "not_modified": True,
            }
        if resp.status_code >= 400:
            return {
                "source_id": source.id,
                "type": "web",
                "ok": False,
                "error": f"HTTP {resp.status_code}",
            }
        try:
            raw = _read_body_limited(resp, max_bytes)
        except ValueError as exc:
            return {
                "source_id": source.id,
                "type": "web",
                "ok": False,
                "error": str(exc),
            }
        content_type = resp.headers.get("content-type", "")
        body = raw.decode(resp.encoding or "utf-8", errors="replace")
        markdown = build_web_snapshot_markdown(
            url=url,
            content_type=content_type,
            body=body,
            status_code=resp.status_code,
            source_id=source.id,
        )
        index_path.write_text(markdown, encoding="utf-8")
        meta_payload = {
            "url": url,
            "status": resp.status_code,
            "path": index_path.as_posix(),
            "etag": resp.headers.get("etag"),
            "last_modified": resp.headers.get("last-modified"),
        }
        meta_path.write_text(json.dumps(meta_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return {
            "source_id": source.id,
            "type": "web",
            "ok": True,
            "path": str(out_dir),
            "snapshot": str(index_path),
        }
    except Exception as exc:
        logger.warning("web source fetch failed %s: %s", source.id, exc)
        return {"source_id": source.id, "type": "web", "ok": False, "error": str(exc)}


def sync_all_sources(sources: list[Source]) -> dict[str, Any]:
    """Pull remotes; github/local pairs prefer github with local fallback metadata."""
    plan = build_sync_plan(sources)
    repo_sync: list[dict[str, Any]] = []
    warnings: list[str] = []
    index_tasks: list[dict[str, Any]] = []

    for pair in plan.pairs:
        pull = sync_github_source(pair.github)
        pull["pair_match"] = pair.match_reason
        if pair.local:
            pull["paired_local_id"] = pair.local.id
        if not pull.get("ok"):
            pull["fallback"] = "local" if pair.local else "existing_or_none"
        repo_sync.append(pull)

        index_source, warning, skip = resolve_index_source(pair, pull)
        if warning:
            warnings.append(warning)
            pull["warning"] = warning
        if index_source is not None:
            index_tasks.append(
                {
                    "source": index_source,
                    "pull": pull,
                    "warning": warning,
                    "github_id": pair.github.id,
                    "local_id": pair.local.id if pair.local else None,
                }
            )
        elif skip:
            index_tasks.append(
                {
                    "source": None,
                    "pull": pull,
                    "warning": warning,
                    "status": skip,
                    "github_id": pair.github.id,
                }
            )

    for source in plan.standalone:
        st = (source.source_type or "local").lower()
        if st == "web":
            web_result = sync_web_source(source)
            repo_sync.append(web_result)
            if not web_result.get("ok"):
                msg = f"source '{source.id}' web fetch failed: {web_result.get('error')}"
                warnings.append(msg)
                web_result["warning"] = msg
            index_tasks.append({"source": source, "pull": web_result, "warning": web_result.get("warning")})
        else:
            index_tasks.append({"source": source, "pull": None, "warning": None})

    return {
        "repo_sync": repo_sync,
        "warnings": warnings,
        "index_tasks": index_tasks,
        "plan": {
            "pairs": [
                {
                    "github_id": p.github.id,
                    "local_id": p.local.id if p.local else None,
                    "match": p.match_reason,
                }
                for p in plan.pairs
            ],
            "skipped_local_ids": [s.id for s in plan.skipped_locals],
        },
    }
