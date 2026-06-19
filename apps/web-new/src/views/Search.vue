<template>
  <div class="view-pane">
    <div class="view-header"><h2>全文搜索</h2></div>
    <div class="filter-bar">
      <input v-model="query" type="text" placeholder="搜索 Markdown/代码…" @keydown.enter="doSearch" />
      <select v-model="sort" @change="applyLocal">
        <option value="relevance">相关度</option>
        <option value="mtime_desc">最近修改</option>
      </select>
      <select v-model="category" @change="applyLocal">
        <option value="">全部分类</option>
        <option value="source">原始素材</option>
        <option value="summary">学习摘要</option>
        <option value="query">问答沉淀</option>
      </select>
      <button class="btn btn-primary" @click="doSearch">搜索</button>
    </div>
    <div class="search-results">
      <p v-if="filtered.length === 0 && searched" class="subtle">无结果</p>
      <div v-for="r in pageItems" :key="r.id" class="result-card" @click="openDoc(r)">
        <div class="result-head">
          <span class="result-title">{{ r.title || r.rel_path }}</span>
          <span class="cat-badge" :class="'cat-' + (r.category || 'source')">
            {{ categoryLabel(r.category) }}
          </span>
          <span v-if="r.source_owner && r.source_owner !== '__shared__'" class="owner-badge" title="私有来源">🔒 私有</span>
        </div>
        <div class="result-meta">{{ r.source_id }} · {{ r.rel_path }}</div>
        <div class="result-snippet" v-html="r.snippet"></div>
      </div>
    </div>
    <div v-if="filtered.length > 0" class="pagination-bar">
      <span class="page-info">{{ (page-1)*pageSize+1 }}-{{ Math.min(page*pageSize, filtered.length) }} / {{ filtered.length }} 条</span>
      <div class="page-controls">
        <button class="btn btn-sm" :disabled="page <= 1" @click="page--">‹ 上一页</button>
        <span v-for="n in pageNumbers" :key="n" class="page-num" :class="{ active: n === page }" @click="page = n">{{ n }}</span>
        <button class="btn btn-sm" :disabled="page >= Math.ceil(filtered.length / pageSize)" @click="page++">下一页 ›</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from "vue";
import api from "../api/index.js";

const query = ref("");
const sort = ref("relevance");
const category = ref("");
const allResults = ref([]);
const searched = ref(false);
const page = ref(1);
const pageSize = 10;

const totalPages = computed(() => Math.ceil(filtered.value.length / pageSize) || 1);

const pageItems = computed(() => {
  const start = (page.value - 1) * pageSize;
  return filtered.value.slice(start, start + pageSize);
});

const pageNumbers = computed(() => {
  const tp = totalPages.value;
  const cur = page.value;
  const pages = [];
  let start = Math.max(1, cur - 3);
  let end = Math.min(tp, start + 6);
  if (end - start < 6) start = Math.max(1, end - 6);
  for (let i = start; i <= end; i++) pages.push(i);
  return pages;
});

const CAT_LABELS = { source: "原始素材", summary: "学习摘要", query: "问答沉淀" };
function categoryLabel(cat) { return CAT_LABELS[cat] || cat || "原始素材"; }

const filtered = computed(() => {
  let items = allResults.value;
  if (category.value) items = items.filter((r) => r.category === category.value);
  if (sort.value === "mtime_desc") {
    items = [...items].sort((a, b) => (b.mtime || 0) - (a.mtime || 0));
  }
  return items;
});

async function doSearch() {
  if (!query.value.trim()) return;
  searched.value = true;
  page.value = 1;
  try {
    const data = await api(`/api/search?q=${encodeURIComponent(query.value)}&limit=200`);
    allResults.value = data.results || data.items || [];
  } catch (e) {
    allResults.value = [];
  }
}

function applyLocal() {
  page.value = 1;
}

import { useRouter } from 'vue-router';
const router = useRouter();

function openDoc(doc) {
  if (doc.id) {
    router.push(`/library?doc=${encodeURIComponent(doc.id)}`);
  }
}
</script>

<style scoped>
.filter-bar {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin: 16px 0;
  align-items: center;
}
.filter-bar input {
  flex: 1;
  min-width: 200px;
}
.search-results {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.result-card {
  border: 1px solid var(--border-default);
  border-radius: var(--radius);
  padding: 12px 16px;
  cursor: pointer;
  transition: background 0.12s;
}
.result-card:hover {
  background: var(--bg-muted);
}
.result-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 2px;
}
.result-title {
  font-weight: 600;
  font-size: 0.95rem;
}
.cat-badge {
  font-size: 0.72rem;
  padding: 1px 7px;
  border-radius: 999px;
  white-space: nowrap;
  border: 1px solid;
}
.cat-badge.cat-source { color: var(--fg-muted); border-color: var(--border-default); }
.cat-badge.cat-summary { color: var(--success-fg); border-color: rgba(63,185,80,0.35); }
.cat-badge.cat-query { color: #a5b4fc; border-color: rgba(165,180,252,0.35); }
.owner-badge {
  font-size: 0.7rem;
  padding: 1px 6px;
  border-radius: 3px;
  background: var(--warning-bg, #fef3c7);
  color: var(--warning-fg, #92400e);
  white-space: nowrap;
  margin-left: auto;
}
.result-count { font-size: 0.82rem; color: var(--fg-subtle); margin-left: auto; }
.result-meta {
  font-size: 0.8rem;
  color: var(--fg-subtle);
  margin-bottom: 6px;
}
.result-snippet {
  font-size: 0.85rem;
  color: var(--fg-muted);
  line-height: 1.5;
}
.pagination-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0;
  border-top: 1px solid var(--border-muted);
  margin-top: 12px;
}
.page-info { font-size: 0.83rem; color: var(--fg-subtle); }
.page-controls { display: flex; align-items: center; gap: 4px; }
.page-num {
  display: grid; place-items: center;
  min-width: 28px; height: 28px;
  border-radius: var(--radius);
  cursor: pointer; font-size: 0.82rem;
  color: var(--fg-muted);
  border: 1px solid transparent;
}
.page-num:hover { background: var(--bg-hover); color: var(--fg-default); }
.page-num.active { background: var(--accent-emphasis); color: #fff; }
</style>
