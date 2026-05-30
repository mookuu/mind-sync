import hashlib
import os
import sqlite3
import time
from pathlib import Path
from typing import Any

import yaml

from ..config import settings
from ..models import Source
from .source_adapters import resolve_source_root as adapter_resolve_source_root
from .source_adapters.base import SourceSpec


def load_sources() -> list[Source]:
    src_file = Path(settings.sources_file)
    if not src_file.exists():
        return []
    raw = yaml.safe_load(src_file.read_text(encoding="utf-8")) or {}
    result: list[Source] = []
    for item in raw.get("sources", []):
        result.append(
            Source(
                id=item["id"],
                source_type=item.get("type", "local"),
                path=item.get("path"),
                url=item.get("url"),
                include=item.get("include", ["**/*.md"]),
            )
        )
    return result


def resolve_source_root(source: Source) -> Path:
    spec = SourceSpec(
        id=source.id,
        source_type=source.source_type,
        path=source.path,
        url=source.url,
        include=source.include,
    )
    p = adapter_resolve_source_root(spec)
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
    raw = path.read_bytes()
    for enc in ("utf-8", "utf-8-sig", "utf-16", "utf-16-le", "utf-16-be", "gb18030", "gbk"):
        try:
            text = raw.decode(enc)
            bad_ratio = text.count("�") / max(len(text), 1)
            if enc.startswith("utf-8") and bad_ratio > 0.01:
                continue
            return text
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


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
) -> None:
    title = Path(rel_path).name
    now = time.time()
    conn.execute(
        """
        INSERT INTO documents(source_id, rel_path, title, content, lang, mtime, size, sha1, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_id, rel_path) DO UPDATE SET
            title=excluded.title,
            content=excluded.content,
            lang=excluded.lang,
            mtime=excluded.mtime,
            size=excluded.size,
            sha1=excluded.sha1,
            updated_at=excluded.updated_at
        """,
        (source_id, rel_path, title, content, lang, mtime, size, sha1, now),
    )
    row = conn.execute(
        "SELECT id FROM documents WHERE source_id = ? AND rel_path = ?",
        (source_id, rel_path),
    ).fetchone()
    doc_id = row["id"]
    conn.execute("DELETE FROM documents_fts WHERE rowid = ?", (doc_id,))
    conn.execute(
        "INSERT INTO documents_fts(rowid, title, content, rel_path, source_id) VALUES (?, ?, ?, ?, ?)",
        (doc_id, title, content, rel_path, source_id),
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
        upsert_document(conn, source.id, rel_path, content, mtime, size, sha1, language_from_suffix(f))
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
