from typing import Any

CONFIDENCE_LEVELS = ("EXTRACTED", "INFERRED", "AMBIGUOUS", "UNVERIFIED")
CONFIDENCE_LABELS = {
    "EXTRACTED": "原文摘录",
    "INFERRED": "推断",
    "AMBIGUOUS": "待澄清",
    "UNVERIFIED": "未验证",
}


def _score_to_level(score: float) -> str:
    if score >= 0.82:
        return "EXTRACTED"
    if score >= 0.68:
        return "INFERRED"
    if score >= 0.52:
        return "AMBIGUOUS"
    return "UNVERIFIED"


def build_evidence_items(citations: list[dict[str, Any]], question: str) -> list[dict[str, Any]]:
    evidences: list[dict[str, Any]] = []
    q = (question or "").strip().lower()
    q_tokens = [t for t in q.split() if len(t) >= 2]
    for idx, c in enumerate(citations, start=1):
        content = c.get("content") or ""
        snippet = c.get("snippet") or ""
        content_lower = content.lower()
        has_full_q = bool(q and q in content_lower)
        token_hits = sum(1 for t in q_tokens if t in content_lower)
        confidence = 0.55
        if has_full_q:
            confidence = 0.88
        elif token_hits >= max(1, len(q_tokens) // 2):
            confidence = 0.78
        elif token_hits > 0:
            confidence = 0.65
        if snippet:
            confidence += 0.05
        confidence = min(confidence, 0.95)
        level = _score_to_level(confidence)
        if not content.strip() and snippet:
            level = "INFERRED"
        evidences.append(
            {
                "ref": idx,
                "doc_id": c.get("id"),
                "source_id": c.get("source_id"),
                "rel_path": c.get("rel_path"),
                "title": c.get("title"),
                "excerpt": snippet if snippet else content[:220],
                "confidence": round(confidence, 2),
                "confidence_level": level,
                "confidence_label": CONFIDENCE_LABELS.get(level, level),
            }
        )
    return evidences
