<template>
  <div class="app-shell" :data-auth="authState" :data-role="role">
    <!-- Session 验证中：什么都不显示，避免闪烁 -->
    <div v-if="checkingSession" class="app-boot"></div>

    <!-- Login screen -->
    <div v-else-if="!isLoggedIn" class="login-screen">
      <div class="login-card">
        <h1 class="login-title">mind-sync</h1>
        <p class="login-subtitle">个人学习知识库</p>
        <form @submit.prevent="handleLogin">
          <div class="field">
            <input
              v-model="username"
              type="text"
              placeholder="用户名（默认留空）"
              autocomplete="username"
            />
          </div>
          <div class="field">
            <input
              v-model="password"
              type="password"
              placeholder="密码"
              autocomplete="current-password"
            />
          </div>
          <label class="checkbox-row" style="margin-bottom: 12px;">
            <input v-model="rememberMe" type="checkbox" />
            记住我（30 天内免登录）
          </label>
          <p v-if="loginError" class="login-error">{{ loginError }}</p>
          <button type="submit" class="btn btn-primary btn-full" :disabled="loggingIn">
            {{ loggingIn ? "登录中…" : "登录" }}
          </button>
        </form>
      </div>
    </div>

    <!-- App -->
    <template v-else-if="isLoggedIn">
      <aside class="sidebar">
        <AppSidebar :user-role="role" />
      </aside>
      <header class="topbar">
        <div class="topbar-left">
          <span class="topbar-title">mind-sync</span>
          <span class="topbar-path">{{ currentRoute }}</span>
        </div>
        <div class="topbar-right">
          <span class="badge" :class="badgeClass">{{ badgeLabel }}</span>
          <router-link to="/account" class="btn btn-ghost btn-sm">{{ displayName || '账户' }}</router-link>
          <button class="btn btn-ghost btn-sm" @click="handleLogout">登出</button>
        </div>
      </header>
      <NotifyBar />
      <main class="content">
        <router-view v-slot="{ Component, route: r }">
          <!-- 注：之前用 <transition> 导致 route transitionend 不触发，组件挂载卡死 -->
          <component :is="Component" :key="$route.fullPath" />
        </router-view>
      </main>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useAuth } from "./composables/useAuth.js";
import AppSidebar from "./components/AppSidebar.vue";
import NotifyBar from "./components/NotifyBar.vue";

const route = useRoute();
const router = useRouter();
const { isLoggedIn, userRole, canWrite, displayName, login, logout, checkSession } = useAuth();

const username = ref("");
const password = ref("");
const rememberMe = ref(false);
const loggingIn = ref(false);
const loginError = ref("");

const LAST_PAGE_KEY = "mind_sync_last_page";

// 保存当前路由到 localStorage
// 路由守卫：拦截非管理员访问管理页面
router.beforeEach((to) => {
  if (to.meta.adminOnly && isLoggedIn.value && userRole.value !== "admin") {
    return { path: "/library", query: { denied: to.path } };
  }
});

watch(
  () => route.path,
  (path) => {
    if (path && path !== "/") {
      localStorage.setItem(LAST_PAGE_KEY, path);
    }
  }
);

// 登录后跳转到上次页面
function navigateToLastPage() {
  const saved = localStorage.getItem(LAST_PAGE_KEY);
  const target = saved && saved !== "/" ? saved : "/library";
  router.push(target);
}
const checkingSession = ref(true);

const authState = computed(() => {
  if (checkingSession.value) return "checking";
  return isLoggedIn.value ? "session" : "guest";
});
const role = computed(() => (isLoggedIn.value ? userRole.value : ""));
const currentRoute = computed(() => route.meta?.title || "");
const badgeLabel = computed(() => {
  if (!isLoggedIn.value) return "未登录";
  return canWrite.value ? "管理员" : "只读";
});
const badgeClass = computed(() => ({
  badge: true,
  "badge-success": canWrite.value,
}));

async function handleLogin() {
  loggingIn.value = true;
  loginError.value = "";
  try {
    await login(username.value, password.value, rememberMe.value);
    navigateToLastPage();
  } catch (e) {
    loginError.value = e.message || "登录失败";
  } finally {
    loggingIn.value = false;
  }
}

async function handleLogout() {
  await logout();
}



onMounted(async () => {
  try {
    await checkSession();
    // 已登录则跳转到上次页面
    if (isLoggedIn.value) {
      navigateToLastPage();
    }
  } catch {
    // not logged in
  } finally {
    checkingSession.value = false;
  }
});
</script>

<style scoped>
.app-shell {
  display: grid;
  grid-template-columns: var(--sidebar-width) 1fr;
  grid-template-rows: var(--topbar-height) 1fr;
  height: 100vh;
  overflow: hidden;
}

.sidebar {
  grid-row: 1 / -1;
  grid-column: 1;
  background: var(--bg-sidebar);
  border-right: 1px solid var(--border-default);
  overflow-y: auto;
  padding: 8px;
}

.topbar {
  grid-row: 1;
  grid-column: 2;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  border-bottom: 1px solid var(--border-default);
  background: var(--bg-default);
  gap: 12px;
}

.topbar-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.topbar-title {
  font-weight: 600;
  font-size: 0.95rem;
  color: var(--fg-muted);
}

.topbar-path {
  font-size: 0.85rem;
  color: var(--fg-subtle);
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.content {
  grid-row: 2;
  grid-column: 2;
  overflow-y: auto;
  padding: 24px 32px;
  background: var(--bg-default);
}

/* Login screen */
.login-screen {
  grid-column: 1 / -1;
  grid-row: 1 / -1;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-muted);
}

.login-card {
  background: var(--bg-card);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  padding: 40px 36px;
  width: 360px;
  box-shadow: var(--shadow-lg);
}

.login-title {
  font-size: 1.5rem;
  font-weight: 700;
  text-align: center;
  margin-bottom: 4px;
}

.login-subtitle {
  text-align: center;
  color: var(--fg-muted);
  font-size: 0.9rem;
  margin-bottom: 24px;
}

.field {
  margin-bottom: 12px;
}
.field input {
  width: 100%;
  padding: 10px 12px;
}

.app-boot {
  grid-column: 1 / -1;
  grid-row: 1 / -1;
  background: var(--bg-default);
}
.login-error {
  color: var(--danger-fg);
  font-size: 0.85rem;
  margin-bottom: 8px;
}
</style>
