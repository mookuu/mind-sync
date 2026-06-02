import logging

from ..config import settings
from .password_util import is_bcrypt_hash
from .permissions import load_auth_users
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
    users = load_auth_users()
    if users:
        plain = [u.username for u in users if not is_bcrypt_hash(u.password)]
        if plain:
            warnings.append(
                f"AUTH_USERS contains plaintext passwords for: {', '.join(plain[:5])}"
                " — use scripts/generate_secrets.py hash-password for bcrypt hashes"
            )
    if settings.cookie_secure and not settings.security_hsts_enabled:
        warnings.append("COOKIE_SECURE=true but SECURITY_HSTS_ENABLED=false — consider enabling HSTS on HTTPS")
    return warnings


def log_security_warnings() -> None:
    for msg in collect_security_warnings():
        logger.warning("SECURITY: %s", msg)


def log_source_warnings() -> None:
    for msg in collect_source_warnings():
        logger.warning("SOURCES: %s", msg)
