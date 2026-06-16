<template>
  <nav class="sidebar-nav" @mouseleave="onNavLeave">
    <!-- 按指定顺序渲染：每个父级紧接其子菜单 -->
    <template v-for="item in orderedItems" :key="item.path">
      <!-- 父级菜单（带子项） -->
      <template v-if="item.children">
        <div
          class="nav-group"
          @mouseenter="onParentEnter(item.path)"
          @mouseleave="onParentLeave(item.path)"
        >
          <router-link
            :to="item.path"
            class="nav-item parent"
            :class="{ active: isActive(item.path) }"
            @click="onParentClick(item.path)"
          >
            <span class="nav-icon">{{ item.icon }}</span>
            <span class="nav-label">{{ item.label }}</span>
            <span class="nav-chevron">{{ hovered === item.path || expanded[item.path] ? "▾" : "▸" }}</span>
          </router-link>
          <div
            v-if="hovered === item.path || expanded[item.path]"
            class="sub-nav"
          >
            <router-link
              v-for="child in item.children"
              :key="child.path"
              :to="child.path"
              class="sub-nav-item"
              :class="{ active: isActive(child.path) }"
            >
              <span class="nav-icon">{{ child.icon }}</span>
              <span class="nav-label">{{ child.label }}</span>
            </router-link>
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
import { ref, computed } from "vue";
import { useRoute } from "vue-router";

const route = useRoute();

// hovered: 鼠标悬停展开的父级（自动收起）
// expanded: 点击锁定的父级（点其他父级或切页面时解锁）
const hovered = ref(null);
const expanded = ref({});
const leaveTimer = ref(null);

const props = defineProps({
  userRole: { type: String, default: "" },
});

const isAdmin = computed(() => props.userRole === "admin");

const orderedItems = computed(() => {
  const items = [
    {
      label: "文档库",
      icon: "📚",
      path: "/library",
      children: [
        { label: "全部文档", icon: "📄", path: "/library" },
      ],
    },
    { label: "搜索", icon: "🔍", path: "/search" },
    { label: "知识查询", icon: "💡", path: "/qa" },
    {
      label: "同步运维",
      icon: "🔄",
      path: "/sync/control",
      children: [
        { label: "同步控制", icon: "📊", path: "/sync/control" },
        { label: "素材管理", icon: "📦", path: "/sync/sources" },
        { label: "仓库管理", icon: "🏪", path: "/sync/vault" },
        { label: "规则约束", icon: "📋", path: "/sync/purpose" },
        { label: "审计", icon: "📜", path: "/sync/audit" },
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

function onParentEnter(path) {
  if (leaveTimer.value) clearTimeout(leaveTimer.value);
  // 关闭其他父级的 hover
  if (hovered.value && hovered.value !== path) {
    hovered.value = null;
  }
  hovered.value = path;
}

function onParentLeave(path) {
  // 延迟收起，避免移入子菜单时闪烁
  leaveTimer.value = setTimeout(() => {
    if (hovered.value === path && !expanded.value[path]) {
      hovered.value = null;
    }
  }, 200);
}

function onParentClick(path) {
  // 点击锁定展开，同时清除 hover 状态
  const isCurrentlyLocked = expanded.value[path];
  // 清除所有锁定
  expanded.value = {};
  hovered.value = null;
  if (!isCurrentlyLocked) {
    expanded.value[path] = true;
  }
}

function onNavLeave() {
  if (leaveTimer.value) clearTimeout(leaveTimer.value);
  // 没有锁定时收起所有 hover 展开
  for (const key of Object.keys(expanded.value)) {
    if (!expanded.value[key]) continue;
    return; // 有锁定项，不收起
  }
  hovered.value = null;
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

.sidebar-spacer {
  flex: 1;
}
</style>
