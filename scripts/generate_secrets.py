#!/usr/bin/env python3
"""Generate random secrets and bcrypt password hashes for mind-sync .env configuration."""
from __future__ import annotations

import argparse
import secrets
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "apps" / "api"))

from app.services.password_util import hash_password  # noqa: E402


def generate() -> dict[str, str]:
    return {
        "AUTH_PASSWORD": secrets.token_urlsafe(12),
        "SECRET_KEY": secrets.token_urlsafe(32),
        "API_KEY": secrets.token_urlsafe(24),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate mind-sync secrets or bcrypt password hashes")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("generate", help="Print random AUTH_PASSWORD, SECRET_KEY, API_KEY")

    hash_cmd = sub.add_parser("hash-password", help="Print bcrypt hash for AUTH_USERS")
    hash_cmd.add_argument("password", help="Plaintext password to hash")
    hash_cmd.add_argument("--rounds", type=int, default=12, help="bcrypt cost factor (default 12)")

    args = parser.parse_args()
    command = args.command or "generate"

    if command == "hash-password":
        print(hash_password(args.password, rounds=args.rounds))
        return

    secrets_map = generate()
    print("# Generated secrets - add these to your .env file")
    for key, val in secrets_map.items():
        print(f"{key}={val}")
    print("# Example bcrypt user (generate hash with: python scripts/generate_secrets.py hash-password 'your-pass')")
    print("# AUTH_USERS=admin:$2b$12$...:admin,viewer:$2b$12$...:viewer")


if __name__ == "__main__":
    main()
