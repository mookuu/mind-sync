"""Admin router: sources, users, stats, reindex."""
from __future__ import annotations
import time, traceback
from pathlib import Path
from typing import Any
import yaml

from fastapi import APIRouter, Depends, HTTPException, Request

from ..config import settings
from ..db import WIKI_DIR, get_db
from ..services.auth import resolve_actor, resolve_current_user, require_admin, require_any_auth
from ..services.audit import add_audit_event
from ..services.indexer import index_single_source, load_sources, reload_sources_config, resolve_source_root
from ..services.sync_settings import load_ordered_sources
from ..services.source_sync_key import parse_sync_key, source_display_label, source_sync_key
from ..services.web_fetch_policy import web_fetch_policy_summary

router = APIRouter(tags=["admin"])


# ── shared helpers ──────────────────────────────────────────

def _resolve_owner_display_name(owner: str | None) -> str | None:
    if not owner:
        return None
    conn = get_db()
    try:
        row = conn.execute("SELECT display_name FROM users WHERE username = ?", (owner,)).fetchone()
        if row and row["display_name"]:
            return row["display_name"]
        return None
    finally:
        conn.close()


def _add_notification(target_username: str, message: str, *, action_link: str = "", highlight: bool = False) -> None:
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO user_notifications(username, message, action_link, highlight, created_at) VALUES(?, ?, ?, ?, ?)",
            (target_username, message, action_link, 1 if highlight else 0, time.time()),
        )
        conn.commit()
    finally:
        conn.close()


# ── sources (shared + admin) ────────────────────────────────

@router.get("/api/sources")
def sources(request: Request, _: Any = Depends(require_any_auth)) -> dict[str, Any]:
    username, role = resolve_current_user(request)
    from ..db import load_settings_map
    settings_map = load_settings_map()
    items = []
    for source in load_ordered_sources(settings_map, username=username, role=role):
        root = resolve_source_root(source)
        items.append({
            "id": source.id,
            "sync_key": source_sync_key(source),
            "label": source_display_label(source),
            "type": source.source_type,
            "path": str(root),
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
        })
    return {"sources": items, "web_fetch_policy": web_fetch_policy_summary()}


@router.post("/api/admin/sources/reload")
def admin_reload_sources(request: Request, _: Any = Depends(require_admin)) -> dict[str, Any]:
    src_file = Path(settings.sources_file)
    if not src_file.is_file():
        raise HTTPException(status_code=404, detail=f"sources file not found: {src_file}")
    reload_sources_config()
    username, role = resolve_current_user(request)
    from ..db import load_settings_map
    settings_map = load_settings_map()
    items = []
    for source in load_ordered_sources(settings_map, username=username, role=role):
        root = resolve_source_root(source)
        items.append({
            "id": source.id, "sync_key": source_sync_key(source), "label": source_display_label(source),
            "type": source.source_type, "path": str(root), "path_exists": root.exists(),
            "url": source.url, "branch": source.branch, "paths": source.paths,
            "include": source.include, "order": source.order, "exists": root.exists(),
            "fetch_confirmed": source.fetch_confirmed, "respect_robots": source.respect_robots,
            "owner": source.owner, "owner_display_name": _resolve_owner_display_name(source.owner),
        })
    payload = {"sources": items, "web_fetch_policy": web_fetch_policy_summary()}
    payload["ok"] = True
    payload["count"] = len(payload["sources"])
    add_audit_event("sources_reloaded", request, actor=resolve_actor(request), detail=f"count={payload['count']} file={src_file}")
    return payload


@router.get("/api/admin/browse-dir")
def browse_directory(path: str = "", _: Any = Depends(require_any_auth)) -> dict[str, Any]:
    if not path:
        default = getattr(settings, "data_root", None) or str(Path.home())
        path = default
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


@router.post("/api/admin/sources/custom")
def admin_add_custom_source(request: Request, body: dict[str, Any], _: Any = Depends(require_admin)) -> dict[str, Any]:
    from ..services.user_manager import get_user_sources_path
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
        "id": source_id, "type": "local",
        "order": max((s.get("order", 0) or 0) for s in sources if isinstance(s, dict)) + 10 if sources else 50,
        "path": str(path),
        "include": ["**/*.md", "**/*.py", "**/*.java", "**/*.txt", "**/*.json", "**/*.yaml", "**/*.yml", "**/*.xml",
                     "**/*.html", "**/*.css", "**/*.js", "**/*.ts", "**/*.sh", "**/*.bash", "**/*.sql",
                     "**/*.cfg", "**/*.ini", "**/*.toml"],
    }
    sources.append(new_source)
    config["sources"] = sources
    user_src.write_text(yaml.dump(config, allow_unicode=True, default_flow_style=False, sort_keys=False), encoding="utf-8")
    reload_sources_config()
    add_audit_event("sources_custom_added", request, actor=resolve_actor(request), detail=f"id={source_id} path={path}")
    return {"ok": True, "source": new_source}


@router.post("/api/admin/sources/delete")
def admin_delete_source(request: Request, body: dict[str, Any], _: Any = Depends(require_admin)) -> dict[str, Any]:
    from ..services.user_manager import get_user_sources_path
    source_id = (body.get("id") or "").strip()
    if not source_id:
        raise HTTPException(status_code=400, detail="source id is required")
    fixed_ids = {"all", "obsidian", "web_snapshots", "wiki"}
    if source_id in fixed_ids:
        raise HTTPException(status_code=400, detail=f"默认来源不可删除：{source_id}")
    parsed_id, parsed_type = parse_sync_key(source_id)

    def _source_matches(s: dict) -> bool:
        sid = s.get("id")
        if not sid: return False
        if sid == source_id: return True
        if parsed_type:
            return sid == parsed_id and (s.get("type") or "local").strip().lower() == parsed_type
        return False

    src_file = Path(settings.sources_file)
    deleted = False
    if src_file.is_file():
        raw = src_file.read_text(encoding="utf-8")
        config = yaml.safe_load(raw) or {}
        sources_list: list = config.get("sources", [])
        before = len(sources_list)
        sources_list = [s for s in sources_list if isinstance(s, dict) and not _source_matches(s)]
        if len(sources_list) < before:
            config["sources"] = sources_list
            try:
                src_file.write_text(yaml.dump(config, allow_unicode=True, default_flow_style=False, sort_keys=False), encoding="utf-8")
                deleted = True
            except OSError:
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

    if not deleted:
        usr_file = get_user_sources_path()
        if usr_file.is_file():
            raw = usr_file.read_text(encoding="utf-8")
            config = yaml.safe_load(raw) or {}
            sources_list = config.get("sources", [])
            before = len(sources_list)
            sources_list = [s for s in sources_list if isinstance(s, dict) and not _source_matches(s)]
            if len(sources_list) < before:
                config["sources"] = sources_list
                usr_file.write_text(yaml.dump(config, allow_unicode=True, default_flow_style=False, sort_keys=False), encoding="utf-8")
                deleted = True

    if not deleted:
        raise HTTPException(status_code=404, detail=f"来源不存在：{source_id}")

    deleted_owner = ""
    deleted_label = source_id
    for s in (sources_list if 'sources_list' in dir() else []):
        if isinstance(s, dict) and _source_matches(s):
            deleted_owner = s.get("owner") or ""
            deleted_label = s.get("id") or source_id
            break

    reload_sources_config()
    cleanup_id = parsed_id or source_id
    try:
        conn = get_db()
        from ..services.indexer import clear_source_index
        clear_source_index(conn, cleanup_id)
        conn.commit()
    except Exception:
        pass
    finally:
        try: conn.close()
        except Exception: pass

    actor = resolve_actor(request)
    if deleted_owner and deleted_owner != actor:
        _add_notification(deleted_owner, f"{actor} 删除了 {deleted_label}，请通过同步控制页面更新库信息",
                          action_link="/sync/control", highlight=True)
    add_audit_event("sources_deleted", request, actor=actor, detail=f"id={source_id}")
    return {"ok": True, "deleted": source_id}


# ── user management ─────────────────────────────────────────

@router.get("/api/admin/users")
def admin_list_users(request: Request, _: Any = Depends(require_admin)) -> dict[str, Any]:
    from ..services.user_manager import get_user_dir, load_user_sources as _load_user_sources
    from ..services.sync_settings import list_sync_presets
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT username, role, created_at, display_name, locked_until, deleted_at FROM users ORDER BY created_at"
        ).fetchall()
        user_sources = _load_user_sources()
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
            uname = row["username"]
            role = row["role"]
            udir = get_user_dir(uname)
            source_count = admin_source_count if role == "admin" else user_map.get(uname, 0)
            deleted_at = row["deleted_at"] or 0
            locked_until = row["locked_until"] or 0
            if deleted_at > 0: status = "deleted"
            elif locked_until > now: status = "locked"
            else: status = "normal"
            items.append({"username": uname, "display_name": row["display_name"] or uname, "role": role,
                          "created_at": row["created_at"], "has_dir": udir.exists(),
                          "source_count": source_count, "status": status})
        return {"users": items}
    finally:
        conn.close()


@router.post("/api/admin/users")
def admin_create_user(request: Request, body: dict[str, Any], _: Any = Depends(require_admin)) -> dict[str, Any]:
    from ..services.user_manager import append_user_source_to_yaml, build_user_source_entry, ensure_user_dir
    from ..services.password_util import hash_password
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

    conn = get_db()
    try:
        existing = conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail=f"用户已存在：{username}")
        password_hash = hash_password(password)
        conn.execute("INSERT INTO users(username, password_hash, role, created_at, display_name) VALUES (?, ?, ?, ?, ?)",
                     (username, password_hash, role, time.time(), display_name or username))
        conn.commit()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"数据库错误: {e}")
    finally:
        conn.close()

    try: ensure_user_dir(username)
    except Exception as e: raise HTTPException(status_code=500, detail=f"创建目录失败: {e}")
    try:
        entry = build_user_source_entry(username)
        append_user_source_to_yaml(entry)
    except Exception as e: raise HTTPException(status_code=500, detail=f"写入 sources.yaml 失败: {e}")
    try: reload_sources_config()
    except Exception as e: raise HTTPException(status_code=500, detail=f"重载配置失败: {e}")

    add_audit_event("user_created", request, actor=resolve_actor(request), detail=f"username={username} role={role}")
    return {"ok": True, "username": username}


@router.delete("/api/admin/users/{username}")
def admin_delete_user(request: Request, username: str, _: Any = Depends(require_admin)) -> dict[str, Any]:
    from ..services.user_manager import remove_user_source_from_yaml
    if username == resolve_actor(request):
        raise HTTPException(status_code=400, detail="不能删除自己")
    conn = get_db()
    try:
        row = conn.execute("SELECT deleted_at FROM users WHERE username = ?", (username,)).fetchone()
        if not row: raise HTTPException(status_code=404, detail=f"用户不存在：{username}")
        if row["deleted_at"] and row["deleted_at"] > 0:
            raise HTTPException(status_code=400, detail="用户已注销")
        conn.execute("UPDATE users SET deleted_at = ? WHERE username = ?", (time.time(), username))
        conn.execute("DELETE FROM sessions WHERE username = ?", (username,))
        conn.commit()
    finally:
        conn.close()
    remove_user_source_from_yaml(username)
    reload_sources_config()
    add_audit_event("user_deleted", request, actor=resolve_actor(request), detail=f"username={username}")
    return {"ok": True, "username": username}


@router.put("/api/admin/users/{username}/role")
def admin_set_user_role(request: Request, username: str, body: dict[str, Any], _: Any = Depends(require_admin)) -> dict[str, Any]:
    from ..services.user_manager import append_user_source_to_yaml, build_user_source_entry, ensure_user_dir, remove_user_source_from_yaml, load_user_sources as _check_src
    role = (body.get("role") or "").strip().lower()
    if role not in ("admin", "member"):
        raise HTTPException(status_code=400, detail="角色必须是 admin 或 member")
    conn = get_db()
    try:
        existing = conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone()
        if not existing: raise HTTPException(status_code=404, detail=f"用户不存在：{username}")
        conn.execute("UPDATE users SET role = ? WHERE username = ?", (role, username))
        conn.commit()
    finally:
        conn.close()
    if role == "member":
        try: ensure_user_dir(username)
        except Exception as e: raise HTTPException(status_code=500, detail=f"创建目录失败: {e}")
        existing_srcs = [s for s in _check_src() if isinstance(s, dict) and s.get("owner") == username]
        if not existing_srcs:
            try:
                append_user_source_to_yaml(build_user_source_entry(username))
            except Exception as e: raise HTTPException(status_code=500, detail=f"写入源配置失败: {e}")
    reload_sources_config()
    add_audit_event("user_role_changed", request, actor=resolve_actor(request), detail=f"username={username} role={role}")
    return {"ok": True, "username": username, "role": role}


@router.post("/api/admin/users/{username}/reset-password")
def admin_reset_password(request: Request, username: str, body: dict[str, Any], _: Any = Depends(require_admin)) -> dict[str, bool]:
    from ..services.password_util import hash_password
    new_password = (body.get("new_password") or "").strip()
    if len(new_password) < 4:
        raise HTTPException(status_code=400, detail="密码至少 4 个字符")
    conn = get_db()
    try:
        existing = conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone()
        if not existing: raise HTTPException(status_code=404, detail=f"用户不存在：{username}")
        conn.execute("UPDATE users SET password_hash = ? WHERE username = ?", (hash_password(new_password), username))
        conn.commit()
    finally:
        conn.close()
    add_audit_event("password_reset", request, actor=resolve_actor(request), detail=f"username={username}")
    return {"ok": True}


# ── stats + reindex ─────────────────────────────────────────

@router.get("/api/admin/stats")
def admin_stats(_: Any = Depends(require_admin)) -> dict[str, Any]:
    conn = get_db()
    try:
        doc_count = conn.execute("SELECT COUNT(1) FROM documents").fetchone()[0]
        user_count = conn.execute("SELECT COUNT(1) FROM users WHERE deleted_at IS NULL OR deleted_at = 0").fetchone()[0]
        src_count = len(load_sources())
        wiki_pages = len(list(WIKI_DIR.rglob("*.md"))) if WIKI_DIR.exists() else 0
    finally:
        conn.close()

    from ..config import settings as _cfg
    db_path = Path(_cfg.data_dir) / "mind_sync.db"
    db_size = db_path.stat().st_size if db_path.exists() else 0
    source_size = 0
    for src in load_sources():
        if src.path:
            p = Path(src.path)
            if p.exists():
                source_size += sum(f.stat().st_size for f in p.rglob("*") if f.is_file())

    conn2 = get_db()
    try:
        user_rows = conn2.execute(
            "SELECT d.source_owner, COUNT(1) AS c FROM documents d GROUP BY d.source_owner").fetchall()
    finally:
        conn2.close()
    user_doc_counts = {}
    for row in user_rows:
        owner = row["source_owner"] or "__shared__"
        user_doc_counts[owner] = user_doc_counts.get(owner, 0) + row["c"]

    return {"doc_count": doc_count, "user_count": user_count, "src_count": src_count,
            "wiki_pages": wiki_pages, "db_size": db_size, "source_size": source_size,
            "user_doc_counts": user_doc_counts}


@router.post("/api/admin/reindex")
def admin_reindex(request: Request, _: Any = Depends(require_admin)) -> dict[str, Any]:
    conn = get_db()
    results = []
    try:
        for source in load_sources():
            try:
                result = index_single_source(conn, source)
                results.append({"source_id": source.id, "status": result.get("status"), "indexed": result.get("indexed", 0)})
            except Exception as e:
                results.append({"source_id": source.id, "status": "error", "error": str(e)})
        conn.commit()
    finally:
        conn.close()
    add_audit_event("reindex", request, actor=resolve_actor(request), detail=f"sources={len(results)}")
    return {"ok": True, "results": results}


# ── admin sources management ────────────────────────────────

@router.get("/api/admin/sources-status")
def admin_sources_status(request: Request, _: Any = Depends(require_admin)) -> dict[str, Any]:
    """返回所有知识库状态列表（含全局默认源），owner=None 的显示为 admin。"""
    from ..services.indexer import load_sources
    from ..services.source_sync_key import source_sync_key, source_display_label

    conn = get_db()
    try:
        # 获取每个源的文档统计
        rows = conn.execute(
            "SELECT source_id, source_owner, MAX(updated_at) AS max_updated, MIN(updated_at) AS min_updated, COUNT(1) AS doc_count "
            "FROM documents GROUP BY source_id, source_owner"
        ).fetchall()
        update_map: dict[str, float] = {}
        create_map: dict[str, float] = {}
        doc_count_map: dict[str, int] = {}
        for row in rows:
            key = f"{row['source_id']}|{row['source_owner'] or ''}"
            update_map[key] = row["max_updated"] or 0
            create_map[key] = row["min_updated"] or 0
            doc_count_map[key] = row["doc_count"] or 0
    finally:
        conn.close()

    items = []
    for src in load_sources():
        root = resolve_source_root(src)
        sk = source_sync_key(src)
        key = f"{src.id}|{src.owner or ''}"
        display_owner = src.owner or "admin"
        owner_dn = _resolve_owner_display_name(src.owner) if src.owner else None

        items.append({
            "source_id": sk,
            "label": source_display_label(src),
            "owner": display_owner,
            "owner_display_name": owner_dn or display_owner,
            "path": src.path or str(root),
            "path_exists": root.exists(),
            "shared": bool(src.shared),
            "source_type": src.source_type or "local",
            "updated_at": update_map.get(key, 0),
            "created_at": create_map.get(key, 0),
            "doc_count": doc_count_map.get(key, 0),
        })

    # 按 owner 排序：admin（全局源）在前，其他按用户名排序
    items.sort(key=lambda x: (0 if x["owner"] == "admin" else 1, x["owner"], x["source_id"]))
    return {"sources": items}


@router.post("/api/admin/sources/{source_id}/share")
def admin_toggle_source_share(request: Request, source_id: str, _: Any = Depends(require_admin)) -> dict[str, Any]:
    """管理员强制切换任意库的共享状态（含全局库）。"""
    from ..services.user_manager import get_user_sources_path

    # 查找源
    all_sources = load_sources()
    target = None
    for s in all_sources:
        sk = source_sync_key(s)
        if sk == source_id or s.id == source_id:
            target = s
            break

    if target is None:
        raise HTTPException(status_code=404, detail=f"来源不存在：{source_id}")

    import yaml as _yaml

    if target.owner is None:
        # 全局库：修改 sources.yaml
        src_file = Path(settings.sources_file)
        if not src_file.is_file():
            raise HTTPException(status_code=404, detail="全局源配置文件不存在")
        raw = src_file.read_text(encoding="utf-8")
        config = _yaml.safe_load(raw) or {}
        sources_list: list = config.get("sources", []) or []
        new_state = None
        for entry in sources_list:
            if isinstance(entry, dict) and entry.get("id") == target.id:
                current = bool(entry.get("shared", False))
                entry["shared"] = not current
                new_state = not current
                config["sources"] = sources_list
                src_file.write_text(_yaml.dump(config, allow_unicode=True, default_flow_style=False, sort_keys=False), encoding="utf-8")
                break
        if new_state is None:
            # 源不在 sources.yaml 中，追加
            new_state = True
            sources_list.append({"id": target.id, "type": target.source_type, "path": target.path,
                                 "include": target.include, "shared": True})
            config["sources"] = sources_list
            src_file.write_text(_yaml.dump(config, allow_unicode=True, default_flow_style=False, sort_keys=False), encoding="utf-8")
    else:
        # 私有库：修改 user_sources.yaml
        user_src = get_user_sources_path()
        if not user_src.is_file():
            raise HTTPException(status_code=404, detail="用户源配置文件不存在")
        raw = user_src.read_text(encoding="utf-8")
        config = _yaml.safe_load(raw) or {}
        sources_list: list = config.get("sources", []) or []
        new_state = None
        for entry in sources_list:
            if isinstance(entry, dict) and entry.get("id") == target.id and entry.get("owner") == target.owner:
                current = bool(entry.get("shared", False))
                entry["shared"] = not current
                new_state = not current
                config["sources"] = sources_list
                user_src.write_text(_yaml.dump(config, allow_unicode=True, default_flow_style=False, sort_keys=False), encoding="utf-8")
                break
        if new_state is None:
            raise HTTPException(status_code=404, detail=f"来源不在可编辑配置中：{source_id}")

    reload_sources_config()
    actor = resolve_actor(request)
    action = "共享" if new_state else "取消共享"
    if target.owner and target.owner != actor:
        _add_notification(target.owner, f"{actor} {action}了 {target.id}，请通过同步控制页面更新库信息",
                          action_link="/sync/control", highlight=True)
    add_audit_event("admin_source_share_toggle", request, actor=actor,
                    detail=f"id={source_id} owner={target.owner} shared={new_state}")
    return {"ok": True, "shared": new_state}


@router.post("/api/admin/sources/{source_id}/delete")
def admin_delete_any_source(request: Request, source_id: str, _: Any = Depends(require_admin)) -> dict[str, Any]:
    """管理员删除任意库（全局或私有）。"""
    from ..services.user_manager import get_user_sources_path

    all_sources = load_sources()
    target = None
    for s in all_sources:
        sk = source_sync_key(s)
        if sk == source_id or s.id == source_id:
            target = s
            break

    if target is None:
        raise HTTPException(status_code=404, detail=f"来源不存在：{source_id}")

    fixed_ids = {"all", "obsidian", "web_snapshots", "wiki"}
    if target.id in fixed_ids and target.owner is None:
        raise HTTPException(status_code=400, detail=f"默认来源不可删除：{target.id}")

    deleted = False
    # 尝试从 sources.yaml 删除（全局源）
    src_file = Path(settings.sources_file)
    if src_file.is_file() and target.owner is None:
        raw = yaml.safe_load(src_file.read_text(encoding="utf-8")) or {}
        sources_list: list = raw.get("sources", []) or []
        before = len(sources_list)
        sources_list = [s for s in sources_list if isinstance(s, dict) and s.get("id") != target.id]
        if len(sources_list) < before:
            raw["sources"] = sources_list
            src_file.write_text(yaml.dump(raw, allow_unicode=True, default_flow_style=False, sort_keys=False), encoding="utf-8")
            deleted = True

    # 尝试从 user_sources.yaml 删除（私有源）
    if not deleted:
        user_src = get_user_sources_path()
        if user_src.is_file():
            raw = yaml.safe_load(user_src.read_text(encoding="utf-8")) or {}
            sources_list = raw.get("sources", []) or []
            before = len(sources_list)
            sources_list = [s for s in sources_list if not (isinstance(s, dict) and s.get("id") == target.id and s.get("owner") == target.owner)]
            if len(sources_list) < before:
                raw["sources"] = sources_list
                user_src.write_text(yaml.dump(raw, allow_unicode=True, default_flow_style=False, sort_keys=False), encoding="utf-8")
                deleted = True

    if not deleted:
        raise HTTPException(status_code=404, detail=f"来源不可删除：{source_id}")

    reload_sources_config()
    # 清理索引
    try:
        conn = get_db()
        from ..services.indexer import clear_source_index
        clear_source_index(conn, target.id)
        conn.commit()
    except Exception:
        pass
    finally:
        try: conn.close()
        except Exception: pass

    actor = resolve_actor(request)
    if target.owner and target.owner != actor:
        _add_notification(target.owner, f"{actor} 删除了您的库 {target.id}，请通过同步控制页面更新库信息",
                          action_link="/sync/control", highlight=True)
    add_audit_event("admin_source_deleted", request, actor=actor,
                    detail=f"id={source_id} owner={target.owner or 'admin'}")
    return {"ok": True, "deleted": source_id}
