import { ref, computed, onMounted } from "vue";
import api, { setOnUnauthorized, clearAuthCookies } from "../api/index.js";

const isLoggedIn = ref(false);
const userRole = ref("");
const canWrite = computed(() => userRole.value === "admin");

export function useAuth() {
  async function login(username, password, rememberMe = false) {
    const data = await api("/api/login", {
      method: "POST",
      body: { username, password, remember_me: rememberMe },
    });
    isLoggedIn.value = true;
    userRole.value = data.role || "admin";
    return data;
  }

  async function logout() {
    clearAuthCookies();
    try {
      await api("/api/logout", { method: "POST" });
    } catch {
      // ignore
    }
    isLoggedIn.value = false;
    userRole.value = "";
  }

  async function checkSession() {
    try {
      const data = await api("/api/auth-mode");
      isLoggedIn.value = data.authenticated || false;
      userRole.value = data.role || "";
      return true;
    } catch {
      isLoggedIn.value = false;
      userRole.value = "";
      return false;
    }
  }

  function forceLogout() {
    clearAuthCookies();
    isLoggedIn.value = false;
    userRole.value = "";
  }

  // Register global 401 handler
  setOnUnauthorized(() => {
    isLoggedIn.value = false;
    userRole.value = "";
  });

  return { isLoggedIn, userRole, canWrite, login, logout, checkSession, forceLogout };
}
