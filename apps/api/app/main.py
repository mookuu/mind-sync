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
    csrf_header_key,
    enforce_csrf,
    login_user,
    logout_user,
    mark_login_failure,
    parse_api_keys,
    require_admin,
    require_any_auth,
    require_auth,
    resolve_actor,
    resolve_current_user,
    resolve_role,
    session_account,
    update_password,
    authenticate,
)
from .services.permissions import can_write
from .services.session_store import delete_session, list_sessions as list_sessions_for_user
from .services.categories import browse_documents, list_category_stats
from .services.evidence import build_evidence_items
from .services.fts import search_documents, search_for_query
from .services.indexer import index_single_source, load_sources, read_text_safely, reload_sources_config, resolve_source_root
from .services.source_sync_key import is_known_sync_key, parse_sync_key, source_display_label, source_sync_key
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


@app.get("/api/health")
def health() -> dict[str, Any]:
    warnings = collect_source_warnings()
    sec = collect_security_warnings()
    return {
        "status": source_health_status(warnings),
        "source_warnings": warnings,
        "security_warnings": sec,
        "vault": vault_status(),
        "web_fetch": web_fetch_policy_summary(),
    }


@app.post("/api/login")
def login(payload: LoginRequest, request: Request, response: Response) -> dict[str, Any]:
    account = (payload.username or "default").strip() or "default"
    check_login_rate_limit(request, account)
    user = authenticate(account, payload.password)
    if user is None:
        mark_login_failure(request, account)
        add_audit_event("login_failed", request, actor=account, detail="invalid credentials")
        raise HTTPException(status_code=401, detail="Invalid username or password")
    clear_login_failures(request, account)

    remember_me = bool(getattr(payload, "remember_me", False))
    session_id, _, _ = login_user(account, payload.password, request, remember_me=remember_me)

    # 清理已过期的 session，并限制每用户最多 5 条活跃 session
    from .services.session_store import cleanup_expired_sessions

    cleanup_expired_sessions()
    # 保留最近 5 条 session，删除更早的
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT session_id FROM sessions WHERE username = ? ORDER BY last_active_at DESC",
            (account,),
        ).fetchall()
        if len(rows) > 5:
            keep = {r["session_id"] for r in rows[:5]}
            conn.execute(
                "DELETE FROM sessions WHERE username = ? AND session_id NOT IN ({})".format(
                    ",".join("?" for _ in keep)
                ),
                (account, *keep),
            )
            conn.commit()
    finally:
        conn.close()

    # Calculate cookie max_age from session TTL
    ttl = max(60, int(settings.session_ttl_seconds))
    if remember_me:
        ttl = max(ttl, 60 * 60 * 24 * 30)
    else:
        ttl = min(ttl, 60 * 60 * 24)

    cookie_samesite = (settings.cookie_samesite or "lax").lower()
    if cookie_samesite not in {"lax", "strict", "none"}:
        cookie_samesite = "lax"
    cookie_secure = bool(settings.cookie_secure or cookie_samesite == "none")
    # Clear any old cookies first
    response.delete_cookie("ms_token", secure=cookie_secure, httponly=True, samesite=cookie_samesite, path="/")
    response.delete_cookie("ms_csrf", secure=cookie_secure, httponly=False, samesite=cookie_samesite, path="/")
    csrf_token = secrets.token_urlsafe(24)
    response.set_cookie(
        "ms_token", session_id,
        httponly=True, secure=cookie_secure, samesite=cookie_samesite, max_age=ttl,
    )
    response.set_cookie(
        "ms_csrf", csrf_token,
        httponly=False, secure=cookie_secure, samesite=cookie_samesite, max_age=ttl,
    )
    add_audit_event(
        "login_success", request, actor=user.username,
        detail=f"server-side session role={user.role.value} remember_me={remember_me}",
    )
    # 获取 display_name
    display_name = user.username
    conn2 = get_db()
    try:
        row = conn2.execute(
            "SELECT display_name FROM users WHERE username = ?", (user.username,)
        ).fetchone()
        if row and row["display_name"]:
            display_name = row["display_name"]
    finally:
        conn2.close()

    return {
        "ok": True,
        "username": user.username,
        "display_name": display_name,
        "role": user.role.value,
        "can_write": can_write(user.role),
        "csrf_header": settings.csrf_header_name,
        "csrf_token": csrf_token,
    }


@app.post("/api/logout")
def logout(request: Request, response: Response) -> dict[str, bool]:
    session_id = request.cookies.get("ms_token", "").strip()
    if session_id:
        logout_user(session_id)
    cookie_samesite = (settings.cookie_samesite or "lax").lower()
    if cookie_samesite not in {"lax", "strict", "none"}:
        cookie_samesite = "lax"
    cookie_secure = bool(settings.cookie_secure or cookie_samesite == "none")
    response.delete_cookie("ms_token", secure=cookie_secure, httponly=True, samesite=cookie_samesite)
    response.delete_cookie("ms_csrf", secure=cookie_secure, httponly=False, samesite=cookie_samesite)
    add_audit_event("logout", request, actor=resolve_actor(request), detail="session deleted")
    return {"ok": True}


@app.get("/api/auth-mode")
def auth_mode(request: Request, _: Any = Depends(require_any_auth)) -> dict[str, Any]:
    role = resolve_role(request)
    from .services.auth import session_account
    username = session_account(request) or None

    # 获取 display_name
    display_name = username
    if username:
        conn = get_db()
        try:
            row = conn.execute(
                "SELECT display_name FROM users WHERE username = ?", (username,)
            ).fetchone()
            if row and row["display_name"]:
                display_name = row["display_name"]
        finally:
            conn.close()

    return {
        "cookie_enabled": True,
        "api_key_enabled": bool(parse_api_keys()),
        "csrf_header": csrf_header_key(),
        "role": role,
        "can_write": can_write(role),
        "username": username,
        "display_name": display_name,
        "authenticated": True,
    }


@app.post("/api/change-password")
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    _: Any = Depends(require_any_auth),
) -> dict[str, bool]:
    enforce_csrf(request)
    account = session_account(request)
    if not account:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = authenticate(account, payload.current_password)
    if not user:
        raise HTTPException(status_code=403, detail="Current password is incorrect")
    from .services.password_util import hash_password

    new_hash = hash_password(payload.new_password)
    if not update_password(account, new_hash):
        raise HTTPException(status_code=500, detail="Failed to update password")
    add_audit_event("password_changed", request, actor=account, detail="password updated")
    return {"ok": True}


@app.get("/api/sessions")
def list_sessions(
    request: Request,
    _: Any = Depends(require_any_auth),
) -> dict[str, Any]:
    account = session_account(request)
    if not account:
        return {"sessions": []}
    sessions = list_sessions_for_user(account)
    current_sid = request.cookies.get("ms_token", "").strip()
    return {
        "sessions": [
            {
                "session_id": s["session_id"],
                "ip": s.get("ip", ""),
                "user_agent": s.get("user_agent", ""),
                "created_at": s.get("created_at", 0),
                "last_active_at": s.get("last_active_at", 0),
                "expires_at": s.get("expires_at", 0),
                "remember_me": bool(s.get("remember_me", 0)),
                "current": s["session_id"] == current_sid,
            }
            for s in sessions
        ]
    }


@app.delete("/api/sessions/{session_id}")
def delete_session_endpoint(
    session_id: str,
    request: Request,
    _: Any = Depends(require_any_auth),
) -> dict[str, bool]:
    enforce_csrf(request)
    account = session_account(request)
    if not account:
        raise HTTPException(status_code=401, detail="Not authenticated")
    current_sid = request.cookies.get("ms_token", "").strip()
    if session_id == current_sid:
        raise HTTPException(status_code=400, detail="Cannot delete current session, use logout instead")
    delete_session(session_id)
    add_audit_event("session_revoked", request, actor=account, detail=f"session {session_id[:12]}…")
    return {"ok": True}


@app.get("/api/api-keys")
def list_api_keys(
    _: Any = Depends(require_admin),
) -> dict[str, Any]:
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT id, key_value, label, created_at, last_used_at FROM api_keys ORDER BY created_at DESC"
        ).fetchall()
        env_keys = parse_api_keys()
        return {
            "keys": [dict(r) for r in rows],
            "env_keys": list(env_keys),
        }
    finally:
        conn.close()


@app.post("/api/api-keys/rotate")
def rotate_api_key(
    payload: RotateApiKeyRequest,
    request: Request,
    _: Any = Depends(require_admin),
) -> dict[str, str]:
    enforce_csrf(request)
    import secrets as secmod

    new_key = f"msk-{secmod.token_urlsafe(32)}"
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO api_keys(key_value, label, created_at) VALUES(?, ?, ?)",
            (new_key, payload.label or "default", time.time()),
        )
        conn.commit()
    finally:
        conn.close()
    add_audit_event("api_key_rotated", request, actor=resolve_actor(request), detail="new API key generated")
    return {"key": new_key}


@app.delete("/api/api-keys/{key_id}")
def delete_api_key(
    key_id: int,
    request: Request,
    _: Any = Depends(require_admin),
) -> dict[str, bool]:
    enforce_csrf(request)
    conn = get_db()
    try:
        cur = conn.execute("DELETE FROM api_keys WHERE id = ?", (key_id,))
        conn.commit()
        deleted = cur.rowcount > 0
    finally:
        conn.close()
    if not deleted:
        raise HTTPException(status_code=404, detail="API Key not found")
    add_audit_event("api_key_deleted", request, actor=resolve_actor(request), detail=f"key_id={key_id}")
    return {"ok": True}


@app.get("/api/audit-events")
def audit_events(limit: int = 50, _: Any = Depends(require_any_auth)) -> dict[str, Any]:
    return {"items": fetch_audit_events(limit)}


@app.get("/api/sources")
def sources(request: Request, _: Any = Depends(require_any_auth)) -> dict[str, Any]:
    username, role = resolve_current_user(request)
    return _build_sources_response(username=username, role=role)


def _build_sources_response(username: str | None = None, role: str | None = None) -> dict[str, Any]:
    settings_map = load_settings_map()
    items = []
    for source in load_ordered_sources(settings_map, username=username, role=role):
        root = resolve_source_root(source)
        path_str = str(root)
        items.append(
            {
                "id": source.id,
                "sync_key": source_sync_key(source),
                "label": source_display_label(source),
                "type": source.source_type,
                "path": path_str,
                "path_exists": root.exists(),
                "url": source.url,
                "branch": source.branch,
                "paths": source.paths,
                "include": source.include,
                "order": source.order,
                "exists": root.exists(),
                "fetch_confirmed": source.fetch_confirmed,
                "respect_robots": source.respect_robots,
                "owner": source.owner,
                "owner_display_name": _resolve_owner_display_name(source.owner),
            }
        )
    return {"sources": items, "web_fetch_policy": web_fetch_policy_summary()}

def _resolve_owner_display_name(owner: str | None) -> str | None:
    if not owner:
        return None
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT display_name FROM users WHERE username = ?", (owner,)
        ).fetchone()
        if row and row["display_name"]:
            return row["display_name"]
        return None
    finally:
        conn.close()


@app.post("/api/admin/sources/reload")
def admin_reload_sources(request: Request, _: Any = Depends(require_admin)) -> dict[str, Any]:
    from pathlib import Path

    src_file = Path(settings.sources_file)
    if not src_file.is_file():
        raise HTTPException(status_code=404, detail=f"sources file not found: {src_file}")
    reload_sources_config()
    username, role = resolve_current_user(request)
    payload = _build_sources_response(username=username, role=role)
    payload["ok"] = True
    payload["count"] = len(payload["sources"])
    add_audit_event(
        "sources_reloaded",
        request,
        actor=resolve_actor(request),
        detail=f"count={payload['count']} file={src_file}",
    )
    return payload


@app.get("/api/admin/browse-dir")
def browse_directory(path: str = "", _: Any = Depends(require_any_auth)) -> dict[str, Any]:
    if not path:
        # 默认浏览路径：优先 DATA_ROOT，否则 ~/
        from pathlib import Path as PPath
        default = getattr(settings, "data_root", None) or str(PPath.home())
        path = default
    from pathlib import Path
    base = Path(path).expanduser().resolve()
    if not base.is_dir():
        raise HTTPException(status_code=400, detail=f"not a directory: {base}")
    entries = []
    try:
        for entry in sorted(base.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            if entry.is_dir() and not entry.name.startswith("."):
                entries.append({"name": entry.name, "path": str(entry.resolve())})
    except PermissionError:
        raise HTTPException(status_code=403, detail=f"permission denied: {base}")
    return {"parent": str(base.parent), "current": str(base), "entries": entries[:50]}


@app.post("/api/admin/sources/custom")
def admin_add_custom_source(request: Request, body: dict[str, Any], _: Any = Depends(require_admin)) -> dict[str, Any]:
    from pathlib import Path
    import yaml
    from .services.user_manager import get_user_sources_path

    path_str = (body.get("path") or "").strip()
    if not path_str:
        raise HTTPException(status_code=400, detail="请输入要同步的文件夹路径")
    path = Path(path_str).expanduser().resolve()
    if not path.exists():
        raise HTTPException(status_code=400, detail=f"文件夹不存在：{path}")
    if not path.is_dir():
        raise HTTPException(status_code=400, detail=f"路径不是文件夹：{path}")
    source_id = path.name
    if not source_id or source_id.startswith("."):
        raise HTTPException(status_code=400, detail=f"文件夹名称无效：{source_id}")

    # 写入 user_sources.yaml（非只读的 sources.yaml）
    user_src = get_user_sources_path()
    user_src.parent.mkdir(parents=True, exist_ok=True)
    if user_src.is_file():
        raw = user_src.read_text(encoding="utf-8")
        config = yaml.safe_load(raw) or {}
    else:
        config = {}
    sources: list = config.get("sources", []) or []
    existing_ids = {s.get("id") for s in sources if isinstance(s, dict)}
    if source_id in existing_ids:
        raise HTTPException(status_code=409, detail=f"同步源已存在：{source_id}（{path}）")

    new_source = {
        "id": source_id,
        "type": "local",
        "order": max((s.get("order", 0) or 0) for s in sources if isinstance(s, dict)) + 10 if sources else 50,
        "path": str(path),
        "include": ["**/*.md", "**/*.py"],
    }
    sources.append(new_source)
    config["sources"] = sources
    user_src.write_text(yaml.dump(config, allow_unicode=True, default_flow_style=False, sort_keys=False), encoding="utf-8")
    reload_sources_config()
    add_audit_event("sources_custom_added", request, actor=resolve_actor(request), detail=f"id={source_id} path={path}")
    return {"ok": True, "source": new_source}


@app.post("/api/admin/sources/delete")
def admin_delete_source(request: Request, body: dict[str, Any], _: Any = Depends(require_admin)) -> dict[str, Any]:
    from pathlib import Path
    import yaml

    source_id = (body.get("id") or "").strip()
    if not source_id:
        raise HTTPException(status_code=400, detail="source id is required")
    fixed_ids = {"all", "obsidian", "web_snapshots", "wiki"}
    if source_id in fixed_ids:
        raise HTTPException(status_code=400, detail=f"默认来源不可删除：{source_id}")

    parsed_id, parsed_type = parse_sync_key(source_id)

    def _source_matches(s: dict) -> bool:
        sid = s.get("id")
        if not sid:
            return False
        if sid == source_id:
            return True
        if parsed_type:
            stype = (s.get("type") or "local").strip().lower()
            return sid == parsed_id and stype == parsed_type
        return False

    # 1) 尝试从 sources.yaml（主文件，可能只读）删除
    src_file = Path(settings.sources_file)
    deleted = False
    if src_file.is_file():
        raw = src_file.read_text(encoding="utf-8")
        config = yaml.safe_load(raw) or {}
        sources: list = config.get("sources", [])
        before = len(sources)
        sources = [s for s in sources if isinstance(s, dict) and not _source_matches(s)]
        if len(sources) < before:
            config["sources"] = sources
            try:
                src_file.write_text(yaml.dump(config, allow_unicode=True, default_flow_style=False, sort_keys=False), encoding="utf-8")
                deleted = True
            except OSError:
                # sources.yaml 只读 → 在 user_sources.yaml 中记录已删除
                from .services.user_manager import get_user_sources_path
                usr_file = get_user_sources_path()
                _config = {}
                if usr_file.is_file():
                    _config = yaml.safe_load(usr_file.read_text(encoding="utf-8")) or {}
                _deleted: set = set(_config.get("_deleted", []))
                _deleted.add(source_id)
                _config["_deleted"] = list(_deleted)
                usr_file.parent.mkdir(parents=True, exist_ok=True)
                usr_file.write_text(yaml.dump(_config, allow_unicode=True, default_flow_style=False, sort_keys=False), encoding="utf-8")
                deleted = True

    # 2) 尝试从 user_sources.yaml（自定义源文件，始终可写）删除
    if not deleted:
        from .services.user_manager import get_user_sources_path
        usr_file = get_user_sources_path()
        if usr_file.is_file():
            raw = usr_file.read_text(encoding="utf-8")
            config = yaml.safe_load(raw) or {}
            sources: list = config.get("sources", [])
        before = len(sources)
        sources = [s for s in sources if isinstance(s, dict) and not _source_matches(s)]
        if len(sources) < before:
            config["sources"] = sources
            usr_file.write_text(yaml.dump(config, allow_unicode=True, default_flow_style=False, sort_keys=False), encoding="utf-8")
            deleted = True

    if not deleted:
        if src_found:
            raise HTTPException(status_code=405, detail=f"sources.yaml 为只读，无法删除：{source_id}")
        raise HTTPException(status_code=404, detail=f"来源不存在：{source_id}")

    reload_sources_config()
    add_audit_event("sources_deleted", request, actor=resolve_actor(request), detail=f"id={source_id}")
    return {"ok": True, "deleted": source_id}


# ──────────────────────────────────────────────
# User management (admin)
# ──────────────────────────────────────────────


@app.get("/api/admin/users")
def admin_list_users(request: Request, _: Any = Depends(require_admin)) -> dict[str, Any]:
    """List all users with their role, creation time, and source count."""
    from .services.user_manager import get_user_dir

    from .services.user_manager import load_user_sources as _load_user_sources
    from .services.sync_settings import list_sync_presets
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT username, role, created_at, display_name, locked_until FROM users ORDER BY created_at"
        ).fetchall()
        user_sources = _load_user_sources()
        # 管理员源数量 = 全局预设中无 owner 的条目数
        all_presets = list_sync_presets()
        admin_source_count = sum(1 for p in all_presets if p.get("owner") is None and p.get("id") not in ("all", "custom"))
        user_map = {}
        for s in user_sources:
            if isinstance(s, dict):
                user_map.setdefault(s.get("owner"), 0)
                user_map[s.get("owner")] += 1
        items = []
        now = time.time()
        for row in rows:
            username = row["username"]
            role = row["role"]
            udir = get_user_dir(username)
            if role == "admin":
                source_count = admin_source_count
            else:
                source_count = user_map.get(username, 0)
            locked_until = row["locked_until"] or 0
            status = "locked" if locked_until > now else "normal"
            items.append({
                "username": username,
                "display_name": row["display_name"] or username,
                "role": role,
                "created_at": row["created_at"],
                "has_dir": udir.exists(),
                "source_count": source_count,
                "status": status,
            })
        return {"users": items}
    finally:
        conn.close()


@app.post("/api/admin/users")
def admin_create_user(request: Request, body: dict[str, Any], _: Any = Depends(require_admin)) -> dict[str, Any]:
    """Create a new user, their personal directory, and default private source."""
    import traceback
    from .services.user_manager import append_user_source_to_yaml, build_user_source_entry, ensure_user_dir
    from .services.password_util import hash_password
    from .services.indexer import reload_sources_config

    username = (body.get("username") or "").strip()
    password = body.get("password") or ""
    role = (body.get("role") or "member").strip().lower()
    display_name = (body.get("display_name") or "").strip()
    if role not in ("admin", "member"):
        raise HTTPException(status_code=400, detail="角色必须是 admin 或 member")
    if not username or len(username) < 2:
        raise HTTPException(status_code=400, detail="用户名至少 2 个字符")
    if len(password) < 4:
        raise HTTPException(status_code=400, detail="密码至少 4 个字符")

    # 1) Create user in DB
    conn = get_db()
    try:
        existing = conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail=f"用户已存在：{username}")
        password_hash = hash_password(password)
        conn.execute(
            "INSERT INTO users(username, password_hash, role, created_at, display_name) VALUES (?, ?, ?, ?, ?)",
            (username, password_hash, role, time.time(), display_name or username),
        )
        conn.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error("创建用户 DB 失败: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"数据库错误: {e}")
    finally:
        conn.close()

    # 2) Create user directory and register source in sources.yaml
    try:
        ensure_user_dir(username)
    except Exception as e:
        logger.error("创建用户目录失败: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"创建目录失败: {e}")

    try:
        entry = build_user_source_entry(username)
        append_user_source_to_yaml(entry)
    except Exception as e:
        logger.error("写入 sources.yaml 失败: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"写入 sources.yaml 失败: {e}")

    try:
        reload_sources_config()
    except Exception as e:
        logger.error("重载 sources 配置失败: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"重载配置失败: {e}")

    add_audit_event("user_created", request, actor=resolve_actor(request), detail=f"username={username} role={role}")
    return {"ok": True, "username": username}


@app.delete("/api/admin/users/{username}")
def admin_delete_user(request: Request, username: str, _: Any = Depends(require_admin)) -> dict[str, Any]:
    """Delete a user — 移除 DB、索引数据、私有源配置，但保留用户目录（复用）。"""
    from .services.user_manager import (
        delete_user_index_data,
        remove_user_source_from_yaml,
    )
    from .services.indexer import reload_sources_config

    if username == resolve_actor(request):
        raise HTTPException(status_code=400, detail="不能删除自己")
    conn = get_db()
    try:
        existing = conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail=f"用户不存在：{username}")
        # Remove user from DB
        conn.execute("DELETE FROM users WHERE username = ?", (username,))
        conn.execute("DELETE FROM sessions WHERE username = ?", (username,))
        conn.commit()
    finally:
        conn.close()
    # Clean up data
    delete_user_index_data(username)
    remove_user_source_from_yaml(username)
    reload_sources_config()
    add_audit_event("user_deleted", request, actor=resolve_actor(request), detail=f"username={username} (directory kept)")
    return {"ok": True, "username": username}


@app.put("/api/admin/users/{username}/role")
def admin_set_user_role(request: Request, username: str, body: dict[str, Any], _: Any = Depends(require_admin)) -> dict[str, Any]:
    """Change a user's role.

    - member → admin: 目录保留（休眠），移除私有源注册
    - admin → member: 创建/确保目录存在，注册私有源
    """
    from .services.user_manager import (
        append_user_source_to_yaml,
        build_user_source_entry,
        ensure_user_dir,
        remove_user_source_from_yaml,
    )
    from .services.indexer import reload_sources_config

    role = (body.get("role") or "").strip().lower()
    if role not in ("admin", "member"):
        raise HTTPException(status_code=400, detail="角色必须是 admin 或 member")
    conn = get_db()
    try:
        existing = conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail=f"用户不存在：{username}")
        conn.execute("UPDATE users SET role = ? WHERE username = ?", (role, username))
        conn.commit()
    finally:
        conn.close()

    if role == "member":
        # 切换为普通用户 → 创建/确保用户目录存在，注册私有源
        try:
            ensure_user_dir(username)
        except Exception as e:
            logger.error("创建用户目录失败: %s", traceback.format_exc())
            raise HTTPException(status_code=500, detail=f"创建目录失败: {e}")
        try:
            entry = build_user_source_entry(username)
            append_user_source_to_yaml(entry)
        except Exception as e:
            logger.error("写入 user_sources.yaml 失败: %s", traceback.format_exc())
            raise HTTPException(status_code=500, detail=f"写入源配置失败: {e}")
    else:
        # 切换为管理员 → 仅移除私有源注册，目录保留（休眠状态）
        remove_user_source_from_yaml(username)

    reload_sources_config()
    add_audit_event("user_role_changed", request, actor=resolve_actor(request), detail=f"username={username} role={role}")
    return {"ok": True, "username": username, "role": role}


@app.post("/api/admin/users/{username}/reset-password")
def admin_reset_password(
    request: Request,
    username: str,
    body: dict[str, Any],
    _: Any = Depends(require_admin),
) -> dict[str, bool]:
    """Admin resets another user's password."""
    from .services.password_util import hash_password

    new_password = (body.get("new_password") or "").strip()
    if len(new_password) < 4:
        raise HTTPException(status_code=400, detail="密码至少 4 个字符")
    conn = get_db()
    try:
        existing = conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail=f"用户不存在：{username}")
        new_hash = hash_password(new_password)
        conn.execute("UPDATE users SET password_hash = ? WHERE username = ?", (new_hash, username))
        conn.commit()
    finally:
        conn.close()
    add_audit_event("password_reset", request, actor=resolve_actor(request), detail=f"username={username}")
    return {"ok": True}


@app.get("/api/user/me")
def user_me(request: Request, _: Any = Depends(require_any_auth)) -> dict[str, Any]:
    """Return current user's profile."""
    from .services.user_manager import get_user_dir

    username, role = resolve_current_user(request)
    if not username:
        return {"username": None, "role": role, "source_count": 0}
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT username, role, created_at, display_name FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        if not row:
            return {"username": username, "role": role, "source_count": 0}
        source_count = conn.execute(
            "SELECT COUNT(1) AS c FROM documents WHERE source_owner = ?", (username,)
        ).fetchone()["c"]
        udir = get_user_dir(username)
        return {
            "username": row["username"],
            "display_name": row["display_name"] or row["username"],
            "role": row["role"],
            "created_at": row["created_at"],
            "has_dir": udir.exists(),
            "source_count": source_count,
        }
    finally:
        conn.close()


# ──────────────────────────────────────────────
# User private source management
# ──────────────────────────────────────────────


@app.put("/api/user/display-name")
def user_set_display_name(request: Request, body: dict[str, Any], _: Any = Depends(require_any_auth)) -> dict[str, bool]:
    """Update current user's display name."""
    username, _ = resolve_current_user(request)
    if not username:
        raise HTTPException(status_code=401, detail="请先登录")
    display_name = (body.get("display_name") or "").strip()
    if not display_name:
        raise HTTPException(status_code=400, detail="表示名不能为空")
    if len(display_name) > 50:
        raise HTTPException(status_code=400, detail="表示名过长（最多 50 字符）")
    conn = get_db()
    try:
        conn.execute(
            "UPDATE users SET display_name = ? WHERE username = ?",
            (display_name, username),
        )
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}


@app.get("/api/user/sources")
def user_list_sources(request: Request, _: Any = Depends(require_any_auth)) -> dict[str, Any]:
    """Return sources visible to the current user (shared + own)."""
    from pathlib import Path
    username, role = resolve_current_user(request)
    sources_enriched = load_ordered_sources(username=username, role=role)
    items = []
    for source in sources_enriched:
        spath = str(source.path or "")
        # 获取 owner 的 display_name
        owner_display_name = None
        if source.owner:
            conn = get_db()
            try:
                row = conn.execute(
                    "SELECT display_name FROM users WHERE username = ?", (source.owner,)
                ).fetchone()
                if row and row["display_name"]:
                    owner_display_name = row["display_name"]
            finally:
                conn.close()
        items.append({
            "id": source.id,
            "sync_key": source_sync_key(source),
            "label": source_display_label(source),
            "type": source.source_type,
            "path": spath,
            "path_exists": Path(spath).exists() if spath else False,
            "owner": source.owner,
            "owner_display_name": owner_display_name,
            "is_shared": source.owner is None,
            "is_owned": source.owner == username,
            "shared": source.shared,
        })
    return {"sources": items}


@app.post("/api/user/sources")
def user_add_source(request: Request, body: dict[str, Any], _: Any = Depends(require_any_auth)) -> dict[str, Any]:
    """Add a private source owned by the current user (写入 user_sources.yaml 而非只读的 sources.yaml)。"""
    from pathlib import Path
    import yaml
    from .services.indexer import reload_sources_config
    from .services.user_manager import get_user_sources_path

    username, role = resolve_current_user(request)
    if not username:
        raise HTTPException(status_code=401, detail="请先登录")

    path_str = (body.get("path") or "").strip()
    if not path_str:
        raise HTTPException(status_code=400, detail="请输入路径")
    path = Path(path_str).expanduser().resolve()
    if not path.exists():
        raise HTTPException(status_code=400, detail=f"路径不存在：{path}")
    if not path.is_dir():
        raise HTTPException(status_code=400, detail=f"路径不是文件夹：{path}")

    # 确保路径在用户自己的目录下
    # 检查路径中是否包含 /users/<username>/ 段
    user_segment = f"/users/{username}/"
    if user_segment not in str(path):
        raise HTTPException(status_code=400, detail=f"只能在你的用户目录下添加源")

    source_id = path.name
    if not source_id or source_id.startswith("."):
        raise HTTPException(status_code=400, detail=f"文件夹名称无效：{source_id}")

    # 读写 user_sources.yaml（始终可写）
    user_src = get_user_sources_path()
    user_src.parent.mkdir(parents=True, exist_ok=True)
    if user_src.is_file():
        raw = user_src.read_text(encoding="utf-8")
        config = yaml.safe_load(raw) or {}
    else:
        config = {}
    sources: list = config.get("sources", []) or []
    # Check duplicate
    for s in sources:
        if isinstance(s, dict) and s.get("id") == source_id and s.get("owner") == username:
            raise HTTPException(status_code=409, detail=f"已存在同名来源：{source_id}")

    new_source = {
        "id": source_id,
        "type": "local",
        "owner": username,
        "path": str(path),
    }
    sources.append(new_source)
    config["sources"] = sources
    user_src.write_text(yaml.dump(config, allow_unicode=True, default_flow_style=False, sort_keys=False), encoding="utf-8")
    reload_sources_config()
    add_audit_event("user_source_added", request, actor=resolve_actor(request), detail=f"id={source_id} owner={username}")
    return {"ok": True, "source": new_source}


@app.put("/api/user/sources/{source_id}/share")
def user_toggle_source_share(request: Request, source_id: str, _: Any = Depends(require_any_auth)) -> dict[str, Any]:
    """Toggle the shared flag of a user's personal source."""
    from .services.user_manager import toggle_source_shared
    from .services.auth import require_own_source
    from .services.indexer import reload_sources_config

    require_own_source(source_id, request)
    username, _ = resolve_current_user(request)
    try:
        new_state = toggle_source_shared(username, source_id)
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(status_code=404, detail=str(e))
    reload_sources_config()
    add_audit_event("user_source_share_toggle", request, actor=resolve_actor(request),
                    detail=f"id={source_id} owner={username} shared={new_state}")
    return {"ok": True, "shared": new_state}


@app.delete("/api/user/sources/{source_id}")
def user_delete_source(request: Request, source_id: str, _: Any = Depends(require_any_auth)) -> dict[str, Any]:
    """Delete a private source owned by the current user (从 user_sources.yaml 删除)。"""
    import yaml
    from .services.indexer import reload_sources_config
    from .services.auth import require_own_source
    from .services.user_manager import get_user_sources_path

    require_own_source(source_id, request)
    username, _ = resolve_current_user(request)

    user_src = get_user_sources_path()
    if not user_src.is_file():
        raise HTTPException(status_code=404, detail=f"私有来源文件不存在：{user_src}")
    raw = user_src.read_text(encoding="utf-8")
    config = yaml.safe_load(raw) or {}
    sources: list = config.get("sources", []) or []
    before = len(sources)
    sources = [
        s for s in sources
        if not (isinstance(s, dict) and s.get("id") == source_id and s.get("owner") == username)
    ]
    if len(sources) == before:
        raise HTTPException(status_code=404, detail=f"来源不存在或无权限删除：{source_id}")
    config["sources"] = sources
    user_src.write_text(yaml.dump(config, allow_unicode=True, default_flow_style=False, sort_keys=False), encoding="utf-8")
    reload_sources_config()
    add_audit_event("user_source_deleted", request, actor=resolve_actor(request), detail=f"id={source_id} owner={username}")
    return {"ok": True, "deleted": source_id}


# ──────────────────────────────────────────────
# Admin stats & reindex
# ──────────────────────────────────────────────


@app.get("/api/admin/stats")
def admin_stats(_: Any = Depends(require_admin)) -> dict[str, Any]:
    """Return system statistics."""
    from pathlib import Path

    conn = get_db()
    try:
        doc_count = conn.execute("SELECT COUNT(1) AS c FROM documents").fetchone()["c"]
        user_count = conn.execute("SELECT COUNT(1) AS c FROM users").fetchone()["c"]
        src_count = len(load_sources())
        wiki_pages = sum(1 for _ in WIKI_DIR.rglob("*.md")) if WIKI_DIR.exists() else 0
    finally:
        conn.close()

    db_path = Path(settings.data_dir) / "mind_sync.db"
    db_size = db_path.stat().st_size if db_path.exists() else 0

    # Estimate source file sizes
    source_size = 0
    for src in load_sources():
        if src.path:
            p = Path(src.path)
            if p.exists():
                source_size += sum(f.stat().st_size for f in p.rglob("*") if f.is_file())

    return {
        "document_count": doc_count,
        "user_count": user_count,
        "source_count": src_count,
        "wiki_page_count": wiki_pages,
        "db_size": db_size,
        "source_size": source_size,
    }


@app.post("/api/admin/reindex")
def admin_reindex(request: Request, _: Any = Depends(require_admin)) -> dict[str, Any]:
    """Reindex all sources."""
    conn = get_db()
    results = []
    try:
        sources = load_sources()
        for source in sources:
            try:
                result = index_single_source(conn, source)
                results.append({
                    "source_id": source.id,
                    "status": result.get("status"),
                    "indexed": result.get("indexed", 0),
                })
            except Exception as e:
                results.append({"source_id": source.id, "status": "error", "error": str(e)})
        conn.commit()
    finally:
        conn.close()
    add_audit_event("reindex", request, actor=resolve_actor(request), detail=f"sources={len(results)}")
    return {"ok": True, "results": results}


@app.get("/api/settings")
def get_settings(request: Request, _: Any = Depends(require_any_auth)) -> dict[str, Any]:
    username, role = resolve_current_user(request)
    conn = get_db()
    st = read_settings(conn)
    conn.close()
    return enrich_settings_response(st, SCHEDULER.build_meta(st))





@app.post("/api/settings")
def update_settings(
    payload: SettingsUpdateRequest,
    request: Request,
    _: Any = Depends(require_any_auth),
) -> dict[str, Any]:
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

            all_src = load_sources()
            # 也接受预设 ID（如 web_snapshots 对应实际 source example_web）
            from .services.sync_settings import list_sync_presets

            valid_preset_ids = {p["id"] for p in list_sync_presets() if p.get("source_ids")}
            ids = [
                str(x).strip()
                for x in payload.sync_source_ids
                if str(x).strip()
                and (is_known_sync_key(str(x).strip(), all_src) or str(x).strip() in valid_preset_ids)
            ]
            conn.execute(
                "INSERT INTO app_settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                ("sync_source_ids", json.dumps(ids, ensure_ascii=False)),
            )
        if payload.sync_source_order is not None:
            import json

            all_src = load_sources()
            order_ids = [
                str(x).strip()
                for x in payload.sync_source_order
                if str(x).strip() and is_known_sync_key(str(x).strip(), all_src)
            ]
            conn.execute(
                "INSERT INTO app_settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                ("sync_source_order", json.dumps(order_ids, ensure_ascii=False)),
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
        actor=resolve_actor(request),
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
    _: Any = Depends(require_admin),
) -> dict[str, Any]:
    check_api_rate_limit(request, "sync")
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
            add_audit_event("sync_requested", request, actor=resolve_actor(request), detail="already running")
            return {"ok": True, "started": False, "message": "sync already running"}
        SYNC_STATE["running"] = True
    background_tasks.add_task(
        lambda: run_sync_job(
            "manual",
            source_ids,
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
    _: Any = Depends(require_admin),
) -> dict[str, Any]:
    """Full index rebuild: clear selected sources in SQLite, then re-scan every file."""
    check_api_rate_limit(request, "sync")
    body = payload or RebuildRequest()
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
            add_audit_event("rebuild_requested", request, actor=resolve_actor(request), detail="already running")
            return {"ok": True, "started": False, "mode": "rebuild", "message": "index job already running"}
        SYNC_STATE["running"] = True
    background_tasks.add_task(lambda: run_rebuild_job("manual", source_ids))
    detail = "rebuild started"
    if source_ids:
        detail += f" sources={','.join(source_ids)}"
    add_audit_event("rebuild_requested", request, actor=resolve_actor(request), detail=detail)
    return {"ok": True, "started": True, "mode": "rebuild", "source_ids": source_ids}


@app.get("/api/sync-status")
def sync_status(_: Any = Depends(require_any_auth)) -> dict[str, Any]:
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


def _read_wiki_page(path: str, username: str | None = None) -> dict[str, Any]:
    """Read a wiki page by relative path, respecting user namespace."""
    target = safe_wiki_path(path, WIKI_DIR, username=username)
    rel = (path or "").strip().replace("\\", "/")
    content = read_text_safely(target)
    return {"path": rel, "content": content}


@app.get("/api/wiki-content")
def wiki_content(path: str, request: Request, _: Any = Depends(require_any_auth)) -> dict[str, Any]:
    return _read_wiki_page(path, username=resolve_current_user(request)[0])


@app.get("/api/wiki-page")
def wiki_page(path: str, _: Any = Depends(require_any_auth)) -> dict[str, Any]:
    """Deprecated alias of /api/wiki-content."""
    return _read_wiki_page(path)


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
    target = safe_wiki_path(rel, WIKI_DIR, must_exist=False, username=username)
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


@app.post("/api/query")
def query(payload: QueryRequest, request: Request, _: Any = Depends(require_any_auth)) -> dict[str, Any]:
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
