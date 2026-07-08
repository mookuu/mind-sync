"""User router: me, notifications, display-name, private sources."""
from __future__ import annotations
import time
from pathlib import Path
from typing import Any
import yaml

from fastapi import APIRouter, Depends, HTTPException, Request

from ..db import get_db
from ..services.auth import resolve_actor, resolve_current_user, require_any_auth, require_own_source
from ..services.audit import add_audit_event
from ..services.indexer import load_ordered_sources, reload_sources_config
from ..services.source_sync_key import source_display_label, source_sync_key

router = APIRouter(tags=["user"])


# ── helpers (used across routers) ────────────────────────────

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


# ── me ───────────────────────────────────────────────────────

@router.get("/api/user/me")
def user_me(request: Request, _: Any = Depends(require_any_auth)) -> dict[str, Any]:
    from ..services.user_manager import get_user_dir
    username, role = resolve_current_user(request)
    if not username:
        return {"username": None, "role": role, "source_count": 0}
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT username, role, created_at, display_name FROM users WHERE username = ?", (username,)
        ).fetchone()
        if not row:
            return {"username": username, "role": role, "source_count": 0}
        source_count = conn.execute(
            "SELECT COUNT(1) AS c FROM documents WHERE source_owner = ?", (username,)
        ).fetchone()["c"]
        udir = get_user_dir(username)
        return {"username": row["username"], "display_name": row["display_name"] or row["username"],
                "role": row["role"], "created_at": row["created_at"], "has_dir": udir.exists(),
                "source_count": source_count}
    finally:
        conn.close()


# ── notifications ────────────────────────────────────────────

@router.get("/api/user/notifications")
def user_notifications(request: Request, _: Any = Depends(require_any_auth)) -> dict[str, Any]:
    username, _ = resolve_current_user(request)
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT id, message, action_link, highlight, created_at FROM user_notifications WHERE username = ? AND read_at = 0 ORDER BY created_at DESC",
            (username,),
        ).fetchall()
        return {"notifications": [dict(r) for r in rows]}
    finally:
        conn.close()


@router.post("/api/user/notifications/{nid}/read")
def user_notification_read(request: Request, nid: int, _: Any = Depends(require_any_auth)) -> dict[str, Any]:
    username, _ = resolve_current_user(request)
    conn = get_db()
    try:
        conn.execute("UPDATE user_notifications SET read_at = ? WHERE id = ? AND username = ?",
                     (time.time(), nid, username))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


# ── display-name ─────────────────────────────────────────────

@router.put("/api/user/display-name")
def user_set_display_name(request: Request, body: dict[str, Any], _: Any = Depends(require_any_auth)) -> dict[str, bool]:
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
        conn.execute("UPDATE users SET display_name = ? WHERE username = ?", (display_name, username))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}


# ── private sources ──────────────────────────────────────────

@router.get("/api/user/sources")
def user_list_sources(request: Request, _: Any = Depends(require_any_auth)) -> dict[str, Any]:
    username, role = resolve_current_user(request)
    sources_enriched = load_ordered_sources(username=username, role=role)
    items = []
    for source in sources_enriched:
        spath = str(source.path or "")
        owner_display_name = None
        if source.owner:
            conn = get_db()
            try:
                row = conn.execute("SELECT display_name FROM users WHERE username = ?", (source.owner,)).fetchone()
                if row and row["display_name"]:
                    owner_display_name = row["display_name"]
            finally:
                conn.close()
        items.append({"id": source.id, "sync_key": source_sync_key(source), "label": source_display_label(source),
                      "type": source.source_type, "path": spath, "path_exists": Path(spath).exists() if spath else False,
                      "owner": source.owner, "owner_display_name": owner_display_name,
                      "is_shared": source.owner is None, "is_owned": source.owner == username, "shared": source.shared})
    return {"sources": items}


@router.post("/api/user/sources")
def user_add_source(request: Request, body: dict[str, Any], _: Any = Depends(require_any_auth)) -> dict[str, Any]:
    from ..services.user_manager import get_user_sources_path
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
    user_segment = f"/users/{username}/"
    if user_segment not in str(path):
        raise HTTPException(status_code=400, detail=f"只能在你的用户目录下添加源")
    source_id = path.name
    if not source_id or source_id.startswith("."):
        raise HTTPException(status_code=400, detail=f"文件夹名称无效：{source_id}")
    user_src = get_user_sources_path()
    user_src.parent.mkdir(parents=True, exist_ok=True)
    config = yaml.safe_load(user_src.read_text(encoding="utf-8")) if user_src.is_file() else {}
    sources: list = config.get("sources", []) or []
    for s in sources:
        if isinstance(s, dict) and s.get("id") == source_id and s.get("owner") == username:
            raise HTTPException(status_code=409, detail=f"已存在同名来源：{source_id}")
    new_source = {"id": source_id, "type": "local", "owner": username, "path": str(path),
                  "include": ["**/*.md", "**/*.py", "**/*.java", "**/*.txt", "**/*.json", "**/*.yaml", "**/*.yml",
                              "**/*.xml", "**/*.html", "**/*.css", "**/*.js", "**/*.ts", "**/*.sh", "**/*.bash",
                              "**/*.sql", "**/*.cfg", "**/*.ini", "**/*.toml"]}
    sources.append(new_source)
    config["sources"] = sources
    user_src.write_text(yaml.dump(config, allow_unicode=True, default_flow_style=False, sort_keys=False), encoding="utf-8")
    reload_sources_config()
    add_audit_event("user_source_added", request, actor=resolve_actor(request), detail=f"id={source_id} owner={username}")
    return {"ok": True, "source": new_source}


@router.put("/api/user/sources/{source_id}/share")
def user_toggle_source_share(request: Request, source_id: str, _: Any = Depends(require_any_auth)) -> dict[str, Any]:
    from ..services.user_manager import toggle_source_shared
    require_own_source(source_id, request)
    username, _ = resolve_current_user(request)
    try:
        new_state = toggle_source_shared(username, source_id)
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(status_code=404, detail=str(e))
    reload_sources_config()
    # 通知相关用户
    import json as _json
    source_key = f"{source_id}:local"
    conn2 = get_db()
    try:
        all_settings = conn2.execute("SELECT key, value FROM app_settings WHERE key LIKE '%:sync_source_ids'").fetchall()
        action = "共享" if new_state else "取消共享"
        for row in all_settings:
            try:
                ids = _json.loads(row["value"] or "[]")
                if source_key in ids or source_id in ids:
                    target_user = row["key"].split(":")[0]
                    if target_user != username:
                        _add_notification(target_user, f"{username} {action}了 {source_id}，请通过同步控制页面更新库信息",
                                          action_link="/sync/control")
            except Exception:
                pass
    finally:
        conn2.close()
    add_audit_event("user_source_share_toggle", request, actor=resolve_actor(request),
                    detail=f"id={source_id} owner={username} shared={new_state}")
    return {"ok": True, "shared": new_state}


@router.delete("/api/user/sources/{source_id}")
def user_delete_source(request: Request, source_id: str, _: Any = Depends(require_any_auth)) -> dict[str, Any]:
    from ..services.user_manager import get_user_sources_path
    require_own_source(source_id, request)
    username, _ = resolve_current_user(request)
    user_src = get_user_sources_path()
    if not user_src.is_file():
        raise HTTPException(status_code=404, detail=f"私有来源文件不存在：{user_src}")
    config = yaml.safe_load(user_src.read_text(encoding="utf-8")) or {}
    sources_list: list = config.get("sources", []) or []
    before = len(sources_list)
    sources_list = [s for s in sources_list if not (isinstance(s, dict) and s.get("id") == source_id and s.get("owner") == username)]
    if len(sources_list) == before:
        raise HTTPException(status_code=404, detail=f"来源不存在或无权限删除：{source_id}")
    config["sources"] = sources_list
    user_src.write_text(yaml.dump(config, allow_unicode=True, default_flow_style=False, sort_keys=False), encoding="utf-8")
    reload_sources_config()
    try:
        conn = get_db()
        from ..services.indexer import clear_source_index
        clear_source_index(conn, source_id)
        conn.commit()
    except Exception:
        pass
    finally:
        try: conn.close()
        except Exception: pass
    add_audit_event("user_source_deleted", request, actor=resolve_actor(request), detail=f"id={source_id} owner={username}")
    return {"ok": True, "deleted": source_id}
