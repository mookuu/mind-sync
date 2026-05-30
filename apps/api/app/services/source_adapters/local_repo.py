from pathlib import Path

from .base import SourceAdapter, SourceSpec


class LocalRepoAdapter(SourceAdapter):
    def resolve_root(self, source: SourceSpec) -> Path:
        if not source.path:
            return Path("")
        return Path(source.path)

