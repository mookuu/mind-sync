"""Pair github/local sources that share the same origin directory or id."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from ..models import Source
from .indexer import resolve_source_root
from .source_adapters.github_repo import resolve_github_clone_dir
from .source_spec_util import source_to_spec


@dataclass
class SourcePair:
    github: Source
    local: Source | None
    match_reason: str


@dataclass
class SyncPlan:
    pairs: list[SourcePair] = field(default_factory=list)
    standalone: list[Source] = field(default_factory=list)
    skipped_locals: list[Source] = field(default_factory=list)


def github_repo_basename(url: str | None) -> str:
    raw = (url or "").strip().rstrip("/")
    if not raw:
        return ""
    if raw.endswith(".git"):
        raw = raw[:-4]
    path = urlparse(raw).path.strip("/")
    if not path:
        return ""
    return path.split("/")[-1]


def _github_root(source: Source) -> Path:
    return resolve_github_clone_dir(source_to_spec(source))


def _same_path(a: Path, b: Path) -> bool:
    try:
        return a.resolve() == b.resolve()
    except OSError:
        return str(a).replace("\\", "/") == str(b).replace("\\", "/")


def _pair_reason(github: Source, local: Source) -> str | None:
    if github.id == local.id:
        return "same_id"
    gh_root = _github_root(github)
    local_root = resolve_source_root(local)
    if _same_path(gh_root, local_root):
        return "same_path"
    repo_name = github_repo_basename(github.url)
    if repo_name and repo_name == local.id:
        return "repo_name"
    if repo_name and local.path and repo_name in local.path.replace("\\", "/"):
        return "repo_name"
    return None


def build_sync_plan(sources: list[Source]) -> SyncPlan:
    github_sources = [s for s in sources if (s.source_type or "local").lower() == "github"]
    local_sources = [s for s in sources if (s.source_type or "local").lower() == "local"]
    web_sources = [s for s in sources if (s.source_type or "local").lower() == "web"]
    other_sources = [
        s
        for s in sources
        if (s.source_type or "local").lower() not in {"github", "local", "web"}
    ]

    used_local_ids: set[str] = set()
    pairs: list[SourcePair] = []

    for github in github_sources:
        matched: Source | None = None
        reason = ""
        for local in local_sources:
            if local.id in used_local_ids:
                continue
            why = _pair_reason(github, local)
            if why:
                matched = local
                reason = why
                break
        if matched:
            used_local_ids.add(matched.id)
            pairs.append(SourcePair(github=github, local=matched, match_reason=reason))
        else:
            pairs.append(SourcePair(github=github, local=None, match_reason="github_only"))

    skipped_locals = [s for s in local_sources if s.id in used_local_ids]
    standalone_locals = [s for s in local_sources if s.id not in used_local_ids]

    plan = SyncPlan(
        pairs=pairs,
        standalone=standalone_locals + web_sources + other_sources,
        skipped_locals=skipped_locals,
    )
    return plan


def resolve_ingest_sources(
    sources: list[Source],
    *,
    source_id_filter: str | None = None,
) -> tuple[list[Source], list[str]]:
    """De-duplicate github/local pairs the same way sync indexes (skip paired locals)."""
    plan = build_sync_plan(sources)
    skipped_ids = {s.id for s in plan.skipped_locals}
    warnings: list[str] = []
    candidates: list[Source] = []
    for pair in plan.pairs:
        candidates.append(pair.github)
    candidates.extend(plan.standalone)

    if source_id_filter:
        matched = [s for s in candidates if s.id == source_id_filter]
        return matched, warnings

    for sid in sorted(skipped_ids):
        warnings.append(
            f"ingest skipped paired local source '{sid}' (indexed via github entry)"
        )
    return candidates, warnings


def resolve_index_source(pair: SourcePair, pull_result: dict[str, Any]) -> tuple[Source | None, str | None, str | None]:
    """Choose which source id to index and optional warning/skip reason."""
    gh_ok = bool(pull_result.get("ok"))
    gh_root = _github_root(pair.github)

    if gh_ok:
        return pair.github, None, None

    err = pull_result.get("error") or "github pull failed"
    if pair.local is not None:
        local_root = resolve_source_root(pair.local)
        if local_root.exists() and any(local_root.rglob("*")):
            warning = (
                f"source '{pair.github.id}' github pull failed ({err}); "
                f"fallback to local '{pair.local.id}' at {local_root}"
            )
            return pair.local, warning, None
        warning = (
            f"source '{pair.github.id}' github pull failed ({err}); "
            f"local fallback '{pair.local.id}' missing or empty at {local_root}"
        )
        return None, warning, "missing"

    if gh_root.exists() and any(gh_root.rglob("*")):
        warning = f"source '{pair.github.id}' github pull failed ({err}); indexing existing files at {gh_root}"
        return pair.github, warning, None

    warning = f"source '{pair.github.id}' github pull failed ({err}); no local fallback configured"
    return None, warning, "missing"
