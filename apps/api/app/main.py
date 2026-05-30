import hashlib
import secrets
import time
from datetime import datetime, timezone
from typing import Any

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .config import CORS_ALLOW_CREDENTIALS, CORS_ORIGINS, settings
from .db import LINT_DIR, WIKI_DIR, get_db, init_db, load_settings_map, read_settings
from .models import IngestRequest, LintRequest, LoginRequest, QueryRequest, SettingsUpdateRequest, SyncRequest
from .services.assets import guess_media_type, resolve_document_asset, resolve_wiki_asset
from .services.audit import add_audit_event, fetch_audit_events
from .services.auth import (
    check_login_rate_limit,
    clear_login_failures,
    csrf_header_key,
    enforce_csrf,
    mark_login_failure,
    parse_api_keys,
    require_any_auth,
    require_auth,
    revoke_session_token,
    serializer,
)
from .services.categories import (
    browse_documents,
    category_sql_clause,
    classify_document,
    list_category_stats,
    path_prefix_sql_clause,
    topic_sql_clause,
)
from .services.evidence import build_evidence_items
from .services.indexer import (
    index_single_source,
    load_sources,
    read_text_safely,
    resolve_source_root,
    snippet_from_content,
)
from .services.library import build_library_index
from .services.link_graph import analyze_wiki_graph
from .services.lint_engine import run_lint_report
from .services.sync_settings import SYNC_PRESETS, enrich_settings_response
from .services.purpose import load_purpose_text, purpose_status
from .services.query_engine import QueryEngineConfig, generate_structured_answer
from .services.scheduler import AutoSyncScheduler
from .services.sync_engine import (
    SYNC_LOCK,
    SYNC_STATE,
    get_sync_status_payload,
    is_sync_running,
    restore_last_sync_summary,
    run_sync_job,
)

app = FastAPI(title="mind-sync API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)

SCHEDULER = AutoSyncScheduler(
    load_settings=load_settings_map,
    is_sync_running=is_sync_running,
    run_sync_job=lambda: run_sync_job("auto"),
)


@app.on_event("startup")
def startup() -> None:
    init_db()
    restore_last_sync_summary()
    SCHEDULER.start()


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


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/login")
def login(payload: LoginRequest, request: Request, response: Response) -> dict[str, Any]:
    account = (payload.username or "default").strip() or "default"
    check_login_rate_limit(request, account)
    if payload.password != settings.auth_password:
        mark_login_failure(request, account)
        add_audit_event("login_failed", request, actor=account, detail="invalid password")
        raise HTTPException(status_code=401, detail="Invalid password")
    clear_login_failures(request, account)
    now = time.time()
    ttl = max(60, int(settings.session_ttl_seconds))
    token = serializer.dumps({"ok": True, "issued_at": now, "expires_at": now + ttl})
    cookie_samesite = (settings.cookie_samesite or "lax").lower()
    if cookie_samesite not in {"lax", "strict", "none"}:
        cookie_samesite = "lax"
    cookie_secure = bool(settings.cookie_secure or cookie_samesite == "none")
    csrf_token = secrets.token_urlsafe(24)
    response.set_cookie(
        "ms_token",
        token,
        httponly=True,
        secure=cookie_secure,
        samesite=cookie_samesite,
        max_age=max(60, int(settings.cookie_max_age_seconds)),
    )
    response.set_cookie(
        "ms_csrf",
        csrf_token,
        httponly=False,
        secure=cookie_secure,
        samesite=cookie_samesite,
        max_age=max(60, int(settings.cookie_max_age_seconds)),
    )
    add_audit_event("login_success", request, actor=account, detail="cookie session issued")
    return {"ok": True, "csrf_header": settings.csrf_header_name, "csrf_token": csrf_token}


@app.post("/api/logout")
def logout(request: Request, response: Response, _: Any = Depends(require_auth)) -> dict[str, bool]:
    enforce_csrf(request)
    token = request.cookies.get("ms_token", "").strip()
    if token:
        revoke_session_token(token)
    cookie_samesite = (settings.cookie_samesite or "lax").lower()
    if cookie_samesite not in {"lax", "strict", "none"}:
        cookie_samesite = "lax"
    cookie_secure = bool(settings.cookie_secure or cookie_samesite == "none")
    response.delete_cookie("ms_token", secure=cookie_secure, httponly=True, samesite=cookie_samesite)
    response.delete_cookie("ms_csrf", secure=cookie_secure, httponly=False, samesite=cookie_samesite)
    add_audit_event("logout", request, actor="cookie-user", detail="session revoked and cookies cleared")
    return {"ok": True}


@app.get("/api/auth-mode")
def auth_mode(_: Any = Depends(require_any_auth)) -> dict[str, Any]:
    return {
        "cookie_enabled": True,
        "api_key_enabled": bool(parse_api_keys()),
        "csrf_header": csrf_header_key(),
    }


@app.get("/api/audit-events")
def audit_events(limit: int = 50, _: Any = Depends(require_any_auth)) -> dict[str, Any]:
    return {"items": fetch_audit_events(limit)}


@app.get("/api/sources")
def sources(_: Any = Depends(require_any_auth)) -> dict[str, Any]:
    items = []
    for source in load_sources():
        root = resolve_source_root(source)
        items.append(
            {
                "id": source.id,
                "type": source.source_type,
                "path": str(root),
                "url": source.url,
                "include": source.include,
                "exists": root.exists(),
            }
        )
    return {"sources": items}


@app.get("/api/settings")
def get_settings(_: Any = Depends(require_any_auth)) -> dict[str, Any]:
    conn = get_db()
    st = read_settings(conn)
    conn.close()
    return enrich_settings_response(st, SCHEDULER.build_meta(st))


@app.post("/api/settings")
def update_settings(payload: SettingsUpdateRequest, request: Request, _: Any = Depends(require_any_auth)) -> dict[str, Any]:
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
            conn.execute(
                "INSERT INTO app_settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                ("sync_preset", preset),
            )
        if payload.sync_source_ids is not None:
            import json

            ids = [str(x).strip() for x in payload.sync_source_ids if str(x).strip()]
            conn.execute(
                "INSERT INTO app_settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                ("sync_source_ids", json.dumps(ids, ensure_ascii=False)),
            )
        conn.commit()
        st = read_settings(conn)
    finally:
        conn.close()
    SCHEDULER.reset_last_run_now()
    data = enrich_settings_response(st, SCHEDULER.build_meta(st))
    data["ok"] = True
    add_audit_event(
        "settings_updated",
        request,
        actor="cookie-user",
        detail=f"auto_sync={payload.auto_sync_enabled}, preset={payload.sync_preset}",
    )
    return data


@app.get("/api/library")
def library(
    category: str | None = "source",
    _: Any = Depends(require_any_auth),
) -> dict[str, Any]:
    conn = get_db()
    try:
        return build_library_index(conn, category=category or "all")
    finally:
        conn.close()


@app.post("/api/sync")
def sync(
    background_tasks: BackgroundTasks,
    request: Request,
    payload: SyncRequest | None = None,
    _: Any = Depends(require_any_auth),
) -> dict[str, Any]:
    body = payload or SyncRequest()
    source_ids: list[str] | None = None
    if body.preset and body.preset in SYNC_PRESETS:
        source_ids = SYNC_PRESETS[body.preset].get("source_ids")
    elif body.source_ids:
        source_ids = [str(x).strip() for x in body.source_ids if str(x).strip()]
    elif body.use_saved_defaults:
        from .services.sync_settings import resolve_sync_source_ids

        source_ids = resolve_sync_source_ids()

    with SYNC_LOCK:
        if SYNC_STATE["running"]:
            add_audit_event("sync_requested", request, actor="cookie-user", detail="already running")
            return {"ok": True, "started": False, "message": "sync already running"}
        SYNC_STATE["running"] = True
    background_tasks.add_task(lambda: run_sync_job("manual", source_ids))
    detail = "sync started"
    if source_ids:
        detail += f" sources={','.join(source_ids)}"
    add_audit_event("sync_requested", request, actor="cookie-user", detail=detail)
    return {"ok": True, "started": True, "source_ids": source_ids}


@app.get("/api/sync-status")
def sync_status(_: Any = Depends(require_any_auth)) -> dict[str, Any]:
    return get_sync_status_payload()


@app.get("/api/purpose")
def get_purpose(_: Any = Depends(require_any_auth)) -> dict[str, Any]:
    return purpose_status()


@app.get("/api/categories")
def categories(_: Any = Depends(require_any_auth)) -> dict[str, Any]:
    conn = get_db()
    try:
        return list_category_stats(conn)
    finally:
        conn.close()


@app.get("/api/browse")
def browse(
    category: str | None = None,
    topic: str | None = None,
    limit: int = 50,
    _: Any = Depends(require_any_auth),
) -> dict[str, Any]:
    conn = get_db()
    try:
        items = browse_documents(conn, category=category, topic=topic, limit=limit)
    finally:
        conn.close()
    return {"items": items}


@app.get("/api/search")
def search(
    q: str,
    limit: int = 30,
    source_id: str | None = None,
    file_type: str | None = None,
    category: str | None = None,
    topic: str | None = None,
    path_prefix: str | None = None,
    _: Any = Depends(require_any_auth),
) -> dict[str, Any]:
    if not q.strip():
        return {"items": []}
    q = q.strip()
    conn = get_db()
    cat_clause, cat_args = category_sql_clause(category)
    topic_clause, topic_args = topic_sql_clause(topic)
    prefix_clause, prefix_args = path_prefix_sql_clause(path_prefix)
    fts_sql = """
        SELECT d.id, d.source_id, d.rel_path, d.lang,
               snippet(documents_fts, 1, '<mark>', '</mark>', '...', 30) AS snippet
        FROM documents_fts
        JOIN documents d ON d.id = documents_fts.rowid
        WHERE documents_fts MATCH ?
    """
    fts_args: list[Any] = [q]
    if source_id:
        fts_sql += " AND d.source_id = ?"
        fts_args.append(source_id)
    if file_type:
        fts_sql += " AND d.lang = ?"
        fts_args.append(file_type)
    fts_sql += cat_clause + topic_clause + prefix_clause
    fts_args.extend(cat_args)
    fts_args.extend(topic_args)
    fts_args.extend(prefix_args)
    fts_sql += " LIMIT ?"
    fts_args.append(limit)
    fts_rows = conn.execute(fts_sql, tuple(fts_args)).fetchall()
    items = []
    for row in fts_rows:
        item = dict(row)
        item["category"] = classify_document(row["source_id"], row["rel_path"])
        items.append(item)
    existing_ids = {item["id"] for item in items}

    if len(items) < limit:
        like_sql = """
            SELECT id, source_id, rel_path, lang, content
            FROM documents d
            WHERE (title LIKE ? OR rel_path LIKE ? OR content LIKE ?)
              AND (? IS NULL OR source_id = ?)
              AND (? IS NULL OR lang = ?)
        """
        like_args: list[Any] = [
            f"%{q}%",
            f"%{q}%",
            f"%{q}%",
            source_id,
            source_id,
            file_type,
            file_type,
        ]
        like_sql += cat_clause + topic_clause + prefix_clause
        like_args.extend(cat_args)
        like_args.extend(topic_args)
        like_args.extend(prefix_args)
        like_sql += " LIMIT ?"
        like_args.append(limit * 5)
        like_rows = conn.execute(like_sql, tuple(like_args)).fetchall()
        for row in like_rows:
            row_id = row["id"]
            if row_id in existing_ids:
                continue
            items.append(
                {
                    "id": row_id,
                    "source_id": row["source_id"],
                    "rel_path": row["rel_path"],
                    "lang": row["lang"],
                    "snippet": snippet_from_content(row["content"], q),
                    "category": classify_document(row["source_id"], row["rel_path"]),
                }
            )
            existing_ids.add(row_id)
            if len(items) >= limit:
                break
    conn.close()
    return {"items": items}


@app.get("/api/document/{doc_id}")
def get_document(doc_id: int, _: Any = Depends(require_any_auth)) -> dict[str, Any]:
    conn = get_db()
    row = conn.execute(
        "SELECT id, source_id, rel_path, title, content, lang, updated_at FROM documents WHERE id = ?",
        (doc_id,),
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
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


def _read_wiki_page(path: str) -> dict[str, Any]:
    rel = (path or "").strip().replace("\\", "/")
    if not rel:
        raise HTTPException(status_code=400, detail="path is required")
    target = (WIKI_DIR / rel).resolve()
    try:
        target.relative_to(WIKI_DIR.resolve())
    except Exception as exc:
        raise HTTPException(status_code=400, detail="invalid wiki path") from exc
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="wiki page not found")
    content = read_text_safely(target)
    return {"path": rel, "content": content}


@app.get("/api/wiki-content")
def wiki_content(path: str, _: Any = Depends(require_any_auth)) -> dict[str, Any]:
    return _read_wiki_page(path)


@app.get("/api/wiki-page")
def wiki_page(path: str, _: Any = Depends(require_any_auth)) -> dict[str, Any]:
    return _read_wiki_page(path)


@app.post("/api/ingest")
def ingest(payload: IngestRequest, _: Any = Depends(require_any_auth)) -> dict[str, Any]:
    conn = get_db()
    try:
        sources_all = load_sources()
        if payload.source_id:
            sources_to_ingest = [s for s in sources_all if s.id == payload.source_id]
            if not sources_to_ingest:
                raise HTTPException(status_code=404, detail=f"source_id not found: {payload.source_id}")
        else:
            sources_to_ingest = sources_all

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
        }
    finally:
        conn.close()


@app.post("/api/query")
def query(payload: QueryRequest, _: Any = Depends(require_any_auth)) -> dict[str, Any]:
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="question is required")

    conn = get_db()
    rows = conn.execute(
        """
        SELECT d.id, d.source_id, d.rel_path, d.title, d.content,
               snippet(documents_fts, 1, '<mark>', '</mark>', '...', 45) AS snippet
        FROM documents_fts
        JOIN documents d ON d.id = documents_fts.rowid
        WHERE documents_fts MATCH ?
        LIMIT ?
        """,
        (question, payload.limit),
    ).fetchall()
    conn.close()

    citations = [dict(row) for row in rows]
    evidences = build_evidence_items(citations, question)
    config = QueryEngineConfig(
        llm_base_url=settings.llm_base_url,
        llm_api_key=settings.llm_api_key,
        llm_model=settings.llm_model,
    )
    answer, used_llm, model_used = generate_structured_answer(
        question=question,
        citations=citations,
        config=config,
        model_override=payload.model,
        purpose_text=load_purpose_text(),
    )

    saved_path = None
    if payload.save_to_wiki:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        slug = hashlib.sha1(question.encode("utf-8", errors="ignore")).hexdigest()[:8]
        queries_dir = WIKI_DIR / "queries"
        queries_dir.mkdir(parents=True, exist_ok=True)
        rel_name = f"queries/{ts}_{slug}.md"
        target = WIKI_DIR / rel_name
        ref_lines = "\n".join([f"- [{e['ref']}] `{e['source_id']}/{e['rel_path']}`" for e in evidences]) or "- (none)"
        body = (
            f"---\ntype: query\nderived: true\nquestion: {question}\nmodel: {model_used}\n"
            f"created: {ts}\n---\n\n"
            f"# Query: {question}\n\n## Answer\n{answer}\n\n## Citations\n{ref_lines}\n"
        )
        target.write_text(body, encoding="utf-8")
        saved_path = rel_name

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
        "used_llm": used_llm,
        "model_used": model_used,
    }


@app.post("/api/lint")
def lint(payload: LintRequest, _: Any = Depends(require_any_auth)) -> dict[str, Any]:
    conn = get_db()
    rows = conn.execute("SELECT id, source_id, rel_path, title, content, updated_at FROM documents").fetchall()
    conn.close()
    return run_lint_report(rows=rows, stale_days=payload.stale_days, report_dir=LINT_DIR, wiki_dir=WIKI_DIR)
