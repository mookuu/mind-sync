"""User management utilities: directory creation, deletion, source registration."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from ..config import settings
from ..db import get_db


# 私有源独立存储文件（sources.yaml 可能只读，私有源写到此文件）
_USER_SOURCES_FILE = Path(settings.data_dir) / "config" / "user_sources.yaml"

# 用户专属目录根路径（宿主机视角：~/data/mind-sync-data/users/ 对应容器内 /data/users/）
_USER_ROOT = Path(settings.data_root) / "users" if settings.data_root else Path(settings.data_dir) / "users"


def get_user_sources_path() -> Path:
    return _USER_SOURCES_FILE


def load_user_sources() -> list[dict[str, Any]]:
    """Read user-specific sources from the separate YAML file."""
    import yaml
    if not _USER_SOURCES_FILE.is_file():
        return []
    try:
        raw = _USER_SOURCES_FILE.read_text(encoding="utf-8")
        config = yaml.safe_load(raw) or {}
        return config.get("sources", []) or []
    except Exception:
        return []


def get_user_dir(username: str) -> Path:
    """Return the user's personal directory path."""
    return _USER_ROOT / username / "default"


def ensure_user_dir(username: str) -> Path:
    """Create user's personal directory and return path."""
    udir = get_user_dir(username)
    udir.mkdir(parents=True, exist_ok=True)
    # Also create user wiki directory
    from ..db import WIKI_DIR
    user_wiki = WIKI_DIR / "users" / username
    user_wiki.mkdir(parents=True, exist_ok=True)
    return udir


def remove_user_dir(username: str) -> None:
    """Remove user's personal directory and all contents."""
    udir = get_user_dir(username)
    if udir.exists():
        import shutil
        shutil.rmtree(str(udir))


def build_user_source_entry(username: str) -> dict[str, Any]:
    """Build a sources.yaml entry for the user's default private source."""
    udir = get_user_dir(username)
    return {
        "id": f"{username}-default",
        "label": "默认",
        "type": "local",
        "owner": username,
        "path": str(udir),
        "include": ["**/*.md", "**/*.py", "**/*.java", "**/*.txt"],
    }


def append_user_source_to_yaml(source_entry: dict[str, Any]) -> None:
    """Append a private source entry to user_sources.yaml (不在 sources.yaml 写入，因可能只读)。"""
    import yaml
    _USER_SOURCES_FILE.parent.mkdir(parents=True, exist_ok=True)
    if _USER_SOURCES_FILE.is_file():
        raw = _USER_SOURCES_FILE.read_text(encoding="utf-8")
        config = yaml.safe_load(raw) or {}
    else:
        config = {}
    sources: list = config.get("sources", []) or []
    # Avoid duplicates
    for s in sources:
        if isinstance(s, dict) and s.get("id") == source_entry["id"]:
            return
    sources.append(source_entry)
    config["sources"] = sources
    _USER_SOURCES_FILE.write_text(yaml.dump(config, allow_unicode=True, default_flow_style=False, sort_keys=False), encoding="utf-8")


def toggle_source_shared(username: str, source_id: str) -> bool:
    """Toggle the shared flag of a user's source. Returns new shared state."""
    import yaml
    if not _USER_SOURCES_FILE.is_file():
        raise FileNotFoundError(f"User sources file not found: {_USER_SOURCES_FILE}")
    raw = _USER_SOURCES_FILE.read_text(encoding="utf-8")
    config = yaml.safe_load(raw) or {}
    sources: list = config.get("sources", []) or []
    for s in sources:
        if isinstance(s, dict) and s.get("id") == source_id and s.get("owner") == username:
            current = bool(s.get("shared", False))
            s["shared"] = not current
            config["sources"] = sources
            _USER_SOURCES_FILE.write_text(yaml.dump(config, allow_unicode=True, default_flow_style=False, sort_keys=False), encoding="utf-8")
            return not current
    raise ValueError(f"Source not found or not owned by user: {source_id}")


def remove_user_source_from_yaml(username: str) -> None:
    """Remove all private sources owned by a user from user_sources.yaml."""
    import yaml
    if not _USER_SOURCES_FILE.is_file():
        return
    raw = _USER_SOURCES_FILE.read_text(encoding="utf-8")
    config = yaml.safe_load(raw) or {}
    sources: list = config.get("sources", []) or []
    sources = [s for s in sources if isinstance(s, dict) and s.get("owner") != username]
    config["sources"] = sources
    _USER_SOURCES_FILE.write_text(yaml.dump(config, allow_unicode=True, default_flow_style=False, sort_keys=False), encoding="utf-8")


def delete_user_index_data(username: str) -> None:
    """Delete all indexed documents owned by a user."""
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT id FROM documents WHERE source_owner = ?", (username,)
        ).fetchall()
        for row in rows:
            conn.execute("DELETE FROM documents_fts WHERE rowid = ?", (row["id"],))
            conn.execute("DELETE FROM documents WHERE id = ?", (row["id"],))
        conn.commit()
    finally:
        conn.close()
