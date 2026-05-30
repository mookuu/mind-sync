from pathlib import Path

from .base import SourceAdapter, SourceSpec


class GitHubRepoAdapter(SourceAdapter):
    """
    Placeholder for future remote GitHub adapter.
    Current strategy: return /sources/<id> mount if present.
    """

    def resolve_root(self, source: SourceSpec) -> Path:
        return Path("/sources") / source.id

