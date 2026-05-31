#!/usr/bin/env python3
import argparse
import ctypes
import json
import os
import sys
from typing import Any

import requests


def request_api(
    base_url: str,
    api_key: str,
    method: str,
    path: str,
    params: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
) -> Any:
    headers = {"x-api-key": api_key}
    url = f"{base_url.rstrip('/')}{path}"
    resp = requests.request(method, url, params=params, json=body, headers=headers, timeout=120)
    if not resp.ok:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text}")
    return resp.json()


def setup_utf8_console() -> None:
    # Best-effort UTF-8 output for Windows terminals.
    if os.name == "nt":
        try:
            ctypes.windll.kernel32.SetConsoleCP(65001)
            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        except Exception:
            pass
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def emit_result(result: Any, output_file: str | None) -> None:
    content = json.dumps(result, ensure_ascii=False, indent=2)
    if output_file:
        with open(output_file, "w", encoding="utf-8", newline="\n") as f:
            f.write(content + "\n")
        print(f"Result written to: {output_file}")
        return
    print(content)


def main() -> int:
    setup_utf8_console()
    parser = argparse.ArgumentParser(description="mind-sync CLI")
    parser.add_argument("--base-url", default=os.getenv("MINDSYNC_BASE_URL", "http://localhost:8000"))
    parser.add_argument("--api-key", default=os.getenv("MINDSYNC_API_KEY", "mind-sync-dev-key"))
    parser.add_argument(
        "--output-file",
        default=None,
        help="Write UTF-8 JSON result to file (recommended when terminal encoding is problematic).",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    sync_p = sub.add_parser("sync", help="trigger background sync")
    sync_p.set_defaults(func=lambda a: request_api(a.base_url, a.api_key, "POST", "/api/sync"))

    sub.add_parser("sync-status", help="show sync status").set_defaults(
        func=lambda a: request_api(a.base_url, a.api_key, "GET", "/api/sync-status")
    )

    search_p = sub.add_parser("search", help="search docs")
    search_p.add_argument("query")
    search_p.add_argument("--limit", type=int, default=20)
    search_p.set_defaults(
        func=lambda a: request_api(
            a.base_url, a.api_key, "GET", "/api/search", params={"q": a.query, "limit": a.limit}
        )
    )

    doc_p = sub.add_parser("doc", help="get document by id")
    doc_p.add_argument("doc_id", type=int)
    doc_p.set_defaults(func=lambda a: request_api(a.base_url, a.api_key, "GET", f"/api/document/{a.doc_id}"))

    sub.add_parser("wiki-graph", help="analyze wiki link graph").set_defaults(
        func=lambda a: request_api(a.base_url, a.api_key, "GET", "/api/wiki-graph")
    )

    query_p = sub.add_parser("query", help="query wiki")
    query_p.add_argument("question")
    query_p.add_argument("--limit", type=int, default=8)
    query_p.add_argument("--save", action="store_true")
    query_p.add_argument("--model", default=None, help="override model, e.g. deepseek-ai/DeepSeek-V4-Flash")
    query_p.set_defaults(
        func=lambda a: request_api(
            a.base_url,
            a.api_key,
            "POST",
            "/api/query",
            body={
                "question": a.question,
                "limit": a.limit,
                "save_to_wiki": a.save,
                "model": a.model,
            },
        )
    )

    ingest_p = sub.add_parser("ingest", help="ingest selected source/path")
    ingest_p.add_argument("--source-id", default=None)
    ingest_p.add_argument("--rel-path", default=None)
    ingest_p.set_defaults(
        func=lambda a: request_api(
            a.base_url,
            a.api_key,
            "POST",
            "/api/ingest",
            body={"source_id": a.source_id, "rel_path": a.rel_path},
        )
    )

    lint_p = sub.add_parser("lint", help="run lint checks")
    lint_p.add_argument("--stale-days", type=int, default=180)
    lint_p.set_defaults(
        func=lambda a: request_api(
            a.base_url, a.api_key, "POST", "/api/lint", body={"stale_days": a.stale_days}
        )
    )

    sub.add_parser("categories", help="list categories and topics").set_defaults(
        func=lambda a: request_api(a.base_url, a.api_key, "GET", "/api/categories")
    )

    browse_p = sub.add_parser("browse", help="browse docs by category/topic")
    browse_p.add_argument("--category", default=None)
    browse_p.add_argument("--topic", default=None)
    browse_p.add_argument("--limit", type=int, default=40)
    browse_p.set_defaults(
        func=lambda a: request_api(
            a.base_url,
            a.api_key,
            "GET",
            "/api/browse",
            params={"category": a.category, "topic": a.topic, "limit": a.limit},
        )
    )

    library_p = sub.add_parser("library", help="library tree index")
    library_p.add_argument("--category", default="all")
    library_p.set_defaults(
        func=lambda a: request_api(
            a.base_url, a.api_key, "GET", "/api/library", params={"category": a.category}
        )
    )

    purpose_p = sub.add_parser("purpose", help="get or set purpose.md")
    purpose_p.add_argument("action", choices=["get", "set"], default="get", nargs="?")
    purpose_p.add_argument("--content", default=None, help="content for set action")
    purpose_p.add_argument("--content-file", default=None, help="UTF-8 file for set action")

    def purpose_cmd(a):
        if (a.action or "get") == "set":
            content = a.content
            if a.content_file:
                with open(a.content_file, "r", encoding="utf-8") as f:
                    content = f.read()
            if content is None:
                raise RuntimeError("set requires --content or --content-file")
            return request_api(
                a.base_url, a.api_key, "POST", "/api/purpose", body={"content": content}
            )
        return request_api(a.base_url, a.api_key, "GET", "/api/purpose")

    purpose_p.set_defaults(func=purpose_cmd)

    audit_p = sub.add_parser("audit-events", help="list audit events")
    audit_p.add_argument("--limit", type=int, default=30)
    audit_p.set_defaults(
        func=lambda a: request_api(
            a.base_url, a.api_key, "GET", "/api/audit-events", params={"limit": a.limit}
        )
    )

    args = parser.parse_args()
    try:
        result = args.func(args)
        emit_result(result, args.output_file)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
