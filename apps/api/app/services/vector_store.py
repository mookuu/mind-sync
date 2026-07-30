"""Vector store for local embedding-based document retrieval.

Provides storage and similarity search for document embeddings.
Default embedding uses TF-IDF keyword vectors (no external model required).
Designed to be swappable with any embedding function (e.g. sentence-transformers)
by setting embedder.embed_fn.
"""
from __future__ import annotations
import json, logging, math, re, sqlite3, struct, time
from pathlib import Path
from typing import Any, Callable
from collections import Counter

logger = logging.getLogger("mind-sync.vector_store")

# ── default lightweight embedding (keyword TF-IDF) ──────────

_TOKEN_SPLIT = re.compile(r"[^\w]+")


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_SPLIT.split(text) if len(t) >= 2]


def _default_embed(texts: list[str]) -> list[list[float]]:
    """Simple keyword-frequency embedding (bag-of-words with TF scaling).

    No external model required. Each document becomes a vector where each
    dimension is the log-normalized frequency of a word.
    Replace this with sentence-transformers or OpenAI embeddings for
    semantic search.
    """
    if not texts:
        return []
    # Build global vocab from all texts
    all_tokens: list[str] = []
    for t in texts:
        all_tokens.extend(_tokenize(t))
    vocab = sorted(set(all_tokens))
    if not vocab:
        return [[0.0]]  # fallback single-dim vector

    word_index = {w: i for i, w in enumerate(vocab)}
    doc_freq: Counter = Counter()
    doc_token_lists: list[Counter] = []
    for t in texts:
        tokens = _tokenize(t)
        doc_token_lists.append(Counter(tokens))
        doc_freq.update(set(tokens))

    num_docs = len(texts)
    vectors: list[list[float]] = []
    for token_counter in doc_token_lists:
        vec = [0.0] * len(vocab)
        max_freq = max(token_counter.values()) if token_counter else 1
        for token, cnt in token_counter.items():
            idx = word_index.get(token)
            if idx is None:
                continue
            tf = cnt / max_freq
            idf = math.log((num_docs + 1) / (doc_freq.get(token, 0) + 1)) + 1
            vec[idx] = tf * idf
        vectors.append(vec)
    return vectors


# ── cosine similarity ───────────────────────────────────────

def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(av * bv for av, bv in zip(a, b))
    na = math.sqrt(sum(av * av for av in a))
    nb = math.sqrt(sum(bv * bv for bv in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


# ── vector serialization ────────────────────────────────────

def _pack_vector(v: list[float]) -> bytes:
    return struct.pack(f"{len(v)}f", *v)


def _unpack_vector(data: bytes) -> list[float]:
    return list(struct.unpack(f"{len(data) // 4}f", data))


# ── VectorStore class ───────────────────────────────────────

class VectorStore:
    """Local vector store backed by SQLite.

    Usage:
        store = VectorStore(conn)
        store.build_index(["doc1 text", "doc2 text"], ["id1", "id2"])
        results = store.search("query text", top_k=5)
    """

    TABLE = "vector_embeddings"

    def __init__(
        self,
        conn: sqlite3.Connection,
        embed_fn: Callable[[list[str]], list[list[float]]] | None = None,
    ):
        self.conn = conn
        self.embed_fn = embed_fn or _default_embed

    # ── schema ──────────────────────────────────────────────

    @staticmethod
    def ensure_table(conn: sqlite3.Connection) -> None:
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {VectorStore.TABLE} (
                doc_id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL DEFAULT '',
                title TEXT NOT NULL DEFAULT '',
                vector BLOB NOT NULL,
                dims INTEGER NOT NULL DEFAULT 0,
                updated_at REAL NOT NULL
            )
        """)

    # ── index management ────────────────────────────────────

    def build_index(
        self,
        texts: list[str],
        doc_ids: list[str],
        source_ids: list[str] | None = None,
        titles: list[str] | None = None,
    ) -> int:
        """Embed texts and store vectors. Returns count of indexed docs."""
        if not texts or not doc_ids:
            return 0
        vectors = self.embed_fn(texts)
        if not vectors or len(vectors) != len(doc_ids):
            logger.warning("embedding returned %d vectors for %d texts", len(vectors or []), len(doc_ids))
            return 0

        now = time.time()
        dims = len(vectors[0]) if vectors else 0
        count = 0
        for i, doc_id in enumerate(doc_ids):
            try:
                self.conn.execute(
                    f"INSERT OR REPLACE INTO {self.TABLE}(doc_id, source_id, title, vector, dims, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        doc_id,
                        (source_ids[i] if source_ids and i < len(source_ids) else ""),
                        (titles[i] if titles and i < len(titles) else ""),
                        _pack_vector(vectors[i]),
                        dims,
                        now,
                    ),
                )
                count += 1
            except Exception:
                logger.warning("failed to store vector for doc_id=%s", doc_id)
        self.conn.commit()
        logger.info("vector_store: indexed %d/%d documents", count, len(doc_ids))
        return count

    def remove_doc(self, doc_id: str) -> None:
        self.conn.execute(f"DELETE FROM {self.TABLE} WHERE doc_id = ?", (doc_id,))
        self.conn.commit()

    def clear(self) -> None:
        self.conn.execute(f"DELETE FROM {self.TABLE}")
        self.conn.commit()

    @property
    def size(self) -> int:
        row = self.conn.execute(f"SELECT COUNT(1) AS c FROM {self.TABLE}").fetchone()
        return int(row["c"]) if row else 0

    # ── search ──────────────────────────────────────────────

    def search(
        self,
        query: str,
        top_k: int = 10,
        min_score: float = 0.0,
    ) -> list[dict[str, Any]]:
        """Vector similarity search. Returns sorted results with score."""
        vecs = self.embed_fn([query])
        if not vecs or not vecs[0]:
            return []
        query_vec = vecs[0]

        rows = self.conn.execute(
            f"SELECT doc_id, source_id, title, vector, dims FROM {self.TABLE}"
        ).fetchall()

        scored: list[tuple[float, dict[str, Any]]] = []
        for row in rows:
            try:
                doc_vec = _unpack_vector(row["vector"])
                score = cosine_similarity(query_vec, doc_vec)
                if score >= min_score:
                    scored.append((score, {
                        "doc_id": row["doc_id"],
                        "source_id": row["source_id"],
                        "title": row["title"],
                        "score": round(score, 4),
                    }))
            except Exception:
                continue

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored[:top_k]]


# ── convenience helpers ─────────────────────────────────────

def rebuild_vector_index(conn: sqlite3.Connection) -> int:
    """Rebuild the entire vector index from the documents table.

    Returns the number of documents indexed.
    """
    rows = conn.execute(
        "SELECT id, source_id, title, content FROM documents WHERE content IS NOT NULL AND content != ''"
    ).fetchall()
    if not rows:
        return 0

    doc_ids = [str(r["id"]) for r in rows]
    source_ids = [r["source_id"] for r in rows]
    titles = [r["title"] or "" for r in rows]
    texts = [f"{r['title'] or ''} {r['content'] or ''}" for r in rows]

    store = VectorStore(conn)
    store.clear()
    return store.build_index(texts, doc_ids, source_ids, titles)
