from dataclasses import dataclass
from typing import Any

import httpx
from fastapi import HTTPException


@dataclass
class QueryEngineConfig:
    llm_base_url: str
    llm_api_key: str
    llm_model: str
    ollama_base_url: str = ""


def _build_query_context(citations: list[dict[str, Any]]) -> str:
    if not citations:
        return "No context found."
    lines: list[str] = []
    for i, c in enumerate(citations, start=1):
        lines.append(f"[{i}] {c['source_id']}/{c['rel_path']}")
        lines.append(c.get("content", "")[:4000])
        lines.append("")
    return "\n".join(lines)


async def _call_llm_stream(
    question: str,
    citations: list[dict[str, Any]],
    config: QueryEngineConfig,
    purpose_text: str = "",
    model_override: str | None = None,
):
    """SSE streaming version of _call_llm. Yields SSE-formatted token dicts."""
    model = (model_override or config.llm_model).strip()
    if not config.llm_api_key.strip():
        yield {"event": "error", "data": "LLM_API_KEY is not configured"}
        return

    purpose_block = ""
    if purpose_text.strip():
        purpose_block = f"规则约束（优先遵循）：\n{purpose_text.strip()}\n\n"

    prompt = (
        "你是 mind-sync 的知识库助手。请只基于给定上下文回答，若证据不足必须明确说明。"
        "禁止引用上下文以外的知识作为事实。摘要类文档（summaries/）优先于原始长文。"
        "请严格输出如下结构，并强制引用编号：\n"
        "## 结论\n"
        "...\n\n"
        "## 依据\n"
        "- [1] ...\n"
        "- [2] ...\n\n"
        "## 引用\n"
        "- [1] source_id/rel_path\n"
        "- [2] source_id/rel_path\n\n"
        "## 不确定性\n"
        "- ...\n\n"
        f"{purpose_block}"
        f"问题：{question}\n\n"
        "上下文：\n"
        f"{_build_query_context(citations)}"
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a precise knowledge-base assistant."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "stream": True,
    }
    headers = {
        "Authorization": f"Bearer {config.llm_api_key}",
        "Content-Type": "application/json",
    }
    url = config.llm_base_url.rstrip("/") + "/chat/completions"
    try:
        async with httpx.AsyncClient(timeout=300) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as resp:
                if resp.status_code >= 400:
                    error_text = await resp.aread()
                    yield {"event": "error", "data": f"LLM error: {resp.status_code} {error_text.decode('utf-8')[:200]}"}
                    return
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    chunk = line[6:].strip()
                    if chunk in ("", "[DONE]"):
                        continue
                    yield {"event": "token", "data": chunk}
    except Exception as exc:
        yield {"event": "error", "data": f"LLM call error: {str(exc)[:200]}"}


def _call_llm(
    question: str,
    citations: list[dict[str, Any]],
    config: QueryEngineConfig,
    purpose_text: str = "",
    model_override: str | None = None,
) -> tuple[str, str]:
    model = (model_override or config.llm_model).strip()
    if not config.llm_api_key.strip():
        raise HTTPException(status_code=400, detail="LLM_API_KEY is not configured")

    purpose_block = ""
    if purpose_text.strip():
        purpose_block = f"规则约束（优先遵循）：\n{purpose_text.strip()}\n\n"

    prompt = (
        "你是 mind-sync 的知识库助手。请只基于给定上下文回答，若证据不足必须明确说明。"
        "禁止引用上下文以外的知识作为事实。摘要类文档（summaries/）优先于原始长文。"
        "请严格输出如下结构，并强制引用编号：\n"
        "## 结论\n"
        "...\n\n"
        "## 依据\n"
        "- [1] ...\n"
        "- [2] ...\n\n"
        "## 引用\n"
        "- [1] source_id/rel_path\n"
        "- [2] source_id/rel_path\n\n"
        "## 不确定性\n"
        "- ...\n\n"
        f"{purpose_block}"
        f"问题：{question}\n\n"
        "上下文：\n"
        f"{_build_query_context(citations)}"
    )
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "You are a precise knowledge-base assistant.",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }
    headers = {
        "Authorization": f"Bearer {config.llm_api_key}",
        "Content-Type": "application/json",
    }
    url = config.llm_base_url.rstrip("/") + "/chat/completions"
    try:
        with httpx.Client(timeout=120) as client:
            resp = client.post(url, headers=headers, json=payload)
        if resp.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail=f"LLM request failed: {resp.status_code} {resp.text}",
            )
        data = resp.json()
        answer = data["choices"][0]["message"]["content"].strip()
        return answer, model
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"LLM call error: {exc}") from exc


def generate_structured_answer(
    question: str,
    citations: list[dict[str, Any]],
    config: QueryEngineConfig,
    model_override: str | None = None,
    purpose_text: str = "",
) -> tuple[str, bool, str]:
    model_used = (model_override or config.llm_model).strip()
    if not citations:
        answer = (
            "## 结论\n"
            "未检索到相关内容，请先同步或调整关键词。\n\n"
            "## 依据\n"
            "- 无可用证据。\n\n"
            "## 引用\n"
            "- (none)\n\n"
            "## 不确定性\n"
            "- 当前检索结果为空，无法形成可信结论。"
        )
        return answer, False, model_used

    if config.llm_api_key.strip():
        answer, model_used = _call_llm(
            question, citations, config, purpose_text, model_override
        )
        return answer, True, model_used

    ollama_url = (config.ollama_base_url or "").strip()
    if ollama_url:
        ollama_config = QueryEngineConfig(
            llm_base_url=ollama_url.rstrip("/") + "/v1",
            llm_api_key="ollama",
            llm_model=model_used,
        )
        try:
            answer, model_used = _call_llm(
                question, citations, ollama_config, purpose_text, model_override
            )
            return answer, True, model_used
        except HTTPException:
            pass

    lines = [
        "## 结论",
        "当前未配置 LLM_API_KEY，以下为检索摘要结论。",
        "",
        "## 依据",
    ]
    for i, c in enumerate(citations[:5], start=1):
        lines.append(f"- [{i}] {c['snippet']}")
    lines.append("")
    lines.append("## 引用")
    for i, c in enumerate(citations[:5], start=1):
        lines.append(f"- [{i}] {c['source_id']}/{c['rel_path']}")
    lines.append("")
    lines.append("## 不确定性")
    lines.append("- 未调用大模型进行深度归纳，结论为检索级摘要。")
    return "\n".join(lines), False, model_used
