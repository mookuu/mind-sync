"""Chinese text tokenizer using jieba for FTS5 pre-tokenization.

Usage:
    from .chinese_tokenizer import tokenize, tokenize_query, has_chinese

    # Indexing: pre-tokenize text before feeding to FTS5
    fts_text = tokenize("Python 知识库工程最佳实践")
    # → "Python 知识库 工程 最佳实践"

    # Searching: tokenize user query for FTS5 MATCH
    fts_query = tokenize_query("知识工程")
    # → '"知识" AND "工程"'

    # Check if text contains CJK characters
    has_chinese("Hello 世界")  # → True
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Tuple as _Tuple

# Lazy import jieba so the module loads even if jieba is not installed
_jieba = None


def _get_jieba():
    global _jieba
    if _jieba is None:
        try:
            import jieba
            _jieba = jieba
        except ImportError:
            _jieba = False  # sentinel
    return _jieba if _jieba is not False else None


# CJK character ranges
_CJK_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]")

# Try to load user dictionary (优先持久卷 /data/jieba_dict.txt，其次内置文件)
try:
    from ..config import settings
    _DATA_DICT = Path(settings.data_dir) / "jieba_dict.txt"
except Exception:
    _DATA_DICT = None

if _DATA_DICT and _DATA_DICT.exists():
    _USER_DICT_PATH = str(_DATA_DICT)
elif Path("/data/config/jieba_dict.txt").exists():
    _USER_DICT_PATH = "/data/config/jieba_dict.txt"
else:
    _DEFAULT_DICT = Path(__file__).resolve().parent.parent / "data" / "jieba_dict.txt"
    _USER_DICT_PATH = str(_DEFAULT_DICT) if _DEFAULT_DICT.exists() else None

# Auto-load dictionary at import time
_auto_loaded = False


def _auto_load_dict():
    global _auto_loaded
    if _auto_loaded:
        return
    _auto_loaded = True
    jieba = _get_jieba()
    if jieba is None:
        return
    if _USER_DICT_PATH:
        try:
            jieba.load_userdict(_USER_DICT_PATH)
        except Exception:
            pass


_auto_load_dict()


def init(user_dict_path: str | None = None) -> None:
    """Initialize the tokenizer with optional custom dictionary.

    Call once at app startup:
        from .chinese_tokenizer import init
        init("/data/jieba_dict.txt")
    """
    global _USER_DICT_PATH
    jieba = _get_jieba()
    if jieba is None:
        return
    if user_dict_path:
        jieba.load_userdict(user_dict_path)
        _USER_DICT_PATH = user_dict_path


def has_chinese(text: str) -> bool:
    """Return True if text contains CJK characters."""
    return bool(_CJK_RE.search(text))


def tokenize(text: str) -> str:
    """Pre-tokenize text for FTS5 indexing.

    Splits Chinese text into space-separated words using jieba.
    Non-Chinese text is returned unchanged (FTS5 unicode61 handles it).
    """
    if not text or not has_chinese(text):
        return text
    jieba = _get_jieba()
    if jieba is None:
        return text
    words = jieba.cut(text)
    return " ".join(w for w in words if w.strip())


def tokenize_query(query: str, default_op: str = "AND") -> str:
    """Tokenize a search query for FTS5 MATCH syntax.

    Each Chinese word is quoted and joined by default_op.
    Non-Chinese queries are returned as a single quoted phrase.
    """
    q = (query or "").strip()
    if not q:
        return ""
    if not has_chinese(q):
        return f'"{q}"'
    jieba = _get_jieba()
    if jieba is None:
        return f'"{q}"'
    words = jieba.cut(q)
    tokens = [w.strip() for w in words if w.strip()]
    if not tokens:
        return ""
    return f" {default_op} ".join(f'"{t}"' for t in tokens)


def tokenize_for_bm25(text: str) -> str:
    """Alias for tokenize() — explicit naming for BM25 indexing."""
    return tokenize(text)
