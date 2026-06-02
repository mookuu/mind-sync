"""Tests for search category weight boosting."""

from app.services.fts import _rank_with_weights, parse_category_weights


def test_parse_category_weights_defaults():
    w = parse_category_weights()
    assert w["summary"] >= 1.0
    assert w["source"] == 1.0


def test_rank_with_weights_prefers_summary():
    items = [
        {"id": 1, "source_id": "notes", "rel_path": "raw/a.md", "rank_score": 1.0, "category": "source"},
        {"id": 2, "source_id": "wiki", "rel_path": "summaries/a.md", "rank_score": 1.1, "category": "summary"},
    ]
    out = _rank_with_weights(items, {"summary": 2.0, "source": 1.0, "query": 1.0})
    assert out[0]["category"] == "summary"
