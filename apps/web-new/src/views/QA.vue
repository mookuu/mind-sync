<template>
  <div class="view-pane">
    <div class="view-header"><h2>结构化问答</h2></div>
    <div class="qa-input-row">
      <input v-model="question" type="text" placeholder="输入问题…" @keydown.enter="ask" />
      <button class="btn btn-primary" @click="ask" :disabled="asking">{{ asking ? "生成中…" : "提问" }}</button>
    </div>
    <label class="checkbox-row">
      <input v-model="saveToWiki" type="checkbox" />
      保存到 wiki/queries
    </label>
    <p class="subtle" style="margin-top: 8px;">未配置 LLM_API_KEY 时将仅返回检索摘要。</p>

    <!-- 推理过程（DeepSeek-R1） -->
    <div v-if="reasoningText" class="reasoning-section">
      <button class="reasoning-toggle" @click="showReasoning = !showReasoning">
        {{ showReasoning ? "▾ 收起推理过程" : "▸ 展开推理过程" }}
        <span class="subtle">({{ reasoningText.length }} 字符)</span>
      </button>
      <pre v-if="showReasoning" class="reasoning-content">{{ reasoningText }}</pre>
    </div>

    <!-- 流式/完整回答 -->
    <div v-if="streaming || answer" class="qa-answer doc-markdown" :class="{ 'qa-streaming': streaming }" v-html="renderedAnswer"></div>

    <!-- 证据 -->
    <ul v-if="evidences.length" class="evidence-list">
      <li v-for="(ev, i) in evidences" :key="i" class="evidence-item">
        <span class="evidence-tag">{{ ev.confidence }}</span>
        <span>{{ ev.source_id }}/{{ ev.rel_path }}</span>
      </li>
    </ul>
  </div>
</template>

<script setup>
import { ref, computed } from "vue";
import api from "../api/index.js";
import { renderMarkdown } from "../composables/useMarkdown.js";

const question = ref("");
const saveToWiki = ref(false);
const asking = ref(false);
const streaming = ref(false);
const answer = ref(null);
const evidences = ref([]);
const reasoningText = ref("");
const showReasoning = ref(false);

const renderedAnswer = computed(() => renderMarkdown(answer.value || ""));

async function ask() {
  if (!question.value.trim()) return;
  asking.value = true;
  streaming.value = false;
  answer.value = null;
  evidences.value = [];
  reasoningText.value = "";
  showReasoning.value = false;

  try {
    // 尝试流式
    await streamQuery(question.value);
  } catch (e) {
    // 流式失败 → 回退同步
    console.warn("stream fallback:", e.message);
    try {
      const data = await api("/api/query", {
        method: "POST",
        body: { question: question.value, save_to_wiki: saveToWiki.value },
      });
      answer.value = data.answer || data.content || "";
      evidences.value = data.evidences || [];
    } catch (e2) {
      showError(e2.message);
    }
  } finally {
    asking.value = false;
    streaming.value = false;
  }
}

async function streamQuery(q) {
  const csrf = document.cookie.split("; ").find(c => c.startsWith("ms_csrf="));
  const csrfToken = csrf ? csrf.split("=")[1] : "";
  const res = await fetch("/api/query/stream", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(csrfToken ? { "x-csrf-token": csrfToken } : {}),
    },
    body: JSON.stringify({ question: q, save_to_wiki: saveToWiki.value }),
    credentials: "include",
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
    throw new Error(err.detail);
  }

  streaming.value = true;
  let content = "";
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const data = line.slice(6).trim();
      if (data === "[DONE]") continue;
      try {
        const msg = JSON.parse(data);
        if (msg.type === "citations") {
          evidences.value = msg.citations || [];
        } else if (msg.type === "reasoning") {
          reasoningText.value += msg.text || "";
        } else if (msg.type === "token") {
          content += msg.text || "";
          answer.value = content;
        } else if (msg.type === "done") {
          if (msg.answer) content = msg.answer;
          if (msg.reasoning) reasoningText.value = msg.reasoning;
          answer.value = content;
        } else if (msg.type === "error") {
          showError(msg.message || "LLM 返回错误");
          return;
        }
      } catch {
        // skip unparseable
      }
    }
  }
}

function showError(msg) {
  if (msg.includes("401") || msg.includes("Authentication failed") || msg.includes("token")) {
    answer.value = "⚠️ **LLM 服务未配置**\n\n请在 `.env` 中设置有效的 `LLM_API_KEY`。";
  } else if (msg.includes("timeout") || msg.includes("timed out")) {
    answer.value = "⏱️ **请求超时**\n\nLLM 服务响应超时，请稍后重试。";
  } else {
    answer.value = `❌ **查询失败**: ${msg}`;
  }
  evidences.value = [];
}
</script>

<style scoped>
.qa-input-row {
  display: flex;
  gap: 8px;
  margin: 16px 0;
}
.qa-input-row input { flex: 1; }
.checkbox-row {
  display: flex; align-items: center; gap: 6px;
  font-size: 0.85rem; color: var(--fg-muted);
}
.qa-answer {
  border: 1px solid var(--border-default);
  border-radius: var(--radius);
  padding: 16px;
  margin-top: 16px;
  line-height: 1.7;
  font-size: 0.92rem;
}
.qa-answer.qa-streaming {
  border-color: var(--accent-emphasis);
}
.evidence-list {
  list-style: none; margin-top: 12px;
}
.evidence-item {
  display: flex; align-items: center; gap: 8px;
  padding: 4px 0; font-size: 0.85rem; color: var(--fg-muted);
}
.evidence-tag {
  font-size: 0.7rem; padding: 1px 6px; border-radius: 3px;
  background: var(--accent-bg); color: var(--accent-fg); font-weight: 600;
}
.reasoning-section {
  margin-top: 12px;
  border: 1px solid var(--border-muted);
  border-radius: var(--radius);
  overflow: hidden;
}
.reasoning-toggle {
  width: 100%; padding: 8px 14px;
  border: none; background: var(--bg-muted);
  font-size: 0.82rem; cursor: pointer; text-align: left;
  color: var(--fg-muted);
}
.reasoning-toggle:hover { background: var(--bg-hover); }
.reasoning-content {
  padding: 12px 14px; font-size: 0.8rem;
  background: var(--bg-default); color: var(--fg-subtle);
  max-height: 300px; overflow-y: auto;
  white-space: pre-wrap; word-break: break-word;
  margin: 0;
}
</style>
