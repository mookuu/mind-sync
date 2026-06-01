"""Shared wiki path safety utilities for mind-sync API."""
from pathlib import Path
from fastapi import HTTPException


def safe_wiki_path(rel: str, wiki_dir: Path) -> Path:
    """Validate and resolve a relative wiki path, ensuring no directory traversal.

    Args:
        must_exist: If True (default), raises 404 when file does not exist.
    Raises HTTPException(400) if the path is invalid or attempts traversal.
    Returns the resolved absolute Path within wiki_dir.
    """
    norm = (rel or "").strip().replace("\\", "/")
    if not norm:
        raise HTTPException(status_code=400, detail="path is required")
    # Reject path traversal sequences
    parts = norm.split("/")
    if ".." in parts:
        raise HTTPException(status_code=400, detail="invalid wiki path")
    if not norm.lower().endswith(".md"):
        raise HTTPException(status_code=400, detail="only .md wiki pages are supported")
    target = (wiki_dir / norm).resolve()
    try:
        target.relative_to(wiki_dir.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid wiki path")
    if must_exist and (not target.exists() or not target.is_file()):
        raise HTTPException(status_code=404, detail="wiki page not found")
    return target
