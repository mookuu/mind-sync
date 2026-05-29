import hashlib
import os
import re
import sqlite3
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import yaml
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from itsdangerous import BadSignature, URLSafeSerializer
from pydantic import BaseModel
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


settings = Settings()
app = FastAPI(title="mind-sync API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
serializer = URLSafeSerializer(settings.secret_key, salt="mind-sync")


@dataclass
class Source:
    id: str
    path: str
    include: list[str]


class LoginRequest(BaseModel):
    password: str


class QueryRequest(BaseModel):
    question: str
    limit: int = 8
    save_to_wiki: bool = False
    model: str | None = None


class IngestRequest(BaseModel):
    source_id: str | None = None
    rel_path: str | None = None


class LintRequest(BaseModel):
    stale_days: int = 180


class SettingsUpdateRequest(BaseModel):
    auto_sync_enabled: bool | None = None
    auto_sync_interval_minutes: int | None = None


DB_PATH = Path(settings.data_dir) / "mind_sync.db"
Path(settings.data_dir).mkdir(parents=True, exist_ok=True)
WIKI_DIR = Path(settings.data_dir) / "wiki"
LINT_DIR = Path(settings.data_dir) / "lint-reports"
SETTINGS_DEFAULTS = {
    "auto_sync_enabled": "false",
    "auto_sync_interval_minutes": "60",
}
AUTO_SYNC_LAST_RUN = 0.0
SCHEDULER_STARTED = False
AUTO_SYNC_INFO: dict[str, Any] = {
    "status": "idle",
    "started_at": None,
    "finished_at": None,
    "indexed": 0,
    "skipped": 0,
    "deleted": 0,
    "error": None,
}
SYNC_LOCK = threading.Lock()
SYNC_STATE: dict[str, Any] = {
    "running": False,
    "started_at": None,
    "finished_at": None,
    "indexed": 0,
    "skipped": 0,
    "deleted": 0,
    "sources": [],
    "current_source": None,
    "processed_files": 0,
    "total_files": 0,
    "error": None,
}


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    return conn


def init_db() -> None:
    conn = get_db()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id TEXT NOT NULL,
            rel_path TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            lang TEXT NOT NULL,
            mtime REAL NOT NULL,
            sha1 TEXT NOT NULL,
            updated_at REAL NOT NULL,
            UNIQUE(source_id, rel_path)
        );
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """
    )
    conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(title, content, rel_path, source_id)")
    for k, v in SETTINGS_DEFAULTS.items():
        conn.execute(
            "INSERT INTO app_settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO NOTHING",
            (k, v),
        )
    conn.commit()
    conn.close()
    WIKI_DIR.mkdir(parents=True, exist_ok=True)
    LINT_DIR.mkdir(parents=True, exist_ok=True)


def require_auth(request: Request) -> None:
    token = request.cookies.get("ms_token")
    if not token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        payload = serializer.loads(token)
        if payload.get("ok") is not True:
            raise HTTPException(status_code=401, detail="Unauthorized")
    except BadSignature as exc:
        raise HTTPException(status_code=401, detail="Unauthorized") from exc


def is_api_key_valid(request: Request) -> bool:
    expected = settings.api_key.strip()
    if not expected:
        return False
    header_key = request.headers.get("x-api-key", "").strip()
    auth_header = request.headers.get("authorization", "").strip()
    bearer_key = ""
    if auth_header.lower().startswith("bearer "):
        bearer_key = auth_header[7:].strip()
    return header_key == expected or bearer_key == expected


def require_any_auth(request: Request) -> None:
    if is_api_key_valid(request):
        return
    require_auth(request)


def load_sources() -> list[Source]:
    src_file = Path(settings.sources_file)
    if not src_file.exists():
        return []
    raw = yaml.safe_load(src_file.read_text(encoding="utf-8")) or {}
    result: list[Source] = []
    for item in raw.get("sources", []):
        result.append(
            Source(
                id=item["id"],
                path=item["path"],
                include=item.get("include", ["**/*.md"]),
            )
        )
    return result


def resolve_source_root(source: Source) -> Path:
    p = Path(source.path)
    if p.exists():
        return p
    fallback = Path("/sources") / source.id
    if fallback.exists():
        return fallback
    return p


def language_from_suffix(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".md":
        return "markdown"
    if suffix == ".py":
        return "python"
    if suffix == ".java":
        return "java"
    return suffix.lstrip(".") or "text"


def read_text_safely(path: Path) -> str:
    raw = path.read_bytes()
    for enc in ("utf-8", "utf-8-sig", "utf-16", "utf-16-le", "utf-16-be", "gb18030", "gbk"):
        try:
            text = raw.decode(enc)
            # Heuristic: when UTF-8 decode yields heavy mojibake chars, prefer GB encodings.
            bad_ratio = text.count("�") / max(len(text), 1)
            if enc.startswith("utf-8") and bad_ratio > 0.01:
                continue
            return text
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def collect_files(root: Path, includes: list[str]) -> list[Path]:
    extension_patterns = [p for p in includes if p.startswith("**/*.")]
    if extension_patterns and len(extension_patterns) == len(includes):
        exts = {"." + p.split(".")[-1].lower() for p in extension_patterns}
        skip_dirs = {
            ".git",
            "node_modules",
            ".venv",
            "venv",
            ".idea",
            ".vscode",
            "dist",
            "build",
            "target",
            "__pycache__",
        }
        files: list[Path] = []
        for dir_path, dir_names, file_names in os.walk(root):
            dir_names[:] = [d for d in dir_names if d not in skip_dirs]
            base = Path(dir_path)
            for name in file_names:
                p = base / name
                if p.suffix.lower() in exts:
                    files.append(p)
        return sorted(files)

    files_set: set[Path] = set()
    for pattern in includes:
        for p in root.glob(pattern):
            if p.is_file():
                files_set.add(p)
    return sorted(files_set)


def upsert_document(conn: sqlite3.Connection, source_id: str, rel_path: str, content: str, mtime: float, sha1: str, lang: str) -> None:
    title = Path(rel_path).name
    now = time.time()
    conn.execute(
        """
        INSERT INTO documents(source_id, rel_path, title, content, lang, mtime, sha1, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_id, rel_path) DO UPDATE SET
            title=excluded.title,
            content=excluded.content,
            lang=excluded.lang,
            mtime=excluded.mtime,
            sha1=excluded.sha1,
            updated_at=excluded.updated_at
        """,
        (source_id, rel_path, title, content, lang, mtime, sha1, now),
    )
    row = conn.execute(
        "SELECT id FROM documents WHERE source_id = ? AND rel_path = ?",
        (source_id, rel_path),
    ).fetchone()
    doc_id = row["id"]
    conn.execute("DELETE FROM documents_fts WHERE rowid = ?", (doc_id,))
    conn.execute(
        "INSERT INTO documents_fts(rowid, title, content, rel_path, source_id) VALUES (?, ?, ?, ?, ?)",
        (doc_id, title, content, rel_path, source_id),
    )


def remove_missing(conn: sqlite3.Connection, source_id: str, existing: set[str]) -> int:
    rows = conn.execute("SELECT id, rel_path FROM documents WHERE source_id = ?", (source_id,)).fetchall()
    removed = 0
    for row in rows:
        if row["rel_path"] not in existing:
            conn.execute("DELETE FROM documents WHERE id = ?", (row["id"],))
            conn.execute("DELETE FROM documents_fts WHERE rowid = ?", (row["id"],))
            removed += 1
    return removed


def read_settings(conn: sqlite3.Connection) -> dict[str, str]:
    rows = conn.execute("SELECT key, value FROM app_settings").fetchall()
    data = {row["key"]: row["value"] for row in rows}
    for k, v in SETTINGS_DEFAULTS.items():
        data.setdefault(k, v)
    return data


def parse_bool(raw: str) -> bool:
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def build_auto_sync_meta(settings_map: dict[str, str]) -> dict[str, Any]:
    enabled = parse_bool(settings_map.get("auto_sync_enabled", "false"))
    interval = max(1, min(int(settings_map.get("auto_sync_interval_minutes", "60")), 24 * 60))
    next_at = None
    with SYNC_LOCK:
        last_run = AUTO_SYNC_LAST_RUN
        last_info = dict(AUTO_SYNC_INFO)
    if enabled and last_run > 0:
        next_at = last_run + interval * 60
    return {
        "auto_sync_enabled": enabled,
        "auto_sync_interval_minutes": interval,
        "next_auto_sync_at": next_at,
        "last_auto_sync": last_info,
    }


def scheduler_loop() -> None:
    global AUTO_SYNC_LAST_RUN
    while True:
        time.sleep(20)
        try:
            conn = get_db()
            st = read_settings(conn)
            conn.close()
            enabled = parse_bool(st.get("auto_sync_enabled", "false"))
            interval = int(st.get("auto_sync_interval_minutes", "60"))
            interval = max(1, min(interval, 24 * 60))
            if not enabled:
                continue
            now = time.time()
            with SYNC_LOCK:
                running = bool(SYNC_STATE["running"])
            if running:
                continue
            if AUTO_SYNC_LAST_RUN <= 0:
                AUTO_SYNC_LAST_RUN = now
                continue
            if now - AUTO_SYNC_LAST_RUN < interval * 60:
                continue
            AUTO_SYNC_LAST_RUN = now
            with SYNC_LOCK:
                AUTO_SYNC_INFO["status"] = "running"
                AUTO_SYNC_INFO["started_at"] = now
                AUTO_SYNC_INFO["finished_at"] = None
                AUTO_SYNC_INFO["error"] = None
            summary = run_sync_job()
            with SYNC_LOCK:
                AUTO_SYNC_INFO["status"] = "success" if not summary.get("error") else "failed"
                AUTO_SYNC_INFO["finished_at"] = time.time()
                AUTO_SYNC_INFO["indexed"] = summary.get("indexed", 0)
                AUTO_SYNC_INFO["skipped"] = summary.get("skipped", 0)
                AUTO_SYNC_INFO["deleted"] = summary.get("deleted", 0)
                AUTO_SYNC_INFO["error"] = summary.get("error")
        except Exception:
            continue


def index_single_source(conn: sqlite3.Connection, source: Source, rel_path_filter: str | None = None) -> dict[str, Any]:
    root = resolve_source_root(source)
    if not root.exists():
        return {"source_id": source.id, "status": "missing", "indexed": 0, "deleted": 0, "scanned": 0}

    files = collect_files(root, source.include)
    existing: set[str] = set()
    scanned = 0
    indexed = 0
    skipped = 0
    for f in files:
        rel_path = str(f.relative_to(root)).replace("\\", "/")
        if rel_path_filter and rel_path != rel_path_filter:
            continue
        scanned += 1
        existing.add(rel_path)
        content = read_text_safely(f)
        mtime = f.stat().st_mtime
        sha1 = hashlib.sha1(content.encode("utf-8", errors="ignore")).hexdigest()
        old = conn.execute(
            "SELECT sha1 FROM documents WHERE source_id = ? AND rel_path = ?",
            (source.id, rel_path),
        ).fetchone()
        if old and old["sha1"] == sha1:
            skipped += 1
            continue
        upsert_document(conn, source.id, rel_path, content, mtime, sha1, language_from_suffix(f))
        indexed += 1
    deleted = 0 if rel_path_filter else remove_missing(conn, source.id, existing)
    return {
        "source_id": source.id,
        "status": "ok",
        "indexed": indexed,
        "skipped": skipped,
        "deleted": deleted,
        "scanned": scanned,
    }


def build_query_context(citations: list[dict[str, Any]]) -> str:
    if not citations:
        return "No context found."
    lines: list[str] = []
    for i, c in enumerate(citations, start=1):
        lines.append(f"[{i}] {c['source_id']}/{c['rel_path']}")
        lines.append(c.get("content", "")[:4000])
        lines.append("")
    return "\n".join(lines)


def snippet_from_content(content: str, query: str, window: int = 80) -> str:
    if not content:
        return ""
    idx = content.find(query)
    if idx < 0:
        return content[: min(len(content), window * 2)]
    start = max(0, idx - window)
    end = min(len(content), idx + len(query) + window)
    excerpt = content[start:end]
    return excerpt.replace(query, f"<mark>{query}</mark>")


def call_llm(question: str, citations: list[dict[str, Any]], model_override: str | None = None) -> tuple[str, str]:
    model = (model_override or settings.llm_model).strip()
    if not settings.llm_api_key.strip():
        raise HTTPException(status_code=400, detail="LLM_API_KEY is not configured")

    prompt = (
        "你是 mind-sync 的知识库助手。请只基于给定上下文回答，若证据不足必须明确说明。"
        "请严格输出如下结构，并强制引用编号：\n"
        "## 结论\n"
        "...\n\n"
        "## 依据\n"
        "- [1] ...\n"
        "- [2] ...\n\n"
        "## 引用\n"
        "- [1] source_id/rel_path\n"
        "- [2] source_id/rel_path\n\n"
        "## 不确定性\n"
        "- ...\n\n"
        f"问题：{question}\n\n"
        "上下文：\n"
        f"{build_query_context(citations)}"
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a precise knowledge-base assistant."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }
    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }
    url = settings.llm_base_url.rstrip("/") + "/chat/completions"
    try:
        with httpx.Client(timeout=120) as client:
            resp = client.post(url, headers=headers, json=payload)
        if resp.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"LLM request failed: {resp.status_code} {resp.text}")
        data = resp.json()
        answer = data["choices"][0]["message"]["content"].strip()
        return answer, model
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"LLM call error: {exc}") from exc


@app.on_event("startup")
def startup() -> None:
    global SCHEDULER_STARTED, AUTO_SYNC_LAST_RUN
    init_db()
    if not SCHEDULER_STARTED:
        AUTO_SYNC_LAST_RUN = time.time()
        threading.Thread(target=scheduler_loop, daemon=True).start()
        SCHEDULER_STARTED = True


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/login")
def login(payload: LoginRequest, response: Response) -> dict[str, bool]:
    if payload.password != settings.auth_password:
        raise HTTPException(status_code=401, detail="Invalid password")
    token = serializer.dumps({"ok": True})
    response.set_cookie("ms_token", token, httponly=True, samesite="lax")
    return {"ok": True}


@app.get("/api/auth-mode")
def auth_mode(_: Any = Depends(require_any_auth)) -> dict[str, bool]:
    return {"cookie_enabled": True, "api_key_enabled": bool(settings.api_key.strip())}


@app.get("/api/sources")
def sources(_: Any = Depends(require_any_auth)) -> dict[str, Any]:
    items = []
    for source in load_sources():
        root = resolve_source_root(source)
        items.append({"id": source.id, "path": str(root), "include": source.include, "exists": root.exists()})
    return {"sources": items}


@app.get("/api/settings")
def get_settings(_: Any = Depends(require_any_auth)) -> dict[str, Any]:
    conn = get_db()
    st = read_settings(conn)
    conn.close()
    return build_auto_sync_meta(st)


@app.post("/api/settings")
def update_settings(payload: SettingsUpdateRequest, _: Any = Depends(require_any_auth)) -> dict[str, Any]:
    global AUTO_SYNC_LAST_RUN
    conn = get_db()
    try:
        if payload.auto_sync_enabled is not None:
            conn.execute(
                "INSERT INTO app_settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                ("auto_sync_enabled", "true" if payload.auto_sync_enabled else "false"),
            )
        if payload.auto_sync_interval_minutes is not None:
            val = max(1, min(int(payload.auto_sync_interval_minutes), 24 * 60))
            conn.execute(
                "INSERT INTO app_settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                ("auto_sync_interval_minutes", str(val)),
            )
        conn.commit()
        st = read_settings(conn)
    finally:
        conn.close()
    AUTO_SYNC_LAST_RUN = time.time()
    data = build_auto_sync_meta(st)
    data["ok"] = True
    return data


def run_sync_job() -> dict[str, Any]:
    with SYNC_LOCK:
        SYNC_STATE["running"] = True
        SYNC_STATE["started_at"] = time.time()
        SYNC_STATE["finished_at"] = None
        SYNC_STATE["indexed"] = 0
        SYNC_STATE["skipped"] = 0
        SYNC_STATE["deleted"] = 0
        SYNC_STATE["sources"] = []
        SYNC_STATE["current_source"] = None
        SYNC_STATE["processed_files"] = 0
        SYNC_STATE["total_files"] = 0
        SYNC_STATE["error"] = None

    conn = None
    indexed = 0
    skipped = 0
    deleted = 0
    source_stats = []
    try:
        conn = get_db()
        for source in load_sources():
            root = resolve_source_root(source)
            if not root.exists():
                source_stats.append({"source_id": source.id, "status": "missing", "indexed": 0, "deleted": 0})
                continue
            files = collect_files(root, source.include)
            with SYNC_LOCK:
                SYNC_STATE["current_source"] = source.id
                SYNC_STATE["processed_files"] = 0
                SYNC_STATE["total_files"] = len(files)
            existing: set[str] = set()
            src_indexed = 0
            for i, f in enumerate(files, start=1):
                rel_path = str(f.relative_to(root)).replace("\\", "/")
                existing.add(rel_path)
                content = read_text_safely(f)
                mtime = f.stat().st_mtime
                sha1 = hashlib.sha1(content.encode("utf-8", errors="ignore")).hexdigest()
                old = conn.execute(
                    "SELECT sha1 FROM documents WHERE source_id = ? AND rel_path = ?",
                    (source.id, rel_path),
                ).fetchone()
                if old and old["sha1"] == sha1:
                    skipped += 1
                    if i % 200 == 0:
                        with SYNC_LOCK:
                            SYNC_STATE["processed_files"] = i
                    continue
                upsert_document(conn, source.id, rel_path, content, mtime, sha1, language_from_suffix(f))
                indexed += 1
                src_indexed += 1
                if i % 200 == 0:
                    with SYNC_LOCK:
                        SYNC_STATE["processed_files"] = i
            with SYNC_LOCK:
                SYNC_STATE["processed_files"] = len(files)
            removed = remove_missing(conn, source.id, existing)
            deleted += removed
            source_stats.append({"source_id": source.id, "status": "ok", "indexed": src_indexed, "deleted": removed})
            conn.commit()
        with SYNC_LOCK:
            SYNC_STATE["error"] = None
        run_error = None
    except Exception as exc:
        if conn:
            conn.rollback()
        with SYNC_LOCK:
            SYNC_STATE["error"] = str(exc)
        run_error = str(exc)
    finally:
        if conn:
            conn.close()
        with SYNC_LOCK:
            SYNC_STATE["running"] = False
            SYNC_STATE["finished_at"] = time.time()
            SYNC_STATE["indexed"] = indexed
            SYNC_STATE["skipped"] = skipped
            SYNC_STATE["deleted"] = deleted
            SYNC_STATE["sources"] = source_stats
            SYNC_STATE["current_source"] = None
    return {
        "indexed": indexed,
        "skipped": skipped,
        "deleted": deleted,
        "sources": source_stats,
        "error": run_error,
    }


@app.post("/api/sync")
def sync(background_tasks: BackgroundTasks, _: Any = Depends(require_any_auth)) -> dict[str, Any]:
    with SYNC_LOCK:
        if SYNC_STATE["running"]:
            return {"ok": True, "started": False, "message": "sync already running"}
        SYNC_STATE["running"] = True
    background_tasks.add_task(run_sync_job)
    return {"ok": True, "started": True}


@app.get("/api/sync-status")
def sync_status(_: Any = Depends(require_any_auth)) -> dict[str, Any]:
    with SYNC_LOCK:
        return dict(SYNC_STATE)


@app.get("/api/search")
def search(
    q: str,
    limit: int = 30,
    source_id: str | None = None,
    file_type: str | None = None,
    _: Any = Depends(require_any_auth),
) -> dict[str, Any]:
    if not q.strip():
        return {"items": []}
    q = q.strip()
    conn = get_db()
    fts_sql = """
        SELECT d.id, d.source_id, d.rel_path, d.lang,
               snippet(documents_fts, 1, '<mark>', '</mark>', '...', 30) AS snippet
        FROM documents_fts
        JOIN documents d ON d.id = documents_fts.rowid
        WHERE documents_fts MATCH ?
    """
    fts_args: list[Any] = [q]
    if source_id:
        fts_sql += " AND d.source_id = ?"
        fts_args.append(source_id)
    if file_type:
        fts_sql += " AND d.lang = ?"
        fts_args.append(file_type)
    fts_sql += " LIMIT ?"
    fts_args.append(limit)
    fts_rows = conn.execute(fts_sql, tuple(fts_args)).fetchall()
    items = [dict(row) for row in fts_rows]
    existing_ids = {item["id"] for item in items}

    # Fallback: FTS may miss mixed CJK+Latin tokens (e.g. "闭包closure").
    # Use LIKE recall to补齐结果，再与FTS结果去重合并。
    if len(items) < limit:
        like_rows = conn.execute(
            """
            SELECT id, source_id, rel_path, lang, content
            FROM documents
            WHERE (title LIKE ? OR rel_path LIKE ? OR content LIKE ?)
              AND (? IS NULL OR source_id = ?)
              AND (? IS NULL OR lang = ?)
            LIMIT ?
            """,
            (
                f"%{q}%",
                f"%{q}%",
                f"%{q}%",
                source_id,
                source_id,
                file_type,
                file_type,
                limit * 5,
            ),
        ).fetchall()
        for row in like_rows:
            row_id = row["id"]
            if row_id in existing_ids:
                continue
            items.append(
                {
                    "id": row_id,
                    "source_id": row["source_id"],
                    "rel_path": row["rel_path"],
                    "lang": row["lang"],
                    "snippet": snippet_from_content(row["content"], q),
                }
            )
            existing_ids.add(row_id)
            if len(items) >= limit:
                break
    conn.close()
    return {"items": items}


@app.get("/api/document/{doc_id}")
def get_document(doc_id: int, _: Any = Depends(require_any_auth)) -> dict[str, Any]:
    conn = get_db()
    row = conn.execute(
        "SELECT id, source_id, rel_path, title, content, lang, updated_at FROM documents WHERE id = ?",
        (doc_id,),
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    return dict(row)


@app.post("/api/ingest")
def ingest(payload: IngestRequest, _: Any = Depends(require_any_auth)) -> dict[str, Any]:
    conn = get_db()
    try:
        sources_all = load_sources()
        if payload.source_id:
            sources_to_ingest = [s for s in sources_all if s.id == payload.source_id]
            if not sources_to_ingest:
                raise HTTPException(status_code=404, detail=f"source_id not found: {payload.source_id}")
        else:
            sources_to_ingest = sources_all

        source_stats = []
        total_indexed = 0
        total_skipped = 0
        total_deleted = 0
        for source in sources_to_ingest:
            stat = index_single_source(conn, source, payload.rel_path)
            source_stats.append(stat)
            total_indexed += stat.get("indexed", 0)
            total_skipped += stat.get("skipped", 0)
            total_deleted += stat.get("deleted", 0)
        conn.commit()
        return {
            "ok": True,
            "indexed": total_indexed,
            "skipped": total_skipped,
            "deleted": total_deleted,
            "sources": source_stats,
        }
    finally:
        conn.close()


@app.post("/api/query")
def query(payload: QueryRequest, _: Any = Depends(require_any_auth)) -> dict[str, Any]:
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="question is required")

    conn = get_db()
    rows = conn.execute(
        """
        SELECT d.id, d.source_id, d.rel_path, d.title, d.content,
               snippet(documents_fts, 1, '<mark>', '</mark>', '...', 45) AS snippet
        FROM documents_fts
        JOIN documents d ON d.id = documents_fts.rowid
        WHERE documents_fts MATCH ?
        LIMIT ?
        """,
        (question, payload.limit),
    ).fetchall()
    conn.close()

    citations = [dict(row) for row in rows]
    used_llm = False
    model_used = (payload.model or settings.llm_model).strip()
    if not citations:
        answer = (
            "## 结论\n"
            "未检索到相关内容，请先同步或调整关键词。\n\n"
            "## 依据\n"
            "- 无可用证据。\n\n"
            "## 引用\n"
            "- (none)\n\n"
            "## 不确定性\n"
            "- 当前检索结果为空，无法形成可信结论。"
        )
    elif settings.llm_api_key.strip():
        answer, model_used = call_llm(question, citations, payload.model)
        used_llm = True
    else:
        lines = [
            "## 结论",
            "当前未配置 LLM_API_KEY，以下为检索摘要结论。",
            "",
            "## 依据",
        ]
        for i, c in enumerate(citations[:5], start=1):
            lines.append(f"- [{i}] {c['snippet']}")
        lines.append("")
        lines.append("## 引用")
        for i, c in enumerate(citations[:5], start=1):
            lines.append(f"- [{i}] {c['source_id']}/{c['rel_path']}")
        lines.append("")
        lines.append("## 不确定性")
        lines.append("- 未调用大模型进行深度归纳，结论为检索级摘要。")
        answer = "\n".join(lines)

    saved_path = None
    if payload.save_to_wiki:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        fname = f"insight_{ts}.md"
        target = WIKI_DIR / fname
        ref_lines = "\n".join([f"- `{c['source_id']}/{c['rel_path']}`" for c in citations]) or "- (none)"
        target.write_text(
            f"# Query Insight\n\n## Question\n{question}\n\n## Model\n{model_used}\n\n## Answer\n{answer}\n\n## Citations\n{ref_lines}\n",
            encoding="utf-8",
        )
        saved_path = str(target)

    lite_citations = [
        {k: v for k, v in c.items() if k in {"id", "source_id", "rel_path", "title", "snippet"}}
        for c in citations
    ]
    return {
        "ok": True,
        "answer": answer,
        "citations": lite_citations,
        "saved_path": saved_path,
        "used_llm": used_llm,
        "model_used": model_used,
    }


@app.post("/api/lint")
def lint(payload: LintRequest, _: Any = Depends(require_any_auth)) -> dict[str, Any]:
    conn = get_db()
    rows = conn.execute("SELECT id, source_id, rel_path, title, content, updated_at FROM documents").fetchall()
    conn.close()

    issues: list[dict[str, Any]] = []
    stale_threshold = time.time() - payload.stale_days * 86400
    title_count: dict[str, int] = {}
    md_link_pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")

    for row in rows:
        title = row["title"]
        title_count[title] = title_count.get(title, 0) + 1
        content = row["content"] or ""
        if len(content.strip()) < 20:
            issues.append(
                {
                    "type": "thin-content",
                    "source_id": row["source_id"],
                    "rel_path": row["rel_path"],
                    "detail": "content too short (<20 chars)",
                }
            )
        if row["updated_at"] < stale_threshold:
            issues.append(
                {
                    "type": "stale-doc",
                    "source_id": row["source_id"],
                    "rel_path": row["rel_path"],
                    "detail": f"not updated in {payload.stale_days}+ days",
                }
            )
        for link in md_link_pattern.findall(content):
            if link.startswith("http://") or link.startswith("https://") or link.startswith("#"):
                continue
            if link.startswith("mailto:"):
                continue
            if " " in link and not link.endswith(".md"):
                continue

    for row in rows:
        if title_count.get(row["title"], 0) > 1:
            issues.append(
                {
                    "type": "duplicate-title",
                    "source_id": row["source_id"],
                    "rel_path": row["rel_path"],
                    "detail": f"title '{row['title']}' appears multiple times",
                }
            )

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    report_path = LINT_DIR / f"lint_{ts}.md"
    report_lines = [
        "# mind-sync lint report",
        "",
        f"- Generated at: {datetime.now(timezone.utc).isoformat()}",
        f"- Total docs: {len(rows)}",
        f"- Total issues: {len(issues)}",
        "",
        "## Issues",
    ]
    if not issues:
        report_lines.append("- No issues found.")
    else:
        for item in issues:
            report_lines.append(
                f"- [{item['type']}] `{item['source_id']}/{item['rel_path']}` - {item['detail']}"
            )
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    return {"ok": True, "issue_count": len(issues), "issues": issues[:200], "report_path": str(report_path)}
