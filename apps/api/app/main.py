from contextlib import asynccontextmanager
import hashlib
import logging
import secrets
import time
from typing import Any

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .config import CORS_ALLOW_CREDENTIALS, CORS_ORIGINS, settings
from .db import LINT_DIR, WIKI_DIR, get_db, init_db, load_settings_map, read_settings
from .models import (
    ChangePasswordRequest,
    IngestRequest,
    LintRequest,
    LoginRequest,
    PurposeUpdateRequest,
    QueryRequest,
    RebuildRequest,
    RotateApiKeyRequest,
    SettingsUpdateRequest,
    SyncRequest,
    VaultSyncRequest,
    WikiWriteRequest,
)
from .services.assets import guess_media_type, resolve_document_asset, resolve_wiki_asset
from .services.audit import add_audit_event, fetch_audit_events
from .services.wiki_util import safe_wiki_path
from .services.wiki_source import assert_wiki_writable, get_wiki_source_or_fallback
from .services.auth import (
    check_login_rate_limit,
    clear_login_failures,
    enforce_csrf,
    mark_login_failure,
    parse_api_keys,
    require_admin,
    require_any_auth,
    require_auth,
    resolve_actor,
    resolve_current_user,
    resolve_role,
    session_account,
)
from .services.permissions import can_write
from .services.categories import browse_documents, list_category_stats
from .services.evidence import build_evidence_items
from .services.fts import search_documents, search_for_query
from .services.indexer import index_single_source, load_sources, read_text_safely, reload_sources_config, resolve_source_root
from .services.source_sync_key import is_known_sync_key, parse_sync_key, source_display_label, source_sync_key
from .responses import (
    DocumentResponse, LibraryResponse, QueryResponse, 
    SearchResponse, SearchResult, SyncStatusResponse,
)
from .services.library import build_library_index
from .services.link_graph import analyze_wiki_graph
from .services.lint_engine import run_lint_report
from .services.rate_limit import check_api_rate_limit
from .services.source_health import collect_source_warnings, source_health_status
from .services.source_pairing import resolve_ingest_sources
from .services.sync_settings import SYNC_PRESETS, enrich_settings_response, load_ordered_sources
from .services.purpose import load_purpose_text, purpose_status, save_purpose_text
from .services.query_engine import QueryEngineConfig, generate_structured_answer
from .services.security import collect_security_warnings, log_security_warnings, log_source_warnings
from .services.vault_git import pull_vault, push_vault, vault_status
from .services.web_fetch_policy import web_fetch_policy_summary
from .services.classify import suggest_wiki_path
from .services.scheduler import AutoSyncScheduler
from .services.wiki_query import save_query_page_with_nav
from .services.rebuild_engine import run_rebuild_job
from .services.sync_engine import (
    SYNC_LOCK,
    SYNC_STATE,
    get_sync_status_payload,
    is_sync_running,
    restore_last_sync_summary,
    run_sync_job,
)

SCHEDULER = AutoSyncScheduler(
    load_settings=load_settings_map,
    is_sync_running=is_sync_running,
    run_sync_job=lambda: run_sync_job("auto"),
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    restore_last_sync_summary()
    log_security_warnings()
    log_source_warnings()
    SCHEDULER.start()
    yield
    logger.info("mind-sync API shutting down")


app = FastAPI(title="mind-sync API", version="0.1.0", lifespan=lifespan)
logger = logging.getLogger("mind-sync")

# ─── 子模块路由 ─────────────────────────────────────────
from .routers.auth import router as auth_router
from .routers.admin import router as admin_router
from .routers.user import router as user_router, _add_notification
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(user_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next: Any) -> Response:
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if settings.security_hsts_enabled:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.get("/api/audit-events")
def audit_events(request: Request, limit: int = 50, _: Any = Depends(require_any_auth)) -> dict[str, Any]:
    username, role = resolve_current_user(request)
    items = fetch_audit_events(limit)
    # 非管理员只看自己的操作记录
    if role != "admin":
        items = [i for i in items if i.get("actor") == username]
    return {"items": items}


# ──────────────────────────────────────────────
# User management (admin) — moved to routers/admin.py
# ──────────────────────────────────────────────

// user endpoints moved to routers/user.py


# ──────────────────────────────────────────────
# Admin stats & reindex
# ──────────────────────────────────────────────

@app.get("/api/settings")
def get_settings(request: Request, _: Any = Depends(require_any_auth)) -> dict[str, Any]:
    username, role = resolve_current_user(request)
    conn = get_db()
    st = read_settings(conn, username)
    conn.close()
    return enrich_settings_response(st, SCHEDULER.build_meta(st), username=username, role=role)





@app.post("/api/settings")
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


@app.get("/api/library", response_model=LibraryResponse)
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


@app.post("/api/sync")
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


@app.post("/api/rebuild-index")
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


@app.get("/api/sync-status", response_model=SyncStatusResponse)
def sync_status(_: Any = Depends(require_any_auth)):
    return get_sync_status_payload()


@app.get("/api/purpose")
def get_purpose(_: Any = Depends(require_any_auth)) -> dict[str, Any]:
    return purpose_status()


@app.post("/api/purpose")
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


@app.get("/api/categories")
def categories(request: Request, _: Any = Depends(require_any_auth)) -> dict[str, Any]:
    username, role = resolve_current_user(request)
    conn = get_db()
    try:
        return list_category_stats(conn, username=username, role=role)
    finally:
        conn.close()


@app.get("/api/browse")
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


@app.get("/api/search", response_model=SearchResponse)
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


@app.get("/api/document/{doc_id}", response_model=DocumentResponse)
def get_document(doc_id: int, request: Request, _: Any = Depends(require_any_auth)):
    conn = get_db()
    row = conn.execute(
        "SELECT id, source_id, rel_path, title, content, lang, updated_at, source_owner FROM documents WHERE id = ?",
        (doc_id,),
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    # 权限检查：私有源文档仅 owner + admin 可读
    username, role = resolve_current_user(request)
    owner = (row["source_owner"] or "").strip()
    if owner and owner != "__shared__":
        if role != "admin" and owner != username:
            raise HTTPException(status_code=403, detail="此文档属于私有知识库，你无权访问")
    return dict(row)


@app.get("/api/document/{doc_id}/asset")
def document_asset(
    doc_id: int,
    src: str,
    _: Any = Depends(require_any_auth),
) -> FileResponse:
    conn = get_db()
    row = conn.execute(
        "SELECT source_id, rel_path FROM documents WHERE id = ?",
        (doc_id,),
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="document not found")
    if not src.strip():
        raise HTTPException(status_code=400, detail="src is required")
    try:
        asset_path = resolve_document_asset(row["source_id"], row["rel_path"], src)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="external src not supported via this endpoint") from exc
    return FileResponse(asset_path, media_type=guess_media_type(asset_path))


@app.get("/api/wiki-asset")
def wiki_asset(
    path: str,
    src: str,
    _: Any = Depends(require_any_auth),
) -> FileResponse:
    if not src.strip():
        raise HTTPException(status_code=400, detail="src is required")
    try:
        asset_path = resolve_wiki_asset(path, src)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="external src not supported via this endpoint") from exc
    return FileResponse(asset_path, media_type=guess_media_type(asset_path))


@app.get("/api/wiki-graph")
def wiki_graph(_: Any = Depends(require_any_auth)) -> dict[str, Any]:
    return analyze_wiki_graph(WIKI_DIR)


def _read_wiki_page(path: str, username: str | None = None, role: str | None = None) -> dict[str, Any]:
    """Read a wiki page by relative path, respecting user namespace."""
    target = safe_wiki_path(path, WIKI_DIR, username=username, role=role)
    rel = (path or "").strip().replace("\\", "/")
    content = read_text_safely(target)
    return {"path": rel, "content": content}


@app.get("/api/wiki-content")
def wiki_content(path: str, request: Request, _: Any = Depends(require_any_auth)) -> dict[str, Any]:
    user, role = resolve_current_user(request)
    return _read_wiki_page(path, username=user, role=role)


@app.get("/api/wiki-page")
def wiki_page(path: str, request: Request, _: Any = Depends(require_any_auth)) -> dict[str, Any]:
    """Deprecated alias of /api/wiki-content."""
    user, role = resolve_current_user(request)
    return _read_wiki_page(path, username=user, role=role)


@app.put("/api/wiki-content")
def update_wiki_content(
    payload: WikiWriteRequest,
    request: Request,
    _: Any = Depends(require_any_auth),
) -> dict[str, Any]:
    enforce_csrf(request)
    username, role = resolve_current_user(request)
    rel = (payload.path or "").strip().replace("\\", "/")
    # Shared wiki: admin only; user wiki: owner only
    if rel.startswith("users/"):
        parts = rel.split("/")
        if len(parts) < 2 or parts[1] != username:
            raise HTTPException(status_code=403, detail="无权写入其他用户的 Wiki")
        # User can write to their own wiki
    else:
        # Shared wiki requires admin
        if role != "admin":
            raise HTTPException(status_code=403, detail="仅管理员可写入共享 Wiki")
    assert_wiki_writable(rel)
    target = safe_wiki_path(rel, WIKI_DIR, must_exist=False, username=username, role=role)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(payload.content or "", encoding="utf-8")
    stat: dict[str, Any] = {}
    conn = get_db()
    try:
        wiki_source = get_wiki_source_or_fallback()
        stat = index_single_source(conn, wiki_source, rel)
        conn.commit()
    finally:
        conn.close()
    add_audit_event(
        "wiki_updated",
        request,
        actor=resolve_actor(request),
        detail=f"path={rel} chars={len(payload.content or '')}",
    )
    return {"ok": True, "path": rel, "indexed": stat}


@app.post("/api/vault-sync")
def vault_sync(
    payload: VaultSyncRequest,
    request: Request,
    _: Any = Depends(require_admin),
) -> dict[str, Any]:
    enforce_csrf(request)
    check_api_rate_limit(request, "sync")
    out: dict[str, Any] = {"ok": True}
    if payload.pull:
        out["pull"] = pull_vault()
    if payload.push:
        out["push"] = push_vault(payload.message)
    add_audit_event("vault_sync", request, actor=resolve_actor(request), detail=str(out)[:300])
    return out


@app.get("/api/vault-status")
def get_vault_status(_: Any = Depends(require_any_auth)) -> dict[str, Any]:
    return vault_status()


@app.get("/api/classify-suggest")
def classify_suggest(q: str, _: Any = Depends(require_any_auth)) -> dict[str, Any]:
    return suggest_wiki_path(q)


@app.post("/api/ingest")
def ingest(payload: IngestRequest, _: Any = Depends(require_admin)) -> dict[str, Any]:
    conn = get_db()
    try:
        settings_map = load_settings_map()
        sources_all = load_ordered_sources(settings_map, username=None, role="admin")
        sources_to_ingest, pairing_warnings = resolve_ingest_sources(
            sources_all,
            source_id_filter=(payload.source_id or "").strip() or None,
        )
        if payload.source_id and not sources_to_ingest:
            from .services.source_pairing import build_sync_plan

            plan = build_sync_plan(sources_all)
            skipped_ids = {s.id for s in plan.skipped_locals}
            sid = payload.source_id.strip()
            if sid in skipped_ids:
                raise HTTPException(
                    status_code=409,
                    detail=f"source '{sid}' is paired local; ingest the github entry instead",
                )
            raise HTTPException(status_code=404, detail=f"source_id not found: {payload.source_id}")

        source_stats = []
        total_indexed = 0
        total_skipped = 0
        total_deleted = 0
        for source in sources_to_ingest:
            stat = index_single_source(conn, source, payload.rel_path)
            source_stats.append(stat)
            total_indexed += stat.get("indexed", 0)
            total_skipped += stat.get("skipped", 0)
            total_deleted += stat.get("deleted", 0)
        conn.commit()
        return {
            "ok": True,
            "indexed": total_indexed,
            "skipped": total_skipped,
            "deleted": total_deleted,
            "sources": source_stats,
            "warnings": pairing_warnings,
        }
    finally:
        conn.close()


@app.post("/api/query", response_model=QueryResponse)
def query(payload: QueryRequest, request: Request, _: Any = Depends(require_any_auth)):
    if payload.save_to_wiki:
        require_admin(request)
    check_api_rate_limit(request, "query")
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="question is required")

    conn = get_db()
    try:
        username, role = resolve_current_user(request)
        citations = search_for_query(conn, question, limit=payload.limit, username=username, role=role)
    finally:
        conn.close()

    evidences = build_evidence_items(citations, question)
    config = QueryEngineConfig(
        llm_base_url=settings.llm_base_url,
        llm_api_key=settings.llm_api_key,
        llm_model=settings.llm_model,
        ollama_base_url=settings.ollama_base_url,
    )
    answer, used_llm, model_used = generate_structured_answer(
        question=question,
        citations=citations,
        config=config,
        model_override=payload.model,
        purpose_text=load_purpose_text(),
    )

    saved_path = None
    index_stat = None
    if payload.save_to_wiki:
        slug = hashlib.sha256(question.encode("utf-8", errors="ignore")).hexdigest()[:12]
        saved_path, index_stat = save_query_page_with_nav(
            question=question,
            answer=answer,
            model_used=model_used,
            evidences=evidences,
            slug=slug,
        )

    lite_citations = [
        {k: v for k, v in c.items() if k in {"id", "source_id", "rel_path", "title", "snippet"}}
        for c in citations
    ]
    return {
        "ok": True,
        "answer": answer,
        "citations": lite_citations,
        "evidences": evidences,
        "saved_path": saved_path,
        "indexed": index_stat,
        "used_llm": used_llm,
        "model_used": model_used,
        "llm_configured": bool((settings.llm_api_key or "").strip()),
    }


@app.post("/api/query/stream")
async def query_stream(
    payload: QueryRequest,
    request: Request,
    _: Any = Depends(require_any_auth),
):
    if payload.save_to_wiki:
        require_admin(request)
    check_api_rate_limit(request, "query")
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="question is required")

    conn = get_db()
    try:
        username, role = resolve_current_user(request)
        citations = search_for_query(conn, question, limit=payload.limit, username=username, role=role)
    finally:
        conn.close()

    evidences = build_evidence_items(citations, question)
    config = QueryEngineConfig(
        llm_base_url=settings.llm_base_url,
        llm_api_key=settings.llm_api_key,
        llm_model=settings.llm_model,
        ollama_base_url=settings.ollama_base_url,
    )
    purpose_text = read_purpose_text()

    from starlette.responses import StreamingResponse
    from query_engine import _call_llm_stream as __stream
    import json as _json

    async def event_stream():
        # Yield citations first
        yield f"data: {_json.dumps({'type': 'citations', 'citations': evidences})}\n\n"
        # Stream LLM tokens
        if not settings.llm_api_key.strip():
            # No LLM → return citations-only result
            yield f"data: {_json.dumps({'type': 'done', 'answer': '未配置 LLM_API_KEY，以下为检索摘要', 'evidences': evidences})}\n\n"
            return
        full_content = ""
        reasoning_content = ""
        async for evt in __stream(question, citations, config, purpose_text):
            if evt["event"] == "error":
                yield f"data: {_json.dumps({'type': 'error', 'message': evt['data']})}\n\n"
                return
            if evt["event"] == "token":
                chunk = _json.loads(evt["data"])
                choice = chunk["choices"][0]["delta"]
                if "reasoning_content" in choice and choice["reasoning_content"]:
                    reasoning_content += choice["reasoning_content"]
                    yield f"data: {_json.dumps({'type': 'reasoning', 'text': choice['reasoning_content']})}\n\n"
                if choice.get("content"):
                    token = choice["content"]
                    full_content += token
                    yield f"data: {_json.dumps({'type': 'token', 'text': token})}\n\n"
        yield f"data: {_json.dumps({'type': 'done', 'answer': full_content, 'reasoning': reasoning_content})}\n\n"
        yield f"data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/api/lint")
def lint(payload: LintRequest, request: Request, _: Any = Depends(require_admin)) -> dict[str, Any]:
    check_api_rate_limit(request, "lint")
    cap = max(1000, int(settings.lint_content_max_chars))
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT id, source_id, rel_path, title, "
            "CASE WHEN length(content) > ? THEN substr(content, 1, ?) ELSE content END AS content, "
            "updated_at FROM documents",
            (cap, cap),
        ).fetchall()
        report = run_lint_report(rows=rows, stale_days=payload.stale_days, report_dir=LINT_DIR, wiki_dir=WIKI_DIR, conn=conn)
    finally:
        conn.close()
    from .services.wiki_nav import touch_wiki_nav

    touch_wiki_nav("lint", f"issues={report.get('issue_count', 0)}")
    add_audit_event(
        "lint_completed",
        request,
        actor=resolve_actor(request),
        detail=f"issues={len(report.get('issues', []))}",
    )
    return report
