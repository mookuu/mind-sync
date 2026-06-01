from app.services.classify import suggest_wiki_path


def test_suggest_python():
    out = suggest_wiki_path("Python 装饰器用法")
    assert "python" in out["recommended"].lower()


def test_suggest_empty():
    out = suggest_wiki_path("")
    assert out["recommended"] is None
