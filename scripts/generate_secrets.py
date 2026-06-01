#!/usr/bin/env python3
"""Generate random secrets for mind-sync .env configuration."""
import secrets


def generate() -> dict[str, str]:
    return {
        "AUTH_PASSWORD": secrets.token_urlsafe(12),
        "SECRET_KEY": secrets.token_urlsafe(32),
        "API_KEY": secrets.token_urlsafe(24),
    }


def main() -> None:
    secrets_map = generate()
    print("# Generated secrets - add these to your .env file")
    for key, val in secrets_map.items():
        print(f"{key}={val}")


if __name__ == "__main__":
    main()
