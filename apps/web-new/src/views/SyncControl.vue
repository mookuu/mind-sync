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
      <button class="btn btn-danger" @click="showRebuildConfirm = true" :disabled="running">全量重建</button>
      <button class="btn btn-ghost" @click="runLint" :disabled="running || !canWrite">Wiki Lint</button>
    </div>
    <p v-if="statusText && statusError" class="status-msg error">{{ statusText }}</p>

    <!-- 全量重建确认弹窗 -->
    <div v-if="showRebuildConfirm" class="modal-overlay" @click.self="showRebuildConfirm = false">
      <div class="confirm-dialog">
        <p>确认执行<strong>全量重建</strong>？</p>
        <p class="subtle">将清空全部索引并强制重扫所有文件，期间搜索功能可能暂时不可用。</p>
        <div class="btn-row" style="justify-content:flex-end;margin-top:12px">
          <button class="btn btn-ghost" @click="showRebuildConfirm = false">取消</button>
          <button class="btn btn-danger btn-sm" @click="doRebuild" :disabled="running">确认重建</button>
        </div>
      </div>
    </div>

    <!-- 自动同步设置 -->
    <div class="settings-section">
      <h3>定时同步</h3>
      <label class="checkbox-row">
        <input v-model="autoSyncEnabled" type="checkbox" :disabled="running" @change="saveAutoSync" />
        启用自动同步
      </label>
      <div class="field-row">
        <label>间隔（分钟）</label>
        <input v-model.number="autoSyncInterval" :disabled="running" type="number" min="10" class="input-sm" @change="saveAutoSync" />
      </div>
      <p class="subtle">下次自动同步：{{ nextSyncAt || '--' }}</p>
    </div>
  </div>

</template>

<script setup>
import { ref, onMounted, onActivated, onUnmounted } from "vue";
import api from "../api/index.js";
import { toast } from "../composables/toast.js";
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
const showRebuildConfirm = ref(false);
let pollTimer = null;

async function loadStatus() {
  try {
    const st = await api("/api/sync-status");
    const wasRunning = running.value;
    running.value = st.running || false;
    currentSource.value = st.current_source || "";
    processed.value = st.processed_files || 0;
    total.value = st.total_files || 0;
    const last = st.last_completed || {};
    if (last.finished_at) {
      lastSyncText.value = `${last.status === "failed" ? "失败" : "成功"} @ ${new Date(last.finished_at * 1000).toLocaleString()}`;
    }
    // 同步完成后停止轮询
    if (wasRunning && !running.value) {
      stopPolling();
      toast.success(last.mode === "rebuild" ? "全量重建完成" : "同步完成");
      window.dispatchEvent(new CustomEvent('mind-sync-tree-refresh'));
      window.dispatchEvent(new CustomEvent('mind-sync-done'));
    }
  } catch {
    // ignore
  }
}

function startPolling() {
  if (!pollTimer) pollTimer = setInterval(loadStatus, 2000);
}
function stopPolling() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
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
  statusText.value = "";
  statusError.value = false;
  localStorage.removeItem('mind_sync_last_search');
  running.value = true;
  startPolling();
  try {
    await api("/api/sync", { method: "POST", body: { use_saved_defaults: true } });
  } catch (e) {
    running.value = false;
    stopPolling();
    toast.error("同步失败：" + (e.message || "未知错误"));
  }
}

async function doRebuild() {
  showRebuildConfirm.value = false;
  statusText.value = "";
  statusError.value = false;
  localStorage.removeItem('mind_sync_last_search');
  running.value = true;
  startPolling();
  try {
    await api("/api/rebuild-index", { method: "POST", body: { use_saved_defaults: true } });
  } catch (e) {
    running.value = false;
    stopPolling();
    toast.error("全量重建失败：" + (e.message || "未知错误"));
  }
}

async function runLint() {
  if (!canWrite.value) return;
  statusText.value = "";
  statusError.value = false;
  try {
    const data = await api("/api/lint", { method: "POST", body: { stale_days: 180 } });
    const issues = data.issues || [];
    toast.info(`Lint 完成：${issues.length} 个问题`);
  } catch (e) {
    toast.error("Lint 失败：" + (e.message || "未知错误"));
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

onMounted(async () => {
  await loadStatus();
  if (running.value) startPolling();
  loadSettings();
});

onActivated(async () => {
  await loadStatus();
  if (running.value) startPolling();
});

onUnmounted(() => stopPolling());
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
.status-msg.error { color: var(--danger-fg); }

/* 确认弹窗 */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
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
