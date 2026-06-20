<template>
  <div class="view-pane">
    <div class="doc-panel">
      <template v-if="currentDoc">
        <div class="doc-toolbar">
          <div class="doc-breadcrumb">{{ currentDoc.source_id }}/{{ currentDoc.rel_path }}</div>
          <div class="doc-toolbar-actions">
            <label class="image-toggle">
              <input v-model="imageEnhance" type="checkbox" />深色底图增强
            </label>
            <button class="btn btn-ghost btn-sm" @click="currentDoc = null">✕</button>
          </div>
        </div>
        <div class="doc-content doc-markdown" :class="{ 'image-enhance': imageEnhance }" v-html="renderedContent" ref="docContentEl" @click="onDocClick"></div>
      </template>
      <template v-else>
        <div class="empty-state">选择左侧文件开始阅读</div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from "vue";
import { useRoute } from 'vue-router';
import api from "../api/index.js";
import { markdownIt, rewriteImageUrls } from "../markdown-it.js";

const route = useRoute();
const isSingleDoc = computed(() => !!route.query.doc);
const searchQuery = computed(() => route.query.q || '');
const currentDoc = ref(null);
const imageEnhance = ref(true);
const docContentEl = ref(null);

const renderedContent = computed(() => {
  if (!currentDoc.value) return "";
  try {
    const rawHtml = markdownIt.render(currentDoc.value.content || "");
    const withImages = rewriteImageUrls(rawHtml, currentDoc.value.id);
    return highlightContent(withImages);
  } catch {
    return `<pre>${currentDoc.value.content || ""}</pre>`;
  }
});

function applyHighlight(doc, q) {
  if (!doc || !doc.content || !q) return;
  doc._searchQuery = q;
}

function highlightContent(html) {
  const q = currentDoc.value?._searchQuery;
  if (!q) return html;
  const escaped = String(q).trim().replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  if (!escaped) return html;
  const regex = new RegExp(`(>)([^<]*?)(${escaped})([^<]*?)(<)`, 'gi');
  return html.replace(regex, '$1$2<mark>$3</mark>$4$5');
}

async function openDoc(docId) {
  try {
    const data = await api(`/api/document/${docId}`);
    currentDoc.value = data;
    if (searchQuery.value) applyHighlight(currentDoc.value, searchQuery.value);
  } catch (e) {
    currentDoc.value = { source_id: "error", rel_path: e.message, content: "" };
  }
}

function onDocClick(e) {
  const target = e.target.closest('a[href]');
  if (target) {
    e.preventDefault();
    const href = target.getAttribute('href');
    if (href && !href.startsWith('http')) {
      const docId = href.replace(/^\/library\?doc=/, '');
      if (docId && !isNaN(docId)) openDoc(docId);
    }
  }
}

onMounted(async () => {
  const docId = route.query.doc;
  if (docId) await openDoc(docId);
});
</script>

<style scoped>
.view-pane { display: flex; flex-direction: column; height: 100%; }
.view-pane { max-width: none !important; padding: 0 !important; }
.doc-panel { flex: 1; overflow-y: auto; padding: 24px 5%; max-width: 100%; }
.doc-toolbar { display: flex; align-items: center; justify-content: space-between; padding: 8px 14px; border-bottom: 1px solid var(--border-muted); gap: 12px; }
.doc-breadcrumb { font-size: 0.82rem; color: var(--fg-subtle); font-family: var(--font-mono); }
.doc-toolbar-actions { display: flex; align-items: center; gap: 8px; }
.image-toggle { font-size: 0.8rem; display: flex; align-items: center; gap: 4px; cursor: pointer; }
.doc-content { overflow-wrap: break-word; }
.doc-content :deep(pre) { background: var(--bg-muted); border-radius: 8px; padding: 1px 0; overflow-x: auto; margin: 12px 0; }
.doc-content :deep(pre code) { display: block; padding: 14px 18px; font-size: 0.83rem; line-height: 1.55; }
.doc-content :deep(code) { font-family: var(--font-mono); background: var(--bg-muted); padding: 2px 5px; border-radius: 4px; font-size: 0.88em; }
.doc-content :deep(img) { max-width: 100%; border-radius: 6px; margin: 8px 0; }
.doc-content :deep(table) { border-collapse: collapse; width: 100%; margin: 12px 0; }
.doc-content :deep(th), .doc-content :deep(td) { border: 1px solid var(--border-default); padding: 8px 12px; text-align: left; }
.doc-content :deep(th) { background: var(--bg-muted); font-weight: 600; }
.empty-state { display: flex; align-items: center; justify-content: center; height: 100%; color: var(--fg-subtle); font-size: 1.1rem; }
</style>