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
      <span v-if="searched" class="result-count">{{ filtered.length }} / {{ allResults.length }} 条</span>
    </div>
    <div class="search-results">
      <p v-if="filtered.length === 0 && searched" class="subtle">无结果</p>
      <div v-for="r in filtered" :key="r.id" class="result-card" @click="openDoc(r)">
        <div class="result-head">
          <span class="result-title">{{ r.title || r.rel_path }}</span>
          <span class="cat-badge" :class="'cat-' + (r.category || 'source')">
            {{ categoryLabel(r.category) }}
          </span>
        </div>
        <div class="result-meta">{{ r.source_id }} · {{ r.rel_path }}</div>
        <div class="result-snippet" v-html="r.snippet"></div>
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
  try {
    const data = await api(`/api/search?q=${encodeURIComponent(query.value)}&limit=200`);
    allResults.value = data.results || data.items || [];
  } catch (e) {
    allResults.value = [];
  }
}

function applyLocal() {
  // computed 自动重新计算 filtered
}

function openDoc(doc) {
  // TODO: navigate to document view or open in library
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
</style>
