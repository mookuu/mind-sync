from pathlib import Path

from .base import SourceAdapter, SourceSpec


class WebPageAdapter(SourceAdapter):
    """
    Placeholder for future web-page ingestion adapter.
    Current strategy: treat pre-downloaded files under /sources/<id>.
    """

    def resolve_root(self, source: SourceSpec) -> Path:
        return Path("/sources") / source.id

