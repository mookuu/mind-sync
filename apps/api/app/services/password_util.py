"""Password hashing and verification (bcrypt with plaintext fallback for migration)."""

from __future__ import annotations

import secrets

BCRYPT_PREFIXES = ("$2a$", "$2b$", "$2y$")


def is_bcrypt_hash(value: str) -> bool:
    s = (value or "").strip()
    return any(s.startswith(prefix) for prefix in BCRYPT_PREFIXES)


def hash_password(plain: str, *, rounds: int = 12) -> str:
    import bcrypt

    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds)).decode("ascii")


def verify_password(supplied: str, stored: str) -> bool:
    stored = stored or ""
    supplied = supplied or ""
    if is_bcrypt_hash(stored):
        import bcrypt

        try:
            return bcrypt.checkpw(supplied.encode("utf-8"), stored.encode("utf-8"))
        except ValueError:
            return False
    return secrets.compare_digest(supplied, stored)
