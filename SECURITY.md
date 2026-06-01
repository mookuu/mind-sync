# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| `main`  | Yes       |

## Reporting a vulnerability

Please report security issues privately (do not open a public issue with exploit details).

1. Email or message the repository owner with a description and reproduction steps.
2. Allow reasonable time for a fix before public disclosure.

## Deployment checklist

- Change `AUTH_PASSWORD`, `SECRET_KEY`, and `API_KEY` from defaults in `.env`.
- Use `COOKIE_SECURE=true` and `SECURITY_HSTS_ENABLED=true` when served over HTTPS.
- Restrict network access (firewall / reverse proxy) for self-hosted instances.
- Store `GITHUB_TOKEN` and `LLM_API_KEY` only in environment variables, never in git.
- Run `pip-audit -r apps/api/requirements.txt` periodically (CI runs this on push).

## Data handling

- Document content is stored under `DATA_DIR` (default `./data`).
- Search indexes are local SQLite FTS; they are not pushed to Git by default.
- Optional `VAULT_GIT_URL` syncs `wiki/` and `purpose.md` only when configured.
