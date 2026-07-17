import hashlib
import os
import sqlite3
import time
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from ..config import settings
from ..models import Source
from .source_adapters import resolve_source_root as adapter_resolve_source_root
from .source_spec_util import source_to_spec
from .chinese_tokenizer import tokenize


_SOURCES_CACHE_TIME = 0.0
_SOURCES_CACHE_TTL = 30  # seconds


def _reset_sources_cache() -> None:
    """Clear the cached sources list. Called after sources.yaml could have changed."""
    _load_sources_cached.cache_clear()


def reload_sources_config() -> list[Source]:
    """Force reload sources.yaml from disk (admin reload API)."""
    _reset_sources_cache()
    return load_sources()


@lru_cache(maxsize=1)
def _load_sources_cached(cache_key: float) -> list[Source]:
    """Internal: read and parse sources.yaml + user_sources.yaml. The cache_key is a coarse timestamp bucket."""
    result: list[Source] = []

    def _parse_items(items: list) -> None:
        for item in items:
            if not isinstance(item, dict):
                continue
            try:
                result.append(
                    Source(
                        id=item["id"],
                        source_type=item.get("type", "local"),
                        path=item.get("path"),
                        url=item.get("url"),
                        include=item.get("include", ["**/*.md"]),
                        branch=item.get("branch", "main"),
                        paths=item.get("paths"),
                        order=item.get("order"),
                        fetch_confirmed=bool(item.get("fetch_confirmed", False)),
                        respect_robots=item.get("respect_robots"),
                        owner=item.get("owner"),
                        shared=bool(item.get("shared", False)),
                    )
                )
            except (KeyError, TypeError):
                continue  # Skip malformed entries

    # 1) Load shared sources.yaml
    src_file = Path(settings.sources_file)
    if src_file.exists():
        raw = yaml.safe_load(src_file.read_text(encoding="utf-8")) or {}
        _parse_items(raw.get("sources", []))

    # 2) Load user-specific sources (private sources, always writable)
    user_src_file = Path(settings.data_dir) / "config" / "user_sources.yaml"
    _deleted_sources: set = set()
    if user_src_file.exists():
        raw = yaml.safe_load(user_src_file.read_text(encoding="utf-8")) or {}
        _parse_items(raw.get("sources", []))
        _deleted_sources = set(raw.get("_deleted", []))

    # 过滤掉已标记删除的源
    if _deleted_sources:
        result = [s for s in result if s.id not in _deleted_sources]

    return result


def load_sources() -> list[Source]:
    bucket = int(time.time() / _SOURCES_CACHE_TTL)
    return _load_sources_cached(bucket)


def load_sources_for_user(username: str | None = None, role: str | None = None) -> list[Source]:
    """返回当前用户可见的源列表。

    - admin → 全部源（含私有）
    - member → 已共享的全局源（shared=True） + 自己的私有源（owner=username）
       + 其他用户设为共享的源（shared=True 且 owner≠username）
    - 未登录（username=None） → 仅已共享全局源
    """
    all_sources = load_sources()
    if role and role.strip().lower() == "admin":
        return all_sources
    if not username:
        return [s for s in all_sources if s.owner is None and s.shared]
    return [
        s for s in all_sources
        if (s.owner is None and s.shared) or s.owner == username or (s.shared and s.owner is not None)
    ]


def resolve_source_root(source: Source) -> Path:
    p = adapter_resolve_source_root(source_to_spec(source))
    if p.exists():
        return p
    fallback = Path("/sources") / source.id
    if fallback.exists():
        return fallback
    return p

def language_from_suffix(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".md":
        return "markdown"
    if suffix == ".py":
        return "python"
    if suffix == ".java":
        return "java"
    return suffix.lstrip(".") or "text"


def read_text_safely(path: Path) -> str:
    enc = _detect_encoding(str(path))
    return path.read_bytes().decode(enc, errors="replace")


@lru_cache(maxsize=256)
def _detect_encoding(path_key: str) -> str:
    """Detect encoding for a file, caching the result by path."""
    raw = Path(path_key).read_bytes()
    for enc in ("utf-8", "utf-8-sig", "utf-16", "utf-16-le", "utf-16-be", "gb18030", "gbk"):
        try:
            text = raw.decode(enc)
            bad_ratio = text.count(chr(0xfffd)) / max(len(text), 1)
            if enc.startswith("utf-8") and bad_ratio > 0.01:
                continue
            return enc
        except UnicodeDecodeError:
            continue
    return "utf-8"


def collect_files(root: Path, includes: list[str]) -> list[Path]:
    extension_patterns = [p for p in includes if p.startswith("**/*.")]
    if extension_patterns and len(extension_patterns) == len(includes):
        exts = {"." + p.split(".")[-1].lower() for p in extension_patterns}
        skip_dirs = {
            ".git",
            "node_modules",
            ".venv",
            "venv",
            ".idea",
            ".vscode",
            "dist",
            "build",
            "target",
            "__pycache__",
        }
        files: list[Path] = []
        for dir_path, dir_names, file_names in os.walk(root):
            dir_names[:] = [d for d in dir_names if d not in skip_dirs]
            base = Path(dir_path)
            for name in file_names:
                p = base / name
                if p.suffix.lower() in exts:
                    files.append(p)
        return sorted(files)

    files_set: set[Path] = set()
    for pattern in includes:
        for p in root.glob(pattern):
            if p.is_file():
                files_set.add(p)
    return sorted(files_set)


def upsert_document(
    conn: sqlite3.Connection,
    source_id: str,
    rel_path: str,
    content: str,
    mtime: float,
    size: int,
    sha1: str,
    lang: str,
    source_owner: str = "__shared__",
) -> None:
    title = Path(rel_path).name
    now = time.time()
    # Pre-tokenize Chinese text for FTS5
    title_fts = tokenize(title)
    content_fts = tokenize(content)
    conn.execute(
        """
        INSERT INTO documents(source_id, rel_path, title, content, lang, mtime, size, sha1, source_owner, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_id, rel_path) DO UPDATE SET
            title=excluded.title,
            content=excluded.content,
            lang=excluded.lang,
            mtime=excluded.mtime,
            size=excluded.size,
            sha1=excluded.sha1,
            source_owner=excluded.source_owner,
            updated_at=excluded.updated_at
        """,
        (source_id, rel_path, title, content, lang, mtime, size, sha1, source_owner, now),
    )
    row = conn.execute(
        "SELECT id FROM documents WHERE source_id = ? AND rel_path = ?",
        (source_id, rel_path),
    ).fetchone()
    doc_id = row["id"]
    conn.execute("DELETE FROM documents_fts WHERE rowid = ?", (doc_id,))
    conn.execute(
        "INSERT INTO documents_fts(rowid, title, content, rel_path, source_id, source_owner) VALUES (?, ?, ?, ?, ?, ?)",
        (doc_id, title_fts, content_fts, rel_path, source_id, source_owner),
    )


def update_document_metadata(conn: sqlite3.Connection, source_id: str, rel_path: str, mtime: float, size: int) -> None:
    conn.execute(
        "UPDATE documents SET mtime = ?, size = ? WHERE source_id = ? AND rel_path = ?",
        (mtime, size, source_id, rel_path),
    )


def remove_missing(conn: sqlite3.Connection, source_id: str, existing: set[str]) -> int:
    rows = conn.execute("SELECT id, rel_path FROM documents WHERE source_id = ?", (source_id,)).fetchall()
    removed = 0
    for row in rows:
        if row["rel_path"] not in existing:
            conn.execute("DELETE FROM documents WHERE id = ?", (row["id"],))
            conn.execute("DELETE FROM documents_fts WHERE rowid = ?", (row["id"],))
            removed += 1
    return removed


def clear_source_index(conn: sqlite3.Connection, source_id: str) -> int:
    """Remove all indexed documents (and FTS rows) for one source."""
    rows = conn.execute("SELECT id FROM documents WHERE source_id = ?", (source_id,)).fetchall()
    for row in rows:
        conn.execute("DELETE FROM documents_fts WHERE rowid = ?", (row["id"],))
        conn.execute("DELETE FROM documents WHERE id = ?", (row["id"],))
    return len(rows)


def index_single_source_force(
    conn: sqlite3.Connection,
    source: Source,
    rel_path_filter: str | None = None,
) -> dict[str, Any]:
    """Re-read every file and rewrite index entries (no mtime/sha1 skip)."""
    root = resolve_source_root(source)
    if not root.exists():
        return {"source_id": source.id, "status": "missing", "indexed": 0, "deleted": 0, "scanned": 0, "skipped": 0}

    files = collect_files(root, source.include)
    existing: set[str] = set()
    scanned = 0
    indexed = 0
    skipped = 0
    for f in files:
        rel_path = str(f.relative_to(root)).replace("\\", "/")
        if rel_path_filter and rel_path != rel_path_filter:
            continue
        scanned += 1
        existing.add(rel_path)
        stat = f.stat()
        mtime = stat.st_mtime
        size = int(stat.st_size)
        if size > int(settings.max_index_file_bytes):
            skipped += 1
            continue
        content = read_text_safely(f)
        sha1 = hashlib.sha1(content.encode("utf-8", errors="ignore")).hexdigest()
        upsert_document(conn, source.id, rel_path, content, mtime, size, sha1, language_from_suffix(f), source_owner=source.owner or "__shared__")
        indexed += 1
    deleted = 0 if rel_path_filter else remove_missing(conn, source.id, existing)
    return {
        "source_id": source.id,
        "status": "ok",
        "indexed": indexed,
        "skipped": skipped,
        "deleted": deleted,
        "scanned": scanned,
    }


def index_single_source(conn: sqlite3.Connection, source: Source, rel_path_filter: str | None = None) -> dict[str, Any]:
    root = resolve_source_root(source)
    if not root.exists():
        return {"source_id": source.id, "status": "missing", "indexed": 0, "deleted": 0, "scanned": 0}

    files = collect_files(root, source.include)
    existing: set[str] = set()
    scanned = 0
    indexed = 0
    skipped = 0
    for f in files:
        rel_path = str(f.relative_to(root)).replace("\\", "/")
        if rel_path_filter and rel_path != rel_path_filter:
            continue
        scanned += 1
        existing.add(rel_path)
        stat = f.stat()
        mtime = stat.st_mtime
        size = int(stat.st_size)
        if size > int(settings.max_index_file_bytes):
            skipped += 1
            continue
        old = conn.execute(
            "SELECT mtime, size, sha1 FROM documents WHERE source_id = ? AND rel_path = ?",
            (source.id, rel_path),
        ).fetchone()
        if old and abs(float(old["mtime"]) - float(mtime)) < 1e-9 and int(old["size"]) == size:
            skipped += 1
            continue
        content = read_text_safely(f)
        sha1 = hashlib.sha1(content.encode("utf-8", errors="ignore")).hexdigest()
        if old and old["sha1"] == sha1:
            update_document_metadata(conn, source.id, rel_path, mtime, size)
            skipped += 1
            continue
        upsert_document(conn, source.id, rel_path, content, mtime, size, sha1, language_from_suffix(f), source_owner=source.owner or "__shared__")
        indexed += 1
    deleted = 0 if rel_path_filter else remove_missing(conn, source.id, existing)
    return {
        "source_id": source.id,
        "status": "ok",
        "indexed": indexed,
        "skipped": skipped,
        "deleted": deleted,
        "scanned": scanned,
    }


def snippet_from_content(content: str, query: str, window: int = 80) -> str:
    if not content:
        return ""
    idx = content.find(query)
    if idx < 0:
        return content[: min(len(content), window * 2)]
    start = max(0, idx - window)
    end = min(len(content), idx + len(query) + window)
    excerpt = content[start:end]
    return excerpt.replace(query, f"<mark>{query}</mark>")
