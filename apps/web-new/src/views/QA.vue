<template>
  <div class="view-pane">
    <div class="view-header"><h2>结构化问答</h2></div>
    <div class="qa-input-row">
      <input v-model="question" type="text" placeholder="输入问题…" @keydown.enter="ask" />
      <button class="btn btn-primary" @click="ask" :disabled="asking">{{ asking ? "思考中…" : "提问" }}</button>
    </div>
    <label class="checkbox-row">
      <input v-model="saveToWiki" type="checkbox" />
      保存到 wiki/queries
    </label>
    <p class="subtle" style="margin-top: 8px;">未配置 LLM_API_KEY 时将仅返回检索摘要。</p>
    <div v-if="answer" class="qa-answer doc-markdown" v-html="renderedAnswer"></div>
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
const answer = ref(null);
const evidences = ref([]);

// TODO: markdown-it rendering
const renderedAnswer = computed(() => renderMarkdown(answer.value));

async function ask() {
  if (!question.value.trim()) return;
  asking.value = true;
  try {
    const data = await api("/api/query", {
      method: "POST",
      body: { question: question.value, save_to_wiki: saveToWiki.value },
    });
    answer.value = data.answer || data.content || "";
    evidences.value = data.evidences || [];
  } catch (e) {
    const msg = e.message || "";
    if (msg.includes("401") || msg.includes("Authentication failed") || msg.includes("token")) {
      answer.value = "⚠️ **LLM 服务未配置**\n\n请在 `.env` 中设置有效的 `LLM_API_KEY`，或联系管理员配置后重试。";
    } else if (msg.includes("timeout") || msg.includes("timed out")) {
      answer.value = "⏱️ **请求超时**\n\nLLM 服务响应超时，请稍后重试。";
    } else {
      answer.value = `❌ **查询失败**: ${msg}`;
    }
    evidences.value = [];
  } finally {
    asking.value = false;
  }
}
</script>

<style scoped>
.qa-input-row {
  display: flex;
  gap: 8px;
  margin: 16px 0;
}
.qa-input-row input {
  flex: 1;
}
.checkbox-row {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.85rem;
  color: var(--fg-muted);
}
.qa-answer {
  border: 1px solid var(--border-default);
  border-radius: var(--radius);
  padding: 16px;
  margin-top: 16px;
  line-height: 1.7;
  font-size: 0.92rem;
}
.evidence-list {
  list-style: none;
  margin-top: 12px;
}
.evidence-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
  font-size: 0.85rem;
  color: var(--fg-muted);
}
.evidence-tag {
  font-size: 0.7rem;
  padding: 1px 6px;
  border-radius: 3px;
  background: var(--accent-bg);
  color: var(--accent-fg);
  font-weight: 600;
}
</style>
