import sqlite3
import time
from pathlib import Path

from .config import settings

SCHEMA_VERSION = 5  # Increment when adding migrations in _run_migrations()

DATA_DIR = Path(settings.data_dir)
DB_PATH = DATA_DIR / "db" / "mind_sync.db"
WIKI_DIR = DATA_DIR / "wiki"
LINT_DIR = DATA_DIR / "lint-reports"
SEED_DIR = Path(__file__).resolve().parent / "seed"
SETTINGS_DEFAULTS = {
    "auto_sync_enabled": "false",
    "auto_sync_interval_minutes": "60",
    "sync_preset": "all",
    "sync_source_ids": "[]",
    "sync_source_order": "[]",
}


def ensure_data_dir() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "db").mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "config").mkdir(parents=True, exist_ok=True)
    return DATA_DIR


def get_db() -> sqlite3.Connection:
    ensure_data_dir()
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    return conn


def _get_schema_version(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT value FROM app_settings WHERE key = ?", ("_schema_version",)
    ).fetchone()
    return int(row["value"]) if row else 0


def _run_migrations(conn: sqlite3.Connection) -> None:
    """Run incremental schema migrations based on version."""
    version = _get_schema_version(conn)
    if version < 1:
        # V1: add size column to documents (existing databases)
        try:
            conn.execute(
                "ALTER TABLE documents ADD COLUMN size INTEGER NOT NULL DEFAULT 0"
            )
        except sqlite3.OperationalError:
            pass  # Column already exists
        conn.execute(
            "INSERT OR REPLACE INTO app_settings(key, value) VALUES(?, ?)",
            ("_schema_version", "1"),
        )
    if version < 2:
        # V2: add sessions, users, api_keys tables (schema already in CREATE IF NOT EXISTS)
        conn.execute(
            "INSERT OR REPLACE INTO app_settings(key, value) VALUES(?, ?)",
            ("_schema_version", "2"),
        )
    if version < 3:
        # V3: add source_owner column + rebuild FTS with source_owner
        try:
            conn.execute("ALTER TABLE documents ADD COLUMN source_owner TEXT NOT NULL DEFAULT '__shared__'")
        except sqlite3.OperationalError:
            pass  # Column already exists
        # FTS5 doesn't support ALTER TABLE ADD COLUMN → rebuild
        try:
            conn.executescript("""
                DROP TABLE IF EXISTS documents_fts;
                CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
                    title, content, rel_path, source_id, source_owner,
                    tokenize='unicode61'
                );
                INSERT INTO documents_fts(rowid, title, content, rel_path, source_id, source_owner)
                SELECT rowid, title, content, rel_path, source_id, '__shared__'
                FROM documents;
            """)
        except sqlite3.OperationalError:
            pass  # Table might not exist yet
        conn.execute(
            "INSERT OR REPLACE INTO app_settings(key, value) VALUES(?, ?)",
            ("_schema_version", "3"),
        )
    if version < 4:
        # V4: add display_name column to users
        try:
            conn.execute("ALTER TABLE users ADD COLUMN display_name TEXT NOT NULL DEFAULT ''")
        except sqlite3.OperationalError:
            pass  # Column already exists
        conn.execute(
            "INSERT OR REPLACE INTO app_settings(key, value) VALUES(?, ?)",
            ("_schema_version", "4"),
        )
    if version < 5:
        # V5: add locked_until column to users
        try:
            conn.execute("ALTER TABLE users ADD COLUMN locked_until REAL NOT NULL DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # Column already exists
        conn.execute(
            "INSERT OR REPLACE INTO app_settings(key, value) VALUES(?, ?)",
            ("_schema_version", "5"),
        )


def _seed_users_to_db(conn: sqlite3.Connection) -> None:
    """Copy users from env config to DB on first run."""
    from .services.permissions import load_auth_users  # local import to avoid cycle

    existing = conn.execute("SELECT COUNT(1) AS c FROM users").fetchone()
    if existing and int(existing["c"]) > 0:
        return
    for user in load_auth_users():
        conn.execute(
            "INSERT OR IGNORE INTO users(username, password_hash, role, created_at) VALUES(?, ?, ?, ?)",
            (user.username, user.password, user.role.value, time.time()),
        )


def init_db() -> None:
    ensure_data_dir()
    conn = get_db()
    conn.executescript("""
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
            source_owner TEXT NOT NULL DEFAULT '__shared__',
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
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'admin',
            ip TEXT NOT NULL DEFAULT '',
            user_agent TEXT NOT NULL DEFAULT '',
            created_at REAL NOT NULL,
            last_active_at REAL NOT NULL,
            expires_at REAL NOT NULL,
            remember_me INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'admin',
            created_at REAL NOT NULL,
            display_name TEXT NOT NULL DEFAULT '',
            locked_until REAL NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS api_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key_value TEXT NOT NULL UNIQUE,
            label TEXT NOT NULL DEFAULT '',
            created_at REAL NOT NULL,
            last_used_at REAL
        );
        """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_api_usage_key_time ON api_usage(identity, bucket, created_at)"
    )
    conn.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(title, content, rel_path, source_id, source_owner, tokenize='unicode61')"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_login_failures_key_time ON login_failures(ip, account, failed_at)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_audit_events_time ON audit_events(created_at)"
    )
    for k, v in SETTINGS_DEFAULTS.items():
        conn.execute(
            "INSERT INTO app_settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO NOTHING",
            (k, v),
        )
    # Schema migration: track version and apply upgrades
    _run_migrations(conn)

    # Seed users from env config (safe after tables exist)
    _seed_users_to_db(conn)
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
                "# 规则约束\n\n## 核心原则\n\n- 所有摘要必须引用可靠来源（sources），不可编造\n- 置信度分级：extracted > inferred > ambiguous > unverified\n\n"
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
    schema_dest = WIKI_DIR / "SCHEMA.md"
    if not schema_dest.exists():
        schema_seed = SEED_DIR / "wiki" / "SCHEMA.md"
        if schema_seed.exists():
            schema_dest.write_text(
                schema_seed.read_text(encoding="utf-8"), encoding="utf-8"
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
