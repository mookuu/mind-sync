<template>
  <div class="view-pane">
    <div class="view-header">
      <h2>📦 素材管理</h2>
    </div>
    <p class="subtle">管理所有用户的知识库，包含全局默认源和个人库。</p>

    <div v-if="loading" class="subtle" style="padding:20px">加载中…</div>

    <template v-else-if="sources.length">
      <!-- 筛选栏 -->
      <div class="filter-bar">
        <div class="filter-dropdown-wrapper">
          <button class="btn btn-ghost btn-sm" @click="ownerDropdownOpen = !ownerDropdownOpen">
            👤 {{ filterOwner || '用户' }} ▾
          </button>
          <div v-if="ownerDropdownOpen" class="filter-dropdown">
            <div class="filter-dropdown-item" @click="filterOwner = ''; ownerDropdownOpen = false">全部</div>
            <div class="filter-dropdown-item" v-for="o in ownerList" :key="o" @click="filterOwner = o; ownerDropdownOpen = false">{{ o }}</div>
          </div>
        </div>
        <input v-model="filterName" type="text" placeholder="🔍 筛选库名…" class="filter-input" />
        <div class="filter-dropdown-wrapper">
          <button class="btn btn-ghost btn-sm" @click="statusDropdownOpen = !statusDropdownOpen">
            {{ statusFilterLabel }} ▾
          </button>
          <div v-if="statusDropdownOpen" class="filter-dropdown">
            <div class="filter-dropdown-item" @click="filterStatus = ''; statusDropdownOpen = false">全部</div>
            <div class="filter-dropdown-item" @click="filterStatus = 'valid'; statusDropdownOpen = false">✅ 有效</div>
            <div class="filter-dropdown-item" @click="filterStatus = 'invalid'; statusDropdownOpen = false">⚠ 无效</div>
          </div>
        </div>
        <button class="btn btn-ghost btn-sm" @click="refresh">↻ 刷新</button>
      </div>

      <!-- 表格 -->
      <table class="sources-table">
        <thead>
          <tr>
            <th>用户</th>
            <th>库名</th>
            <th>库路径</th>
            <th>库状态</th>
            <th>共享状态</th>
            <th>添加时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="s in pagedSources" :key="s.source_id">
            <td>
              <span v-if="s.owner === null" class="admin-tag">全局</span>
              <span v-else-if="s.owner === 'admin'" class="admin-tag">admin</span>
              <span v-else>{{ s.owner_display_name || s.owner }}</span>
            </td>
            <td>{{ labelName(s.label) }}<span class="label-type-tag">{{ labelType(s.label) }}</span></td>
            <td class="path-cell">{{ displayPath(s.path) }}</td>
            <td>
              <span v-if="s.path_exists" class="tag-ok">✅ 有效</span>
              <span v-else class="tag-err">⚠ 无效</span>
            </td>
            <td>
              <span v-if="s.shared" class="tag-shared">🔓 共享中</span>
              <span v-else class="tag-private">🔒 私有</span>
            </td>
            <td>{{ formatTime(s.created_at || s.updated_at) }}</td>
            <td class="action-cell">
              <button
                class="btn btn-ghost btn-xs"
                :disabled="acting === s.source_id"
                @click="toggleShare(s)"
                :title="s.shared ? '取消共享' : '共享'"
              >{{ s.shared ? '取消共享' : '共享' }}</button>
              <button
                class="btn btn-ghost btn-xs btn-danger-text"
                :disabled="acting === s.source_id || isDefaultSource(s)"
                @click="confirmDelete(s)"
                title="删除"
              >删除</button>
            </td>
          </tr>
        </tbody>
      </table>

      <!-- 分页 -->
      <div v-if="totalPages > 1" class="pagination-row">
        <button class="btn btn-ghost btn-xs" :disabled="page <= 1" @click="page--">‹ 上一页</button>
        <span class="page-info">{{ page }} / {{ totalPages }}</span>
        <button class="btn btn-ghost btn-xs" :disabled="page >= totalPages" @click="page++">下一页 ›</button>
      </div>
    </template>
    <p v-else class="subtle" style="padding:20px">暂无知识库</p>

    <!-- 删除确认弹窗 -->
    <div v-if="deleteTarget" class="modal-overlay" @click.self="deleteTarget = null">
      <div class="confirm-dialog">
        <p>确认删除「<strong>{{ deleteTarget.label }}</strong>」？</p>
        <p class="subtle">此操作将同时删除该库的索引数据，不可撤销。</p>
        <div class="btn-row" style="justify-content:flex-end;margin-top:12px">
          <button class="btn btn-ghost" @click="deleteTarget = null">取消</button>
          <button class="btn btn-danger btn-sm" @click="doDelete" :disabled="acting === deleteTarget.source_id">
            {{ acting === deleteTarget.source_id ? "删除中…" : "确认删除" }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, onActivated } from "vue";
import api from "../api/index.js";

const sources = ref([]);
const loading = ref(true);
const acting = ref("");
const deleteTarget = ref(null);

// Filters
const filterName = ref("");
const filterOwner = ref("");
const filterStatus = ref("");
const ownerDropdownOpen = ref(false);
const statusDropdownOpen = ref(false);

// Pagination
const pageSize = 15;
const page = ref(1);

const DEFAULT_SOURCE_IDS = ["obsidian", "web_snapshots", "wiki"];

function isDefaultSource(s) {
  return DEFAULT_SOURCE_IDS.includes(s.source_id) && s.owner === "admin";
}

const ownerList = computed(() => {
  const owners = new Set(sources.value.map(s => s.owner === "admin" ? "admin" : (s.owner_display_name || s.owner)));
  return Array.from(owners).sort();
});

const statusFilterLabel = computed(() => {
  if (filterStatus.value === "valid") return "✅ 有效";
  if (filterStatus.value === "invalid") return "⚠ 无效";
  return "库状态";
});

const filteredSources = computed(() => {
  let list = sources.value;
  if (filterName.value.trim()) {
    const q = filterName.value.trim().toLowerCase();
    list = list.filter(s => (s.label || s.source_id).toLowerCase().includes(q));
  }
  if (filterOwner.value) {
    list = list.filter(s => {
      const display = s.owner === "admin" ? "admin" : (s.owner_display_name || s.owner);
      return display === filterOwner.value;
    });
  }
  if (filterStatus.value === "valid") {
    list = list.filter(s => s.path_exists);
  } else if (filterStatus.value === "invalid") {
    list = list.filter(s => !s.path_exists);
  }
  return list;
});

const totalPages = computed(() => Math.max(1, Math.ceil(filteredSources.value.length / pageSize)));

const pagedSources = computed(() => {
  const start = (page.value - 1) * pageSize;
  return filteredSources.value.slice(start, start + pageSize);
});

function formatTime(ts) {
  if (!ts || ts <= 0) return "—";
  return new Date(ts * 1000).toLocaleString();
}

// 从 "库名:类型" label 中提取库名
function labelName(label) {
  if (!label) return "";
  const idx = label.lastIndexOf(":");
  return idx > 0 ? label.slice(0, idx) : label;
}
// 从 "库名:类型" label 中提取类型标签
function labelType(label) {
  if (!label) return "";
  const idx = label.lastIndexOf(":");
  return idx > 0 ? label.slice(idx) : "";
}

// 路径显示：容器内路径转为 ~ 格式
function displayPath(path) {
  if (!path) return "";
  return path
    .replace(/^\/home\/moku\//, "~/")
    .replace(/^\/data\/users\//, "~/data/mind-sync-data/users/")
    .replace(/^\/data\//, "~/data/mind-sync-data/");
}

async function loadSources() {
  loading.value = true;
  try {
    const data = await api("/api/admin/sources-status");
    sources.value = data.sources || [];
    page.value = 1;
  } catch {
    sources.value = [];
  } finally {
    loading.value = false;
  }
}

async function refresh() {
  await loadSources();
}

async function toggleShare(s) {
  acting.value = s.source_id;
  try {
    const data = await api(`/api/admin/sources/${encodeURIComponent(s.source_id)}/share`, { method: "POST" });
    s.shared = data.shared;
  } catch {
    // ignore
  } finally {
    acting.value = "";
  }
}

function confirmDelete(s) {
  deleteTarget.value = s;
}

async function doDelete() {
  if (!deleteTarget.value) return;
  const s = deleteTarget.value;
  deleteTarget.value = null;
  acting.value = s.source_id;
  try {
    await api(`/api/admin/sources/${encodeURIComponent(s.source_id)}/delete`, { method: "POST" });
    sources.value = sources.value.filter(item => item.source_id !== s.source_id);
  } catch (e) {
    if (e.message && !e.message.includes("Internal Server Error")) {
      alert(`删除失败: ${e.message || "未知错误"}`);
    }
  } finally {
    acting.value = "";
  }
}

// 全局 ESC 关闭弹窗和下拉
function onGlobalKeydown(e) {
  if (e.key === 'Escape') {
    deleteTarget.value = null;
    ownerDropdownOpen.value = false;
    statusDropdownOpen.value = false;
  }
}

function onClickOutside(e) {
  if (ownerDropdownOpen.value || statusDropdownOpen.value) {
    const target = e.target;
    if (!target.closest('.filter-dropdown-wrapper')) {
      ownerDropdownOpen.value = false;
      statusDropdownOpen.value = false;
    }
  }
}

onMounted(() => {
  document.addEventListener('keydown', onGlobalKeydown);
  document.addEventListener('click', onClickOutside);
  loadSources();
});

onUnmounted(() => {
  document.removeEventListener('keydown', onGlobalKeydown);
  document.removeEventListener('click', onClickOutside);
});

// 从同步素材页切回时刷新（如添加/删除源后）
onActivated(() => {
  loadSources();
});
</script>

<style scoped>
.filter-bar {
  display: flex;
  gap: 8px;
  align-items: center;
  margin: 16px 0;
  flex-wrap: wrap;
}
.filter-input {
  width: 180px;
  padding: 4px 8px;
  font-size: 0.82rem;
}
.filter-dropdown-wrapper {
  position: relative;
}
.filter-dropdown {
  position: absolute;
  top: 100%;
  left: 0;
  z-index: 50;
  background: var(--bg-card);
  border: 1px solid var(--border-default);
  border-radius: var(--radius);
  min-width: 140px;
  max-height: 250px;
  overflow-y: auto;
  box-shadow: var(--shadow-md);
}
.filter-dropdown-item {
  padding: 6px 12px;
  font-size: 0.82rem;
  cursor: pointer;
  white-space: nowrap;
}
.filter-dropdown-item:hover {
  background: var(--bg-hover);
}

.sources-table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 8px;
}
.sources-table th, .sources-table td {
  text-align: left;
  padding: 8px 10px;
  border-bottom: 1px solid var(--border-muted);
  font-size: 0.85rem;
}
.sources-table th {
  font-weight: 600;
  color: var(--fg-muted);
  font-size: 0.78rem;
  white-space: nowrap;
}
.path-cell {
  font-family: var(--font-mono);
  font-size: 0.78rem;
  color: var(--fg-subtle);
  max-width: 280px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.action-cell {
  white-space: nowrap;
  display: flex;
  gap: 4px;
}
.admin-tag {
  display: inline-block;
  font-size: 0.7rem;
  color: var(--accent-fg);
  background: var(--accent-bg);
  padding: 1px 6px;
  border-radius: 3px;
  font-weight: 600;
}
.tag-ok { color: #16a34a; font-size: 0.8rem; }
.tag-err { color: #dc2626; font-size: 0.8rem; }
.tag-shared { color: var(--accent-fg); font-size: 0.8rem; }
.tag-private { color: var(--fg-subtle); font-size: 0.8rem; }
.label-type-tag { font-size: 0.72rem; color: var(--fg-subtle); margin-left: 2px; }

.pagination-row {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 12px 0;
}
.page-info {
  font-size: 0.82rem;
  color: var(--fg-subtle);
}

.btn-danger-text {
  color: var(--danger-fg);
}
.btn-danger-text:hover {
  background: rgba(220, 38, 38, 0.1);
}

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
.btn-row {
  display: flex;
  gap: 8px;
}
</style>
