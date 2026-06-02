#!/usr/bin/env python3
"""One-off helper: split apps/web/app.js into feature modules."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "apps" / "web"
src_lines = (ROOT / "app.js").read_text(encoding="utf-8").splitlines(keepends=True)


def slice_lines(start: int, end: int) -> str:
    return "".join(src_lines[start - 1 : end])


blocks: dict[str, list[tuple[int, int]]] = {
    "app-shared.js": [(1, 113), (228, 312), (588, 636)],
    "auth-ui.js": [(115, 226)],
    "search-ui.js": [(314, 503), (638, 757)],
    "sync-ui.js": [(517, 542), (669, 697), (759, 915)],
    "graph-ui.js": [(505, 515), (544, 1298)],
    "query-ui.js": [(699, 742), (1300, 1329)],
}

headers = {
    "app-shared.js": "/** Shared DOM state, API wrapper, modals (loaded before feature modules). */\n",
    "auth-ui.js": "/** Authentication UI (depends on app-shared.js). */\n",
    "search-ui.js": "/** Search, highlight, browse filters (depends on app-shared.js). */\n",
    "sync-ui.js": "/** Sync status, audit, lint, settings loaders (depends on app-shared.js). */\n",
    "graph-ui.js": "/** Wiki graph visualization (depends on app-shared.js). */\n",
    "query-ui.js": "/** Q&A panel (depends on app-shared.js). */\n",
}

removed: set[int] = set()
for fname, ranges in blocks.items():
    parts = [headers[fname]]
    for start, end in ranges:
        parts.append(slice_lines(start, end))
        removed.update(range(start, end + 1))
    (ROOT / fname).write_text("".join(parts), encoding="utf-8")

bindings: list[str] = []
for i, line in enumerate(src_lines, start=1):
    if i not in removed:
        bindings.append(line)

(ROOT / "app.js").write_text(
    "/** Event bindings and bootstrap (feature logic in *-ui.js modules). */\n" + "".join(bindings),
    encoding="utf-8",
)
print(f"split complete; app.js now {len(bindings)} lines")
