<template>
  <div class="view-pane">
    <div v-if="!canWrite" class="view-header">
      <p class="subtle">仅管理员可访问此页面</p>
    </div>
    <template v-else>
    <div class="view-header">
      <h2>📋 规则约束</h2>
      <p class="subtle">问答时注入 LLM 的上下文约束，失焦自动保存</p>
    </div>
    <div class="purpose-editor-wrap">
      <textarea
        v-model="content"
        class="purpose-editor"
        rows="16"
        placeholder="定义规则约束与优先关注主题…"
        :readonly="!canWrite"
        @blur="onBlur"
      ></textarea>
      <p v-if="saveMsg" class="status-msg" :class="{ error: saveError }">{{ saveMsg }}</p>
    </div>
  </template>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import api from "../api/index.js";
import { useAuth } from "../composables/useAuth.js";

const { canWrite } = useAuth();
const content = ref("");
const savedContent = ref("");  // last known saved state
const saveMsg = ref("");
const saveError = ref(false);
let saveTimer = null;

async function load() {
  try {
    const data = await api("/api/purpose");
    content.value = data.content || data.preview || "";
    savedContent.value = content.value;
  } catch {
    content.value = "";
  }
}

async function save() {
  if (!canWrite.value || content.value === savedContent.value) return;
  try {
    await api("/api/purpose", { method: "POST", body: { content: content.value } });
    savedContent.value = content.value;
    saveMsg.value = "已保存";
    saveError.value = false;
    clearTimeout(saveTimer);
    saveTimer = setTimeout(() => { saveMsg.value = ""; }, 2000);
  } catch (e) {
    saveMsg.value = `保存失败: ${e.message}`;
    saveError.value = true;
  }
}

function onBlur() {
  if (content.value !== savedContent.value) {
    saveMsg.value = "自动保存中…";
    save();
  }
}

onMounted(load);
</script>

<style scoped>
.purpose-editor-wrap {
  max-width: 800px;
  margin-top: 16px;
}
.purpose-editor {
  width: 100%;
  min-height: 320px;
  font-family: var(--font-mono);
  font-size: 0.85rem;
  line-height: 1.6;
  padding: 14px;
  border: 1px solid var(--border-default);
  border-radius: var(--radius);
  resize: vertical;
}
.status-msg { margin-top: 8px; font-size: 0.85rem; color: var(--fg-muted); }
.status-msg.error { color: var(--danger-fg); }
</style>
