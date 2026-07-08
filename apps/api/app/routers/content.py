"""Content router: document, wiki, query, vault, ingest, lint, classify."""
from __future__ import annotations
import hashlib, json, time
from typing import Any
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from ..config import settings
from ..db import LINT_DIR, WIKI_DIR, get_db, load_settings_map
from ..models import IngestRequest, LintRequest, QueryRequest, VaultSyncRequest, WikiWriteRequest, PurposeUpdateRequest
from ..responses import DocumentResponse, QueryResponse, SearchResponse
from ..services.assets import guess_media_type, resolve_document_asset, resolve_wiki_asset
from ..services.auth import enforce_csrf, resolve_actor, resolve_current_user, require_admin, require_any_auth
from ..services.audit import add_audit_event
from ..services.classify import suggest_wiki_path
from ..services.evidence import build_evidence_items
from ..services.fts import search_for_query
from ..services.indexer import index_single_source, load_ordered_sources, read_text_safely
from ..services.ingest import resolve_ingest_sources
from ..services.link_graph import analyze_wiki_graph
from ..services.lint_engine import run_lint_report
from ..services.purpose import load_purpose_text
from ..services.query_engine import QueryEngineConfig, generate_structured_answer
from ..services.query_engine import _call_llm_stream
from ..services.rate_limit import check_api_rate_limit
from ..services.vault_git import pull_vault, push_vault, vault_status
from ..services.wiki_nav import touch_wiki_nav
from ..services.wiki_query import save_query_page_with_nav
from ..services.wiki_source import assert_wiki_writable, get_wiki_source_or_fallback
from ..services.wiki_util import safe_wiki_path

router = APIRouter(tags=["content"])

def _read_wiki_page(path: str, username: str | None = None, role: str | None = None) -> dict[str, Any]:
    target = safe_wiki_path(path, WIKI_DIR, username=username, role=role)
    rel = (path or "").strip().replace("\", "/")
    content = read_text_safely(target)
    return {"path": rel, "content": content}

@router.get("/api/document/{doc_id}", response_model=DocumentResponse)
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


@router.get("/api/document/{doc_id}/asset")
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


@router.get("/api/wiki-asset")
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


@router.get("/api/wiki-graph")
def wiki_graph(_: Any = Depends(require_any_auth)) -> dict[str, Any]:
    return analyze_wiki_graph(WIKI_DIR)


def _read_wiki_page(path: str, username: str | None = None, role: str | None = None) -> dict[str, Any]:
    """Read a wiki page by relative path, respecting user namespace."""
    target = safe_wiki_path(path, WIKI_DIR, username=username, role=role)
    rel = (path or "").strip().replace("\\", "/")
    content = read_text_safely(target)
    return {"path": rel, "content": content}


@router.get("/api/wiki-content")
def wiki_content(path: str, request: Request, _: Any = Depends(require_any_auth)) -> dict[str, Any]:
    user, role = resolve_current_user(request)
    return _read_wiki_page(path, username=user, role=role)


@router.get("/api/wiki-page")
def wiki_page(path: str, request: Request, _: Any = Depends(require_any_auth)) -> dict[str, Any]:
    """Deprecated alias of /api/wiki-content."""
    user, role = resolve_current_user(request)
    return _read_wiki_page(path, username=user, role=role)


@router.put("/api/wiki-content")
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


@router.post("/api/vault-sync")
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


@router.get("/api/vault-status")
def get_vault_status(_: Any = Depends(require_any_auth)) -> dict[str, Any]:
    return vault_status()


@router.get("/api/classify-suggest")
def classify_suggest(q: str, _: Any = Depends(require_any_auth)) -> dict[str, Any]:
    return suggest_wiki_path(q)


@router.post("/api/ingest")
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
            from ..services.source_pairing import build_sync_plan

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


@router.post("/api/query", response_model=QueryResponse)
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


@router.post("/api/query/stream")
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
    from ..services.query_engine import _call_llm_stream as __stream
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


@router.post("/api/lint")
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
    from ..services.wiki_nav import touch_wiki_nav

    touch_wiki_nav("lint", f"issues={report.get('issue_count', 0)}")
    add_audit_event(
        "lint_completed",
        request,
        actor=resolve_actor(request),
        detail=f"issues={len(report.get('issues', []))}",
    )
    return report
