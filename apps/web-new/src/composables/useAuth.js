import { ref, computed } from "vue";
import api, { setOnUnauthorized, clearAuthCookies } from "../api/index.js";

const isLoggedIn = ref(false);
const userRole = ref("");
const displayName = ref("");
const canWrite = computed(() => userRole.value === "admin");

export function useAuth() {
  async function login(username, password, rememberMe = false) {
    const data = await api("/api/login", {
      method: "POST",
      body: { username, password, remember_me: rememberMe },
    });
    isLoggedIn.value = true;
    userRole.value = data.role || "admin";
    displayName.value = data.display_name || username;
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
    displayName.value = "";
  }

  async function checkSession() {
    try {
      const data = await api("/api/auth-mode");
      isLoggedIn.value = data.authenticated || false;
      userRole.value = data.role || "";
      displayName.value = data.display_name || data.username || "";
      return true;
    } catch {
      isLoggedIn.value = false;
      userRole.value = "";
      displayName.value = "";
      return false;
    }
  }

  async function updateDisplayName(name) {
    await api("/api/user/display-name", {
      method: "PUT",
      body: { display_name: name },
    });
    displayName.value = name;
  }

  function forceLogout() {
    clearAuthCookies();
    isLoggedIn.value = false;
    userRole.value = "";
    displayName.value = "";
  }

  // Register global 401 handler
  setOnUnauthorized(() => {
    isLoggedIn.value = false;
    userRole.value = "";
    displayName.value = "";
  });

  return { isLoggedIn, userRole, displayName, canWrite, login, logout, checkSession, updateDisplayName, forceLogout };
}
