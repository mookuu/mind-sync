from pathlib import Path

from ...db import DATA_DIR
from .base import SourceAdapter, SourceSpec


def resolve_github_clone_dir(source: SourceSpec) -> Path:
    """GitHub clone/pull target; defaults to /sources/<id> like local sources."""
    if source.path:
        return Path(source.path)
    return Path("/sources") / source.id


class GitHubRepoAdapter(SourceAdapter):
    """Resolved path is the local clone under source.path or /sources/<id>."""

    def resolve_root(self, source: SourceSpec) -> Path:
        clone = resolve_github_clone_dir(source)
        if clone.is_dir():
            if source.paths:
                first = source.paths[0].strip("/\\")
                nested = clone / first
                if nested.is_dir():
                    return nested
            return clone
        legacy = DATA_DIR / "repos" / source.id
        if legacy.is_dir():
            if source.paths:
                first = source.paths[0].strip("/\\")
                nested = legacy / first
                if nested.is_dir():
                    return nested
            return legacy
        return clone
