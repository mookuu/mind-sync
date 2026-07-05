"""Shared wiki path safety utilities for mind-sync API."""
from pathlib import Path
from fastapi import HTTPException


def resolve_wiki_prefix(path: str, username: str | None = None) -> str:
    """Determine whether a wiki path is shared or user-private.

    - path starts with 'shared/' → shared wiki
    - path starts with 'users/<name>/' → user wiki (check permission)
    - otherwise → shared wiki (default)

    Returns the effective path prefix: 'shared/' or 'users/<username>/'
    """
    norm = (path or "").strip().replace("\\", "/")
    if norm.startswith("users/"):
        parts = norm.split("/")
        if len(parts) >= 2:
            requested_user = parts[1]
            if requested_user == username:
                return f"users/{username}/"
            raise HTTPException(status_code=403, detail="无权访问其他用户的 Wiki")
    return "shared/"


def safe_wiki_path(rel: str, wiki_dir: Path, *, must_exist: bool = True, username: str | None = None, role: str | None = None) -> Path:
    """Validate and resolve a relative wiki path, ensuring no directory traversal.

    当路径以 'users/' 开头时，检查当前用户是否匹配（隔离检查）。
    admin 角色不受此限制（可访问任何用户 Wiki）。

    Args:
        must_exist: If True (default), raises 404 when file does not exist.
        username: Current user name for namespace isolation.
        role: Current user role ('admin' bypasses isolation).
    Raises HTTPException(400/403/404) on validation/permission/not-found errors.
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
    # 用户 Wiki 隔离检查
    if norm.startswith("users/"):
        if len(parts) >= 2:
            requested_user = parts[1]
            if role != "admin" and requested_user != (username or ""):
                raise HTTPException(status_code=403, detail="无权访问其他用户的 Wiki")
    target = (wiki_dir / norm).resolve()
    try:
        target.relative_to(wiki_dir.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid wiki path")
    if must_exist and (not target.exists() or not target.is_file()):
        raise HTTPException(status_code=404, detail="wiki page not found")
    return target
