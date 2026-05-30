import hashlib
import json
import threading
import time
from typing import Any

from ..db import get_db
from .audit import add_audit_event_meta
from .indexer import (
    collect_files,
    language_from_suffix,
    load_sources,
    read_text_safely,
    remove_missing,
    resolve_source_root,
    update_document_metadata,
    upsert_document,
)

SYNC_LOCK = threading.Lock()
SYNC_STATE: dict[str, Any] = {
    "running": False,
    "started_at": None,
    "finished_at": None,
    "indexed": 0,
    "skipped": 0,
    "deleted": 0,
    "sources": [],
    "current_source": None,
    "processed_files": 0,
    "total_files": 0,
    "error": None,
}
LAST_SYNC_SUMMARY: dict[str, Any] = {
    "status": "idle",
    "trigger": None,
    "started_at": None,
    "finished_at": None,
    "indexed": 0,
    "skipped": 0,
    "deleted": 0,
    "error": None,
}


def _update_sync_counts(processed_files: int, indexed: int, skipped: int, deleted: int) -> None:
    with SYNC_LOCK:
        SYNC_STATE["processed_files"] = processed_files
        SYNC_STATE["indexed"] = indexed
        SYNC_STATE["skipped"] = skipped
        SYNC_STATE["deleted"] = deleted


def load_last_sync_summary() -> dict[str, Any]:
    conn = get_db()
    try:
        row = conn.execute("SELECT value FROM app_settings WHERE key = ?", ("last_sync_summary",)).fetchone()
        if not row:
            return {}
        data = json.loads(row["value"])
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}
    finally:
        conn.close()


def persist_last_sync_summary(summary: dict[str, Any]) -> None:
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO app_settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            ("last_sync_summary", json.dumps(summary, ensure_ascii=False)),
        )
        conn.commit()
    finally:
        conn.close()


def restore_last_sync_summary() -> None:
    loaded = load_last_sync_summary()
    if loaded:
        with SYNC_LOCK:
            LAST_SYNC_SUMMARY.clear()
            LAST_SYNC_SUMMARY.update(loaded)


def finalize_sync_run(trigger: str, started_at: float, result: dict[str, Any]) -> None:
    summary = {
        "status": "failed" if result.get("error") else "success",
        "trigger": trigger,
        "started_at": started_at,
        "finished_at": time.time(),
        "indexed": int(result.get("indexed", 0)),
        "skipped": int(result.get("skipped", 0)),
        "deleted": int(result.get("deleted", 0)),
        "error": result.get("error"),
    }
    with SYNC_LOCK:
        LAST_SYNC_SUMMARY.clear()
        LAST_SYNC_SUMMARY.update(summary)
    persist_last_sync_summary(summary)
    detail = (
        f"trigger={trigger} indexed={summary['indexed']} "
        f"skipped={summary['skipped']} deleted={summary['deleted']}"
    )
    if summary["error"]:
        detail += f" error={str(summary['error'])[:200]}"
    add_audit_event_meta("sync_completed", actor=trigger, ip="local", detail=detail)


def is_sync_running() -> bool:
    with SYNC_LOCK:
        return bool(SYNC_STATE["running"])


def get_sync_status_payload() -> dict[str, Any]:
    with SYNC_LOCK:
        data = dict(SYNC_STATE)
        data["last_completed"] = dict(LAST_SYNC_SUMMARY)
    return data


def run_sync_job(trigger: str = "manual", source_ids: list[str] | None = None) -> dict[str, Any]:
    if source_ids is None and trigger in ("manual", "auto"):
        from .sync_settings import resolve_sync_source_ids

        source_ids = resolve_sync_source_ids()

    started_at = time.time()
    with SYNC_LOCK:
        SYNC_STATE["running"] = True
        SYNC_STATE["started_at"] = time.time()
        SYNC_STATE["finished_at"] = None
        SYNC_STATE["indexed"] = 0
        SYNC_STATE["skipped"] = 0
        SYNC_STATE["deleted"] = 0
        SYNC_STATE["sources"] = []
        SYNC_STATE["current_source"] = None
        SYNC_STATE["processed_files"] = 0
        SYNC_STATE["total_files"] = 0
        SYNC_STATE["error"] = None

    conn = None
    indexed = 0
    skipped = 0
    deleted = 0
    source_stats = []
    run_error = None
    try:
        conn = get_db()
        all_sources = load_sources()
        if source_ids:
            allowed = set(source_ids)
            all_sources = [s for s in all_sources if s.id in allowed]
        for source in all_sources:
            root = resolve_source_root(source)
            if not root.exists():
                source_stats.append({"source_id": source.id, "status": "missing", "indexed": 0, "deleted": 0})
                continue
            files = collect_files(root, source.include)
            with SYNC_LOCK:
                SYNC_STATE["current_source"] = source.id
                SYNC_STATE["processed_files"] = 0
                SYNC_STATE["total_files"] = len(files)
            existing: set[str] = set()
            src_indexed = 0
            for i, f in enumerate(files, start=1):
                rel_path = str(f.relative_to(root)).replace("\\", "/")
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
                    if i % 200 == 0:
                        _update_sync_counts(i, indexed, skipped, deleted)
                    continue
                content = read_text_safely(f)
                sha1 = hashlib.sha1(content.encode("utf-8", errors="ignore")).hexdigest()
                if old and old["sha1"] == sha1:
                    update_document_metadata(conn, source.id, rel_path, mtime, size)
                    skipped += 1
                    if i % 200 == 0:
                        _update_sync_counts(i, indexed, skipped, deleted)
                    continue
                upsert_document(conn, source.id, rel_path, content, mtime, size, sha1, language_from_suffix(f))
                indexed += 1
                src_indexed += 1
                if i % 200 == 0:
                    _update_sync_counts(i, indexed, skipped, deleted)
            _update_sync_counts(len(files), indexed, skipped, deleted)
            removed = remove_missing(conn, source.id, existing)
            deleted += removed
            source_stats.append({"source_id": source.id, "status": "ok", "indexed": src_indexed, "deleted": removed})
            conn.commit()
        with SYNC_LOCK:
            SYNC_STATE["error"] = None
    except Exception as exc:
        if conn:
            conn.rollback()
        run_error = str(exc)
        with SYNC_LOCK:
            SYNC_STATE["error"] = run_error
    finally:
        if conn:
            conn.close()
        with SYNC_LOCK:
            SYNC_STATE["running"] = False
            SYNC_STATE["finished_at"] = time.time()
            SYNC_STATE["indexed"] = indexed
            SYNC_STATE["skipped"] = skipped
            SYNC_STATE["deleted"] = deleted
            SYNC_STATE["sources"] = source_stats
            SYNC_STATE["current_source"] = None
    result = {
        "indexed": indexed,
        "skipped": skipped,
        "deleted": deleted,
        "sources": source_stats,
        "error": run_error,
    }
    finalize_sync_run(trigger, started_at, result)
    return result
