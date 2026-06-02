/** Shared DOM state, API wrapper, modals (loaded before feature modules). */
const loginBtn = document.getElementById("loginBtn");
const syncBtn = document.getElementById("syncBtn");
const searchBtn = document.getElementById("searchBtn");
const pwdInput = document.getElementById("pwd");
const qInput = document.getElementById("q");
const categoryFilter = document.getElementById("categoryFilter");
const topicFilter = document.getElementById("topicFilter");
const sourceFilter = document.getElementById("sourceFilter");
const typeFilter = document.getElementById("typeFilter");
const askInput = document.getElementById("askQ");
const askBtn = document.getElementById("askBtn");
const saveInsight = document.getElementById("saveInsight");
const askMeta = document.getElementById("askMeta");
const askHint = document.getElementById("askHint");
const askAnswer = document.getElementById("askAnswer");
const evidenceList = document.getElementById("evidenceList");
const settingsBtn = document.getElementById("settingsBtn");
const accountBtn = document.getElementById("accountBtn");
const settingsModal = document.getElementById("settingsModal");
const accountModal = document.getElementById("accountModal");
const loginModal = document.getElementById("loginModal");
const closeSettingsBtn = document.getElementById("closeSettingsBtn");
const closeAccountBtn = document.getElementById("closeAccountBtn");
const logoutBtn = document.getElementById("logoutBtn");
const saveSettingsBtn = document.getElementById("saveSettingsBtn");
const autoSyncEnabled = document.getElementById("autoSyncEnabled");
const autoSyncInterval = document.getElementById("autoSyncInterval");
const settingsStatus = document.getElementById("settingsStatus");
const purposeEditor = document.getElementById("purposeEditor");
const purposeStatus = document.getElementById("purposeStatus");
const savePurposeBtn = document.getElementById("savePurposeBtn");
const browseBtn = document.getElementById("browseBtn");
const browseList = document.getElementById("browseList");
const browseTitle = document.getElementById("browseTitle");
const auditListTitle = document.getElementById("auditListTitle");
const refreshAuditBtn = document.getElementById("refreshAuditBtn");
const auditStatus = document.getElementById("auditStatus");
const auditList = document.getElementById("auditList");
const accountModeText = document.getElementById("accountModeText");
const authBadge = document.getElementById("authBadge");
const loginStatus = document.getElementById("loginStatus");
const nextAutoSyncText = document.getElementById("nextAutoSyncText");
const lastAutoSyncText = document.getElementById("lastAutoSyncText");
const syncProgressText = document.getElementById("syncProgressText");
const lastSyncSummaryText = document.getElementById("lastSyncSummaryText");
const runLintBtn = document.getElementById("runLintBtn");
const lintStatus = document.getElementById("lintStatus");
const lintSummary = document.getElementById("lintSummary");
const results = document.getElementById("results");
const docMeta = document.getElementById("docMeta");
const docContent = document.getElementById("docContent");
const graphSummary = document.getElementById("graphSummary");
const graphMeta = document.getElementById("graphMeta");
const refreshGraphBtn = document.getElementById("refreshGraphBtn");
const graphCanvas = document.getElementById("graphCanvas");
const graphFilterInput = document.getElementById("graphFilterInput");
const graphMinDegreeSelect = document.getElementById("graphMinDegreeSelect");
const graphResetLayoutBtn = document.getElementById("graphResetLayoutBtn");
const graphListTitle = document.getElementById("graphListTitle");
const graphUnifiedList = document.getElementById("graphUnifiedList");
const graphViewTopBtn = document.getElementById("graphViewTopBtn");
const graphViewOrphanBtn = document.getElementById("graphViewOrphanBtn");
const graphViewHubBtn = document.getElementById("graphViewHubBtn");
const docNav = document.getElementById("docNav");
const prevMatchBtn = document.getElementById("prevMatchBtn");
const nextMatchBtn = document.getElementById("nextMatchBtn");
const matchCount = document.getElementById("matchCount");
const GRAPH_VIEW_STORAGE_KEY = "mindsync.graph.view";
const PANEL_COLLAPSE_KEY_PREFIX = "mindsync.panel.";
let CSRF_HEADER_NAME = "x-csrf-token";
let autoSyncTimer = null;
let currentSearchTerm = "";
let currentMatchIndex = -1;
let graphTimer = null;
let currentGraphData = null;
let currentGraphView = "top";
let graphRenderState = null;
let graphAnimId = null;
let graphFilterKeyword = "";
let graphFilterMinDegree = 0;
let isLoggedIn = false;
let canWrite = true;
let userRole = "admin";
let activeModal = null;
try {
  const saved = localStorage.getItem(GRAPH_VIEW_STORAGE_KEY);
  if (saved === "top" || saved === "orphan" || saved === "hub") {
    currentGraphView = saved;
  }
} catch (_) {
  // ignore storage access errors
}

function setStatus(text) {
  loginStatus.textContent = text;
}

function readCookie(name) {
  if (window.MindSyncApi?.readCookie) return window.MindSyncApi.readCookie(name);
  const raw = document.cookie || "";
  const parts = raw.split(";").map((p) => p.trim());
  const prefix = `${name}=`;
  for (const item of parts) {
    if (item.startsWith(prefix)) {
      return decodeURIComponent(item.slice(prefix.length));
    }
  }
  return "";
}

function clearClientSessionCookies() {
  document.cookie = "ms_csrf=; Max-Age=0; path=/";
}
function openModal(modal) {
  if (!modal) return;
  modal.classList.remove("hidden");
  activeModal = modal;
  const focusTarget = modal.querySelector("input, button, select, textarea");
  if (focusTarget) {
    setTimeout(() => focusTarget.focus(), 0);
  }
}

function closeModal(modal) {
  if (!modal) return;
  modal.classList.add("hidden");
  if (activeModal === modal) activeModal = null;
}

function closeTransientModals() {
  closeModal(settingsModal);
  closeModal(accountModal);
}

function getTopTransientModal() {
  if (accountModal && !accountModal.classList.contains("hidden")) return accountModal;
  if (settingsModal && !settingsModal.classList.contains("hidden")) return settingsModal;
  return null;
}

function trapModalFocus(modal, event) {
  if (!modal || modal.classList.contains("hidden")) return;
  const items = [...modal.querySelectorAll("input, button, select, textarea, [tabindex]:not([tabindex='-1'])")]
    .filter((el) => !el.disabled);
  if (!items.length) return;
  const first = items[0];
  const last = items[items.length - 1];
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}

function setPanelCollapsed(panelId, collapsed) {
  const panel = document.querySelector(`.panel[data-panel-id="${panelId}"]`);
  if (!panel) return;
  panel.classList.toggle("collapsed", !!collapsed);
  const btn = panel.querySelector(".panel-toggle");
  if (btn) {
    btn.textContent = collapsed ? "展开" : "收起";
  }
  try {
    localStorage.setItem(`${PANEL_COLLAPSE_KEY_PREFIX}${panelId}`, collapsed ? "1" : "0");
  } catch (_) {
    // ignore storage errors
  }
  if (panelId === "graph" && currentGraphData) {
    if (collapsed) {
      stopGraphAnimation();
    } else {
      renderGraph(currentGraphData);
    }
  }
}

function initPanelCollapse() {
  const buttons = document.querySelectorAll(".panel-toggle[data-panel-target]");
  buttons.forEach((btn) => {
    const panelId = btn.getAttribute("data-panel-target");
    if (!panelId) return;
    let collapsed = false;
    try {
      collapsed = localStorage.getItem(`${PANEL_COLLAPSE_KEY_PREFIX}${panelId}`) === "1";
    } catch (_) {
      collapsed = false;
    }
    setPanelCollapsed(panelId, collapsed);
    btn.onclick = () => {
      const panel = document.querySelector(`.panel[data-panel-id="${panelId}"]`);
      if (!panel) return;
      const next = !panel.classList.contains("collapsed");
      setPanelCollapsed(panelId, next);
    };
  });
}
async function api(path, options = {}) {
  if (window.MindSyncApi?.api) {
    try {
      return await window.MindSyncApi.api(path, options);
    } catch (e) {
      if (e.status === 401 && path !== "/api/login") {
        clearClientSessionCookies();
        setAuthUI(false);
        setStatus("登录已失效，请重新登录");
      }
      throw e;
    }
  }
  const method = String(options.method || "GET").toUpperCase();
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
    const csrfToken = readCookie("ms_csrf");
    if (csrfToken) headers[CSRF_HEADER_NAME] = csrfToken;
  }
  const res = await fetch(path, { ...options, method, headers, credentials: "include" });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    if (res.status === 401 && path !== "/api/login") {
      clearClientSessionCookies();
      setAuthUI(false);
      setStatus("登录已失效，请重新登录");
    }
    throw new Error(data.detail || `HTTP ${res.status}`);
  }
  return data;
}

function renderSimpleMarkdown(text) {
  if (!text) return "";
  const escaped = escapeHtml(text);
  return escaped
    .replace(/^###\s+(.*)$/gm, "<h4>$1</h4>")
    .replace(/^##\s+(.*)$/gm, "<h3>$1</h3>")
    .replace(/^#\s+(.*)$/gm, "<h2>$1</h2>")
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\n/g, "<br/>");
}

window.onclick = (e) => {
  if (e.target === settingsModal || e.target === accountModal) {
    closeTransientModals();
  }
};
