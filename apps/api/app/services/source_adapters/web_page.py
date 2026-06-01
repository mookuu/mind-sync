from pathlib import Path

from ...db import DATA_DIR
from .base import SourceAdapter, SourceSpec


class WebPageAdapter(SourceAdapter):
    """Cached snapshot lives under DATA_DIR/web-cache/<id>/."""

    def resolve_root(self, source: SourceSpec) -> Path:
        cache = DATA_DIR / "web-cache" / source.id
        if cache.is_dir():
            return cache
        fallback = Path("/sources") / source.id
        if fallback.exists():
            return fallback
        return cache
