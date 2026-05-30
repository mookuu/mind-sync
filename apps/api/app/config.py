from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    auth_password: str = "changeme"
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
    security_hsts_enabled: bool = False
    cors_allow_origins: str = "http://localhost:8080,http://127.0.0.1:8080"
    csrf_header_name: str = "x-csrf-token"
    audit_retention_days: int = 30


settings = Settings()


def parse_cors_origins(raw: str) -> list[str]:
    items = [item.strip() for item in (raw or "").split(",") if item.strip()]
    return items or ["http://localhost:8080", "http://127.0.0.1:8080"]


CORS_ORIGINS = parse_cors_origins(settings.cors_allow_origins)
CORS_ALLOW_CREDENTIALS = "*" not in CORS_ORIGINS
