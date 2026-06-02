from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    auth_password: str = "changeme"
    # Multi-user RBAC. CSV: user:pass:role,... or JSON list. Roles: admin | viewer
    auth_users: str = ""
    secret_key: str = "replace-with-random-secret"
    api_key: str = "mind-sync-dev-key"
    data_dir: str = "/data"
    sources_file: str = "/workspace/sources.yaml"
    llm_base_url: str = "https://api.siliconflow.cn/v1"
    llm_api_key: str = ""
    llm_model: str = "deepseek-ai/DeepSeek-V4-Flash"
    cookie_secure: bool = False
    cookie_samesite: str = "lax"
    cookie_max_age_seconds: int = 60 * 60 * 24 * 7
    session_ttl_seconds: int = 60 * 60 * 24 * 7
    login_rate_limit_window_seconds: int = 300
    login_rate_limit_max_attempts: int = 5
    api_rate_limit_window_seconds: int = 3600
    api_rate_limit_query_max: int = 30
    api_rate_limit_sync_max: int = 10
    api_rate_limit_lint_max: int = 20
    max_index_file_bytes: int = 2_000_000
    lint_content_max_chars: int = 500_000
    security_hsts_enabled: bool = False
    cors_allow_origins: str = "http://localhost:8080,http://127.0.0.1:8080"
    csrf_header_name: str = "x-csrf-token"
    audit_retention_days: int = 30
    github_token: str = ""
    vault_git_url: str = ""
    vault_git_branch: str = "main"
    ollama_base_url: str = ""
    # Web source fetch compliance (see docs/MIND_SYNC_WORKFLOW.md)
    web_fetch_enabled: bool = True
    web_fetch_respect_robots: bool = True
    web_fetch_user_agent: str = "mind-sync/0.1"
    web_fetch_contact: str = ""
    web_fetch_min_interval_seconds: float = 5.0
    web_fetch_allowlist: str = ""
    web_fetch_require_allowlist: bool = False
    web_fetch_require_opt_in: bool = False
    web_fetch_max_bytes: int = 5_000_000
    # Search: multiply bm25 rank boost (summary=1.2 favors summaries in default sort)
    search_category_weights: str = "summary=1.2,query=1.1,source=1.0"
    # Per-source sync failure backoff (stored in app_settings)
    sync_backoff_enabled: bool = True
    sync_backoff_base_seconds: float = 60.0
    sync_backoff_max_seconds: float = 3600.0


settings = Settings()


def parse_cors_origins(raw: str) -> list[str]:
    items = [item.strip() for item in (raw or "").split(",") if item.strip()]
    return items or ["http://localhost:8080", "http://127.0.0.1:8080"]


CORS_ORIGINS = parse_cors_origins(settings.cors_allow_origins)
CORS_ALLOW_CREDENTIALS = "*" not in CORS_ORIGINS
