#!/usr/bin/env python3
"""Verify persistent login rate limit and audit logging."""

import argparse
import json
import sys
import urllib.error
import urllib.request
from http.cookiejar import CookieJar


def request_json(opener, method, url, body=None, headers=None):
    data = None
    req_headers = dict(headers or {})
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        req_headers.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url=url, data=data, headers=req_headers, method=method)
    with opener.open(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
        return resp.status, json.loads(raw or "{}")


def get_cookie(cj, name):
    for c in cj:
        if c.name == name:
            return c.value
    return ""


def main() -> int:
    parser = argparse.ArgumentParser(description="mind-sync auth meta smoke check")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--password", required=True)
    parser.add_argument("--api-key", default="mind-sync-dev-key")
    parser.add_argument("--wrong-password", default="__definitely_wrong__")
    parser.add_argument("--max-attempts", type=int, default=5)
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    cj = CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    api_headers = {"x-api-key": args.api_key}

    status, data = request_json(opener, "GET", f"{base}/api/health")
    if status != 200 or data.get("status") != "ok":
        raise RuntimeError(f"health failed: {status} {data}")

    status, data = request_json(opener, "POST", f"{base}/api/login", body={"password": args.password})
    if status != 200 or not data.get("ok"):
        raise RuntimeError(f"initial login failed: {status} {data}")
    csrf = get_cookie(cj, "ms_csrf")
    if not csrf:
        raise RuntimeError("csrf cookie missing after login")

    status, audit = request_json(opener, "GET", f"{base}/api/audit-events?limit=10")
    if status != 200 or "items" not in audit:
        raise RuntimeError(f"audit-events failed: {status} {audit}")
    if not any(item.get("event_type") == "login_success" for item in audit.get("items", [])):
        raise RuntimeError("audit-events missing login_success")

    status, data = request_json(
        opener,
        "POST",
        f"{base}/api/logout",
        headers={"x-csrf-token": csrf},
    )
    if status != 200 or not data.get("ok"):
        raise RuntimeError(f"logout failed: {status} {data}")

    limit = max(1, int(args.max_attempts))
    for i in range(limit):
        try:
            request_json(
                opener,
                "POST",
                f"{base}/api/login",
                body={"password": args.wrong_password},
            )
            raise RuntimeError(f"expected 401 on failed login attempt {i + 1}")
        except urllib.error.HTTPError as exc:
            if exc.code != 401:
                raise RuntimeError(f"expected 401 on attempt {i + 1}, got {exc.code}") from exc

    try:
        request_json(
            opener,
            "POST",
            f"{base}/api/login",
            body={"password": args.wrong_password},
        )
        raise RuntimeError("expected 429 after too many failed login attempts")
    except urllib.error.HTTPError as exc:
        if exc.code != 429:
            raise RuntimeError(f"expected 429 on rate-limited login, got {exc.code}") from exc

    status, audit = request_json(
        opener,
        "GET",
        f"{base}/api/audit-events?limit=30",
        headers=api_headers,
    )
    if status != 200 or "items" not in audit:
        raise RuntimeError(f"audit-events failed after rate limit: {status} {audit}")

    failed_count = sum(1 for item in audit.get("items", []) if item.get("event_type") == "login_failed")
    if failed_count < limit:
        raise RuntimeError(f"audit-events missing login_failed records: got {failed_count}, expected >= {limit}")

    print("smoke auth meta ok: rate limit + audit persistence verified")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"smoke auth meta failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
