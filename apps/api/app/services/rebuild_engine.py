import time
from typing import Any

from ..db import get_db, load_settings_map
from .audit import add_audit_event_meta
from .indexer import clear_source_index, collect_files, index_single_source_force, resolve_source_root
from .sync_engine import SYNC_LOCK, SYNC_STATE, finalize_sync_run
from .sync_settings import apply_source_order, load_ordered_sources
from .source_sync_key import filter_sources_by_sync_keys


def _update_rebuild_counts(processed_files: int, indexed: int, skipped: int, deleted: int, cleared: int) -> None:
    with SYNC_LOCK:
        SYNC_STATE["processed_files"] = processed_files
        SYNC_STATE["indexed"] = indexed
        SYNC_STATE["skipped"] = skipped
        SYNC_STATE["deleted"] = deleted
        SYNC_STATE["cleared"] = cleared


def run_rebuild_job(trigger: str = "manual", source_ids: list[str] | None = None, *, username: str | None = None) -> dict[str, Any]:
    """Clear index for selected sources, then force a full re-scan (no remote pull)."""
    if source_ids is None and trigger in ("manual", "auto"):
        from .sync_settings import resolve_sync_source_ids

        source_ids = resolve_sync_source_ids(username=username)

    started_at = time.time()
    with SYNC_LOCK:
        SYNC_STATE["running"] = True
        SYNC_STATE["job_mode"] = "rebuild"
        SYNC_STATE["started_at"] = started_at
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

    conn = None
    indexed = 0
    skipped = 0
    deleted = 0
    cleared = 0
    source_stats: list[dict[str, Any]] = []
    run_error = None
    try:
        conn = get_db()
        settings_map = load_settings_map(username)
        role = None
        if username:
            r = conn.execute("SELECT role FROM users WHERE username = ?", (username,)).fetchone()
            if r: role = r["role"]
        all_sources = load_ordered_sources(settings_map, username=username, role=role)
        if source_ids:
            all_sources = apply_source_order(
                filter_sources_by_sync_keys(all_sources, source_ids),
                settings_map,
            )

        for source in all_sources:
            root = resolve_source_root(source)
            if not root.exists():
                source_stats.append(
                    {
                        "source_id": source.id,
                        "status": "missing",
                        "cleared": 0,
                        "indexed": 0,
                        "deleted": 0,
                        "skipped": 0,
                    }
                )
                continue

            src_cleared = clear_source_index(conn, source.id)
            cleared += src_cleared

            files = collect_files(root, source.include)
            with SYNC_LOCK:
                SYNC_STATE["current_source"] = source.id
                SYNC_STATE["processed_files"] = 0
                SYNC_STATE["total_files"] = len(files)

            stat = index_single_source_force(conn, source)
            indexed += stat.get("indexed", 0)
            skipped += stat.get("skipped", 0)
            deleted += stat.get("deleted", 0)
            _update_rebuild_counts(len(files), indexed, skipped, deleted, cleared)
            source_stats.append(
                {
                    "source_id": source.id,
                    "status": stat.get("status", "ok"),
                    "cleared": src_cleared,
                    "indexed": stat.get("indexed", 0),
                    "skipped": stat.get("skipped", 0),
                    "deleted": stat.get("deleted", 0),
                    "scanned": stat.get("scanned", 0),
                }
            )
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
            SYNC_STATE["cleared"] = cleared
            SYNC_STATE["sources"] = source_stats
            SYNC_STATE["current_source"] = None

    from .sync_engine import persist_last_sync_summary
    persist_last_sync_summary({
        "status": "success" if not run_error else "failed",
        "mode": "rebuild",
        "trigger": trigger,
        "started_at": started_at,
        "finished_at": time.time(),
        "indexed": indexed,
        "skipped": skipped,
        "deleted": deleted,
        "cleared": cleared,
        "error": run_error,
    }, username or "")

    result = {
        "mode": "rebuild",
        "indexed": indexed,
        "skipped": skipped,
        "deleted": deleted,
        "cleared": cleared,
        "sources": source_stats,
        "error": run_error,
    }
    finalize_sync_run(trigger, started_at, result)
    detail = (
        f"trigger={trigger} mode=rebuild cleared={cleared} indexed={indexed} "
        f"skipped={skipped} deleted={deleted}"
    )
    if run_error:
        detail += f" error={str(run_error)[:200]}"
    add_audit_event_meta("rebuild_completed", actor=trigger, ip="local", detail=detail)
    if not run_error:
        from .wiki_nav import touch_wiki_nav

        touch_wiki_nav("rebuild", detail)
    return result
