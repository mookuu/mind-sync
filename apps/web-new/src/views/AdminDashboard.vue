<template>
  <div class="view-pane">
    <div class="view-header" style="display:flex;align-items:center">
      <h2>📊 系统概览</h2>
      <div style="margin-left:auto">
        <button class="btn btn-ghost btn-sm" @click="refresh" :disabled="refreshing" title="刷新">↻</button>
      </div>
    </div>

    <!-- 全局统计 -->
    <div class="stats-grid">
      <div class="stat-card"><div class="stat-value">{{ stats.doc_count ?? '-' }}</div><div class="stat-label">文档总数</div></div>
      <div class="stat-card"><div class="stat-value">{{ stats.src_count ?? '-' }}</div><div class="stat-label">库总数</div></div>
      <div class="stat-card"><div class="stat-value">{{ stats.user_count ?? '-' }}</div><div class="stat-label">用户数</div></div>
      <div class="stat-card"><div class="stat-value">{{ stats.wiki_pages ?? '-' }}</div><div class="stat-label">Wiki 页面</div></div>
      <div class="stat-card"><div class="stat-value">{{ formatBytes(stats.db_size) }}</div><div class="stat-label">数据库</div></div>
    </div>

    <!-- 用户统计表 -->
    <section class="settings-section" v-if="stats.users && stats.users.length">
      <h3>用户数据</h3>
      <table class="user-stats-table">
        <thead>
          <tr><th>用户</th><th>角色</th><th>库数</th><th>文档数</th><th>专属目录</th><th>状态</th></tr>
        </thead>
        <tbody>
          <tr v-for="u in stats.users" :key="u.username">
            <td>{{ fmtUser(u) }}</td>
            <td>{{ u.role === 'admin' ? '管理员' : '成员' }}</td>
            <td>{{ u.source_count }}<span v-if="u.role === 'admin'" class="subtle-tag">全员共享</span></td>
            <td>{{ u.doc_count ?? '-' }}</td>
            <td>{{ u.has_dir ? '✅' : '❌' }}</td>
            <td><span :class="statusClass(u.status)">{{ statusLabel(u.status) }}</span></td>
          </tr>
        </tbody>
      </table>
    </section>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import api from "../api/index.js";

const stats = ref({});
const refreshing = ref(false);

async function loadStats() {
  try {
    const [s, users] = await Promise.all([
      api("/api/admin/stats"),
      api("/api/admin/users"),
    ]);
    // 合并文档统计：管理员看全部，成员看自己源的文档
    const docMap = s.user_doc_counts || {};
    const totalDocs = s.doc_count || 0;
    const merged = (users.users || []).map(u => ({
      ...u,
      doc_count: u.role === 'admin' ? totalDocs : (docMap[u.username] || 0),
    }));
    // 按角色+用户名排序
    merged.sort((a, b) => {
      if (a.role !== b.role) return a.role === 'admin' ? -1 : 1;
      return (a.username || '').localeCompare(b.username || '', undefined, { numeric: true });
    });
    stats.value = { ...s, users: merged };
  } catch {
    stats.value = {};
  }
}

async function refresh() {
  refreshing.value = true;
  await loadStats();
  refreshing.value = false;
}

function formatBytes(bytes) {
  if (!bytes && bytes !== 0) return "-";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function statusLabel(s) { return { normal: '✅ 正常', locked: '🔒 锁定', deleted: '💤 已注销' }[s] || s; }
function statusClass(s) { return { normal: 'tag-normal', locked: 'tag-locked', deleted: 'tag-deleted' }[s] || ''; }
function fmtUser(u) {
  const dn = u.display_name || u.username;
  if (!u.display_name || u.display_name === u.username) return u.username;
  return `${dn}(${u.username})`;
}

onMounted(loadStats);
</script>

<style scoped>
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 10px;
  margin: 16px 0;
}
.stat-card {
  border: 1px solid var(--border-default);
  border-radius: var(--radius);
  padding: 14px;
  text-align: center;
}
.stat-value { font-size: 1.4rem; font-weight: 700; }
.stat-label { font-size: 0.75rem; color: var(--fg-muted); margin-top: 2px; }
.settings-section { margin-top: 20px; }
.settings-section h3 { font-size: 1rem; font-weight: 600; margin-bottom: 8px; }
.user-stats-table { width: 100%; border-collapse: collapse; }
.user-stats-table th, .user-stats-table td {
  text-align: left; padding: 6px 10px; border-bottom: 1px solid var(--border-muted); font-size: 0.85rem;
}
.user-stats-table th { font-weight: 600; color: var(--fg-muted); font-size: 0.78rem; }
.tag-normal { color: #16a34a; }
.tag-locked { color: #dc2626; }
.tag-deleted { color: var(--fg-subtle); opacity: 0.6; }
.subtle-tag { font-size: 0.7rem; color: var(--fg-subtle); margin-left: 4px; }
</style>