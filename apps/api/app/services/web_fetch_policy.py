"""Web source fetch compliance: robots.txt, User-Agent, domain throttle, allowlist."""

from __future__ import annotations

import logging
import time
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

from ..config import settings

logger = logging.getLogger("mind-sync.web_fetch")

_last_fetch_by_host: dict[str, float] = {}
_robots_cache: dict[str, tuple[float, RobotFileParser | None]] = {}
_ROBOTS_CACHE_TTL = 3600.0


def build_user_agent() -> str:
    base = (settings.web_fetch_user_agent or "mind-sync/0.1").strip() or "mind-sync/0.1"
    contact = (settings.web_fetch_contact or "").strip()
    if contact:
        if "@" in contact and not contact.startswith("("):
            return f"{base} (+mailto:{contact})"
        return f"{base} ({contact})"
    return base


def parse_allowlist(raw: str) -> set[str]:
    hosts: set[str] = set()
    for item in (raw or "").split(","):
        host = item.strip().lower().rstrip(".")
        if host.startswith("*."):
            host = host[2:]
        if host:
            hosts.add(host)
    return hosts


def _host_matches_allowlist(host: str, allowlist: set[str]) -> bool:
    host = host.lower()
    if host in allowlist:
        return True
    return any(host == entry or host.endswith(f".{entry}") for entry in allowlist)


def check_allowlist(url: str) -> str | None:
    allowlist = parse_allowlist(settings.web_fetch_allowlist)
    host = (urlparse(url).hostname or "").lower()
    if not host:
        return "invalid URL host"

    if settings.web_fetch_require_allowlist:
        if not allowlist:
            return "WEB_FETCH_REQUIRE_ALLOWLIST=true but WEB_FETCH_ALLOWLIST is empty"
        if not _host_matches_allowlist(host, allowlist):
            return f"host '{host}' not in WEB_FETCH_ALLOWLIST"
        return None

    if allowlist and not _host_matches_allowlist(host, allowlist):
        return f"host '{host}' not in WEB_FETCH_ALLOWLIST"
    return None


def _respect_robots_for_source(source) -> bool:
    per_source = getattr(source, "respect_robots", None)
    if per_source is not None:
        return bool(per_source)
    return bool(settings.web_fetch_respect_robots)


def _load_robots_parser(robots_url: str, client: httpx.Client) -> RobotFileParser | None:
    now = time.time()
    cached = _robots_cache.get(robots_url)
    if cached and now - cached[0] < _ROBOTS_CACHE_TTL:
        return cached[1]

    parser = RobotFileParser()
    parser.set_url(robots_url)
    try:
        resp = client.get(robots_url, timeout=15)
        if resp.status_code >= 400:
            parser = None
        else:
            parser.parse(resp.text.splitlines())
    except Exception as exc:
        logger.warning("robots.txt fetch failed %s: %s", robots_url, exc)
        parser = None

    _robots_cache[robots_url] = (now, parser)
    return parser


def check_robots(url: str, user_agent: str, client: httpx.Client) -> str | None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return "invalid URL for robots check"

    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    parser = _load_robots_parser(robots_url, client)
    if parser is None:
        # Unreachable or missing robots.txt — proceed (common industry practice for 404)
        return None

    if not parser.can_fetch(user_agent, url):
        return f"robots.txt disallows fetch for {url}"
    return None


def enforce_domain_interval(host: str) -> None:
    interval = max(0.0, float(settings.web_fetch_min_interval_seconds))
    if interval <= 0 or not host:
        return
    now = time.time()
    last = _last_fetch_by_host.get(host.lower())
    if last is not None:
        wait = interval - (now - last)
        if wait > 0:
            time.sleep(wait)
    _last_fetch_by_host[host.lower()] = time.time()


def validate_web_fetch(source, url: str, client: httpx.Client) -> str | None:
    """Return error message if fetch should be blocked, else None."""
    if not settings.web_fetch_enabled:
        return "WEB_FETCH_ENABLED=false"

    if settings.web_fetch_require_opt_in and not getattr(source, "fetch_confirmed", False):
        return (
            f"source '{source.id}' fetch not confirmed — set fetch_confirmed: true in sources.yaml "
            "(WEB_FETCH_REQUIRE_OPT_IN=true)"
        )

    allow_err = check_allowlist(url)
    if allow_err:
        return allow_err

    if _respect_robots_for_source(source):
        ua = build_user_agent()
        robots_err = check_robots(url, ua, client)
        if robots_err:
            return robots_err

    host = (urlparse(url).hostname or "").lower()
    enforce_domain_interval(host)
    return None


def web_fetch_policy_summary() -> dict[str, object]:
    allowlist = sorted(parse_allowlist(settings.web_fetch_allowlist))
    return {
        "enabled": bool(settings.web_fetch_enabled),
        "respect_robots": bool(settings.web_fetch_respect_robots),
        "require_opt_in": bool(settings.web_fetch_require_opt_in),
        "require_allowlist": bool(settings.web_fetch_require_allowlist),
        "allowlist": allowlist,
        "user_agent": build_user_agent(),
        "min_interval_seconds": float(settings.web_fetch_min_interval_seconds),
        "max_bytes": int(settings.web_fetch_max_bytes),
    }


def reset_web_fetch_state_for_tests() -> None:
    _last_fetch_by_host.clear()
    _robots_cache.clear()
