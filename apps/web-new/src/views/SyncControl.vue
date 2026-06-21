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
      <button class="btn btn-danger" @click="showRebuildConfirm = true">全量重建</button>
      <button class="btn btn-ghost" @click="runLint">Wiki Lint</button>
    </div>
    <p v-if="statusText" class="status-msg" :class="{ error: statusError }">{{ statusText }}</p>

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

  <!-- 路径有效性警告 -->
  <div class="settings-section">
    <h3>📁 知识库状态 <span class="shared-tag">同步范围中各知识库的文件夹路径状态</span></h3>
    <div v-if="missingFiles.length" class="missing-list">
      <div class="missing-file-header">
        <span class="missing-source">库名</span>
        <span class="missing-owner">拥有者</span>
        <span class="missing-path">路径</span>
        <span class="missing-status">状态</span>
      </div>
      <div v-for="mf in pagedFiles" :key="mf.source_id" class="missing-file-row">
        <span class="missing-source">{{ mf.source_id }}</span>
        <span class="missing-owner">{{ mf.owner ? formatOwner(mf) : '管理员' }}</span>
        <span class="missing-path">{{ mf.path }}</span>
        <span class="missing-status"><span class="path-invalid-tag">⚠ 路径无效</span></span>
      </div>
      <div v-if="totalPages > 1" class="pagination-row">
        <button class="btn btn-ghost btn-xs" :disabled="page <= 1" @click="prevPage">‹ 上一页</button>
        <span class="page-info">{{ page }} / {{ totalPages }}</span>
        <button class="btn btn-ghost btn-xs" :disabled="page >= totalPages" @click="nextPage">下一页 ›</button>
      </div>
    </div>
    <p v-else class="subtle" style="padding:8px 0">✅ 所有库路径均有效</p>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import api from "../api/index.js";
import { useAuth } from "../composables/useAuth.js";

const { canWrite, isLoggedIn, userRole } = useAuth();

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
const missingFiles = ref([]);
const showRebuildConfirm = ref(false);

// 分页
const pageSize = 10;
const page = ref(1);

const totalPages = computed(() => Math.max(1, Math.ceil(missingFiles.value.length / pageSize)));

const pagedFiles = computed(() => {
  const start = (page.value - 1) * pageSize;
  return missingFiles.value.slice(start, start + pageSize);
});

function prevPage() { if (page.value > 1) page.value--; }
function nextPage() { if (page.value < totalPages.value) page.value++; }

function formatOwner(src) {
  if (!src.owner) return "";
  const dn = src.owner_display_name;
  if (!dn || dn === src.owner) return src.owner;
  return `${dn}(${src.owner})`;
}

async function loadMissingFiles() {
  try {
    const [me, data] = await Promise.all([
      api("/api/user/me"),
      api("/api/sources"),
    ]);
    const isAdmin = userRole.value === "admin";
    const currentUser = me.username || "";
    const items = [];
    for (const src of (data.sources || [])) {
      if (src.path && src.path_exists === false) {
        // 权限过滤：管理员全看，个人只看全局库+自己的库
        if (!isAdmin && src.owner && src.owner !== currentUser) continue;
        items.push({
          source_id: src.id,
          path: src.path,
          owner: src.owner,
          owner_display_name: src.owner_display_name,
        });
      }
    }
    // 排序：共享库（无 owner）排最前按名称序，有 owner 的按 用户名+库名 排序
    const ns = (x, y) => String(x || '').localeCompare(String(y || ''), undefined, { numeric: true, sensitivity: 'base' });
    items.sort((a, b) => {
      if (!a.owner && !b.owner) return ns(a.source_id, b.source_id);
      if (!a.owner) return -1;
      if (!b.owner) return 1;
      const byOwner = ns(a.owner, b.owner);
      if (byOwner !== 0) return byOwner;
      return ns(a.source_id, b.source_id);
    });
    missingFiles.value = items;
    page.value = 1;
  } catch {
    missingFiles.value = [];
  }
}

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
  statusText.value = "同步中…";
  statusError.value = false;
  // 增量同步后文档 ID 可能变化，清空搜索缓存
  localStorage.removeItem('mind_sync_last_search');
  try {
    await api("/api/sync", { method: "POST", body: { use_saved_defaults: true } });
    statusText.value = "同步完成";
    await loadStatus();
  } catch (e) {
    statusText.value = `同步失败: ${e.message}`;
    statusError.value = true;
  }
}

async function doRebuild() {
  showRebuildConfirm.value = false;
  statusText.value = "全量重建中…";
  statusError.value = false;
  // 全量重建后文档 ID 全部变化，清空搜索缓存
  localStorage.removeItem('mind_sync_last_search');
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
  loadMissingFiles();
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
.missing-file-header {
  display: flex;
  gap: 12px;
  padding: 6px 10px;
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--fg-muted);
  border-bottom: 2px solid var(--border-default);
  align-items: center;
}
.missing-status {
  min-width: 80px;
  text-align: center;
}
.missing-file-row {
  display: flex;
  gap: 12px;
  padding: 6px 10px;
  font-size: 0.85rem;
  border-bottom: 1px solid var(--border-muted);
  align-items: center;
}
.missing-source {
  font-weight: 500;
  min-width: 120px;
}
.missing-path {
  color: var(--fg-subtle);
  font-family: var(--font-mono);
  font-size: 0.8rem;
  flex: 1;
}
.missing-owner {
  font-size: 0.78rem;
  color: var(--fg-muted);
  min-width: 100px;
}
.pagination-row {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 10px 0;
}
.page-info {
  font-size: 0.82rem;
  color: var(--fg-subtle);
}
.shared-tag { font-size: 0.7rem; color: var(--fg-subtle); font-weight: 400; opacity: 0.7; margin-left: 6px; }
.status-msg { margin-top: 8px; font-size: 0.85rem; color: var(--fg-muted); }
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
