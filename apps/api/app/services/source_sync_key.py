"""Unique keys for sync/UI when sources.yaml has duplicate ids (e.g. paired github + local)."""

from __future__ import annotations

from ..models import Source

_VALID_TYPES = frozenset({"local", "github", "web"})


def source_sync_key(source: Source) -> str:
    st = (source.source_type or "local").strip().lower()
    return f"{source.id}:{st}"


def parse_sync_key(key: str) -> tuple[str, str | None]:
    raw = (key or "").strip()
    if not raw:
        return "", None
    if ":" in raw:
        sid, stype = raw.rsplit(":", 1)
        stype = stype.strip().lower()
        if stype in _VALID_TYPES:
            return sid.strip(), stype
    return raw, None


def source_matches_sync_key(source: Source, key: str) -> bool:
    sk = (key or "").strip()
    if not sk:
        return False
    if source_sync_key(source) == sk:
        return True
    parsed_id, parsed_type = parse_sync_key(sk)
    if parsed_type is not None:
        return False
    return source.id == parsed_id


def filter_sources_by_sync_keys(sources: list[Source], keys: list[str] | None) -> list[Source]:
    if not keys:
        return sources
    return [s for s in sources if any(source_matches_sync_key(s, k) for k in keys)]


def expand_sync_keys(raw_keys: list[str], sources: list[Source]) -> list[str]:
    """Resolve stored selection to explicit id:type keys (legacy bare ids expand to all matches)."""
    out: list[str] = []
    seen: set[str] = set()
    for key in raw_keys:
        chunk = (key or "").strip()
        if not chunk:
            continue
        parsed_id, parsed_type = parse_sync_key(chunk)
        if parsed_type is not None:
            sk = f"{parsed_id}:{parsed_type}"
            if any(source_sync_key(s) == sk for s in sources) and sk not in seen:
                out.append(sk)
                seen.add(sk)
            continue
        matches = [s for s in sources if s.id == parsed_id]
        if not matches:
            continue
        for s in matches:
            sk = source_sync_key(s)
            if sk not in seen:
                out.append(sk)
                seen.add(sk)
    return out


def is_known_sync_key(key: str, sources: list[Source]) -> bool:
    sk = (key or "").strip()
    if not sk:
        return False
    if any(source_sync_key(s) == sk for s in sources):
        return True
    parsed_id, parsed_type = parse_sync_key(sk)
    return parsed_type is None and any(s.id == parsed_id for s in sources)


def source_display_label(source: Source) -> str:
    st = (source.source_type or "local").strip().lower()
    cn = {"local": "本地", "github": "远程", "web": "网页"}.get(st, st)
    if source.id.endswith("-default"):
        owner = (source.owner or "")
        return f"{owner}默认库" if owner else "默认库"
    return f"{source.id}:{cn}"
