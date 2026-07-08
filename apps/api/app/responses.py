"""Pydantic response models for core API endpoints."""
from __future__ import annotations
from typing import Any
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    source_warnings: list[str]
    health: str
    security: list[str]


class AuthModeResponse(BaseModel):
    cookie_enabled: bool
    api_key_enabled: bool
    csrf_header: str
    role: str
    can_write: bool
    username: str | None
    display_name: str | None
    authenticated: bool
    csrf_token: str


class SearchResult(BaseModel):
    id: int
    source_id: str
    rel_path: str
    title: str
    lang: str
    snippet: str
    category: str | None = None


class SearchResponse(BaseModel):
    items: list[SearchResult]


class LibrarySection(BaseModel):
    id: str
    label: str
    sources: list[dict[str, Any]] | None = None
    flat: bool | None = None
    count: int | None = None
    source_id: str | None = None
    tree: list[dict[str, Any]] | None = None


class LibraryResponse(BaseModel):
    sections: list[LibrarySection]
    total_documents: int
    etag: str


class DocumentResponse(BaseModel):
    id: int
    source_id: str
    rel_path: str
    title: str
    content: str
    lang: str
    updated_at: float


class QueryEvidence(BaseModel):
    id: int
    source_id: str
    rel_path: str
    snippet: str
    confidence: str


class QueryResponse(BaseModel):
    ok: bool
    answer: str
    citations: list[dict[str, Any]]
    evidences: list[QueryEvidence]
    saved_path: str | None = None
    indexed: dict[str, Any] | None = None
    used_llm: bool = False
    model_used: str | None = None
    llm_configured: bool = False


class SyncStatusResponse(BaseModel):
    running: bool
    job_mode: str | None = None
    current_source: str | None = None
    processed_files: int = 0
    total_files: int = 0
    indexed: int = 0
    skipped: int = 0
    deleted: int = 0
    error: str | None = None
