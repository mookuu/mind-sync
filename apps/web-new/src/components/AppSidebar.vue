<template>
  <nav class="sidebar-nav">
    <!-- 按指定顺序渲染：每个父级紧接其子菜单 -->
    <template v-for="item in orderedItems" :key="item.path">
      <!-- 父级菜单（带子项） -->
      <template v-if="item.children">
        <div class="nav-group">
          <router-link
            :to="item.path"
            class="nav-item parent"
            :class="{ active: isActive(item.path) }"
            @click="onParentClick(item.path)"
          >
            <span class="nav-icon">{{ item.icon }}</span>
            <span class="nav-label">{{ item.label }}</span>
            <span class="nav-chevron">{{ expanded[item.path] ? "▾" : "▸" }}</span>
          </router-link>
          <div v-if="expanded[item.path]" class="sub-nav">
            <template v-for="child in item.children" :key="child.path">
              <template v-if="child.catKey">
                <!-- 可展开树子菜单 -->
                <button v-if="!child.admin || isAdmin" class="sub-nav-item" :class="{ active: catExpanded[child.catKey] }" @click.stop="toggleCatTree(child.catKey)">
                  <span class="nav-icon">{{ child.icon }}</span>
                  <span class="nav-label">{{ child.label }}</span>
                  <span class="nav-chevron" style="font-size:0.65rem">{{ catExpanded[child.catKey] ? '▾' : '▸' }}</span>
                </button>
                <template v-if="catExpanded[child.catKey]">
                  <p v-if="catLoading[child.catKey]" class="subtle" style="padding:4px 10px 4px 48px;font-size:0.75rem">加载中…</p>
                  <template v-else v-for="node in (catTrees[child.catKey] || [])" :key="node.sourceId">
                    <TreeBranch :label="node.label" :source-id="node.sourceId" :count="node.count" :depth="2" :default-expanded="treeContains(node, activeDocId)">
                      <TreeNode v-for="titem in (node.tree || [])" :key="titem.path || titem.name" :node="titem" :depth="3" :active-doc-id="activeDocId" @select="openDocFromSidebar" />
                    </TreeBranch>
                  </template>
                </template>
              </template>
              <router-link v-else-if="!child.admin || isAdmin" :to="child.path" class="sub-nav-item" :class="{ active: isActive(child.path) }">
                <span class="nav-icon">{{ child.icon }}</span>
                <span class="nav-label">{{ child.label }}</span>
              </router-link>
            </template>

          </div>
        </div>
      </template>

      <!-- 平级菜单（无子项） -->
      <template v-else>
        <router-link
          v-if="!item.admin || isAdmin"
          :to="item.path"
          class="nav-item"
          :class="{ active: isActive(item.path) }"
        >
          <span class="nav-icon">{{ item.icon }}</span>
          <span class="nav-label">{{ item.label }}</span>
        </router-link>
      </template>
    </template>

    <div class="sidebar-spacer"></div>
    <router-link to="/account" class="nav-item" :class="{ active: isActive('/account') }">
      <span class="nav-icon">👤</span>
      <span class="nav-label">账户</span>
    </router-link>
  </nav>
</template>

<script setup>
import { ref, reactive, computed, watch, onUnmounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import api from "../api/index.js";
import TreeBranch from "./TreeBranch.vue";
import TreeNode from "./TreeNode.vue";

const router = useRouter();

// 每个分类独立的树状态
const catTrees = reactive({ source: null, summary: null, query: null });
const catLoading = reactive({ source: false, summary: false, query: false });
const catExpanded = reactive({ source: false, summary: false, query: false });

function clearTreeCache() {
  catTrees.source = null;
  catTrees.summary = null;
  catTrees.query = null;
}

// sync/rebuild 后精准清缓存
window.addEventListener('mind-sync-tree-refresh', clearTreeCache);
onUnmounted(() => window.removeEventListener('mind-sync-tree-refresh', clearTreeCache));

async function toggleCatTree(catKey) {
  if (catExpanded[catKey]) {
    catExpanded[catKey] = false;
    return;
  }
  // 关闭其他展开的分类
  catExpanded.source = false;
  catExpanded.summary = false;
  catExpanded.query = false;
  catExpanded[catKey] = true;
  // 有缓存直接复用（sync/rebuild 后会被 event 清空）
  if (catTrees[catKey]) return;
  catLoading[catKey] = true;
  try {
    const data = await api(`/api/library?category=${encodeURIComponent(catKey)}`);
    const nodes = [];
    for (const sec of (data.sections || [])) {
      if (sec.flat && sec.tree && sec.tree.length) {
        nodes.push({ label: sec.label || sec.source_id, sourceId: sec.source_id || 'wiki', type: 'source', tree: sec.tree, count: sec.count });
        continue;
      }
      for (const src of (sec.sources || [])) {
        if (src.tree && src.tree.length) {
          nodes.push({ label: src.label || src.id, sourceId: src.id, type: 'source', tree: src.tree, count: src.count });
        }
      }
    }
    catTrees[catKey] = nodes;
  } catch { catTrees[catKey] = []; }
  finally { catLoading[catKey] = false; }
}

function openDocFromSidebar(docId) {
  if (docId) router.push('/library?doc=' + docId);
}

function treeContains(node, targetId) {
  if (!node || !targetId) return false;
  const t = String(targetId);
  const tree = node.tree || node.children || [];
  for (const item of tree) {
    if (item.type === 'file' && String(item.doc_id) === t) return true;
    if (item.type === 'dir' && treeContains(item, t)) return true;
  }
  return false;
}

const route = useRoute();
const activeDocId = computed(() => route.query.doc ? String(route.query.doc) : null);

// 从搜索跳转时自动加载并展开对应分类树
watch(activeDocId, async (docId) => {
  if (!docId) return;
  try {
    const doc = await api(`/api/document/${docId}`);
    const sourceId = doc.source_id || '';
    const relPath = doc.rel_path || '';
    // 根据文档信息判断分类
    let catKey = 'source';
    if (sourceId === 'wiki' || relPath.startsWith('summaries/')) catKey = 'summary';
    else if (relPath.startsWith('queries/') || relPath.startsWith('insight_')) catKey = 'query';
    // 加载并展开对应分类树（如果尚未加载）
    if (!catTrees[catKey]) {
      await toggleCatTree(catKey);
    } else if (!catExpanded[catKey]) {
      catExpanded.source = false;
      catExpanded.summary = false;
      catExpanded.query = false;
      catExpanded[catKey] = true;
    }
  } catch {
    // 文档加载失败，忽略
  }
});

// expanded: 当前展开的父级（同一时间只有一个）
const expanded = ref({});

// 根据当前路由自动展开对应父级
function expandForRoute(path) {
  if (path.startsWith('/sync/')) return { '/sync/control': true };
  if (path.startsWith('/admin/')) return { '/admin/users': true };
  if (path === '/library') return { '/library': true };
  return {};
}
expanded.value = expandForRoute(route.path);

// 路由变化时自动展开对应父级
watch(() => route.path, (path) => {
  const target = expandForRoute(path);
  if (Object.keys(target).length) {
    expanded.value = target;
  } else {
    expanded.value = {};
  }
});

const props = defineProps({
  userRole: { type: String, default: "" },
});

const isAdmin = computed(() => props.userRole === "admin");

const orderedItems = computed(() => {
  const items = [
    { label: "搜索", icon: "🔍", path: "/search" },
    {
      label: "文档库",
      icon: "📚",
      path: "/library",
      children: [
        { label: "原始素材", icon: "📦", path: "/library?category=source", catKey: "source" },
        { label: "学习摘要", icon: "📝", path: "/library?category=summary", catKey: "summary" },
        { label: "问答沉淀", icon: "💬", path: "/library?category=query", catKey: "query" },
      ],
    },
    { label: "知识查询", icon: "💡", path: "/qa" },
    {
      label: "同步运维",
      icon: "🔄",
      path: "/sync/control",
      children: [
        { label: "同步控制", icon: "📊", path: "/sync/control" },
        { label: "同步素材", icon: "📦", path: "/sync/sources" },
        { label: "仓库管理", icon: "🏪", path: "/sync/vault" },
        { label: "规则约束", icon: "📋", path: "/sync/purpose", admin: true },
        { label: "操作记录", icon: "📜", path: "/sync/audit" },
      ],
    },
    { label: "Wiki 图谱", icon: "🕸", path: "/graph", admin: true },
  ];

  // Admin-only links
  if (isAdmin.value) {
    items.push({
      label: "系统管理",
      icon: "⚙️",
      path: "/admin/users",
      children: [
        { label: "用户管理", icon: "👥", path: "/admin/users" },
        { label: "API keys", icon: "🔑", path: "/admin/api-keys" },
        { label: "素材管理", icon: "📦", path: "/admin/sources" },
        { label: "Web 快照", icon: "🌍", path: "/admin/web-snapshots" },
      ],
    });
  }

  return items;
});

function isActive(path) {
  return route.path === path || route.path.startsWith(path + "/");
}

function onParentClick(path) {
  // 单击父级：展开/收起切换，同一时间只能有一个父级展开
  if (expanded.value[path]) {
    expanded.value = {};
  } else {
    expanded.value = { [path]: true };
  }
}
</script>

<style scoped>
.sidebar-nav {
  display: flex;
  flex-direction: column;
  gap: 1px;
  height: 100%;
}

.nav-group {
  display: flex;
  flex-direction: column;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 10px;
  border-radius: var(--radius);
  color: var(--fg-muted);
  font-size: 0.88rem;
  text-decoration: none;
  transition: background 0.12s, color 0.12s;
  cursor: pointer;
  border: none;
  background: transparent;
  width: 100%;
  text-align: left;
}

.nav-item:hover {
  background: var(--bg-hover);
  color: var(--fg-default);
}

.nav-item.active {
  background: var(--accent-bg);
  color: var(--accent-fg);
}

.nav-icon {
  flex-shrink: 0;
  width: 20px;
  text-align: center;
  font-size: 0.95rem;
}

.nav-label {
  flex: 1;
}

.nav-chevron {
  font-size: 0.7rem;
  color: var(--fg-subtle);
}

.sub-nav {
  margin-left: 12px;
  display: flex;
  flex-direction: column;
  gap: 1px;
  padding-bottom: 4px;
}

.sub-nav-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 10px 5px 32px;
  border-radius: var(--radius);
  color: var(--fg-muted);
  font-size: 0.82rem;
  text-decoration: none;
  transition: background 0.12s, color 0.12s;
}

.sub-nav-item:hover {
  background: var(--bg-hover);
  color: var(--fg-default);
}

.sub-nav-item.active {
  color: var(--accent-fg);
  background: var(--accent-bg);
}
.sub-nav-item.active:hover {
  background: var(--accent-bg);
}
.sub-nav-item-deeper {
  padding-left: 48px;
  font-size: 0.78rem;
}
.nav-separator {
  height: 1px;
  background: var(--border-muted);
  margin: 2px 8px;
}

.sidebar-file-item {
  display: flex; align-items: center; gap: 4px;
  width: 100%; padding: 2px 8px; border: none; border-radius: var(--radius);
  background: transparent; color: var(--fg-muted); font-size: 0.75rem;
  cursor: pointer; text-align: left; transition: background 0.1s;
}
.sidebar-file-item:hover { background: var(--bg-hover); color: var(--fg-default); }
.sidebar-spacer {
  flex: 1;
}
/* 子菜单 button 与 router-link 统一扁平样式 */
button.sub-nav-item {
  font-family: inherit; cursor: pointer; border: none; outline: none; box-shadow: none;
}
button.sub-nav-item:hover { background: var(--bg-hover); color: var(--fg-default); }
/* 去掉侧边栏树节点边框 */
.sub-nav :deep(.tree-branch) { border: none; outline: none; box-shadow: none; }
.sub-nav :deep(.branch-head) { padding: 2px 8px; font-size: 0.78rem; border: none; outline: none; box-shadow: none; background: transparent; border-radius: 0; }
.sub-nav :deep(.branch-body) { border: none; }
.sub-nav :deep(.file-item) { padding: 2px 8px; font-size: 0.75rem; border: none; outline: none; box-shadow: none; border-radius: 0; }
</style>
