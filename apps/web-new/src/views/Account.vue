<template>
  <div class="view-pane">
    <div class="view-header">
      <h2>👤 账户</h2>
    </div>

    <!-- 密码修改 -->
    <section class="settings-section">
      <h3>修改密码</h3>
      <form @submit.prevent="changePassword" class="password-form">
        <div class="field">
          <input v-model="pwCurrent" type="password" placeholder="当前密码" />
        </div>
        <div class="field">
          <input v-model="pwNew" type="password" placeholder="新密码" />
        </div>
        <div class="field">
          <input v-model="pwConfirm" type="password" placeholder="确认新密码" />
        </div>
        <button type="submit" class="btn btn-primary" :disabled="pwSaving">
          {{ pwSaving ? "修改中…" : "修改密码" }}
        </button>
        <p v-if="pwMsg" class="status-msg" :class="{ error: pwError }">{{ pwMsg }}</p>
      </form>
    </section>

    <!-- 活跃会话 -->
    <section class="settings-section">
      <h3>活跃会话</h3>
      <p class="subtle">当前设备标注为"当前会话"，可远程踢下线其他设备</p>
      <div class="session-list">
        <div v-for="s in sessions" :key="s.session_id" class="session-card" :class="{ current: s.current }">
          <div class="session-head">
            <span class="session-badge" :class="{ current: s.current }">
              {{ s.current ? "当前会话" : "其他设备" }}
            </span>
            <span v-if="s.remember_me" class="session-tag">记住我</span>
          </div>
          <div class="session-meta">
            <span>IP: {{ s.ip || "--" }}</span>
            <span>· {{ s.user_agent ? truncateUA(s.user_agent) : "--" }}</span>
          </div>
          <div class="session-meta">
            <span>登录于 {{ fmtTime(s.created_at) }}</span>
            <span>· 最后活跃 {{ fmtTime(s.last_active_at) }}</span>
            <span>· 过期 {{ fmtTime(s.expires_at) }}</span>
          </div>
          <button
            v-if="!s.current"
            class="btn btn-danger btn-sm"
            @click="revokeSession(s.session_id)"
            :disabled="revoking === s.session_id"
          >
            {{ revoking === s.session_id ? "踢下线中…" : "踢下线" }}
          </button>
        </div>
        <p v-if="!sessions.length" class="subtle">暂无会话</p>
      </div>
    </section>

    <!-- API Key 管理 -->
    <section class="settings-section">
      <h3>API Key</h3>
      <p class="subtle">管理已生成的 API Key，删除后立即失效</p>

      <!-- 已有 Key 列表 -->
      <div v-if="apiKeys.length" class="api-key-list">
        <div v-for="k in apiKeys" :key="k.id" class="api-key-card">
          <div class="api-key-row">
            <code class="api-key-value">{{ k.key_value.slice(0, 16) }}…</code>
            <span class="api-key-label">{{ k.label || "default" }}</span>
            <span class="api-key-time" :title="'创建于 ' + fmtTime(k.created_at)">
              创建于 {{ fmtTime(k.created_at) }}
            </span>
            <button class="btn btn-danger btn-sm" @click="deleteKey(k.id)" :disabled="deleting === k.id">
              {{ deleting === k.id ? "删除中…" : "删除" }}
            </button>
          </div>
        </div>
      </div>

      <div v-if="newApiKey" class="new-api-key">
        <strong>新 API Key：</strong>
        <code class="api-key-display">{{ newApiKey }}</code>
        <button class="btn btn-sm btn-ghost" @click="copyKey">复制</button>
      </div>
      <div class="api-key-actions">
        <button class="btn btn-primary btn-sm" @click="rotateKey" :disabled="keyRotating">
          {{ keyRotating ? "生成中…" : "生成新 API Key" }}
        </button>
      </div>
      <p v-if="keyMsg" class="status-msg">{{ keyMsg }}</p>
    </section>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import api from "../api/index.js";

// Password change
const pwCurrent = ref("");
const pwNew = ref("");
const pwConfirm = ref("");
const pwSaving = ref(false);
const pwMsg = ref("");
const pwError = ref(false);

async function changePassword() {
  pwMsg.value = "";
  pwError.value = false;
  if (!pwCurrent.value || !pwNew.value) {
    pwMsg.value = "请填写当前密码和新密码";
    pwError.value = true;
    return;
  }
  if (pwNew.value !== pwConfirm.value) {
    pwMsg.value = "两次密码不一致";
    pwError.value = true;
    return;
  }
  if (pwNew.value.length < 6) {
    pwMsg.value = "新密码至少 6 位";
    pwError.value = true;
    return;
  }
  pwSaving.value = true;
  try {
    await api("/api/change-password", {
      method: "POST",
      body: { current_password: pwCurrent.value, new_password: pwNew.value },
    });
    pwMsg.value = "密码已修改";
    pwCurrent.value = "";
    pwNew.value = "";
    pwConfirm.value = "";
  } catch (e) {
    pwMsg.value = e.message || "修改失败";
    pwError.value = true;
  } finally {
    pwSaving.value = false;
  }
}

// Sessions
const sessions = ref([]);
const revoking = ref("");

async function loadSessions() {
  try {
    const data = await api("/api/sessions");
    sessions.value = data.sessions || [];
  } catch {
    sessions.value = [];
  }
}

async function revokeSession(sid) {
  revoking.value = sid;
  try {
    await api(`/api/sessions/${encodeURIComponent(sid)}`, { method: "DELETE" });
    sessions.value = sessions.value.filter((s) => s.session_id !== sid);
  } catch (e) {
    alert(e.message);
  } finally {
    revoking.value = "";
  }
}

// API Key
const newApiKey = ref("");
const keyRotating = ref(false);
const keyMsg = ref("");
const apiKeys = ref([]);
const deleting = ref(null);

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
  keyMsg.value = "";
  try {
    const data = await api("/api/api-keys/rotate", {
      method: "POST",
      body: { label: "Web UI" },
    });
    newApiKey.value = data.key;
    keyMsg.value = "新 Key 已生成，请立即复制";
  } catch (e) {
    keyMsg.value = e.message || "生成失败";
  } finally {
    keyRotating.value = false;
  }
}

async function deleteKey(id) {
  if (!confirm("确定删除此 API Key？该 Key 将立即失效。")) return;
  deleting.value = id;
  keyMsg.value = "";
  try {
    await api(`/api/api-keys/${id}`, { method: "DELETE" });
    apiKeys.value = apiKeys.value.filter((k) => k.id !== id);
    keyMsg.value = "已删除";
  } catch (e) {
    keyMsg.value = e.message || "删除失败";
  } finally {
    deleting.value = null;
  }
}

function copyKey() {
  navigator.clipboard.writeText(newApiKey.value).then(() => {
    keyMsg.value = "已复制到剪贴板";
  }).catch(() => {
    keyMsg.value = "复制失败，请手动复制";
  });
}

// Helpers
function truncateUA(ua) {
  if (ua.length > 60) return ua.slice(0, 60) + "…";
  return ua;
}

function fmtTime(ts) {
  const n = Number(ts);
  if (!Number.isFinite(n) || n <= 0) return "--";
  return new Date(n * 1000).toLocaleString();
}

onMounted(() => {
  loadSessions();
  loadApiKeys();
});
</script>

<style scoped>
.settings-section {
  margin-top: 24px;
  max-width: 600px;
}
.settings-section h3 {
  font-size: 1rem;
  font-weight: 600;
  margin-bottom: 8px;
}
.field { margin-bottom: 10px; }
.field input { width: 100%; padding: 8px 10px; }

.password-form {
  max-width: 360px;
}

.status-msg {
  margin-top: 8px;
  font-size: 0.85rem;
  color: var(--fg-muted);
}
.status-msg.error { color: var(--danger-fg); }

.session-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 8px;
}
.session-card {
  border: 1px solid var(--border-default);
  border-radius: var(--radius);
  padding: 10px 14px;
  font-size: 0.85rem;
}
.session-card.current {
  border-color: var(--accent-emphasis);
  background: var(--accent-bg);
}
.session-head {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 4px;
}
.session-badge {
  font-size: 0.75rem;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: 3px;
  background: var(--bg-muted);
  color: var(--fg-muted);
}
.session-badge.current {
  background: var(--accent-emphasis);
  color: #fff;
}
.session-tag {
  font-size: 0.7rem;
  padding: 1px 5px;
  border-radius: 3px;
  background: var(--warning-bg);
  color: var(--warning-fg);
}
.session-meta {
  font-size: 0.8rem;
  color: var(--fg-subtle);
  margin-top: 2px;
}
.new-api-key {
  margin: 10px 0;
  padding: 10px 12px;
  background: var(--bg-muted);
  border-radius: var(--radius);
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.api-key-display {
  font-family: var(--font-mono);
  font-size: 0.82rem;
  word-break: break-all;
  flex: 1;
}

.api-key-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 10px;
}
.api-key-card {
  border: 1px solid var(--border-muted);
  border-radius: var(--radius);
  padding: 8px 12px;
}
.api-key-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.api-key-value {
  font-family: var(--font-mono);
  font-size: 0.8rem;
  color: var(--fg-muted);
  background: var(--bg-muted);
  padding: 2px 6px;
  border-radius: 3px;
}
.api-key-label {
  font-size: 0.8rem;
  color: var(--fg-subtle);
}
.api-key-time {
  font-size: 0.75rem;
  color: var(--fg-subtle);
  flex: 1;
}
.api-key-actions {
  margin-top: 8px;
}
</style>
