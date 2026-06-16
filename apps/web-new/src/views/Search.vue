<template>
  <div class="view-pane">
    <div class="view-header"><h2>全文搜索</h2></div>
    <div class="filter-bar">
      <input v-model="query" type="text" placeholder="搜索 Markdown/代码…" @keydown.enter="doSearch" />
      <select v-model="sort">
        <option value="relevance">相关度</option>
        <option value="mtime_desc">最近修改</option>
      </select>
      <select v-model="category">
        <option value="">全部分类</option>
        <option value="source">原始素材</option>
        <option value="summary">学习摘要</option>
        <option value="query">问答沉淀</option>
      </select>
      <button class="btn btn-primary" @click="doSearch">搜索</button>
    </div>
    <div class="search-results">
      <p v-if="results.length === 0 && searched" class="subtle">无结果</p>
      <div v-for="r in results" :key="r.id" class="result-card" @click="openDoc(r)">
        <div class="result-title">{{ r.title || r.rel_path }}</div>
        <div class="result-meta">{{ r.source_id }} · {{ r.rel_path }}</div>
        <div class="result-snippet" v-html="r.snippet"></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from "vue";
import api from "../api/index.js";

const query = ref("");
const sort = ref("relevance");
const category = ref("");
const results = ref([]);
const searched = ref(false);

async function doSearch() {
  if (!query.value.trim()) return;
  searched.value = true;
  const params = new URLSearchParams({ q: query.value, sort: sort.value });
  if (category.value) params.set("category", category.value);
  try {
    const data = await api(`/api/search?${params}`);
    results.value = data.results || data.items || [];
  } catch (e) {
    results.value = [];
  }
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
.result-title {
  font-weight: 600;
  font-size: 0.95rem;
  margin-bottom: 2px;
}
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
