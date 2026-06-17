<template>
  <div class="view-pane">
    <div class="view-header" style="display:flex;align-items:center">
      <h2>📊 系统概览</h2>
      <div style="margin-left:auto">
        <button class="btn btn-ghost btn-sm refresh-btn" @click="refresh" :disabled="refreshing" :class="{ spinning: refreshing }" title="刷新统计数据">
          <span class="refresh-icon">↻</span>
        </button>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-value">{{ stats.source_count ?? '-' }}</div>
        <div class="stat-label">来源总数</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ stats.document_count ?? '-' }}</div>
        <div class="stat-label">文档总数</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ stats.user_count ?? '-' }}</div>
        <div class="stat-label">用户数</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ formatBytes(stats.db_size) }}</div>
        <div class="stat-label">数据库大小</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ stats.wiki_page_count ?? '-' }}</div>
        <div class="stat-label">Wiki 页面</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ formatBytes(stats.source_size) }}</div>
        <div class="stat-label">源文件占用</div>
      </div>
    </div>

    <!-- 快捷操作 -->
    <section class="settings-section">
      <h3>快捷操作</h3>
      <div class="action-row">
        <button class="btn btn-primary" @click="reindex" :disabled="reindexing">
          {{ reindexing ? '重索引中…' : '🔄 重新索引所有来源' }}
        </button>
        <span v-if="reindexMsg" class="status-msg" :class="{ error: reindexError }">{{ reindexMsg }}</span>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import api from "../api/index.js";

const stats = ref({});
const reindexing = ref(false);
const refreshing = ref(false);
const reindexMsg = ref("");
const reindexError = ref(false);

async function loadStats() {
  try {
    const data = await api("/api/admin/stats");
    stats.value = data;
  } catch {
    stats.value = {};
  }
}

async function reindex() {
  reindexing.value = true;
  reindexMsg.value = "正在重新索引…";
  reindexError.value = false;
  try {
    const data = await api("/api/admin/reindex", { method: "POST" });
    reindexMsg.value = `索引完成：${data.results?.length || 0} 个来源`;
    await loadStats();
  } catch (e) {
    reindexMsg.value = e.message || "重索引失败";
    reindexError.value = true;
  } finally {
    reindexing.value = false;
  }
}

async function refresh() {
  refreshing.value = true;
  await loadStats();
  setTimeout(() => { refreshing.value = false; }, 400);
}

function formatBytes(bytes) {
  if (!bytes && bytes !== 0) return "-";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

onMounted(loadStats);
</script>

<style scoped>
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 12px;
  margin: 16px 0;
}
.stat-card {
  border: 1px solid var(--border-default);
  border-radius: var(--radius);
  padding: 16px;
  text-align: center;
  background: var(--bg-card);
}
.stat-value {
  font-size: 1.6rem;
  font-weight: 700;
  color: var(--fg-default);
}
.stat-label {
  font-size: 0.78rem;
  color: var(--fg-muted);
  margin-top: 4px;
}
.settings-section {
  margin-top: 24px;
}
.settings-section h3 {
  font-size: 1rem;
  font-weight: 600;
  margin-bottom: 8px;
}
.action-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.refresh-btn { font-size: 1.1rem; padding: 4px 10px; }
.refresh-icon { display: inline-block; }
.refresh-btn.spinning .refresh-icon { animation: spin 0.6s linear; }
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
.status-msg { font-size: 0.85rem; color: var(--fg-muted); }
.status-msg.error { color: var(--danger-fg); }
</style>
