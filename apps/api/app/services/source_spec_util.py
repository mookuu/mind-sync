"""Convert Source model to SourceSpec for adapters."""

from __future__ import annotations

from ..models import Source
from .source_adapters.base import SourceSpec


def source_to_spec(source: Source) -> SourceSpec:
    return SourceSpec(
        id=source.id,
        source_type=source.source_type,
        path=source.path,
        url=source.url,
        include=source.include,
        branch=source.branch,
        paths=source.paths,
        order=source.order,
    )
