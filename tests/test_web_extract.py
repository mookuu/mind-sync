from app.services.web_extract import build_web_snapshot_markdown, web_response_to_markdown


SAMPLE_HTML = """
<!doctype html>
<html>
<head><title>Harness Pipeline Basics</title></head>
<body>
<article>
<h1>Harness Pipeline Basics</h1>
<p>Pipeline stages include Build and Deploy.</p>
</article>
</body>
</html>
"""


def test_web_response_html_to_markdown():
    result = web_response_to_markdown("https://example.com/docs", "text/html", SAMPLE_HTML)
    assert result["title"]
    assert "Pipeline" in result["markdown"] or "Harness" in result["markdown"]
    assert result["extractor"] in {"trafilatura", "html-plain"}


def test_web_response_json_to_markdown():
    body = '{"ok": true, "name": "mind-sync"}'
    result = web_response_to_markdown("https://example.com/api", "application/json", body)
    assert result["title"] == "JSON snapshot"
    assert "mind-sync" in result["markdown"]
    assert result["extractor"] == "json"


def test_build_web_snapshot_markdown_frontmatter():
    md = build_web_snapshot_markdown(
        url="https://example.com",
        content_type="text/html",
        body=SAMPLE_HTML,
        status_code=200,
        source_id="example_web",
    )
    assert md.startswith("---")
    assert "type: web_snapshot" in md
    assert "source_id: example_web" in md
    assert "# Harness Pipeline Basics" in md
