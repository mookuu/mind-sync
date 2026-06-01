import sqlite3
from pathlib import Path

from .config import settings

DATA_DIR = Path(settings.data_dir)
DB_PATH = DATA_DIR / "mind_sync.db"
WIKI_DIR = DATA_DIR / "wiki"
LINT_DIR = DATA_DIR / "lint-reports"
SEED_DIR = Path(__file__).resolve().parent / "seed"
SETTINGS_DEFAULTS = {
    "auto_sync_enabled": "false",
    "auto_sync_interval_minutes": "60",
    "sync_preset": "all",
    "sync_source_ids": "[]",
}


def ensure_data_dir() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR


def get_db() -> sqlite3.Connection:
    ensure_data_dir()
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    return conn


def init_db() -> None:
    ensure_data_dir()
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
            size INTEGER NOT NULL DEFAULT 0,
            sha1 TEXT NOT NULL,
            updated_at REAL NOT NULL,
            UNIQUE(source_id, rel_path)
        );
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS session_revocations (
            token_hash TEXT PRIMARY KEY,
            expires_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS login_failures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip TEXT NOT NULL,
            account TEXT NOT NULL,
            failed_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS audit_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            actor TEXT NOT NULL,
            ip TEXT NOT NULL,
            detail TEXT NOT NULL,
            created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS api_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            identity TEXT NOT NULL,
            bucket TEXT NOT NULL,
            created_at REAL NOT NULL
        );
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_api_usage_key_time ON api_usage(identity, bucket, created_at)")
    try:
        conn.execute("ALTER TABLE documents ADD COLUMN size INTEGER NOT NULL DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(title, content, rel_path, source_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_login_failures_key_time ON login_failures(ip, account, failed_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_events_time ON audit_events(created_at)")
    for k, v in SETTINGS_DEFAULTS.items():
        conn.execute(
            "INSERT INTO app_settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO NOTHING",
            (k, v),
        )
    conn.commit()
    conn.close()
    WIKI_DIR.mkdir(parents=True, exist_ok=True)
    (WIKI_DIR / "summaries").mkdir(parents=True, exist_ok=True)
    (WIKI_DIR / "queries").mkdir(parents=True, exist_ok=True)
    LINT_DIR.mkdir(parents=True, exist_ok=True)
    purpose_path = Path(settings.data_dir) / "purpose.md"
    if not purpose_path.exists():
        example = SEED_DIR / "purpose.example.md"
        if example.exists():
            text = example.read_text(encoding="utf-8")
        else:
            text = (
                "# 研究方向\n\n## 核心目标\n\n- 建立可检索、可溯源的个人学习知识库\n\n"
                "## 关键问题\n\n- （填写你正在学习的问题）\n"
            )
        purpose_path.write_text(text, encoding="utf-8")
    summary_readme = WIKI_DIR / "summaries" / "README.md"
    if not summary_readme.exists():
        summary_readme.write_text(
            "# 学习摘要\n\n按主题分子目录，例如 `summaries/harness/pipeline-basics.md`。\n"
            "模板见项目 `templates/wiki/summary-template.md`。\n",
            encoding="utf-8",
        )
    _seed_wiki_examples()


def _seed_wiki_examples() -> None:
    examples_dir = SEED_DIR / "wiki" / "examples"
    if not examples_dir.is_dir():
        return
    for src in sorted(examples_dir.rglob("*.md")):
        rel = src.relative_to(examples_dir)
        dest = WIKI_DIR / "summaries" / rel
        if dest.exists():
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")


def read_settings(conn: sqlite3.Connection) -> dict[str, str]:
    rows = conn.execute("SELECT key, value FROM app_settings").fetchall()
    data = {row["key"]: row["value"] for row in rows}
    for k, v in SETTINGS_DEFAULTS.items():
        data.setdefault(k, v)
    return data


def load_settings_map() -> dict[str, str]:
    conn = get_db()
    try:
        return read_settings(conn)
    finally:
        conn.close()
