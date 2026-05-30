import mimetypes
from pathlib import Path

from fastapi import HTTPException

from ..db import WIKI_DIR
from .indexer import load_sources, resolve_source_root

ASSET_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".svg",
    ".bmp",
    ".ico",
    ".avif",
}


def _is_external_src(src: str) -> bool:
    s = (src or "").strip().lower()
    return s.startswith(("http://", "https://", "data:", "mailto:"))


def _safe_resolve_under_root(root: Path, target: Path) -> Path:
    root_resolved = root.resolve()
    target_resolved = target.resolve()
    try:
        target_resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="path traversal denied") from exc
    return target_resolved


def resolve_document_asset(source_id: str, from_rel_path: str, src: str) -> Path:
    if _is_external_src(src):
        raise ValueError("external")

    sources = {s.id: s for s in load_sources()}
    source = sources.get(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="source not found")

    root = resolve_source_root(source)
    if not root.exists():
        fallback = Path("/sources") / source_id
        if fallback.exists():
            root = fallback
    if not root.exists():
        raise HTTPException(status_code=404, detail="source root missing")

    rel_doc = (from_rel_path or "").replace("\\", "/")
    doc_parent = Path(rel_doc).parent
    raw_src = src.strip().replace("\\", "/")

    candidates: list[Path] = [
        (root / doc_parent / raw_src).resolve(),
        (root / raw_src).resolve(),
        (root / raw_src.lstrip("./")).resolve(),
    ]
    if raw_src.startswith("/"):
        candidates.append((root / raw_src.lstrip("/")).resolve())

    seen: set[str] = set()
    target: Path | None = None
    for candidate in candidates:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        try:
            resolved = _safe_resolve_under_root(root, candidate)
        except HTTPException:
            continue
        if resolved.is_file():
            target = resolved
            break

    if not target:
        raise HTTPException(status_code=404, detail="asset not found")

    if target.suffix.lower() not in ASSET_EXTENSIONS:
        raise HTTPException(status_code=415, detail="unsupported asset type")

    return target


def resolve_wiki_asset(wiki_page_rel: str, src: str) -> Path:
    if _is_external_src(src):
        raise ValueError("external")

    page = (wiki_page_rel or "").strip().replace("\\", "/")
    if not page:
        raise HTTPException(status_code=400, detail="wiki path required")

    raw_src = src.strip().replace("\\", "/")
    page_parent = Path(page).parent
    candidates = [
        WIKI_DIR / page_parent / raw_src,
        WIKI_DIR / raw_src,
    ]

    target: Path | None = None
    for candidate in candidates:
        resolved = _safe_resolve_under_root(WIKI_DIR, candidate)
        if resolved.is_file():
            target = resolved
            break

    if not target:
        raise HTTPException(status_code=404, detail="asset not found")

    if target.suffix.lower() not in ASSET_EXTENSIONS:
        raise HTTPException(status_code=415, detail="unsupported asset type")

    return target


def guess_media_type(path: Path) -> str:
    media, _ = mimetypes.guess_type(str(path))
    if media:
        return media
    suffix = path.suffix.lower()
    if suffix == ".svg":
        return "image/svg+xml"
    return "application/octet-stream"
