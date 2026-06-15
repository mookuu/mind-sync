import json
from typing import Any

from ..models import Source
from .indexer import load_sources
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
    },
    "web_snapshots": {
        "label": "Web 快照",
        "description": "type: web 抓取并转换的 Markdown",
        "source_ids": ["example_web"],
    },
    "wiki": {
        "label": "Wiki",
        "description": "摘要与问答沉淀目录",
        "source_ids": ["wiki"],
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
    for key, meta in SYNC_PRESETS.items():
        items.append(
            {
                "id": key,
                "label": meta["label"],
                "description": meta.get("description", ""),
                "source_ids": meta.get("source_ids"),
            }
        )
    items.append(
        {
            "id": "custom",
            "label": "自定义选择",
            "description": "手动勾选要同步的来源",
            "source_ids": None,
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


def load_ordered_sources(settings_map: dict[str, str] | None = None) -> list[Source]:
    return apply_source_order(load_sources(), settings_map)


def read_sync_settings(settings_map: dict[str, str]) -> dict[str, Any]:
    preset = (settings_map.get("sync_preset") or "all").strip() or "all"
    custom_ids = _parse_source_ids(settings_map.get("sync_source_ids"))
    manual_order = _parse_source_ids(settings_map.get("sync_source_order"))
    all_sources = load_sources()
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
    ordered_all = load_ordered_sources(settings_map)
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


def resolve_sync_source_ids(settings_map: dict[str, str] | None = None) -> list[str] | None:
    """Return None to sync all sources, or a filtered ordered list of sync keys (id:type)."""
    if settings_map is None:
        from ..db import load_settings_map

        settings_map = load_settings_map()
    meta = read_sync_settings(settings_map)
    selected_keys = meta["sync_selected_keys"]
    all_keys = [source_sync_key(s) for s in load_ordered_sources(settings_map)]
    if not selected_keys or set(selected_keys) >= set(all_keys):
        return None
    selected_set = set(selected_keys)
    return [k for k in all_keys if k in selected_set]


def enrich_settings_response(settings_map: dict[str, str], scheduler_meta: dict[str, Any]) -> dict[str, Any]:
    sync_meta = read_sync_settings(settings_map)
    data = dict(scheduler_meta)
    data.update(sync_meta)
    return data
