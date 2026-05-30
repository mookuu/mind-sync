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
def list_library(category: str = "all") -> dict[str, Any]:
    """Browse indexed documents as a hierarchical library (sources → languages → files)."""
    return call_api("GET", "/api/library", params={"category": category})


@mcp.tool()
def sync_sources(use_saved_defaults: bool = True, preset: str | None = None) -> dict[str, Any]:
    """Start background sync. Uses saved sync scope by default, or optional preset."""
    body: dict[str, Any] = {"use_saved_defaults": use_saved_defaults}
    if preset:
        body["preset"] = preset
    return call_api("POST", "/api/sync", body=body)


@mcp.tool()
def sync_status() -> dict[str, Any]:
    """Get current sync progress and status."""
    return call_api("GET", "/api/sync-status")


@mcp.tool()
def search_docs(
    query: str,
    limit: int = 20,
    category: str | None = None,
    topic: str | None = None,
    source_id: str | None = None,
) -> dict[str, Any]:
    """Search indexed documents. Optional filters: category (source/summary/query), topic, source_id."""
    params: dict[str, Any] = {"q": query, "limit": limit}
    if category:
        params["category"] = category
    if topic:
        params["topic"] = topic
    if source_id:
        params["source_id"] = source_id
    return call_api("GET", "/api/search", params=params)


@mcp.tool()
def list_categories() -> dict[str, Any]:
    """List wiki document categories and summary topics with counts."""
    return call_api("GET", "/api/categories")


@mcp.tool()
def browse_docs(
    category: str | None = None,
    topic: str | None = None,
    limit: int = 40,
) -> dict[str, Any]:
    """Browse documents by category/topic without full-text search."""
    params: dict[str, Any] = {"limit": limit}
    if category:
        params["category"] = category
    if topic:
        params["topic"] = topic
    return call_api("GET", "/api/browse", params=params)


@mcp.tool()
def get_purpose() -> dict[str, Any]:
    """Read research direction from DATA_DIR/purpose.md."""
    return call_api("GET", "/api/purpose")


@mcp.tool()
def get_document(doc_id: int) -> dict[str, Any]:
    """Read document content by numeric id."""
    return call_api("GET", f"/api/document/{doc_id}")


@mcp.tool()
def wiki_graph() -> dict[str, Any]:
    """Analyze wiki markdown link graph and return hubs/orphans."""
    return call_api("GET", "/api/wiki-graph")


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
