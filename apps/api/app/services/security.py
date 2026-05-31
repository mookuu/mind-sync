import logging

from ..config import settings
from .source_health import collect_source_warnings

logger = logging.getLogger("mind-sync.security")

WEAK_PASSWORDS = {"changeme", "password", "123456", ""}
WEAK_API_KEYS = {"mind-sync-dev-key", "dev", ""}
WEAK_SECRET_KEYS = {"replace-with-random-secret", "changeme", ""}


def collect_security_warnings() -> list[str]:
    warnings: list[str] = []
    if settings.auth_password.strip() in WEAK_PASSWORDS:
        warnings.append("AUTH_PASSWORD is weak or default — change it in .env before exposing the service")
    if settings.api_key.strip() in WEAK_API_KEYS:
        warnings.append("API_KEY is default — set a strong random value in .env")
    if settings.secret_key.strip() in WEAK_SECRET_KEYS:
        warnings.append("SECRET_KEY is default — set a random secret in .env for session signing")
    if settings.cookie_secure and not settings.security_hsts_enabled:
        warnings.append("COOKIE_SECURE=true but SECURITY_HSTS_ENABLED=false — consider enabling HSTS on HTTPS")
    return warnings


def log_security_warnings() -> None:
    for msg in collect_security_warnings():
        logger.warning("SECURITY: %s", msg)


def log_source_warnings() -> None:
    for msg in collect_source_warnings():
        logger.warning("SOURCES: %s", msg)
