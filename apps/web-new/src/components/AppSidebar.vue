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
              <router-link
                v-if="!child.admin || isAdmin"
                :to="child.path"
                class="sub-nav-item"
                :class="{ active: isActive(child.path) }"
                @click.stop="child.loadTree && loadLibTree(child.loadTree)"
              >
              <span class="nav-icon">{{ child.icon }}</span>
              <span class="nav-label">{{ child.label }}</span>
            </router-link>
            </template>
            <!-- 文档库动态子目录 -->
            <template v-if="libSubItems.length">
              <div class="nav-separator"></div>
              <router-link
                v-for="si in libSubItems"
                :key="si.path"
                :to="si.path"
                class="sub-nav-item sub-nav-item-deeper"
              >
                <span class="nav-icon">{{ si.icon }}</span>
                <span class="nav-label">{{ si.label }}</span>
              </router-link>
            </template>
          </div>
        </div>
      </template>

      <!-- 平级菜单 -->
      <template v-else>
        <router-link
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
import { ref, computed, watch } from "vue";
import { useRoute } from "vue-router";
import api from "../api/index.js";

const route = useRoute();

// 文档库子菜单的动态树数据
const libTree = ref(null);
const libTreeLoading = ref(false);
const libTreeCategory = ref('');

async function loadLibTree(category) {
  if (libTreeLoading.value && libTreeCategory.value === category) return;
  libTreeLoading.value = true;
  libTreeCategory.value = category;
  try {
    const data = await api(`/api/library?category=${encodeURIComponent(category)}`);
    libTree.value = data.sections || [];
  } catch {
    libTree.value = [];
  } finally {
    libTreeLoading.value = false;
  }
}

// 将 library tree section 转为扁平的子菜单项
const libSubItems = computed(() => {
  if (!libTree.value) return [];
  const items = [];
  for (const section of libTree.value) {
    for (const group of (section.groups || [])) {
      if (group.source) {
        items.push({
          label: group.source,
          icon: group.type === 'web' ? '🌐' : '📁',
          path: `/library?category=${encodeURIComponent(libTreeCategory.value)}&source=${encodeURIComponent(group.source || '')}`,
        });
      }
    }
  }
  return items;
});

// expanded: 当前展开的父级（同一时间只有一个）
const expanded = ref({});

// 根据当前路由自动展开对应父级
function expandForRoute(path) {
  if (path.startsWith('/sync/')) return { '/sync/control': true };
  if (path.startsWith('/admin/')) return { '/admin/dashboard': true };
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
        { label: "原始素材", icon: "📦", path: "/library?category=source", loadTree: "source" },
        { label: "学习摘要", icon: "📝", path: "/library?category=summary", loadTree: "summary" },
        { label: "问答沉淀", icon: "💬", path: "/library?category=query", loadTree: "query" },
      ],
    },
    { label: "知识查询", icon: "💡", path: "/qa" },
    {
      label: "同步运维",
      icon: "🔄",
      path: "/sync/control",
      children: [
        { label: "同步控制", icon: "📊", path: "/sync/control" },
        { label: "素材管理", icon: "📦", path: "/sync/sources" },
        { label: "仓库管理", icon: "🏪", path: "/sync/vault" },
        { label: "规则约束", icon: "📋", path: "/sync/purpose", admin: true },
        { label: "审计", icon: "📜", path: "/sync/audit", admin: true },
      ],
    },
    { label: "Wiki 图谱", icon: "🕸", path: "/graph" },
  ];

  // Admin-only links
  if (isAdmin.value) {
    items.push({
      label: "系统管理",
      icon: "⚙️",
      path: "/admin/dashboard",
      children: [
        { label: "系统概览", icon: "📊", path: "/admin/dashboard" },
        { label: "用户管理", icon: "👥", path: "/admin/users" },
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
.sub-nav-item-deeper {
  padding-left: 48px;
  font-size: 0.78rem;
}
.nav-separator {
  height: 1px;
  background: var(--border-muted);
  margin: 2px 8px;
}

.sidebar-spacer {
  flex: 1;
}
</style>
