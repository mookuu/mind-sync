"""Convert HTTP response bodies into indexable Markdown for web sources."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from html import unescape
from typing import Any
from urllib.parse import urlparse

import yaml

try:
    import trafilatura
except ImportError:  # pragma: no cover - optional at import time in minimal envs
    trafilatura = None  # type: ignore[assignment]


def _strip_html_tags(html: str) -> str:
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = unescape(re.sub(r"\s+", " ", text)).strip()
    return text


def _extract_title(html: str) -> str:
    match = re.search(r"(?is)<title[^>]*>(.*?)</title>", html)
    if not match:
        return ""
    return unescape(re.sub(r"\s+", " ", match.group(1))).strip()


def _html_to_markdown(url: str, html: str) -> tuple[str, str]:
    title = _extract_title(html)
    body = ""
    if trafilatura is not None:
        try:
            body = trafilatura.extract(
                html,
                url=url,
                output_format="markdown",
                include_links=True,
                include_tables=True,
            ) or ""
        except Exception:
            body = ""
    if not body.strip():
        plain = _strip_html_tags(html)
        if plain:
            body = plain
    if not title and trafilatura is not None:
        try:
            meta = trafilatura.extract_metadata(html, default_url=url)
            if meta and meta.title:
                title = meta.title.strip()
        except Exception:
            pass
    if not title:
        title = urlparse(url).path.rstrip("/").split("/")[-1] or urlparse(url).netloc or "Web snapshot"
    return title, body.strip()


def _json_to_markdown(body: str) -> tuple[str, str]:
    try:
        data = json.loads(body)
        pretty = json.dumps(data, ensure_ascii=False, indent=2)
    except json.JSONDecodeError:
        pretty = body.strip()
    return "JSON snapshot", f"```json\n{pretty[:50000]}\n```"


def web_response_to_markdown(url: str, content_type: str, body: str) -> dict[str, Any]:
    """Return {title, markdown, extractor} for a fetched web response."""
    ct = (content_type or "").lower()
    raw = body or ""

    if "html" in ct or re.search(r"(?is)<html|<body|<article|<main", raw[:8000]):
        title, md_body = _html_to_markdown(url, raw)
        extractor = "trafilatura" if trafilatura is not None and md_body else "html-plain"
        return {"title": title, "markdown": md_body, "extractor": extractor}

    if "json" in ct or raw.lstrip().startswith(("{", "[")):
        title, md_body = _json_to_markdown(raw)
        return {"title": title, "markdown": md_body, "extractor": "json"}

    if "markdown" in ct or "text/plain" in ct:
        title = urlparse(url).path.rstrip("/").split("/")[-1] or "Web snapshot"
        return {"title": title, "markdown": raw.strip(), "extractor": "text"}

    plain = raw.strip()
    if plain:
        return {"title": "Web snapshot", "markdown": f"```\n{plain[:50000]}\n```", "extractor": "raw"}

    return {"title": "Web snapshot", "markdown": "_Empty response body._", "extractor": "empty"}


def build_web_snapshot_markdown(
    *,
    url: str,
    content_type: str,
    body: str,
    status_code: int,
    source_id: str,
) -> str:
    extracted = web_response_to_markdown(url, content_type, body)
    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    frontmatter = {
        "type": "web_snapshot",
        "source_id": source_id,
        "url": url,
        "fetched_at": fetched_at,
        "status_code": status_code,
        "content_type": content_type or "unknown",
        "extractor": extracted["extractor"],
    }
    fm = yaml.safe_dump(frontmatter, allow_unicode=True, sort_keys=False).strip()
    lines = [f"---", fm, "---", "", f"# {extracted['title']}", "", f"> Source: {url}", ""]
    md_body = extracted["markdown"].strip()
    if md_body:
        lines.append(md_body)
    else:
        lines.append("_No extractable content._")
    lines.append("")
    return "\n".join(lines)
