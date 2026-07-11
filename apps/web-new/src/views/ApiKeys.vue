<template>
  <div class="view-pane">
    <div class="view-header">
      <h2>🔑 API keys</h2>
    </div>

    <section class="settings-section api-key-section">
      <p class="subtle">管理已生成的 API key，删除后立即失效</p>

      <!-- Key 列表 -->
      <div v-if="apiKeys.length" class="api-key-table">
        <div class="api-key-header">
          <span class="col-label">名称</span>
          <span class="col-key">Key</span>
          <span class="col-date">创建日期</span>
          <span class="col-date">最新使用</span>
          <span class="col-actions">操作</span>
        </div>
        <div v-for="k in apiKeys" :key="k.id" class="api-key-row">
          <span class="col-label">
            <span class="label-text">{{ k.label || "default" }}</span>
          </span>
          <span class="col-key"><code>{{ k.key_value.slice(0, 16) }}…</code></span>
          <span class="col-date">{{ fmtTime(k.created_at) }}</span>
          <span class="col-date">{{ k.last_used_at ? fmtTime(k.last_used_at) : "—" }}</span>
          <span class="col-actions">
            <button class="btn-icon" title="修改名称" @click="openEditModal(k)">✏️</button>
            <button class="btn-icon btn-icon-danger" title="删除" @click="deleteKey(k.id)" :disabled="deleting === k.id">🗑️</button>
          </span>
        </div>
      </div>

      <div class="api-key-actions">
        <button class="btn btn-primary btn-sm" @click="rotateKey" :disabled="keyRotating">
          {{ keyRotating ? "创建中…" : "创建 API key" }}
        </button>
      </div>
    </section>

    <!-- 新 Key 弹窗 -->
    <div v-if="newApiKey" class="modal-overlay" @click.self="closeNewKeyModal">
      <div class="confirm-dialog">
        <h4 style="margin:0 0 4px">🎉 新 API key 已生成</h4>
        <p class="subtle" style="margin:0 0 12px">请立即复制，关闭后无法再次查看完整 key</p>
        <code class="api-key-display">{{ newApiKey }}</code>
        <div class="btn-row" style="justify-content:flex-end;margin-top:16px;gap:8px">
          <button class="btn btn-primary btn-sm" @click="copyKeyAndClose">{{ keyCopied ? '✅ 已复制' : '复制' }}</button>
          <button class="btn btn-ghost btn-sm" @click="closeNewKeyModal">关闭</button>
        </div>
      </div>
    </div>

    <!-- 编辑名称弹窗 -->
    <div v-if="editTarget" class="modal-overlay" @click.self="cancelEditLabel">
      <div class="confirm-dialog">
        <h4 style="margin:0 0 12px">修改 API key</h4>
        <input v-model="editLabelInput" type="text" class="label-input" maxlength="50" placeholder="输入名称" style="width:100%;padding:8px 10px" />
        <div class="btn-row" style="justify-content:flex-end;margin-top:16px;gap:8px">
          <button class="btn btn-ghost btn-sm" @click="cancelEditLabel">取消</button>
          <button class="btn btn-primary btn-sm" @click="saveLabel" :disabled="labelSaving">
            {{ labelSaving ? "保存中…" : "保存" }}
          </button>
        </div>
      </div>
    </div>

    <!-- 确认弹窗 -->
    <div v-if="confirmTarget" class="modal-overlay" @click.self="confirmTarget = null">
      <div class="confirm-dialog">
        <h4 style="margin:0 0 12px">删除 API key</h4>
        <p>{{ confirmTarget.label }}</p>
        <div class="btn-row" style="justify-content:flex-end;margin-top:12px">
          <button class="btn btn-ghost" @click="confirmTarget = null">取消</button>
          <button class="btn btn-danger btn-sm" @click="doDeleteKey" :disabled="deleting === confirmTarget.id">
            {{ deleting === confirmTarget.id ? '删除中…' : '确认删除' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import api from "../api/index.js";
import { toast } from "../composables/toast.js";

// API Key
const newApiKey = ref("");
const keyRotating = ref(false);
const apiKeys = ref([]);
const deleting = ref(null);
const editTarget = ref(null);
const editLabelInput = ref("");
const labelSaving = ref(false);
const keyCopied = ref(false);

async function loadApiKeys() {
  try {
    const data = await api("/api/api-keys");
    apiKeys.value = data.keys || [];
  } catch {
    apiKeys.value = [];
  }
}

async function rotateKey() {
  keyRotating.value = true;
  try {
    const data = await api("/api/api-keys/rotate", {
      method: "POST",
      body: { label: "Web UI" },
    });
    newApiKey.value = data.key;
    await loadApiKeys();
    toast.success("API key 已创建");
  } catch (e) {
    toast.error(e.message || "生成失败");
  } finally {
    keyRotating.value = false;
  }
}

function closeNewKeyModal() {
  newApiKey.value = "";
  keyCopied.value = false;
}

async function copyKeyAndClose() {
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(newApiKey.value);
    } else {
      // fallback for HTTP
      const ta = document.createElement("textarea");
      ta.value = newApiKey.value;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
    }
    keyCopied.value = true;
  } catch {
    toast.warning("复制失败，请手动选择复制");
  }
}

function openEditModal(k) {
  editTarget.value = k;
  editLabelInput.value = k.label || "";
}

function cancelEditLabel() {
  editTarget.value = null;
  editLabelInput.value = "";
}

async function saveLabel() {
  if (!editTarget.value) return;
  labelSaving.value = true;
  try {
    await api(`/api/api-keys/${editTarget.value.id}`, {
      method: "PUT",
      body: { label: editLabelInput.value },
    });
    editTarget.value = null;
    await loadApiKeys();
    toast.success("名称已更新");
  } catch (e) {
    toast.error(e.message || "更新失败");
  } finally {
    labelSaving.value = false;
  }
}

async function deleteKey(id) {
  confirmTarget.value = { id, label: "确定删除此 API key？该 key 将立即失效。" };
}

async function doDeleteKey() {
  if (!confirmTarget.value) return;
  const id = confirmTarget.value.id;
  confirmTarget.value = null;
  deleting.value = id;
  try {
    await api(`/api/api-keys/${id}`, { method: "DELETE" });
    apiKeys.value = apiKeys.value.filter((k) => k.id !== id);
    toast.success("API key 已删除");
  } catch (e) {
    toast.error(e.message || "删除失败");
  } finally {
    deleting.value = null;
  }
}

// Confirm state
const confirmTarget = ref(null);

// Helpers
function fmtTime(ts) {
  const n = Number(ts);
  if (!Number.isFinite(n) || n <= 0) return "--";
  return new Date(n * 1000).toLocaleString();
}

function onGlobalKeydown(e) {
  if (e.key === "Escape") {
    confirmTarget.value = null;
    if (!newApiKey.value) { closeNewKeyModal(); }
    if (editTarget.value) { cancelEditLabel(); }
  }
}

onMounted(() => {
  document.addEventListener("keydown", onGlobalKeydown);
  loadApiKeys();
});
</script>

<style scoped>
.view-pane {
  max-width: 860px;
}
.settings-section {
  margin-top: 8px;
}
.subtle {
  color: var(--fg-subtle);
  font-size: 0.85rem;
  margin: 0 0 12px;
}
.api-key-table {
  border: 1px solid var(--border-default);
  border-radius: var(--radius);
  overflow: hidden;
  margin-bottom: 10px;
}
.api-key-header {
  display: flex;
  align-items: center;
  background: var(--bg-muted);
  padding: 8px 12px;
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--fg-muted);
  border-bottom: 1px solid var(--border-default);
}
.api-key-row {
  display: flex;
  align-items: center;
  padding: 8px 12px;
  border-bottom: 1px solid var(--border-muted);
  font-size: 0.82rem;
}
.api-key-row:last-child {
  border-bottom: none;
}
.col-label {
  width: 140px;
  flex-shrink: 0;
}
.col-key {
  width: 160px;
  flex-shrink: 0;
  font-family: var(--font-mono);
  font-size: 0.78rem;
  color: var(--fg-muted);
}
.col-key code {
  background: var(--bg-muted);
  padding: 2px 5px;
  border-radius: 3px;
}
.col-date {
  flex: 1;
  font-size: 0.78rem;
  color: var(--fg-subtle);
}
.col-actions {
  flex-shrink: 0;
  display: flex;
  gap: 2px;
  justify-content: flex-end;
}
.btn-icon {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 0.9rem;
  padding: 2px 4px;
  border-radius: 3px;
  line-height: 1;
  color: var(--fg-muted);
}
.btn-icon:hover {
  background: var(--bg-muted);
  color: var(--fg-default);
}
.btn-icon-danger:hover {
  color: var(--danger-fg);
}
.btn-icon:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.label-text {
  cursor: default;
  font-size: 0.82rem;
}
.api-key-actions {
  margin-top: 8px;
}
.api-key-display {
  display: block;
  font-family: var(--font-mono);
  font-size: 0.82rem;
  word-break: break-all;
  padding: 10px 12px;
  background: var(--bg-muted);
  border-radius: var(--radius);
  border: 1px solid var(--border-muted);
  margin-bottom: 4px;
}
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}
.confirm-dialog {
  background: var(--bg-card);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  padding: 24px;
  max-width: 420px;
  box-shadow: var(--shadow-lg);
}
</style>
