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
          <button class="btn btn-ghost btn-sm notify-bell" @click="showNotices = !showNotices" v-if="notifyCount > 0">
            🔔<span class="bell-badge">{{ notifyCount }}</span>
          </button>
          <router-link to="/account" class="btn btn-ghost btn-sm">{{ displayName || '账户' }}</router-link>
          <button class="btn btn-ghost btn-sm" @click="handleLogout">登出</button>
        </div>
      </header>
      <NotifyBar />
      <Toast />
      <main class="content">
        <router-view v-slot="{ Component }">
          <keep-alive>
            <component :is="Component" />
          </keep-alive>
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
import Toast from "./components/Toast.vue";

const route = useRoute();
const router = useRouter();
const { isLoggedIn, userRole, canWrite, displayName, login, logout, checkSession } = useAuth();

const username = ref("");
const password = ref("");
const rememberMe = ref(false);
const loggingIn = ref(false);
const loginError = ref("");

// 按用户隔离 localStorage key，避免不同用户登录记录共享
function pageKey() { return displayName.value ? `mind_sync_last_page_${displayName.value}` : "mind_sync_last_page"; }
function docKey()  { return displayName.value ? `mind_sync_last_doc_${displayName.value}`  : "mind_sync_last_doc"; }

// 保存当前路由到 localStorage
// 路由守卫：拦截非管理员访问管理页面
router.beforeEach((to) => {
  if (to.meta.adminOnly && isLoggedIn.value && userRole.value !== "admin") {
    return { path: "/library", query: { denied: to.path } };
  }
});

watch(
  () => route.fullPath,
  (fullPath) => {
    if (fullPath && fullPath !== "/") {
      localStorage.setItem(pageKey(), fullPath);
      // 保存 doc 参数
      if (route.query.doc) {
        localStorage.setItem(docKey(), route.query.doc);
      }
    }
  }
);

// 登录后跳转到上次页面，受限路径非管理员回退到 /library
function navigateToLastPage() {
  const saved = localStorage.getItem(pageKey());
  const target = saved && saved !== "/" ? saved : "/library";
  const resolved = router.resolve(target);
  if (resolved.meta?.adminOnly && userRole.value !== "admin") {
    router.push("/library");
    return;
  }
  router.push(target);
}

// 页面加载时恢复 doc（用于服务器重启后保持）
onMounted(async () => {
  try {
    await checkSession();
    if (isLoggedIn.value) {
      // 如果路由没有 doc 参数但有缓存的 doc，尝试恢复
      if (!route.query.doc) {
        const cachedDoc = localStorage.getItem(docKey());
        if (cachedDoc && route.path === "/library") {
          router.replace(`/library?doc=${cachedDoc}`);
          return;
        }
      }
      navigateToLastPage();
    }
  } catch {
    // not logged in
  } finally {
    checkingSession.value = false;
  }
});
const notifyCount = ref(0);

window.addEventListener("mind-notify-count", (e) => {
  notifyCount.value = e.detail.count || 0;
});

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
  router.push("/library");
}
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
  min-height: 100%;
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
.notify-bell {
  position: relative;
  font-size: 1.1rem;
}
.bell-badge {
  position: absolute;
  top: -4px;
  right: -6px;
  background: var(--danger-fg, #dc2626);
  color: #fff;
  font-size: 0.65rem;
  min-width: 16px;
  height: 16px;
  line-height: 16px;
  border-radius: 8px;
  text-align: center;
  padding: 0 4px;
}
.login-error {
  color: var(--danger-fg);
  font-size: 0.85rem;
  margin-bottom: 8px;
}
</style>
