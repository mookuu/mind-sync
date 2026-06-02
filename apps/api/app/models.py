from dataclasses import dataclass

from pydantic import BaseModel


@dataclass
class Source:
    id: str
    source_type: str
    path: str | None
    url: str | None
    include: list[str]
    branch: str = "main"
    paths: list[str] | None = None
    order: int | None = None
    fetch_confirmed: bool = False
    respect_robots: bool | None = None


class LoginRequest(BaseModel):
    username: str = "default"
    password: str


class QueryRequest(BaseModel):
    question: str
    limit: int = 8
    save_to_wiki: bool = False
    model: str | None = None


class IngestRequest(BaseModel):
    source_id: str | None = None
    rel_path: str | None = None


class LintRequest(BaseModel):
    stale_days: int = 180


class SettingsUpdateRequest(BaseModel):
    auto_sync_enabled: bool | None = None
    auto_sync_interval_minutes: int | None = None
    sync_preset: str | None = None
    sync_source_ids: list[str] | None = None
    sync_source_order: list[str] | None = None


class SyncRequest(BaseModel):
    use_saved_defaults: bool = True
    source_ids: list[str] | None = None
    preset: str | None = None
    vault_pull: bool = True
    vault_push: bool = False


class RebuildRequest(BaseModel):
    use_saved_defaults: bool = True
    source_ids: list[str] | None = None
    preset: str | None = None


class VaultSyncRequest(BaseModel):
    pull: bool = True
    push: bool = False
    message: str | None = None


class WikiWriteRequest(BaseModel):
    path: str
    content: str


class PurposeUpdateRequest(BaseModel):
    content: str = ""
