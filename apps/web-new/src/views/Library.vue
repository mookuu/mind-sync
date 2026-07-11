<template>
  <div class="view-pane">
    <div class="doc-panel">
      <template v-if="loadingDoc">
        <div class="doc-content" style="padding: 24px 5%;">
          <Skeleton height="28px" width="60%" style="margin-bottom:16px" />
          <Skeleton height="16px" width="80%" style="margin-bottom:10px" />
          <Skeleton height="16px" width="75%" style="margin-bottom:10px" />
          <Skeleton height="16px" width="70%" style="margin-bottom:24px" />
          <Skeleton height="200px" width="100%" />
        </div>
      </template>
      <template v-else-if="currentDoc">
        <div class="doc-toolbar">
          <div class="doc-breadcrumb">{{ currentDoc.source_id }}/{{ currentDoc.rel_path }}</div>
          <div class="doc-toolbar-actions">
            <button v-if="currentDoc.source_id === 'error'" class="btn btn-ghost btn-sm" @click="retryLoadDoc">重试</button>
            <button v-if="hasSearchHighlight" class="btn btn-ghost btn-sm" @click="resetSearchHighlight">重置高亮</button>
            <button class="btn btn-ghost btn-sm" @click="currentDoc = null">✕</button>
          </div>
        </div>
        <div class="doc-content doc-markdown" v-html="renderedContent" ref="docContentEl" @click="onDocClick"></div>
      </template>
      <template v-else>
        <div v-if="deniedMsg" class="denied-notice">{{ deniedMsg }}</div>
        <div v-else class="empty-state">选择左侧文件开始阅读</div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from "vue";
import { useRoute } from 'vue-router';
import api from "../api/index.js";
import { markdownIt, rewriteImageUrls, hljs } from "../markdown-it.js";
import Skeleton from "../components/Skeleton.vue";

const route = useRoute();
const deniedMsg = ref('');

// 权限拦截后显示提示
watch(() => route.query.denied, (path) => {
  deniedMsg.value = path ? `页面「${path}」仅管理员可访问` : '';
}, { immediate: true });

const isSingleDoc = computed(() => !!route.query.doc);
const searchQuery = computed(() => route.query.q || '');
const currentDoc = ref(null);
const docContentEl = ref(null);
const hasSearchHighlight = computed(() => currentDoc.value?._searchQuery ? true : false);
const loadingDoc = ref(false);
const lastDocId = ref(null);

const CODE_LANGS = { python: "python", java: "java", javascript: "javascript", js: "javascript", html: "html", css: "css", json: "json", bash: "bash", sh: "bash", yaml: "yaml", yml: "yaml", sql: "sql", xml: "xml", dockerfile: "dockerfile", nginx: "nginx" };

const renderedContent = computed(() => {
  if (!currentDoc.value) return "";
  const doc = currentDoc.value;
  const lang = (doc.lang || "text").toLowerCase();
  try {
    if (lang === "markdown" || lang === "md") {
      const rawHtml = markdownIt.render(doc.content || "");
      const withImages = rewriteImageUrls(rawHtml, doc.id);
      return highlightContent(withImages);
    }
    // 代码文件：使用 hljs 做语法高亮
    const codeLang = CODE_LANGS[lang] || "";
    const content = doc.content || "";
    if (codeLang && hljs.getLanguage(codeLang)) {
      try {
        return `<pre class="hljs"><code class="language-${codeLang}">${hljs.highlight(content, { language: codeLang, ignoreIllegals: true }).value}</code></pre>`;
      } catch {}
    }
    return `<pre class="hljs"><code>${markdownIt.utils.escapeHtml(content)}</code></pre>`;
  } catch {
    return `<pre>${markdownIt.utils.escapeHtml(doc.content || "")}</pre>`;
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

const SEARCH_CACHE_KEY = 'mind_sync_last_search';
const KEYBOARD_MODE_KEY = 'mind_sync_kbd_mode';

async function openDoc(docId) {
  loadingDoc.value = true;
  lastDocId.value = docId;
  try {
    const data = await api(`/api/document/${docId}`);
    currentDoc.value = data;
    if (searchQuery.value) applyHighlight(currentDoc.value, searchQuery.value);
  } catch (e) {
    const msg = e.message || '';
    if (msg.includes('404')) {
      localStorage.removeItem(SEARCH_CACHE_KEY);
    }
    const displayMsg = msg.includes('403') ? '此文档属于私有知识库，你无权访问'
      : msg.includes('404') ? '文档不存在（可能索引已重建，请重新搜索）'
      : msg;
    currentDoc.value = { source_id: "error", rel_path: displayMsg, content: "" };
  } finally {
    loadingDoc.value = false;
  }
}

function retryLoadDoc() {
  if (lastDocId.value) openDoc(lastDocId.value);
}

function resetSearchHighlight() {
  if (currentDoc.value) {
    delete currentDoc.value._searchQuery;
    // 强制刷新 renderedContent（触发重组）
    currentDoc.value = { ...currentDoc.value };
  }
  highlightIndex.value = -1;
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

// 键盘高亮导航
const highlightIndex = ref(-1);

function navigateHighlights(direction) {
  const marks = docContentEl.value?.querySelectorAll("mark");
  if (!marks || !marks.length) return;
  if (direction === "next") {
    highlightIndex.value = (highlightIndex.value + 1) % marks.length;
  } else {
    highlightIndex.value = highlightIndex.value <= 0 ? marks.length - 1 : highlightIndex.value - 1;
  }
  // 清除旧高亮
  marks.forEach((m, i) => {
    if (i === highlightIndex.value) {
      m.classList.add("hl-active");
      m.scrollIntoView({ behavior: "smooth", block: "center" });
    } else {
      m.classList.remove("hl-active");
    }
  });
}

function onKeyDown(e) {
  if (e.key === "ArrowDown" || e.key === "ArrowUp") {
    // 仅当文档来自搜索结果时拦截
    if (currentDoc.value?._searchQuery) {
      e.preventDefault();
      navigateHighlights(e.key === "ArrowDown" ? "next" : "prev");
    }
  }
}

// 键盘模式持久化
watch(() => route.path, (newPath, oldPath) => {
  if (oldPath === '/library' && newPath !== '/library') {
    // 离开文档库时保存键盘模式
    const mode = currentDoc.value?._searchQuery ? 'highlight' : 'scroll';
    localStorage.setItem(KEYBOARD_MODE_KEY, mode);
  }
  if (newPath === '/library' && oldPath !== '/library') {
    // 回到文档库时恢复键盘模式
    const saved = localStorage.getItem(KEYBOARD_MODE_KEY);
    if (saved === 'highlight' && currentDoc.value?._searchQuery) {
      // 自动激活高亮模式
    } else {
      localStorage.removeItem(KEYBOARD_MODE_KEY);
    }
  }
});

async function loadOrRestoreDoc(docId) {
  if (docId) {
    await openDoc(docId);
    setTimeout(() => navigateHighlights("next"), 100);
  } else {
    const saved = localStorage.getItem(KEYBOARD_MODE_KEY);
    if (saved === 'highlight') {
      setTimeout(() => navigateHighlights("next"), 200);
    }
  }
}

// doc 变化时自动加载（同路由切换 doc）
watch(() => route.query.doc, (docId) => {
  loadOrRestoreDoc(docId);
});

onMounted(async () => {
  loadOrRestoreDoc(route.query.doc);
  window.addEventListener("keydown", onKeyDown);
});

onUnmounted(() => window.removeEventListener("keydown", onKeyDown));
</script>

<style scoped>
.view-pane { display: flex; flex-direction: column; height: 100%; }
.view-pane { max-width: none !important; padding: 0 !important; }
.doc-panel { flex: 1; overflow-y: auto; padding: 24px 5%; max-width: 100%; }
.doc-toolbar { display: flex; align-items: center; justify-content: space-between; padding: 8px 14px; border-bottom: 1px solid var(--border-muted); gap: 12px; }
.doc-breadcrumb { font-size: 0.82rem; color: var(--fg-subtle); font-family: var(--font-mono); }
.doc-toolbar-actions { display: flex; align-items: center; gap: 8px; }
.doc-content { overflow-wrap: break-word; }
.doc-content :deep(pre) { background: var(--bg-muted); border-radius: 8px; padding: 1px 0; overflow-x: auto; margin: 12px 0; }
.doc-content :deep(pre code) { display: block; padding: 14px 18px; font-size: 0.83rem; line-height: 1.55; }
.doc-content :deep(code) { font-family: var(--font-mono); background: var(--bg-muted); padding: 2px 5px; border-radius: 4px; font-size: 0.88em; }
.doc-content :deep(img) { max-width: 100%; border-radius: 6px; margin: 8px 0; }
.doc-content :deep(table) { border-collapse: collapse; width: 100%; margin: 12px 0; }
.doc-content :deep(th), .doc-content :deep(td) { border: 1px solid var(--border-default); padding: 8px 12px; text-align: left; }
.doc-content :deep(th) { background: var(--bg-muted); font-weight: 600; }
.doc-content :deep(h1) { font-size: 1.6rem; font-weight: 700; margin: 24px 0 12px; border-bottom: 1px solid var(--border-muted); padding-bottom: 8px; }
.doc-content :deep(h2) { font-size: 1.3rem; font-weight: 600; margin: 20px 0 10px; }
.doc-content :deep(h3) { font-size: 1.1rem; font-weight: 600; margin: 16px 0 8px; }
.doc-content :deep(h4) { font-size: 1rem; font-weight: 600; margin: 12px 0 6px; }
.doc-content :deep(p) { margin: 8px 0; line-height: 1.6; }
.doc-content :deep(ul), .doc-content :deep(ol) { margin: 8px 0; padding-left: 24px; }
.doc-content :deep(li) { margin: 4px 0; }
.doc-content :deep(blockquote) { border-left: 3px solid var(--accent-emphasis); padding: 4px 14px; margin: 12px 0; color: var(--fg-muted); background: var(--bg-muted); border-radius: 0 6px 6px 0; }
.doc-content :deep(hr) { border: none; border-top: 1px solid var(--border-muted); margin: 16px 0; }
.doc-content :deep(a) { color: var(--accent-fg); }
.doc-content :deep(a:hover) { text-decoration: underline; }
.denied-notice {
  padding: 12px 16px;
  margin-bottom: 12px;
  border-radius: var(--radius);
  background: var(--warning-bg, #fef3c7);
  color: var(--warning-fg, #92400e);
  font-size: 0.9rem;
}
.doc-content :deep(mark.hl-active) { background: var(--accent-emphasis); color: #fff; border-radius: 2px; }
.empty-state { display: flex; align-items: center; justify-content: center; height: 100%; color: var(--fg-subtle); font-size: 1.1rem; }
</style>
