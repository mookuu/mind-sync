<template>
  <div class="view-pane library-pane">
    <div class="view-header">
      <h2>文档库</h2>
      <p class="subtle">按来源与语言分类浏览，点击文件阅读</p>
    </div>
    <div class="library-layout">
      <aside class="tree-panel">
        <div class="tree-toolbar">
          <select v-model="category" @change="loadTree" class="tree-category-select">
            <option value="all">全部分类</option>
            <option value="source">原始素材</option>
            <option value="summary">学习摘要</option>
            <option value="query">问答沉淀</option>
          </select>
          <span class="tree-count">{{ totalDocs }} 篇</span>
        </div>
        <div class="tree-scroll">
          <TreeView
            v-for="sec in sections"
            :key="sec.id"
          >
            <TreeBranch
              :label="sec.label"
              :count="sec.count"
            >
              <!-- Wiki sources (flat languages) -->
              <template v-if="sec.flat">
                <TreeView v-for="lang in (sec.languages || [])" :key="lang.id">
                  <TreeBranch :label="lang.label" :count="lang.count">
                    <TreeNode
                      v-for="item in lang.tree"
                      :key="item.path"
                      :node="item"
                      :depth="2"
                      @select="openDoc"
                    />
                  </TreeBranch>
                </TreeView>
              </template>
              <!-- Raw sources (source → languages → tree) -->
              <template v-else>
                <TreeView v-for="src in (sec.sources || [])" :key="src.id">
                  <TreeBranch :label="src.label" :count="src.count" :source-id="src.id">
                    <TreeView v-for="lang in (src.languages || [])" :key="lang.id">
                      <TreeBranch :label="lang.label" :count="lang.count">
                        <TreeNode
                          v-for="item in lang.tree"
                          :key="item.path"
                          :node="item"
                          :depth="3"
                          @select="openDoc"
                        />
                      </TreeBranch>
                    </TreeView>
                  </TreeBranch>
                </TreeView>
              </template>
            </TreeBranch>
          </TreeView>
          <p v-if="!sections.length && loaded" class="subtle" style="padding: 20px; text-align: center;">暂无文档，请先同步来源</p>
          <p v-if="!loaded" class="subtle" style="padding: 20px; text-align: center;">加载中…</p>
        </div>
      </aside>
      <div class="doc-panel">
        <template v-if="currentDoc">
          <div class="doc-toolbar">
            <div class="doc-breadcrumb">{{ currentDoc.source_id }}/{{ currentDoc.rel_path }}</div>
            <div class="doc-toolbar-actions">
              <label class="image-toggle">
                <input v-model="imageEnhance" type="checkbox" />
                深色底图增强
              </label>
              <button class="btn btn-ghost btn-sm" @click="currentDoc = null">✕</button>
            </div>
          </div>
          <div
            class="doc-content doc-markdown"
            :class="{ 'image-enhance': imageEnhance }"
            v-html="renderedContent"
            ref="docContentEl"
            @click="onDocClick"
          ></div>
        </template>
        <template v-else>
          <div class="doc-empty">
            <p>选择左侧文件开始阅读</p>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from "vue";
import { useRoute } from 'vue-router';
import api from "../api/index.js";
import { markdownIt } from "../markdown-it.js";
import TreeView from "../components/TreeView.vue";
import TreeBranch from "../components/TreeBranch.vue";
import TreeNode from "../components/TreeNode.vue";

const route = useRoute();
const category = ref(route.query.category || "all");
const sections = ref([]);
const totalDocs = ref(0);
const loaded = ref(false);
const currentDoc = ref(null);
const imageEnhance = ref(true);
const docContentEl = ref(null);

const renderedContent = computed(() => {
  if (!currentDoc.value) return "";
  try {
    return markdownIt.render(currentDoc.value.content || "");
  } catch {
    return `<pre>${currentDoc.value.content || ""}</pre>`;
  }
});

async function loadTree() {
  loaded.value = false;
  try {
    const data = await api(`/api/library?category=${encodeURIComponent(category.value)}`);
    sections.value = data.sections || [];
    totalDocs.value = data.total_documents || 0;
  } catch {
    sections.value = [];
    totalDocs.value = 0;
  } finally {
    loaded.value = true;
  }
}

async function openDoc(docId) {
  try {
    const data = await api(`/api/document/${docId}`);
    currentDoc.value = data;
  } catch (e) {
    currentDoc.value = { source_id: "error", rel_path: e.message, content: "" };
  }
}

function onDocClick(e) {
  // Handle internal links
  const link = e.target.closest("a");
  if (!link) return;
  const href = link.getAttribute("href");
  if (!href || href.startsWith("http") || href.startsWith("#")) return;
  // TODO: resolve wiki links
  e.preventDefault();
}

onMounted(async () => {
  await loadTree();
  const docId = route.query.doc;
  if (docId) {
    await openDoc(docId);
  }
});
</script>

<style scoped>
.library-pane {
  max-width: none;
  height: calc(100vh - var(--topbar-height) - 48px);
}
.library-layout {
  display: grid;
  grid-template-columns: 300px 1fr;
  gap: 16px;
  height: 100%;
  margin-top: 8px;
}

.tree-panel {
  border: 1px solid var(--border-default);
  border-radius: var(--radius);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.tree-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 10px;
  border-bottom: 1px solid var(--border-muted);
  gap: 8px;
}
.tree-category-select {
  font-size: 0.8rem;
  padding: 4px 6px;
  flex: 1;
}
.tree-count {
  font-size: 0.78rem;
  color: var(--fg-subtle);
  white-space: nowrap;
}
.tree-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 4px 0;
}

.doc-panel {
  border: 1px solid var(--border-default);
  border-radius: var(--radius);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.doc-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 14px;
  border-bottom: 1px solid var(--border-muted);
  gap: 12px;
  flex-wrap: wrap;
}
.doc-breadcrumb {
  font-size: 0.82rem;
  color: var(--fg-subtle);
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.doc-toolbar-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}
.image-toggle {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 0.78rem;
  color: var(--fg-muted);
  cursor: pointer;
}
.image-toggle input {
  width: 14px;
  height: 14px;
}

.doc-content {
  flex: 1;
  overflow-y: auto;
  padding: 20px 28px;
  line-height: 1.7;
  font-size: 0.92rem;
}
.doc-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--fg-subtle);
}
</style>
