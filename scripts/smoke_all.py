import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
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


def has_secure_cookie(cj, name):
    for c in cj:
        if c.name == name:
            return bool(getattr(c, "secure", False))
    return False


def build_parser():
    parser = argparse.ArgumentParser(description="mind-sync unified smoke check")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--password", required=True)
    parser.add_argument("--search-q", default="python")
    parser.add_argument("--sync-timeout-seconds", type=int, default=120)
    parser.add_argument("--skip-sync", action="store_true")
    parser.add_argument("--mode", choices=["all", "auth"], default="all")
    return parser


def run_smoke(args):
    base = args.base_url.rstrip("/")
    cj = CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

    status, data = request_json(opener, "GET", f"{base}/api/health")
    if status != 200:
        raise RuntimeError(f"health failed: {status} {data}")
    if data.get("status") not in ("ok", "degraded"):
        raise RuntimeError(f"unexpected health status: {data}")
    if data.get("status") == "degraded" and not args.skip_sync:
        raise RuntimeError(f"health degraded: {data}")

    status, data = request_json(opener, "POST", f"{base}/api/login", body={"password": args.password})
    if status != 200 or not data.get("ok"):
        raise RuntimeError(f"login failed: {status} {data}")
    csrf = get_cookie(cj, "ms_csrf")
    if not csrf:
        raise RuntimeError("csrf cookie missing after login")

    try:
        status, data = request_json(opener, "GET", f"{base}/api/auth-mode")
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            if base.lower().startswith("http://") and has_secure_cookie(cj, "ms_token"):
                raise RuntimeError(
                    "auth-mode unauthorized right after login. COOKIE_SECURE is enabled but base-url is HTTP. "
                    "Use HTTPS base-url or set COOKIE_SECURE=false for local HTTP testing."
                ) from exc
        raise
    if status != 200 or "cookie_enabled" not in data:
        raise RuntimeError(f"auth-mode failed: {status} {data}")

    status, audit = request_json(opener, "GET", f"{base}/api/audit-events?limit=10")
    if status != 200 or "items" not in audit:
        raise RuntimeError(f"audit-events failed: {status} {audit}")
    if not any(item.get("event_type") == "login_success" for item in audit.get("items", [])):
        raise RuntimeError("audit-events missing login_success after login")

    full_flow = args.mode == "all"
    if full_flow and not args.skip_sync:
        status, data = request_json(
            opener,
            "POST",
            f"{base}/api/sync",
            headers={"x-csrf-token": csrf},
        )
        if status != 200 or not data.get("ok"):
            raise RuntimeError(f"sync start failed: {status} {data}")

        deadline = time.time() + max(15, args.sync_timeout_seconds)
        last_status = None
        while time.time() < deadline:
            status, st = request_json(opener, "GET", f"{base}/api/sync-status")
            if status != 200:
                raise RuntimeError(f"sync-status failed: {status} {st}")
            last_status = st
            if not st.get("running"):
                if st.get("error"):
                    raise RuntimeError(f"sync finished with error: {st.get('error')}")
                break
            time.sleep(2)
        else:
            raise RuntimeError("sync timeout")

        last_completed = (last_status or {}).get("last_completed") or {}
        if not last_completed.get("finished_at"):
            raise RuntimeError("sync-status missing last_completed summary")
        if last_completed.get("status") != "success":
            raise RuntimeError(f"sync last_completed not success: {last_completed}")

        status, audit = request_json(opener, "GET", f"{base}/api/audit-events?limit=20")
        if status != 200 or "items" not in audit:
            raise RuntimeError(f"audit-events after sync failed: {status} {audit}")
        if not any(item.get("event_type") == "sync_completed" for item in audit.get("items", [])):
            raise RuntimeError("audit-events missing sync_completed after sync")

    if full_flow:
        q = urllib.parse.quote(args.search_q)
        status, data = request_json(opener, "GET", f"{base}/api/search?q={q}&limit=5")
        if status != 200 or "items" not in data:
            raise RuntimeError(f"search failed: {status} {data}")
        items = data.get("items", [])
        if items:
            doc_id = items[0].get("id")
            if doc_id is not None:
                status, doc = request_json(opener, "GET", f"{base}/api/document/{doc_id}")
                if status != 200 or "content" not in doc:
                    raise RuntimeError(f"document fetch failed: {status} {doc}")

    status, data = request_json(
        opener,
        "POST",
        f"{base}/api/logout",
        headers={"x-csrf-token": csrf},
    )
    if status != 200 or not data.get("ok"):
        raise RuntimeError(f"logout failed: {status} {data}")

    try:
        request_json(opener, "GET", f"{base}/api/auth-mode")
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            return "smoke all ok: auth/sync/search/logout" if full_flow else "smoke auth ok: login/logout/session revocation works"
        raise
    raise RuntimeError("expected 401 after logout, but auth-mode succeeded")


def main():
    args = build_parser().parse_args()
    message = run_smoke(args)
    print(message)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"smoke failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
