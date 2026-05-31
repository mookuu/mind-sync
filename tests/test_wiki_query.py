from app.services.wiki_query import build_query_page_body


def test_build_query_page_body_yaml_safe():
    body = build_query_page_body(
        question='问: "Plan" 是什么？',
        answer="## 结论\n测试",
        model_used="test-model",
        ts="20260101_120000",
        evidences=[{"ref": 1, "source_id": "wiki", "rel_path": "a.md"}],
    )
    assert body.startswith("---\n")
    assert 'question: \'问: "Plan" 是什么？\'' in body or "question:" in body
    assert "## Answer" in body
    assert "wiki/a.md" in body
