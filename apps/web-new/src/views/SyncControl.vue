<template>
  <div class="view-pane">
    <div class="view-header">
      <h2>📊 同步控制</h2>
    </div>
    <div class="sync-status-card">
      <div class="sync-status-row">
        <span class="sync-label">当前任务</span>
        <span class="sync-value" :class="{ 'sync-active': running }">{{ running ? `${currentSource} (${processed}/${total})` : '空闲' }}</span>
      </div>
      <div class="sync-status-row">
        <span class="sync-label">上次同步</span>
        <span class="sync-value">{{ lastSyncText }}</span>
      </div>
    </div>
    <div class="sync-actions">
      <button class="btn btn-primary" @click="startSync" :disabled="running">增量同步</button>
      <button class="btn btn-danger" @click="confirmRebuild">全量重建</button>
      <button class="btn btn-ghost" @click="runLint">Wiki Lint</button>
    </div>
    <p v-if="statusText" class="status-msg" :class="{ error: statusError }">{{ statusText }}</p>

    <!-- 自动同步设置 -->
    <div class="settings-section">
      <h3>定时同步</h3>
      <label class="checkbox-row">
        <input v-model="autoSyncEnabled" type="checkbox" @change="saveAutoSync" />
        启用自动同步
      </label>
      <div class="field-row">
        <label>间隔（分钟）</label>
        <input v-model.number="autoSyncInterval" type="number" min="10" class="input-sm" @change="saveAutoSync" />
      </div>
      <p class="subtle">下次自动同步：{{ nextSyncAt || '--' }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import api from "../api/index.js";
import { useAuth } from "../composables/useAuth.js";

const { canWrite } = useAuth();

const running = ref(false);
const currentSource = ref("");
const processed = ref(0);
const total = ref(0);
const lastSyncText = ref("尚未执行");
const statusText = ref("");
const statusError = ref(false);
const autoSyncEnabled = ref(false);
const autoSyncInterval = ref(60);
const nextSyncAt = ref("");

async function loadStatus() {
  try {
    const st = await api("/api/sync-status");
    running.value = st.running || false;
    currentSource.value = st.current_source || "";
    processed.value = st.processed_files || 0;
    total.value = st.total_files || 0;
    const last = st.last_completed || {};
    if (last.finished_at) {
      lastSyncText.value = `${last.status === "failed" ? "失败" : "成功"} @ ${new Date(last.finished_at * 1000).toLocaleString()}`;
    }
  } catch {
    // ignore
  }
}

async function loadSettings() {
  try {
    const st = await api("/api/settings");
    autoSyncEnabled.value = !!st.auto_sync_enabled;
    autoSyncInterval.value = st.auto_sync_interval_minutes || 60;
    nextSyncAt.value = st.next_auto_sync_at ? new Date(st.next_auto_sync_at * 1000).toLocaleString() : "--";
  } catch {
    // ignore
  }
}

async function startSync() {
  if (!canWrite.value) return;
  statusText.value = "同步中…";
  statusError.value = false;
  try {
    await api("/api/sync", { method: "POST", body: { use_saved_defaults: true } });
    statusText.value = "同步完成";
    await loadStatus();
  } catch (e) {
    statusText.value = `同步失败: ${e.message}`;
    statusError.value = true;
  }
}

async function confirmRebuild() {
  if (!canWrite.value || !confirm("全量重建将清空索引并强制重扫所有文件，确定？")) return;
  statusText.value = "全量重建中…";
  statusError.value = false;
  try {
    await api("/api/rebuild-index", { method: "POST", body: { use_saved_defaults: true } });
    statusText.value = "全量重建完成";
    await loadStatus();
  } catch (e) {
    statusText.value = `全量重建失败: ${e.message}`;
    statusError.value = true;
  }
}

async function runLint() {
  if (!canWrite.value) return;
  statusText.value = "Lint 运行中…";
  statusError.value = false;
  try {
    const data = await api("/api/lint", { method: "POST", body: { stale_days: 180 } });
    const issues = data.issues || [];
    statusText.value = `Lint 完成：${issues.length} 个问题`;
  } catch (e) {
    statusText.value = `Lint 失败: ${e.message}`;
    statusError.value = true;
  }
}

async function saveAutoSync() {
  try {
    await api("/api/settings", {
      method: "POST",
      body: { auto_sync_enabled: autoSyncEnabled.value, auto_sync_interval_minutes: autoSyncInterval.value },
    });
  } catch {
    // ignore
  }
}

onMounted(() => {
  loadStatus();
  loadSettings();
});
</script>

<style scoped>
.sync-status-card {
  border: 1px solid var(--border-default);
  border-radius: var(--radius);
  padding: 16px;
  margin: 16px 0;
}
.sync-status-row {
  display: flex;
  justify-content: space-between;
  padding: 4px 0;
  font-size: 0.9rem;
}
.sync-label { color: var(--fg-muted); }
.sync-value { font-weight: 500; }
.sync-active { color: var(--accent-fg); }
.sync-actions { display: flex; gap: 8px; margin: 16px 0; }
.settings-section {
  border-top: 1px solid var(--border-muted);
  padding-top: 16px;
  margin-top: 16px;
}
.settings-section h3 { font-size: 1rem; margin-bottom: 8px; }
.field-row { display: flex; align-items: center; gap: 8px; margin-top: 8px; }
.input-sm { width: 80px; }
.status-msg { margin-top: 8px; font-size: 0.85rem; color: var(--fg-muted); }
.status-msg.error { color: var(--danger-fg); }
</style>
