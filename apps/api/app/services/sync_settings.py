import json
from pathlib import Path
from typing import Any

from ..models import Source
from .indexer import load_sources, load_sources_for_user, resolve_source_root
from .source_sync_key import (
    expand_sync_keys,
    filter_sources_by_sync_keys,
    is_known_sync_key,
    source_display_label,
    source_matches_sync_key,
    source_sync_key,
)

SYNC_PRESETS: dict[str, dict[str, Any]] = {
    "all": {
        "label": "全部来源（默认）",
        "description": "同步 sources.yaml 中所有已配置来源",
        "source_ids": None,
    },
    "obsidian": {
        "label": "Obsidian 剪藏",
        "description": "Obsidian Web Clipper 等导出的 Markdown",
        "source_ids": ["obsidian"],
        "path": "~/data/mind-sync-data/obsidian",
    },
    "web_snapshots": {
        "label": "Web 快照",
        "description": "抓取并转换的 Markdown",
        "source_ids": ["example_web"],
        "path": "~/data/mind-sync-data/web_snapshots",
    },
    "wiki": {
        "label": "Wiki",
        "description": "摘要与问答沉淀目录",
        "source_ids": ["wiki"],
        "path": "~/data/mind-sync-data/wiki",
    },
}

LANG_LABELS = {
    "python": "Python",
    "java": "Java",
    "markdown": "Markdown",
    "text": "Text",
    "unknown": "其他",
}

SOURCE_LABELS = {
    "PythonBasic": "Python 基础",
    "JavaBasic": "Java 基础",
    "knowledge_engineering": "知识工程",
    "obsidian": "Obsidian 剪藏",
    "example_web": "Web 快照",
    "example_github": "GitHub 仓库",
    "wiki": "Wiki 知识库",
}


def list_sync_presets() -> list[dict[str, Any]]:
    items = []
    fixed_ids = {"all", "obsidian", "web_snapshots", "wiki"}
    all_sources = load_sources()
    # 构建 fixed_id → shared 映射；用 resolve_source_root 检查路径存在性
    src_shared = {s.id: bool(s.shared) for s in all_sources}
    src_path_exists = {s.id: resolve_source_root(s).exists() for s in all_sources}

    for key, meta in SYNC_PRESETS.items():
        presets_path = meta.get("path", "")
        items.append(
            {
                "id": key,
                "label": meta["label"],
                "description": meta.get("description", ""),
                "source_ids": meta.get("source_ids"),
                "path": presets_path,
                "path_exists": src_path_exists.get(key),
                "shared": src_shared.get(key, False),
            }
        )
    from .source_sync_key import source_sync_key

    seen_ids = set()
    for src in all_sources:
        if src.id in fixed_ids:
            continue
        sk = source_sync_key(src)
        stype = (src.source_type or "local").lower()
        suffix = " (remote)" if stype == "github" else ""
        label = f"{src.id}{suffix}"
        spath = src.path or src.url or ""
        if sk in seen_ids:
            continue
        seen_ids.add(sk)
        items.append(
            {
                "id": sk,
                "label": label,
                "description": spath,
                "source_ids": [sk],
                "path": spath,
                "path_exists": Path(spath).exists() if spath and not spath.startswith(('http://', 'https://', 'git@')) else None,
                "type": stype,
                "owner": getattr(src, "owner", None),
                "shared": bool(getattr(src, "shared", False)),
            }
        )
    return items


def _parse_source_ids(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return [str(x).strip() for x in data if str(x).strip()]
    except Exception:
        pass
    return []


def apply_source_order(sources: list[Source], settings_map: dict[str, str] | None = None) -> list[Source]:
    """Order sources for sync/index merge. Does not affect search ranking."""
    if not sources:
        return []
    index_map = {source_sync_key(s): idx for idx, s in enumerate(sources)}
    manual: list[str] = []
    if settings_map is not None:
        manual = expand_sync_keys(_parse_source_ids(settings_map.get("sync_source_order")), sources)

    def sort_key(source: Source) -> tuple[int, int, int]:
        sk = source_sync_key(source)
        if manual:
            if sk in manual:
                return (0, manual.index(sk), index_map[sk])
            for i, mk in enumerate(manual):
                if source_matches_sync_key(source, mk):
                    return (0, i, index_map[sk])
        yaml_order = source.order if source.order is not None else 10_000
        return (1, yaml_order, index_map[sk])

    return sorted(sources, key=sort_key)


def load_ordered_sources(
    settings_map: dict[str, str] | None = None,
    username: str | None = None,
    role: str | None = None,
) -> list[Source]:
    sources = load_sources_for_user(username, role)
    return apply_source_order(sources, settings_map)


def read_sync_settings(settings_map: dict[str, str], username: str | None = None, role: str | None = None) -> dict[str, Any]:
    preset = (settings_map.get("sync_preset") or "all").strip() or "all"
    custom_ids = _parse_source_ids(settings_map.get("sync_source_ids"))
    manual_order = _parse_source_ids(settings_map.get("sync_source_order"))
    if role is None and username:
        from ..db import get_db as _gdb
        conn = _gdb()
        try:
            r = conn.execute("SELECT role FROM users WHERE username = ?", (username,)).fetchone()
            if r: role = r["role"]
        finally:
            conn.close()
    all_sources = load_sources_for_user(username, role)
    known_keys = {source_sync_key(s) for s in all_sources}
    expanded_custom = expand_sync_keys(custom_ids, all_sources)
    if preset == "custom":
        selected_keys = expanded_custom
    elif preset in SYNC_PRESETS:
        preset_ids = SYNC_PRESETS[preset].get("source_ids")
        if preset_ids is None:
            selected_keys = list(known_keys)
        else:
            selected_keys = expand_sync_keys(preset_ids, all_sources)
    else:
        preset = "all"
        selected_keys = list(known_keys)
    ordered_all = load_ordered_sources(settings_map, username=username, role=role)
    selected_set = set(selected_keys)
    effective_order = [source_sync_key(s) for s in ordered_all if source_sync_key(s) in selected_set]
    selected_labels = [source_display_label(s) for s in ordered_all if source_sync_key(s) in selected_set]
    return {
        "sync_preset": preset,
        "sync_source_ids": custom_ids,
        "sync_selected_source_ids": selected_labels,
        "sync_selected_keys": selected_keys,
        "sync_source_order": manual_order,
        "sync_effective_order": effective_order or [source_sync_key(s) for s in ordered_all],
        "sync_presets": list_sync_presets(),
    }


def resolve_sync_source_ids(settings_map: dict[str, str] | None = None, username: str | None = None, role: str | None = None) -> list[str] | None:
    """Return None to sync all sources, or a filtered ordered list of sync keys (id:type).

    Admin "all" = all visible sources. Non-admin "all" = owned sources + checked shared/global.
    """
    if settings_map is None:
        from ..db import load_settings_map

        settings_map = load_settings_map(username)
    meta = read_sync_settings(settings_map, username=username, role=role)
    all_srcs = load_ordered_sources(settings_map, username=username, role=role)
    all_keys = [source_sync_key(s) for s in all_srcs]

    if meta["sync_preset"] == "all":
        if role == "admin":
            # Admin "all": all global + all owned + checked shared
            global_keys = {source_sync_key(s) for s in all_srcs if s.owner is None}
            owned_keys = {source_sync_key(s) for s in all_srcs if s.owner == username}
            checked_keys = set(meta["sync_selected_keys"])
            shared_keys = checked_keys - global_keys - owned_keys
            effective = list(global_keys | owned_keys | shared_keys)
        else:
            # Non-admin "all": all owned + checked (global + shared)
            owned_keys = {source_sync_key(s) for s in all_srcs if s.owner == username}
            checked_keys = set(meta["sync_selected_keys"])
            effective = list(owned_keys | checked_keys)
        valid = [k for k in all_keys if k in set(effective)]
        return valid if valid else []

    selected_keys = meta["sync_selected_keys"]
    if not selected_keys or set(selected_keys) >= set(all_keys):
        return None
    selected_set = set(selected_keys)
    return [k for k in all_keys if k in selected_set]


def enrich_settings_response(settings_map: dict[str, str], scheduler_meta: dict[str, Any], username: str | None = None, role: str | None = None) -> dict[str, Any]:
    sync_meta = read_sync_settings(settings_map, username=username, role=role)
    data = dict(scheduler_meta)
    data.update(sync_meta)
    return data
