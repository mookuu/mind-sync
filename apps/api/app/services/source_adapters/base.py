from dataclasses import dataclass
from pathlib import Path


@dataclass
class SourceSpec:
    id: str
    source_type: str
    path: str | None
    url: str | None
    include: list[str]
    branch: str = "main"
    paths: list[str] | None = None
    order: int | None = None


class SourceAdapter:
    def resolve_root(self, source: SourceSpec) -> Path:
        raise NotImplementedError

