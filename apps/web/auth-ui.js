/** Authentication UI (depends on app-shared.js). */
function applyWritePermissions() {
  const hideWhenReadonly = [
    syncBtn,
    document.getElementById("rebuildBtn"),
    runLintBtn,
    document.getElementById("reloadSourcesBtn"),
  ];
  hideWhenReadonly.forEach((el) => {
    if (!el) return;
    el.classList.toggle("hidden", !canWrite);
    if (canWrite) el.removeAttribute("disabled");
    else el.setAttribute("disabled", "true");
  });
  const writeControls = [
    saveSettingsBtn,
    savePurposeBtn,
    document.getElementById("vaultPullBtn"),
    document.getElementById("vaultPushBtn"),
    saveInsight,
  ];
  writeControls.forEach((el) => {
    if (!el) return;
    if (canWrite) el.removeAttribute("disabled");
    else el.setAttribute("disabled", "true");
  });
  if (purposeEditor) purposeEditor.readOnly = !canWrite;
  const saveInsightRow = saveInsight?.closest(".checkbox-row");
  if (saveInsightRow) saveInsightRow.classList.toggle("hidden", !canWrite);
  document.querySelectorAll(".settings-pane input, .settings-pane textarea, .settings-pane select, .settings-pane button")
    .forEach((el) => {
      if (!el.id || el.id === "closeSettingsBtn") return;
      if (el.classList.contains("settings-tab")) return;
      if (canWrite) el.removeAttribute("disabled");
      else if (el.tagName !== "BUTTON" || el.id !== "refreshAuditBtn") el.setAttribute("disabled", "true");
    });
  window.MindSyncAuth = { canWrite, role: userRole, applyWritePermissions };
  if (window.MindSyncWikiEditor?.refreshEditBar) {
    window.MindSyncWikiEditor.refreshEditBar();
  }
}

function setAuthUI(loggedIn, opts = {}) {
  isLoggedIn = !!loggedIn;
  if (opts.canWrite !== undefined) canWrite = !!opts.canWrite;
  if (opts.role) userRole = opts.role;
  document.documentElement.dataset.auth = loggedIn ? "session" : "guest";
  document.documentElement.dataset.role = loggedIn ? userRole : "";
  if (!loggedIn) clearClientSessionCookies();
  const loginScreen = document.getElementById("loginScreen");
  const appRoot = document.getElementById("appRoot");
  if (loggedIn) {
    loginScreen?.classList.add("hidden");
    appRoot?.classList.remove("hidden");
  } else {
    loginScreen?.classList.remove("hidden");
    appRoot?.classList.add("hidden");
  }
  authBadge.textContent = isLoggedIn ? (canWrite ? "管理员" : "只读") : "未登录";
  authBadge.className = isLoggedIn ? (canWrite ? "badge badge-success" : "badge") : "badge";
  authBadge.title = isLoggedIn
    ? (canWrite ? "可编辑 Wiki、同步与 Vault" : "仅浏览与问答，不可写入")
    : "";
  const gated = [
    syncBtn,
    searchBtn,
    askBtn,
    settingsBtn,
    accountBtn,
    qInput,
    askInput,
    sourceFilter,
    typeFilter,
    categoryFilter,
    topicFilter,
    browseBtn,
    document.getElementById("globalSearch"),
  ];
  gated.forEach((el) => {
    if (!el) return;
    el.disabled = !isLoggedIn;
  });
  if (isLoggedIn) applyWritePermissions();
}

async function bootstrapAuthState() {
  try {
    const auth = await api("/api/auth-mode");
    if (auth && typeof auth.csrf_header === "string" && auth.csrf_header.trim()) {
      CSRF_HEADER_NAME = auth.csrf_header.trim().toLowerCase();
      window.MindSyncApi?.setCsrfHeaderName?.(CSRF_HEADER_NAME);
    }
    canWrite = auth?.can_write !== false;
    userRole = auth?.role || "admin";
    window.MindSyncSearch?.renderDatalist?.(document.getElementById("searchHistoryList"));
    setAuthUI(true, { canWrite, role: userRole });
    await loadSourcesFilter();
    await loadCategoriesFilter();
    await loadSettings();
    await loadSyncStatus();
    await loadWikiGraph();
    if (autoSyncTimer) clearInterval(autoSyncTimer);
    autoSyncTimer = setInterval(() => {
      loadSettings();
      loadSyncStatus();
    }, 15000);
    if (graphTimer) clearInterval(graphTimer);
    startGraphPolling();
    setStatus("已恢复登录状态");
  } catch (_) {
    clearClientSessionCookies();
    setAuthUI(false);
  }
}
