import os
from typing import Any

import requests
from mcp.server.fastmcp import FastMCP


BASE_URL = os.getenv("MINDSYNC_BASE_URL", "http://localhost:8000").rstrip("/")
API_KEY = os.getenv("MINDSYNC_API_KEY", "mind-sync-dev-key")

mcp = FastMCP("mind-sync")


def call_api(method: str, path: str, *, params: dict[str, Any] | None = None, body: dict[str, Any] | None = None) -> Any:
    headers = {"x-api-key": API_KEY}
    resp = requests.request(method, f"{BASE_URL}{path}", params=params, json=body, headers=headers, timeout=120)
    if not resp.ok:
        raise RuntimeError(f"mind-sync API error {resp.status_code}: {resp.text}")
    return resp.json()


@mcp.tool()
def health() -> dict[str, Any]:
    """Check whether mind-sync API is reachable."""
    return call_api("GET", "/api/health")


@mcp.tool()
def list_sources() -> dict[str, Any]:
    """List configured knowledge sources."""
    return call_api("GET", "/api/sources")


@mcp.tool()
def sync_sources() -> dict[str, Any]:
    """Start background sync for all sources."""
    return call_api("POST", "/api/sync")


@mcp.tool()
def sync_status() -> dict[str, Any]:
    """Get current sync progress and status."""
    return call_api("GET", "/api/sync-status")


@mcp.tool()
def search_docs(query: str, limit: int = 20) -> dict[str, Any]:
    """Search indexed markdown/code documents."""
    return call_api("GET", "/api/search", params={"q": query, "limit": limit})


@mcp.tool()
def get_document(doc_id: int) -> dict[str, Any]:
    """Read document content by numeric id."""
    return call_api("GET", f"/api/document/{doc_id}")


@mcp.tool()
def query_wiki(
    question: str,
    limit: int = 8,
    save_to_wiki: bool = False,
    model: str | None = None,
) -> dict[str, Any]:
    """Ask a question over the knowledge base and optionally save insight page."""
    return call_api(
        "POST",
        "/api/query",
        body={"question": question, "limit": limit, "save_to_wiki": save_to_wiki, "model": model},
    )


@mcp.tool()
def ingest_source(source_id: str | None = None, rel_path: str | None = None) -> dict[str, Any]:
    """Ingest all sources or a specific source/path into index."""
    return call_api("POST", "/api/ingest", body={"source_id": source_id, "rel_path": rel_path})


@mcp.tool()
def lint_wiki(stale_days: int = 180) -> dict[str, Any]:
    """Run lint checks and generate a lint report."""
    return call_api("POST", "/api/lint", body={"stale_days": stale_days})


if __name__ == "__main__":
    mcp.run()
