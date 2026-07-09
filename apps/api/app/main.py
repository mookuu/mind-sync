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

from .state import SCHEDULER


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
app.include_router(auth_router)
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
# User management (admin)
# ──────────────────────────────────────────────

# user endpoints


# ──────────────────────────────────────────────
