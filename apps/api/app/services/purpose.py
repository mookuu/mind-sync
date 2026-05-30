from pathlib import Path

from ..db import WIKI_DIR
from ..config import settings

PURPOSE_PATH = Path(settings.data_dir) / "purpose.md"


def load_purpose_text(max_chars: int = 4000) -> str:
    if not PURPOSE_PATH.exists():
        return ""
    text = PURPOSE_PATH.read_text(encoding="utf-8", errors="ignore").strip()
    if max_chars > 0 and len(text) > max_chars:
        return text[:max_chars] + "\n...(truncated)"
    return text


def purpose_status() -> dict[str, object]:
    exists = PURPOSE_PATH.exists()
    preview = load_purpose_text(400) if exists else ""
    return {
        "exists": exists,
        "path": str(PURPOSE_PATH),
        "preview": preview,
        "wiki_dir": str(WIKI_DIR),
    }
