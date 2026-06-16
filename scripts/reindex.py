"""Reindex all sources: re-read files, re-tokenize with jieba, rebuild FTS."""
import sys
import os
import time

# Add app to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "apps/api"))

from app.db import get_db, init_db
from app.services.indexer import index_single_source
from app.services.indexer import load_sources
from app.services.chinese_tokenizer import init as init_tokenizer


def reindex_all():
    print("=== Reindex All Sources ===")
    init_tokenizer()  # Load jieba if available
    conn = get_db()
    try:
        sources = load_sources()
        print(f"Found {len(sources)} sources")
        for source in sources:
            print(f"  Indexing: {source.id} ({source.source_type})...", end=" ", flush=True)
            try:
                result = index_single_source(conn, source)
                print(f"indexed={result['indexed']}, skipped={result['skipped']}, deleted={result['deleted']}")
            except Exception as e:
                print(f"ERROR: {e}")
        conn.commit()
        print("=== Done ===")
    finally:
        conn.close()


if __name__ == "__main__":
    reindex_all()
