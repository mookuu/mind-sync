from pathlib import Path

from ...db import DATA_DIR
from .base import SourceAdapter, SourceSpec


class GitHubRepoAdapter(SourceAdapter):
    """Resolved path is the local clone under DATA_DIR/repos/<id>."""

    def resolve_root(self, source: SourceSpec) -> Path:
        clone = DATA_DIR / "repos" / source.id
        if clone.is_dir():
            if source.paths:
                first = source.paths[0].strip("/\\")
                nested = clone / first
                if nested.is_dir():
                    return nested
            return clone
        fallback = Path("/sources") / source.id
        if fallback.exists():
            return fallback
        return clone
