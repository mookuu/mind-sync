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
    read_text_safely,
    remove_missing,
    resolve_source_root,
    update_document_metadata,
    upsert_document,
)
from .source_sync import sync_all_sources
from .source_sync_key import filter_sources_by_sync_keys
from .sync_settings import apply_source_order, load_ordered_sources
from .vault_git import pull_vault, push_vault, write_sources_manifest

SYNC_LOCK = threading.Lock()
SYNC_STATE: dict[str, Any] = {
    "running": False,
    "job_mode": "sync",
    "started_at": None,
    "finished_at": None,
    "indexed": 0,
    "skipped": 0,
    "deleted": 0,
    "cleared": 0,
    "sources": [],
    "current_source": None,
    "processed_files": 0,
    "total_files": 0,
    "error": None,
    "warnings": [],
}
LAST_SYNC_SUMMARY: dict[str, Any] = {
    "status": "idle",
    "mode": "sync",
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


def load_last_sync_summary(username: str = "") -> dict[str, Any]:
    conn = get_db()
    try:
        key = f"last_sync_summary_{username}" if username else "last_sync_summary"
        row = conn.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
        if not row:
            return {}
        data = json.loads(row["value"])
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}
    finally:
        conn.close()


def persist_last_sync_summary(summary: dict[str, Any], username: str = "") -> None:
    conn = get_db()
    try:
        key = f"last_sync_summary_{username}" if username else "last_sync_summary"
        conn.execute(
            "INSERT INTO app_settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, json.dumps(summary, ensure_ascii=False)),
        )
        conn.commit()
    finally:
        conn.close()
    # 同步更新内存
    with SYNC_LOCK:
        if username:
            LAST_SYNC_SUMMARY[username] = summary
        else:
            LAST_SYNC_SUMMARY[""] = summary


def restore_last_sync_summary(username: str = "") -> None:
    loaded = load_last_sync_summary(username)
    if loaded:
        with SYNC_LOCK:
            if username:
                LAST_SYNC_SUMMARY[username] = loaded
            else:
                LAST_SYNC_SUMMARY[""] = loaded


def finalize_sync_run(trigger: str, started_at: float, result: dict[str, Any], username: str = "") -> None:
    summary = {
        "status": "failed" if result.get("error") else "success",
        "mode": result.get("mode", "sync"),
        "trigger": trigger,
        "started_at": started_at,
        "finished_at": time.time(),
        "indexed": int(result.get("indexed", 0)),
        "skipped": int(result.get("skipped", 0)),
        "deleted": int(result.get("deleted", 0)),
        "cleared": int(result.get("cleared", 0)),
        "error": result.get("error"),
    }
    with SYNC_LOCK:
        LAST_SYNC_SUMMARY.clear()
        LAST_SYNC_SUMMARY.update(summary)
    persist_last_sync_summary(summary, username or "")
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


def get_sync_status_payload(username: str = "") -> dict[str, Any]:
    from .sync_backoff import list_backoff_status

    # 从 DB 加载上次同步记录（若内存为空则回退到 DB）
    u = username or ""
    if u not in LAST_SYNC_SUMMARY:
        restore_last_sync_summary(u)

    with SYNC_LOCK:
        data = dict(SYNC_STATE)
        data["last_completed"] = dict(LAST_SYNC_SUMMARY.get(u, {}))
    data["source_backoff"] = list_backoff_status()
    return data


def run_sync_job(
    trigger: str = "manual",
    source_ids: list[str] | None = None,
    *,
    username: str | None = None,
    vault_pull: bool = True,
    vault_push: bool = False,
) -> dict[str, Any]:
    if source_ids is None and trigger in ("manual", "auto"):
        from .sync_settings import resolve_sync_source_ids

        source_ids = resolve_sync_source_ids(username=username)

    started_at = time.time()
    with SYNC_LOCK:
        SYNC_STATE["running"] = True
        SYNC_STATE["job_mode"] = "sync"
        SYNC_STATE["started_at"] = time.time()
        SYNC_STATE["finished_at"] = None
        SYNC_STATE["indexed"] = 0
        SYNC_STATE["skipped"] = 0
        SYNC_STATE["deleted"] = 0
        SYNC_STATE["cleared"] = 0
        SYNC_STATE["sources"] = []
        SYNC_STATE["current_source"] = None
        SYNC_STATE["processed_files"] = 0
        SYNC_STATE["total_files"] = 0
        SYNC_STATE["error"] = None
        SYNC_STATE["warnings"] = []

    conn = None
    indexed = 0
    skipped = 0
    deleted = 0
    source_stats = []
    repo_sync: list[dict[str, Any]] = []
    vault_meta: dict[str, Any] = {}
    run_error = None
    sync_warnings: list[str] = []
    try:
        if vault_pull:
            vault_meta["pull"] = pull_vault()
        conn = get_db()
        from ..db import load_settings_map

        settings_map = load_settings_map(username)
        all_sources = load_ordered_sources(settings_map, username=username)
        if source_ids:
            all_sources = apply_source_order(
                filter_sources_by_sync_keys(all_sources, source_ids),
                settings_map,
            )
        remote_sync = sync_all_sources(all_sources)
        repo_sync = remote_sync.get("repo_sync", [])
        sync_warnings = list(remote_sync.get("warnings") or [])
        index_tasks = remote_sync.get("index_tasks") or []

        for task in index_tasks:
            source = task.get("source")
            task_warning = task.get("warning")
            if task_warning and task_warning not in sync_warnings:
                sync_warnings.append(task_warning)

            if source is None:
                gh_id = task.get("github_id") or "unknown"
                source_stats.append(
                    {
                        "source_id": gh_id,
                        "status": task.get("status", "missing"),
                        "indexed": 0,
                        "deleted": 0,
                        "warning": task_warning,
                    }
                )
                continue

            root = resolve_source_root(source)
            if not root.exists():
                source_stats.append(
                    {
                        "source_id": source.id,
                        "status": "missing",
                        "indexed": 0,
                        "deleted": 0,
                        "warning": task_warning,
                    }
                )
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
            stat = {
                "source_id": source.id,
                "status": "ok",
                "indexed": src_indexed,
                "deleted": removed,
            }
            if task_warning:
                stat["warning"] = task_warning
            pull = task.get("pull") or {}
            if pull.get("source_id"):
                stat["github_id"] = pull.get("source_id")
            elif task.get("github_id"):
                stat["github_id"] = task.get("github_id")
            if pull.get("ok") is False and pull.get("fallback"):
                stat["fallback"] = pull.get("fallback")
            source_stats.append(stat)
            conn.commit()
        write_sources_manifest(source_stats)
        if vault_push:
            vault_meta["push"] = push_vault()
        if not run_error:
            from .wiki_nav import touch_wiki_nav

            detail = f"indexed={indexed} skipped={skipped} deleted={deleted}"
            if sync_warnings:
                detail += f" warnings={len(sync_warnings)}"
            touch_wiki_nav("sync", detail)
        with SYNC_LOCK:
            SYNC_STATE["error"] = None
            SYNC_STATE["warnings"] = sync_warnings
    except Exception as exc:
        if conn:
            conn.rollback()
        run_error = str(exc)
        with SYNC_LOCK:
            SYNC_STATE["error"] = run_error
    finally:
        if conn:
            conn.close()
    result = {
        "mode": "sync",
        "indexed": indexed,
        "skipped": skipped,
        "deleted": deleted,
        "cleared": 0,
        "sources": source_stats,
        "repo_sync": repo_sync,
        "warnings": sync_warnings,
        "vault": vault_meta,
        "error": run_error,
    }
    # 先持久化 last_completed，再标记 running=False，
    # 避免前端轮询在窗口期拿到 running=false 但 last_completed 尚未更新
    finalize_sync_run(trigger, started_at, result, username or "")
    with SYNC_LOCK:
        SYNC_STATE["running"] = False
        SYNC_STATE["finished_at"] = time.time()
        SYNC_STATE["indexed"] = indexed
        SYNC_STATE["skipped"] = skipped
        SYNC_STATE["deleted"] = deleted
        SYNC_STATE["sources"] = source_stats
        SYNC_STATE["current_source"] = None
        SYNC_STATE["warnings"] = sync_warnings
    return result
