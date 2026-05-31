from app.services.evidence import build_evidence_items, question_tokens


def test_question_tokens_chinese_bigrams():
    tokens = question_tokens("Python 异常层次结构")
    assert "python" in tokens
    assert "异常层次结构" in tokens
    assert "异常" in tokens or "层次" in tokens


def test_build_evidence_items_extracted_when_full_question_matches():
    citations = [
        {
            "id": 1,
            "source_id": "wiki",
            "rel_path": "a.md",
            "title": "a",
            "content": "PlanAndSolve 是一种 Agent 规划范式",
            "snippet": "",
        }
    ]
    items = build_evidence_items(citations, "PlanAndSolve 是一种 Agent 规划范式")
    assert len(items) == 1
    assert items[0]["confidence_level"] == "EXTRACTED"
    assert items[0]["confidence_label"] == "原文摘录"
