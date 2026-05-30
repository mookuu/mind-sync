import json
from typing import Any

from .indexer import load_sources

SYNC_PRESETS: dict[str, dict[str, Any]] = {
    "all": {
        "label": "全部来源（默认）",
        "description": "同步 sources.yaml 中所有已配置来源",
        "source_ids": None,
    },
    "learning_repos": {
        "label": "学习仓库",
        "description": "PythonBasic + JavaBasic",
        "source_ids": ["PythonBasic", "JavaBasic"],
    },
    "notes": {
        "label": "笔记与知识工程",
        "description": "knowledge_engineering 原始笔记",
        "source_ids": ["knowledge_engineering"],
    },
    "wiki": {
        "label": "仅 Wiki",
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


def read_sync_settings(settings_map: dict[str, str]) -> dict[str, Any]:
    preset = (settings_map.get("sync_preset") or "all").strip() or "all"
    custom_ids = _parse_source_ids(settings_map.get("sync_source_ids"))
    known = {s.id for s in load_sources()}
    if preset == "custom":
        selected = [sid for sid in custom_ids if sid in known]
    elif preset in SYNC_PRESETS:
        preset_ids = SYNC_PRESETS[preset].get("source_ids")
        selected = list(known) if preset_ids is None else [sid for sid in preset_ids if sid in known]
    else:
        preset = "all"
        selected = list(known)
    return {
        "sync_preset": preset,
        "sync_source_ids": custom_ids,
        "sync_selected_source_ids": selected,
        "sync_presets": list_sync_presets(),
    }


def resolve_sync_source_ids(settings_map: dict[str, str] | None = None) -> list[str] | None:
    """Return None to sync all sources, or a filtered list of source ids."""
    if settings_map is None:
        from ..db import load_settings_map

        settings_map = load_settings_map()
    meta = read_sync_settings(settings_map)
    selected = meta["sync_selected_source_ids"]
    all_ids = [s.id for s in load_sources()]
    if not selected or set(selected) >= set(all_ids):
        return None
    return selected


def enrich_settings_response(settings_map: dict[str, str], scheduler_meta: dict[str, Any]) -> dict[str, Any]:
    sync_meta = read_sync_settings(settings_map)
    data = dict(scheduler_meta)
    data.update(sync_meta)
    return data
