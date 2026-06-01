"""Heuristic wiki path suggestions without LLM."""

from __future__ import annotations

import re
from typing import Any

_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"python|django|flask|pytest", re.I), "summaries/python"),
    (re.compile(r"java|spring|jvm", re.I), "summaries/java"),
    (re.compile(r"harness|pipeline|ci/cd|devops", re.I), "summaries/harness"),
    (re.compile(r"agent|llm|rag|prompt", re.I), "summaries/ai"),
    (re.compile(r"git|github", re.I), "summaries/tooling"),
]


def suggest_wiki_path(query: str) -> dict[str, Any]:
    text = (query or "").strip()
    if not text:
        return {"suggestions": [], "recommended": None}
    suggestions: list[str] = []
    for pattern, folder in _RULES:
        if pattern.search(text):
            slug = re.sub(r"[^\w\u4e00-\u9fff]+", "-", text.lower())[:40].strip("-") or "note"
            path = f"{folder}/{slug}.md"
            if path not in suggestions:
                suggestions.append(path)
    recommended = suggestions[0] if suggestions else f"summaries/general/{text[:24].strip()}.md"
    return {"suggestions": suggestions[:5], "recommended": recommended}
