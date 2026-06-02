from pathlib import Path

from ...db import DATA_DIR
from .base import SourceAdapter, SourceSpec


def resolve_web_output_dir(source: SourceSpec) -> Path:
    if source.path:
        return Path(source.path)
    return Path("/sources/web_snapshots") / source.id


class WebPageAdapter(SourceAdapter):
    """Cached snapshot lives under source.path or /sources/web_snapshots/<id>."""

    def resolve_root(self, source: SourceSpec) -> Path:
        cache = resolve_web_output_dir(source)
        if cache.is_dir():
            return cache
        legacy = DATA_DIR / "web-cache" / source.id
        if legacy.is_dir():
            return legacy
        fallback = Path("/sources") / source.id
        if fallback.exists():
            return fallback
        return cache
