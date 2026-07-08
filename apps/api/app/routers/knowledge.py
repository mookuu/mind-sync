"""Knowledge router: settings, library, sync, rebuild, search, browse, categories, purpose."""
from __future__ import annotations
import json, time
from typing import Any
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from ..config import settings
from ..db import get_db, read_settings
from ..models import RebuildRequest, SettingsUpdateRequest, SyncRequest, PurposeUpdateRequest
from ..responses import LibraryResponse, SyncStatusResponse, SearchResponse
from ..services.auth import resolve_actor, resolve_current_user, require_admin, require_any_auth
from ..services.audit import add_audit_event
from ..services.categories import browse_documents, list_category_stats
from ..services.fts import search_documents
from ..services.indexer import load_sources
from ..services.library import build_library_index
from ..services.purpose import purpose_status, save_purpose_text
from ..services.rate_limit import check_api_rate_limit
from ..services.rebuild_engine import run_rebuild_job
from ..services.scheduler import SCHEDULER
from ..services.settings import enrich_settings_response
from ..services.source_sync_key import is_known_sync_key
from ..services.sync_engine import SYNC_LOCK, SYNC_STATE, SYNC_PRESETS, run_sync_job, get_sync_status_payload

router = APIRouter(tags=["knowledge"])

@router.get("/api/settings")
def get_settings(request: Request, _: Any = Depends(require_any_auth)) -> dict[str, Any]:
    username, role = resolve_current_user(request)
    conn = get_db()
    st = read_settings(conn, username)
    conn.close()
    return enrich_settings_response(st, SCHEDULER.build_meta(st), username=username, role=role)





@router.post("/api/settings")
def update_settings(
    payload: SettingsUpdateRequest,
    request: Request,
    _: Any = Depends(require_any_auth),
) -> dict[str, Any]:
    from .db import save_user_setting

    updater_username, _ = resolve_current_user(request)
    conn = get_db()
    try:
        if payload.auto_sync_enabled is not None:
            conn.execute(
                "INSERT INTO app_settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                ("auto_sync_enabled", "true" if payload.auto_sync_enabled else "false"),
            )
        if payload.auto_sync_interval_minutes is not None:
            val = max(1, min(int(payload.auto_sync_interval_minutes), 24 * 60))
            conn.execute(
                "INSERT INTO app_settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                ("auto_sync_interval_minutes", str(val)),
            )
        if payload.sync_preset is not None:
            preset = (payload.sync_preset or "all").strip() or "all"
            if preset != "custom" and preset not in SYNC_PRESETS:
                preset = "all"
            save_user_setting(conn, updater_username, "sync_preset", preset)
        if payload.sync_source_ids is not None:
            import json

            all_src = load_sources()
            from .services.sync_settings import list_sync_presets

            valid_preset_ids = {p["id"] for p in list_sync_presets() if p.get("source_ids")}
            ids = [
                str(x).strip()
                for x in payload.sync_source_ids
                if str(x).strip()
                and (is_known_sync_key(str(x).strip(), all_src) or str(x).strip() in valid_preset_ids)
            ]
            save_user_setting(conn, updater_username, "sync_source_ids", json.dumps(ids, ensure_ascii=False))
        if payload.sync_source_order is not None:
            import json

            all_src = load_sources()
            order_ids = [
                str(x).strip()
                for x in payload.sync_source_order
                if str(x).strip() and is_known_sync_key(str(x).strip(), all_src)
            ]
            save_user_setting(conn, updater_username, "sync_source_order", json.dumps(order_ids, ensure_ascii=False))
        conn.commit()
        st = read_settings(conn, updater_username)
    finally:
        conn.close()
    SCHEDULER.reset_last_run_now()
    data = enrich_settings_response(st, SCHEDULER.build_meta(st), username=updater_username, role=None)
    data["ok"] = True
    add_audit_event(
        "settings_updated",
        request,
        actor=resolve_actor(request),
        detail=f"auto_sync={payload.auto_sync_enabled}, preset={payload.sync_preset}",
    )
    return data


@router.get("/api/library", response_model=LibraryResponse)
def library(
    request: Request,
    category: str | None = "source",
    _: Any = Depends(require_any_auth),
) -> dict[str, Any]:
    username, role = resolve_current_user(request)
    conn = get_db()
    try:
        return build_library_index(conn, category=category or "all", username=username, role=role)
    finally:
        conn.close()


@router.post("/api/sync")
def sync(
    background_tasks: BackgroundTasks,
    request: Request,
    payload: SyncRequest | None = None,
    _: Any = Depends(require_any_auth),
) -> dict[str, Any]:
    check_api_rate_limit(request, "sync")
    username, role = resolve_current_user(request)
    body = payload or SyncRequest()
    source_ids: list[str] | None = None
    if body.preset and body.preset in SYNC_PRESETS:
        source_ids = SYNC_PRESETS[body.preset].get("source_ids")
    elif body.source_ids:
        source_ids = [str(x).strip() for x in body.source_ids if str(x).strip()]
    elif body.use_saved_defaults:
        from .services.sync_settings import resolve_sync_source_ids

        source_ids = resolve_sync_source_ids(username=username, role=role)

    with SYNC_LOCK:
        if SYNC_STATE["running"]:
            add_audit_event("sync_requested", request, actor=resolve_actor(request), detail="already running")
            return {"ok": True, "started": False, "message": "sync already running"}
        SYNC_STATE["running"] = True
    background_tasks.add_task(
        lambda: run_sync_job(
            "manual",
            source_ids,
            username=username,
            vault_pull=body.vault_pull,
            vault_push=body.vault_push,
        )
    )
    detail = "sync started"
    if source_ids:
        detail += f" sources={','.join(source_ids)}"
    add_audit_event("sync_requested", request, actor=resolve_actor(request), detail=detail)
    return {"ok": True, "started": True, "mode": "sync", "source_ids": source_ids}


@router.post("/api/rebuild-index")
def rebuild_index(
    background_tasks: BackgroundTasks,
    request: Request,
    payload: RebuildRequest | None = None,
    _: Any = Depends(require_any_auth),
) -> dict[str, Any]:
    """Full index rebuild: clear selected sources in SQLite, then re-scan every file."""
    check_api_rate_limit(request, "sync")
    username, role = resolve_current_user(request)
    body = payload or RebuildRequest()
    source_ids: list[str] | None = None
    if body.preset and body.preset in SYNC_PRESETS:
        source_ids = SYNC_PRESETS[body.preset].get("source_ids")
    elif body.source_ids:
        source_ids = [str(x).strip() for x in body.source_ids if str(x).strip()]
    elif body.use_saved_defaults:
        from .services.sync_settings import resolve_sync_source_ids

        source_ids = resolve_sync_source_ids(username=username, role=role)

    with SYNC_LOCK:
        if SYNC_STATE["running"]:
            add_audit_event("rebuild_requested", request, actor=resolve_actor(request), detail="already running")
            return {"ok": True, "started": False, "mode": "rebuild", "message": "index job already running"}
        SYNC_STATE["running"] = True
    background_tasks.add_task(lambda: run_rebuild_job("manual", source_ids, username=username))
    detail = "rebuild started"
    if source_ids:
        detail += f" sources={','.join(source_ids)}"
    add_audit_event("rebuild_requested", request, actor=resolve_actor(request), detail=detail)
    return {"ok": True, "started": True, "mode": "rebuild", "source_ids": source_ids}


@router.get("/api/sync-status", response_model=SyncStatusResponse)
def sync_status(_: Any = Depends(require_any_auth)):
    return get_sync_status_payload()


@router.get("/api/purpose")
def get_purpose(_: Any = Depends(require_any_auth)) -> dict[str, Any]:
    return purpose_status()


@router.post("/api/purpose")
def update_purpose(
    payload: PurposeUpdateRequest,
    request: Request,
    _: Any = Depends(require_admin),
) -> dict[str, Any]:
    save_purpose_text(payload.content)
    add_audit_event(
        "purpose_updated",
        request,
        actor=resolve_actor(request),
        detail=f"chars={len(payload.content or '')}",
    )
    return {"ok": True, **purpose_status()}


@router.get("/api/categories")
def categories(request: Request, _: Any = Depends(require_any_auth)) -> dict[str, Any]:
    username, role = resolve_current_user(request)
    conn = get_db()
    try:
        return list_category_stats(conn, username=username, role=role)
    finally:
        conn.close()


@router.get("/api/browse")
def browse(
    request: Request,
    category: str | None = None,
    topic: str | None = None,
    limit: int = 50,
    _: Any = Depends(require_any_auth),
) -> dict[str, Any]:
    username, role = resolve_current_user(request)
    conn = get_db()
    try:
        items = browse_documents(conn, category=category, topic=topic, limit=limit, username=username, role=role)
    finally:
        conn.close()
    return {"items": items}


@router.get("/api/search", response_model=SearchResponse)
def search(
    q: str,
    request: Request,
    limit: int = 30,
    source_id: str | None = None,
    file_type: str | None = None,
    category: str | None = None,
    topic: str | None = None,
    path_prefix: str | None = None,
    sort: str = "relevance",
    _: Any = Depends(require_any_auth),
) -> dict[str, Any]:
    if not q.strip():
        return {"items": []}
    q = q.strip()
    conn = get_db()
    try:
        username, role = resolve_current_user(request)
        items = search_documents(
            conn,
            q,
            limit=limit,
            source_id=source_id,
            file_type=file_type,
            category=category,
            topic=topic,
            path_prefix=path_prefix,
            sort=sort,
            username=username,
            role=role,
        )
    finally:
        conn.close()
    return {"items": items}


