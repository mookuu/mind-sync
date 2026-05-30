from dataclasses import dataclass
from pathlib import Path


@dataclass
class SourceSpec:
    id: str
    source_type: str
    path: str | None
    url: str | None
    include: list[str]


class SourceAdapter:
    def resolve_root(self, source: SourceSpec) -> Path:
        raise NotImplementedError

