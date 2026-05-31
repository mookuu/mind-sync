from pathlib import Path

from .indexer import load_sources, resolve_source_root


def collect_source_warnings() -> list[str]:
    warnings: list[str] = []
    sources = load_sources()
    if not sources:
        warnings.append("sources.yaml has no sources configured")
        return warnings
    for source in sources:
        root = resolve_source_root(source)
        if not root.exists():
            warnings.append(f"source '{source.id}' path missing: {root}")
            continue
        if root.is_dir():
            try:
                has_files = any(p.is_file() for p in root.rglob("*"))
            except OSError:
                has_files = False
            if not has_files:
                warnings.append(f"source '{source.id}' directory is empty: {root}")
        elif source.source_type not in {"local"}:
            warnings.append(
                f"source '{source.id}' type '{source.source_type}' is not fully implemented; mount files at {root}"
            )
    return warnings


def source_health_status(warnings: list[str] | None = None) -> str:
    items = warnings if warnings is not None else collect_source_warnings()
    if not items:
        return "ok"
    if any("missing" in w or "empty" in w or "no sources" in w for w in items):
        return "degraded"
    return "ok"
