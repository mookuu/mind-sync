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

function setAuthUI(loggedIn) {
  isLoggedIn = !!loggedIn;
  document.documentElement.dataset.auth = loggedIn ? "session" : "guest";
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
  authBadge.textContent = isLoggedIn ? "已登录" : "未登录";
  authBadge.className = isLoggedIn ? "badge badge-success" : "badge";
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
}

async function bootstrapAuthState() {
  try {
    const auth = await api("/api/auth-mode");
    if (auth && typeof auth.csrf_header === "string" && auth.csrf_header.trim()) {
      CSRF_HEADER_NAME = auth.csrf_header.trim().toLowerCase();
      window.MindSyncApi?.setCsrfHeaderName?.(CSRF_HEADER_NAME);
    }
    window.MindSyncSearch?.renderDatalist?.(document.getElementById("searchHistoryList"));
    setAuthUI(true);
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

function escapeHtml(text) {
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function escapeRegExp(text) {
  return String(text).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

const PUNCT_EQUIVALENTS = {
  ",": ["，", ",", "、"],
  ".": [".", "。", "．"],
  "!": ["!", "！"],
  "?": ["?", "？"],
  ":": [":", "："],
  ";": [";", "；"],
  "(": ["(", "（"],
  ")": [")", "）"],
  "[": ["[", "【", "［"],
  "]": ["]", "】", "］"],
  '"': ['"', "\u201c", "\u201d", "「", "」"],
  "'": ["'", "\u2018", "\u2019", "『", "』"],
  "-": ["-", "—", "－", "–"],
  "/": ["/", "／"],
  "\\": ["\\", "＼"],
};

const CHINESE_TO_ASCII = {
  "，": ",",
  "、": ",",
  "。": ".",
  "．": ".",
  "！": "!",
  "？": "?",
  "：": ":",
  "；": ";",
  "（": "(",
  "）": ")",
  "【": "[",
  "】": "]",
  "「": '"',
  "」": '"',
  "『": "'",
  "』": "'",
  "《": "<",
  "》": ">",
  "—": "-",
  "…": "...",
  "\u201c": '"',
  "\u201d": '"',
  "\u2018": "'",
  "\u2019": "'",
};

function toHalfWidthChar(ch) {
  const code = ch.charCodeAt(0);
  if (code === 0x3000) return " ";
  if (code >= 0xff01 && code <= 0xff5e) return String.fromCharCode(code - 0xfee0);
  return ch;
}

function normalizeCharForSearch(ch) {
  let c = toHalfWidthChar(ch);
  if (CHINESE_TO_ASCII[c]) c = CHINESE_TO_ASCII[c];
  return c.toLowerCase();
}

function variantsForChar(ch) {
  const norm = normalizeCharForSearch(ch);
  const variants = new Set([ch, toHalfWidthChar(ch)]);
  for (const [canonical, alts] of Object.entries(PUNCT_EQUIVALENTS)) {
    const canonicalNorm = normalizeCharForSearch(canonical);
    if (norm === canonicalNorm || alts.some((alt) => normalizeCharForSearch(alt) === norm)) {
      variants.add(canonical);
      for (const alt of alts) variants.add(alt);
    }
  }
  if (norm.length === 1) {
    const code = norm.charCodeAt(0);
    if (code >= 0x21 && code <= 0x7e) {
      variants.add(String.fromCharCode(code + 0xfee0));
    }
    if (code >= 0x41 && code <= 0x5a) variants.add(norm.toLowerCase());
    if (code >= 0x61 && code <= 0x7a) variants.add(norm.toUpperCase());
  }
  return [...variants];
}

function buildFlexibleSearchRegex(term) {
  const t = (term || "").trim();
  if (!t) return null;
  try {
    const pattern = [...t]
      .map((ch) => {
        const chars = variantsForChar(ch).map(escapeRegExp).join("");
        return `[${chars}]`;
      })
      .join("");
    return new RegExp(pattern, "g");
  } catch (_) {
    return null;
  }
}

function highlightInElement(container, term) {
  const re = buildFlexibleSearchRegex(term);
  if (!re || !container) return 0;

  const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
  const textNodes = [];
  while (walker.nextNode()) {
    const parent = walker.currentNode.parentElement;
    if (!parent || parent.closest("mark, script, style")) continue;
    textNodes.push(walker.currentNode);
  }

  let total = 0;
  for (const node of textNodes) {
    const text = node.textContent || "";
    re.lastIndex = 0;
    const matches = [];
    let match;
    while ((match = re.exec(text)) !== null) {
      matches.push({
        start: match.index,
        end: match.index + match[0].length,
        text: match[0],
      });
      if (match[0].length === 0) re.lastIndex += 1;
    }
    if (!matches.length) continue;

    const frag = document.createDocumentFragment();
    let last = 0;
    for (const hit of matches) {
      if (hit.start > last) {
        frag.appendChild(document.createTextNode(text.slice(last, hit.start)));
      }
      const mark = document.createElement("mark");
      mark.className = "search-hit";
      mark.textContent = hit.text;
      frag.appendChild(mark);
      last = hit.end;
      total += 1;
    }
    if (last < text.length) {
      frag.appendChild(document.createTextNode(text.slice(last)));
    }
    node.parentNode.replaceChild(frag, node);
  }
  return total;
}

function getSearchMarks() {
  return [...docContent.querySelectorAll("mark.search-hit")];
}

function updateMatchNav() {
  const marks = getSearchMarks();
  if (!marks.length) {
    docNav.classList.add("hidden");
    matchCount.textContent = "0 / 0";
    currentMatchIndex = -1;
    return;
  }
  docNav.classList.remove("hidden");
  if (currentMatchIndex < 0 || currentMatchIndex >= marks.length) {
    currentMatchIndex = 0;
  }
  marks.forEach((mark, idx) => {
    mark.classList.toggle("search-hit-active", idx === currentMatchIndex);
  });
  matchCount.textContent = `${currentMatchIndex + 1} / ${marks.length}`;
}

function scrollToMatch(index) {
  const marks = getSearchMarks();
  if (!marks.length) {
    updateMatchNav();
    return;
  }
  currentMatchIndex = ((index % marks.length) + marks.length) % marks.length;
  marks.forEach((mark, idx) => {
    mark.classList.toggle("search-hit-active", idx === currentMatchIndex);
  });
  matchCount.textContent = `${currentMatchIndex + 1} / ${marks.length}`;
  marks[currentMatchIndex].scrollIntoView({ block: "center", behavior: "smooth" });
}

function refreshGraphIfActive() {
  const graphView = document.getElementById("view-graph");
  if (graphView && graphView.classList.contains("active")) {
    loadWikiGraph();
  }
}

function startGraphPolling() {
  if (graphTimer) clearInterval(graphTimer);
  graphTimer = setInterval(refreshGraphIfActive, 60000);
}

async function runWikiLint() {
  if (!isLoggedIn || !runLintBtn) return;
  runLintBtn.disabled = true;
  if (lintStatus) lintStatus.textContent = "Lint 运行中…";
  if (lintSummary) {
    lintSummary.classList.add("hidden");
    lintSummary.textContent = "";
  }
  try {
    const data = await api("/api/lint", { method: "POST", body: JSON.stringify({ stale_days: 180 }) });
    const issues = data.issues || [];
    const reportPath = data.report_path || data.path || "";
    if (lintStatus) {
      lintStatus.textContent = `Lint 完成：${issues.length} 个问题${reportPath ? ` · 报告 ${reportPath}` : ""}`;
    }
    if (lintSummary) {
      const preview = issues.slice(0, 12).map((item) => `[${item.type}] ${item.source_id}/${item.rel_path} — ${item.detail}`).join("\n");
      lintSummary.textContent = preview || "未发现问题。";
      lintSummary.classList.remove("hidden");
    }
  } catch (e) {
    if (lintStatus) lintStatus.textContent = `Lint 失败: ${e.message}`;
  } finally {
    runLintBtn.disabled = false;
  }
}

function setGraphView(view) {
  currentGraphView = view;
  try {
    localStorage.setItem(GRAPH_VIEW_STORAGE_KEY, view);
  } catch (_) {
    // ignore storage access errors
  }
  graphViewTopBtn.classList.toggle("active", view === "top");
  graphViewOrphanBtn.classList.toggle("active", view === "orphan");
  graphViewHubBtn.classList.toggle("active", view === "hub");
  renderGraphList();
}

function stopGraphAnimation() {
  if (graphAnimId) {
    cancelAnimationFrame(graphAnimId);
    graphAnimId = null;
  }
}

function matchesGraphFilter(node, degreeMap) {
  const key = graphFilterKeyword.trim().toLowerCase();
  const okKeyword = !key || String(node.id || "").toLowerCase().includes(key);
  const degree = degreeMap.get(node.id) || 0;
  return okKeyword && degree >= graphFilterMinDegree;
}

async function openWikiNode(path) {
  const data = await api(`/api/wiki-content?path=${encodeURIComponent(path)}`);
  docMeta.textContent = `wiki / ${data.path} (markdown)`;
  const breadcrumb = document.getElementById("docBreadcrumb");
  if (breadcrumb) breadcrumb.textContent = `wiki / ${data.path}`;
  if (typeof renderWikiMarkdown === "function") {
    renderWikiMarkdown(data.content || "", data.path);
  } else {
    docContent.innerHTML = renderSimpleMarkdown(data.content || "");
  }
  window.MindSyncWikiEditor?.setWikiContext?.(data.path);
  if (typeof switchView === "function") switchView("library");
  docNav.classList.add("hidden");
  matchCount.textContent = "0 / 0";
  currentMatchIndex = -1;
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

const CATEGORY_UI = {
  source: "原始素材",
  summary: "学习摘要",
  query: "问答沉淀",
};

function categoryBadge(cat) {
  const label = CATEGORY_UI[cat] || cat || "";
  if (!label) return "";
  return `<span class="cat-badge cat-${cat}">${label}</span>`;
}

async function loadCategoriesFilter() {
  try {
    const data = await api("/api/categories");
    topicFilter.innerHTML = '<option value="">全部主题</option>';
    for (const t of data.topics || []) {
      const opt = document.createElement("option");
      opt.value = t.id;
      opt.textContent = `${t.label} (${t.count})`;
      topicFilter.appendChild(opt);
    }
    const summaryCat = (data.categories || []).find((c) => c.id === "summary");
    if (summaryCat && browseTitle) {
      browseTitle.textContent = `分类浏览（摘要 ${summaryCat.count} 篇）`;
    }
  } catch (_) {
    // ignore before login
  }
}

async function loadPurposePreview() {
  if (!purposeEditor) return;
  try {
    const data = await api("/api/purpose");
    if (!data.exists) {
      purposeEditor.value = "";
      if (purposeStatus) purposeStatus.textContent = "未找到 purpose.md，保存后将创建";
      return;
    }
    purposeEditor.value = data.content || data.preview || "";
    if (purposeStatus) purposeStatus.textContent = "";
  } catch (e) {
    if (purposeStatus) purposeStatus.textContent = `加载失败: ${e.message}`;
  }
}

async function savePurposeContent() {
  if (!purposeEditor) return;
  try {
    if (purposeStatus) purposeStatus.textContent = "保存中…";
    await api("/api/purpose", {
      method: "POST",
      body: JSON.stringify({ content: purposeEditor.value || "" }),
    });
    if (purposeStatus) purposeStatus.textContent = "已保存";
  } catch (e) {
    if (purposeStatus) purposeStatus.textContent = `保存失败: ${e.message}`;
  }
}

function renderAskAnswer(markdownText) {
  if (!askAnswer) return;
  askAnswer.className = "doc-content doc-markdown ask-answer";
  if (typeof parseMarkdown === "function") {
    askAnswer.innerHTML = parseMarkdown(markdownText || "");
    if (typeof fixMisclassifiedProseBlocks === "function") {
      fixMisclassifiedProseBlocks(askAnswer);
    }
    if (typeof applyImageEnhanceState === "function") {
      applyImageEnhanceState();
    }
    return;
  }
  askAnswer.innerHTML = renderSimpleMarkdown(markdownText || "");
}

async function loadBrowseList() {
  browseList.innerHTML = "";
  try {
    const params = new URLSearchParams({ limit: "40" });
    if (categoryFilter.value) params.set("category", categoryFilter.value);
    if (topicFilter.value) params.set("topic", topicFilter.value);
    const data = await api(`/api/browse?${params.toString()}`);
    const items = data.items || [];
    if (!items.length) {
      const li = document.createElement("li");
      li.textContent = "当前分类下暂无文档";
      browseList.appendChild(li);
      return;
    }
    for (const item of items) {
      const li = document.createElement("li");
      li.innerHTML = `<div>${categoryBadge(item.category)} <b>${item.source_id}</b> / ${item.rel_path}</div>`;
      li.onclick = async () => {
        const doc = await api(`/api/document/${item.id}`);
        if (typeof switchView === "function") switchView("library");
        renderDocumentPreview(doc, "");
      };
      browseList.appendChild(li);
    }
  } catch (e) {
    setStatus(`分类浏览失败: ${e.message}`);
  }
}

async function loadSourcesFilter() {
  try {
    sourceFilter.innerHTML = '<option value="">全部来源</option>';
    const data = await api("/api/sources");
    for (const s of data.sources || []) {
      const opt = document.createElement("option");
      opt.value = s.id;
      opt.textContent = s.id;
      sourceFilter.appendChild(opt);
    }
  } catch (e) {
    // ignore before login
  }
}

async function loadSettings() {
  try {
    const st = await api("/api/settings");
    autoSyncEnabled.checked = !!st.auto_sync_enabled;
    autoSyncInterval.value = st.auto_sync_interval_minutes || 60;
    const nextText = st.next_auto_sync_at
      ? new Date(st.next_auto_sync_at * 1000).toLocaleString()
      : "--";
    nextAutoSyncText.textContent = `下次自动同步时间：${nextText}`;
    const last = st.last_auto_sync || {};
    if (!last.started_at && !last.finished_at) {
      lastAutoSyncText.textContent = `最近一次自动同步状态：${last.status || "idle"}（尚未执行）`;
    } else if (last.status === "running") {
      lastAutoSyncText.textContent = "最近一次自动同步状态：进行中";
    } else {
      const t = last.finished_at ? new Date(last.finished_at * 1000).toLocaleString() : "--";
      const status = last.status || "unknown";
      const detail = last.error
        ? `失败（${last.error}）`
        : `成功（新增/更新 ${last.indexed || 0}，跳过 ${last.skipped || 0}，删除 ${last.deleted || 0}）`;
      lastAutoSyncText.textContent = `最近一次自动同步状态：${status} @ ${t} ${detail}`;
    }
  } catch (e) {
    // ignore before login
  }
}

function formatSyncTrigger(trigger) {
  if (trigger === "auto") return "自动";
  if (trigger === "manual") return "手动";
  return trigger || "未知";
}

function formatSyncCounts(indexed, skipped, deleted) {
  return `新增/更新 ${indexed || 0}，跳过 ${skipped || 0}，删除 ${deleted || 0}`;
}

function renderSyncPanel(status = {}) {
  if (status.running) {
    const src = status.current_source || "准备中";
    const prog = `${status.processed_files || 0}/${status.total_files || 0}`;
    syncProgressText.textContent = `当前同步：${src} (${prog}) — ${formatSyncCounts(
      status.indexed,
      status.skipped,
      status.deleted
    )}`;
    syncProgressText.classList.add("sync-active");
  } else {
    syncProgressText.textContent = "当前同步：空闲";
    syncProgressText.classList.remove("sync-active");
  }

  const last = status.last_completed || {};
  if (!last.finished_at) {
    lastSyncSummaryText.textContent = "最近一次同步：尚未执行";
    return;
  }
  const when = formatAuditTime(last.finished_at);
  const trigger = formatSyncTrigger(last.trigger);
  const counts = formatSyncCounts(last.indexed, last.skipped, last.deleted);
  if (last.status === "failed" || last.error) {
    lastSyncSummaryText.textContent = `最近一次同步：失败（${trigger}） @ ${when} — ${counts}；${last.error || "未知错误"}`;
    return;
  }
  lastSyncSummaryText.textContent = `最近一次同步：成功（${trigger}） @ ${when} — ${counts}`;
}

async function loadSyncStatus() {
  if (!isLoggedIn) return null;
  try {
    const status = await api("/api/sync-status");
    renderSyncPanel(status);
    return status;
  } catch (e) {
    return null;
  }
}

const AUDIT_EVENT_LABELS = {
  login_failed: "登录失败",
  login_success: "登录成功",
  logout: "退出登录",
  settings_updated: "设置变更",
  purpose_updated: "研究方向更新",
  sync_requested: "同步请求",
  sync_completed: "同步完成",
};

function formatAuditEventType(eventType) {
  return AUDIT_EVENT_LABELS[eventType] || eventType || "未知事件";
}

function formatAuditTime(ts) {
  const n = Number(ts);
  if (!Number.isFinite(n) || n <= 0) return "--";
  return new Date(n * 1000).toLocaleString();
}

function renderAuditEvents(items = []) {
  auditList.innerHTML = "";
  auditListTitle.textContent = `最近审计 (${items.length} 条)`;
  if (!items.length) {
    const li = document.createElement("li");
    li.textContent = "暂无审计记录";
    auditList.appendChild(li);
    return;
  }
  for (const item of items) {
    const li = document.createElement("li");
    const eventType = String(item.event_type || "");
    const typeClass = eventType.replace(/[^a-z0-9_]/gi, "");
    li.innerHTML = `
      <div class="audit-top">
        <span class="audit-type ${escapeHtml(typeClass)}">${escapeHtml(formatAuditEventType(eventType))}</span>
        <span class="audit-meta">${escapeHtml(formatAuditTime(item.created_at))}</span>
      </div>
      <div class="audit-meta">${escapeHtml(item.actor || "unknown")} · ${escapeHtml(item.ip || "unknown")}</div>
      <div class="audit-detail">${escapeHtml(item.detail || "")}</div>
    `;
    auditList.appendChild(li);
  }
}

async function loadAuditEvents() {
  if (!isLoggedIn) return;
  auditStatus.textContent = "加载中...";
  try {
    const data = await api("/api/audit-events?limit=30");
    const items = data.items || [];
    renderAuditEvents(items);
    auditStatus.textContent = `显示最近 ${items.length} 条（只读）`;
  } catch (e) {
    auditList.innerHTML = "";
    auditListTitle.textContent = "最近审计";
    auditStatus.textContent = `加载失败: ${e.message}`;
  }
}

async function loadWikiGraph() {
  try {
    const g = await api("/api/wiki-graph");
    currentGraphData = g;
    graphSummary.textContent = `节点: ${g.node_count} | 边: ${g.edge_count}`;
    graphMeta.textContent = `孤儿页: ${g.orphans?.length || 0} | Hub页: ${g.hubs?.length || 0}`;
    renderGraph(g);
    renderGraphList();
  } catch (e) {
    currentGraphData = null;
    stopGraphAnimation();
    graphSummary.textContent = "节点: -- | 边: --";
    graphMeta.textContent = `图谱加载失败: ${e.message}`;
    graphCanvas.innerHTML = "";
    graphUnifiedList.innerHTML = "";
  }
}

function renderGraphList() {
  const g = currentGraphData;
  graphUnifiedList.innerHTML = "";
  const key = graphFilterKeyword.trim().toLowerCase();
  const byKeyword = (path) => !key || String(path || "").toLowerCase().includes(key);
  if (!g) {
    graphListTitle.textContent = "关键节点";
    return;
  }
  if (currentGraphView === "orphan") {
    const list = (g.orphans || []).filter(byKeyword);
    graphListTitle.textContent = `孤儿页 (${list.length})`;
    if (!list.length) {
      const li = document.createElement("li");
      li.textContent = "暂无孤儿页";
      graphUnifiedList.appendChild(li);
      return;
    }
    for (const path of list) {
      const li = document.createElement("li");
      li.innerHTML = `<span>${path}</span><button class="open-node-btn">打开</button>`;
      li.querySelector("button").onclick = async () => {
        try {
          await openWikiNode(path);
        } catch (e) {
          setStatus(`打开孤儿页失败: ${e.message}`);
        }
      };
      graphUnifiedList.appendChild(li);
    }
    return;
  }
  if (currentGraphView === "hub") {
    const list = (g.hubs || []).filter(byKeyword);
    graphListTitle.textContent = `Hub页 (${list.length})`;
    if (!list.length) {
      const li = document.createElement("li");
      li.textContent = "暂无Hub页";
      graphUnifiedList.appendChild(li);
      return;
    }
    for (const path of list) {
      const li = document.createElement("li");
      li.innerHTML = `<span>${path}</span><button class="open-node-btn">打开</button>`;
      li.querySelector("button").onclick = async () => {
        try {
          await openWikiNode(path);
        } catch (e) {
          setStatus(`打开Hub页失败: ${e.message}`);
        }
      };
      graphUnifiedList.appendChild(li);
    }
    return;
  }

  graphListTitle.textContent = "关键节点";
  const nodes = [...(g.nodes || [])]
    .filter((n) => {
      const degree = (n.in_degree || 0) + (n.out_degree || 0);
      return byKeyword(n.id) && degree >= graphFilterMinDegree;
    })
    .sort((a, b) => b.in_degree + b.out_degree - (a.in_degree + a.out_degree))
    .slice(0, 8);
  if (!nodes.length) {
    const li = document.createElement("li");
    li.textContent = "暂无关键节点";
    graphUnifiedList.appendChild(li);
    return;
  }
  for (const n of nodes) {
    const li = document.createElement("li");
    li.innerHTML = `<span>${n.id} (in:${n.in_degree}, out:${n.out_degree})</span><button class="open-node-btn">打开</button>`;
    li.querySelector("button").onclick = async () => {
      try {
        await openWikiNode(n.id);
      } catch (e) {
        setStatus(`打开节点失败: ${e.message}`);
      }
    };
    graphUnifiedList.appendChild(li);
  }
}

function renderGraph(g) {
  stopGraphAnimation();
  const allNodes = (g.nodes || []).slice(0, 90);
  const allNodeIds = new Set(allNodes.map((n) => n.id));
  const allEdges = (g.edges || [])
    .filter((e) => allNodeIds.has(e.source) && allNodeIds.has(e.target))
    .slice(0, 220);

  const degreeMap = new Map();
  for (const n of allNodes) degreeMap.set(n.id, 0);
  for (const e of allEdges) {
    degreeMap.set(e.source, (degreeMap.get(e.source) || 0) + 1);
    degreeMap.set(e.target, (degreeMap.get(e.target) || 0) + 1);
  }

  const filteredNodes = allNodes.filter((n) => matchesGraphFilter(n, degreeMap));
  const filteredNodeIds = new Set(filteredNodes.map((n) => n.id));
  const filteredEdges = allEdges.filter((e) => filteredNodeIds.has(e.source) && filteredNodeIds.has(e.target));

  const canvas = document.createElement("canvas");
  canvas.className = "graph-canvas-el";
  canvas.width = Math.max(graphCanvas.clientWidth || 900, 320);
  canvas.height = 260;
  graphCanvas.innerHTML = "";
  graphCanvas.appendChild(canvas);
  const ctx = canvas.getContext("2d");
  if (!ctx) return;

  const nodeMap = new Map();
  const nodes = filteredNodes.map((n) => {
    const item = {
      id: n.id,
      in_degree: n.in_degree || 0,
      out_degree: n.out_degree || 0,
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      vx: 0,
      vy: 0,
      r: 6,
      fixed: false,
    };
    nodeMap.set(item.id, item);
    return item;
  });
  const edges = filteredEdges
    .map((e) => ({ source: nodeMap.get(e.source), target: nodeMap.get(e.target) }))
    .filter((e) => e.source && e.target);

  graphRenderState = { nodes, edges, degreeMap };
  if (!nodes.length) {
    ctx.fillStyle = "#94a3b8";
    ctx.font = "13px Arial";
    ctx.fillText("当前过滤条件下无节点", 12, 24);
    return;
  }

  const centerX = canvas.width / 2;
  const centerY = canvas.height / 2;
  let dragged = null;
  let hovered = null;
  let panning = false;
  let mouseDownMoved = false;
  let panStartX = 0;
  let panStartY = 0;
  let panOriginX = 0;
  let panOriginY = 0;
  let dragStartX = 0;
  let dragStartY = 0;
  const view = {
    scale: 1,
    offsetX: 0,
    offsetY: 0,
  };

  function worldToCanvas(wx, wy) {
    return {
      x: wx * view.scale + view.offsetX,
      y: wy * view.scale + view.offsetY,
    };
  }

  function canvasToWorld(cx, cy) {
    return {
      x: (cx - view.offsetX) / view.scale,
      y: (cy - view.offsetY) / view.scale,
    };
  }

  function pickNode(worldX, worldY) {
    for (let i = nodes.length - 1; i >= 0; i -= 1) {
      const n = nodes[i];
      const dx = n.x - worldX;
      const dy = n.y - worldY;
      if (dx * dx + dy * dy <= (n.r + 4) * (n.r + 4)) return n;
    }
    return null;
  }

  function pointerPos(evt) {
    const rect = canvas.getBoundingClientRect();
    return {
      x: ((evt.clientX - rect.left) / rect.width) * canvas.width,
      y: ((evt.clientY - rect.top) / rect.height) * canvas.height,
    };
  }

  canvas.onmousedown = (evt) => {
    const p = pointerPos(evt);
    const world = canvasToWorld(p.x, p.y);
    dragged = pickNode(world.x, world.y);
    mouseDownMoved = false;
    dragStartX = p.x;
    dragStartY = p.y;
    if (dragged) {
      dragged.fixed = true;
      dragged.x = world.x;
      dragged.y = world.y;
      dragged.vx = 0;
      dragged.vy = 0;
      return;
    }
    panning = true;
    panStartX = p.x;
    panStartY = p.y;
    panOriginX = view.offsetX;
    panOriginY = view.offsetY;
  };

  canvas.onmousemove = (evt) => {
    const p = pointerPos(evt);
    const world = canvasToWorld(p.x, p.y);
    hovered = pickNode(world.x, world.y);
    if (Math.abs(p.x - dragStartX) + Math.abs(p.y - dragStartY) > 2) {
      mouseDownMoved = true;
    }
    if (dragged) {
      dragged.x = world.x;
      dragged.y = world.y;
      return;
    }
    if (panning) {
      view.offsetX = panOriginX + (p.x - panStartX);
      view.offsetY = panOriginY + (p.y - panStartY);
    }
  };

  canvas.onmouseup = async (evt) => {
    const p = pointerPos(evt);
    const world = canvasToWorld(p.x, p.y);
    const released = dragged;
    if (dragged) {
      dragged.fixed = false;
      dragged = null;
    }
    panning = false;
    const clicked = pickNode(world.x, world.y);
    if (clicked && clicked === released && !mouseDownMoved) {
      try {
        await openWikiNode(clicked.id);
      } catch (e) {
        setStatus(`打开图谱节点失败: ${e.message}`);
      }
    }
  };
  canvas.onmouseleave = () => {
    hovered = null;
    panning = false;
  };

  canvas.onwheel = (evt) => {
    evt.preventDefault();
    const p = pointerPos(evt);
    const before = canvasToWorld(p.x, p.y);
    const ratio = evt.deltaY < 0 ? 1.1 : 0.9;
    view.scale = Math.max(0.35, Math.min(3.2, view.scale * ratio));
    const after = worldToCanvas(before.x, before.y);
    view.offsetX += p.x - after.x;
    view.offsetY += p.y - after.y;
  };

  function tick() {
    const repulsion = 1300;
    const spring = 0.02;
    const rest = 85;
    const damping = 0.86;
    const centerPull = 0.0035;

    for (let i = 0; i < nodes.length; i += 1) {
      const a = nodes[i];
      for (let j = i + 1; j < nodes.length; j += 1) {
        const b = nodes[j];
        let dx = a.x - b.x;
        let dy = a.y - b.y;
        const d2 = dx * dx + dy * dy + 0.01;
        const f = repulsion / d2;
        const inv = 1 / Math.sqrt(d2);
        dx *= inv;
        dy *= inv;
        if (!a.fixed) {
          a.vx += dx * f;
          a.vy += dy * f;
        }
        if (!b.fixed) {
          b.vx -= dx * f;
          b.vy -= dy * f;
        }
      }
    }

    for (const e of edges) {
      const dx = e.target.x - e.source.x;
      const dy = e.target.y - e.source.y;
      const dist = Math.sqrt(dx * dx + dy * dy) + 0.001;
      const f = (dist - rest) * spring;
      const ux = dx / dist;
      const uy = dy / dist;
      if (!e.source.fixed) {
        e.source.vx += ux * f;
        e.source.vy += uy * f;
      }
      if (!e.target.fixed) {
        e.target.vx -= ux * f;
        e.target.vy -= uy * f;
      }
    }

    for (const n of nodes) {
      if (!n.fixed) {
        n.vx += (centerX - n.x) * centerPull;
        n.vy += (centerY - n.y) * centerPull;
        n.vx *= damping;
        n.vy *= damping;
        n.x += n.vx;
        n.y += n.vy;
        n.x = Math.max(8, Math.min(canvas.width - 8, n.x));
        n.y = Math.max(8, Math.min(canvas.height - 8, n.y));
      }
    }

    const neighbors = new Set();
    if (hovered) {
      neighbors.add(hovered.id);
      for (const e of edges) {
        if (e.source.id === hovered.id) neighbors.add(e.target.id);
        if (e.target.id === hovered.id) neighbors.add(e.source.id);
      }
    }

    ctx.clearRect(0, 0, canvas.width, canvas.height);
    for (const e of edges) {
      const s = worldToCanvas(e.source.x, e.source.y);
      const t = worldToCanvas(e.target.x, e.target.y);
      const active = hovered && (e.source.id === hovered.id || e.target.id === hovered.id);
      ctx.beginPath();
      ctx.strokeStyle = active ? "#60a5fa" : "#475569";
      ctx.lineWidth = active ? 1.9 : 1;
      ctx.moveTo(s.x, s.y);
      ctx.lineTo(t.x, t.y);
      ctx.stroke();
    }

    for (const n of nodes) {
      const p = worldToCanvas(n.x, n.y);
      const isHover = hovered && n.id === hovered.id;
      const isNeighbor = hovered && neighbors.has(n.id);
      ctx.beginPath();
      ctx.fillStyle = isHover ? "#f59e0b" : isNeighbor ? "#60a5fa" : "#3b82f6";
      ctx.arc(p.x, p.y, n.r * Math.max(1, Math.min(1.8, view.scale * 0.9)), 0, Math.PI * 2);
      ctx.fill();
      if (view.scale >= 0.7 || isHover) {
        const short = n.id.length > 18 ? `${n.id.slice(0, 18)}...` : n.id;
        ctx.fillStyle = isHover ? "#fde68a" : "#cbd5e1";
        ctx.font = "10px Arial";
        ctx.fillText(short, p.x + 9, p.y + 4);
      }
    }
    graphAnimId = requestAnimationFrame(tick);
  }
  tick();
}

function renderEvidences(evidences = []) {
  evidenceList.innerHTML = "";
  if (!evidences.length) {
    const li = document.createElement("li");
    li.textContent = "暂无证据。";
    evidenceList.appendChild(li);
    return;
  }
  for (const ev of evidences) {
    const li = document.createElement("li");
    li.innerHTML = `
      <div class="ev-top">
        <div><b>[${ev.ref}] ${ev.source_id}/${ev.rel_path}</b></div>
        <button class="ev-open" data-doc-id="${ev.doc_id}">打开</button>
      </div>
      <div>${ev.confidence_label || ev.confidence_level || ""} (${ev.confidence ?? "-"})</div>
      <div>${ev.excerpt || ""}</div>
    `;
    const btn = li.querySelector(".ev-open");
    btn.onclick = async () => {
      try {
        const doc = await api(`/api/document/${ev.doc_id}`);
        renderDocumentPreview(doc, ev.excerpt || "");
      } catch (e) {
        setStatus(`打开证据文档失败: ${e.message}`);
      }
    };
    evidenceList.appendChild(li);
  }
}

loginBtn.onclick = async () => {
  try {
    const auth = await api("/api/login", {
      method: "POST",
      body: JSON.stringify({ password: pwdInput.value }),
    });
    if (auth && typeof auth.csrf_header === "string" && auth.csrf_header.trim()) {
      CSRF_HEADER_NAME = auth.csrf_header.trim().toLowerCase();
    }
    setAuthUI(true);
    setStatus("登录成功");
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
  } catch (e) {
    setAuthUI(false);
    setStatus(`登录失败: ${e.message}`);
  }
};

searchBtn.onclick = async () => {
  const q = qInput.value.trim();
  if (!q) return;
  currentSearchTerm = q;
  window.MindSyncSearch?.recordSearch?.(q);
  results.innerHTML = "";
  docMeta.textContent = "";
  docContent.textContent = "";
  window.MindSyncWikiEditor?.setWikiContext?.(null);
  docNav.classList.add("hidden");
  matchCount.textContent = "0 / 0";
  currentMatchIndex = -1;
  try {
    const params = new URLSearchParams({ q });
    if (sourceFilter.value) params.set("source_id", sourceFilter.value);
    if (typeFilter.value) params.set("file_type", typeFilter.value);
    if (categoryFilter.value) params.set("category", categoryFilter.value);
    if (topicFilter.value) params.set("topic", topicFilter.value);
    const sort = window.MindSyncSearch?.getSort?.() || "relevance";
    if (sort && sort !== "relevance") params.set("sort", sort);
    const data = await api(`/api/search?${params.toString()}`);
    for (const item of data.items) {
      const li = document.createElement("li");
      li.innerHTML = `<div>${categoryBadge(item.category)} <b>${item.source_id}</b> / ${item.rel_path}</div><div>${item.snippet || ""}</div>`;
      li.onclick = async () => {
        const doc = await api(`/api/document/${item.id}`);
        if (typeof switchView === "function") switchView("library");
        renderDocumentPreview(doc, currentSearchTerm);
      };
      results.appendChild(li);
    }
  } catch (e) {
    setStatus(`搜索失败: ${e.message}`);
  }
};

qInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") searchBtn.onclick();
});

prevMatchBtn.onclick = () => scrollToMatch(currentMatchIndex - 1);
nextMatchBtn.onclick = () => scrollToMatch(currentMatchIndex + 1);

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    const top = getTopTransientModal();
    if (top) {
      closeModal(top);
      return;
    }
  }
  if (e.key === "Tab") {
    const top = getTopTransientModal();
    if (top) {
      trapModalFocus(top, e);
    }
  }
  if (!getSearchMarks().length) return;
  if (e.target.matches("input, textarea, select")) return;
  if (e.key === "F3") {
    e.preventDefault();
    if (e.shiftKey) {
      scrollToMatch(currentMatchIndex - 1);
    } else {
      scrollToMatch(currentMatchIndex + 1);
    }
  }
});

askBtn.onclick = async () => {
  const question = askInput.value.trim();
  if (!question) return;
  askMeta.textContent = "";
  renderAskAnswer("");
  renderEvidences([]);
  try {
    setStatus("问答中...");
    const data = await api("/api/query", {
      method: "POST",
      body: JSON.stringify({
        question,
        limit: 8,
        save_to_wiki: !!saveInsight.checked,
      }),
    });
    const indexedNote = data.indexed && data.indexed.indexed ? " · 已索引" : "";
    askMeta.textContent = `模型: ${data.model_used} | LLM: ${data.used_llm ? "是" : "否"}${
      data.saved_path ? ` | 已保存: ${data.saved_path}${indexedNote}` : ""
    }`;
    if (askHint) {
      askHint.textContent = data.llm_configured
        ? "已配置 LLM_API_KEY，问答将优先使用大模型生成结构化答案。"
        : "未配置 LLM_API_KEY：当前仅基于检索片段生成摘要，非完整 LLM 回答。";
    }
    renderAskAnswer(data.answer || "");
    renderEvidences(data.evidences || []);
    await loadWikiGraph();
    setStatus("问答完成");
  } catch (e) {
    setStatus(`问答失败: ${e.message}`);
  }
};

askInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") askBtn.onclick();
});

if (runLintBtn) {
  runLintBtn.onclick = () => runWikiLint();
}

browseBtn.onclick = async () => {
  if (!isLoggedIn) return;
  await loadBrowseList();
};

categoryFilter.onchange = () => {
  if (categoryFilter.value !== "summary") {
    topicFilter.value = "";
  }
};

refreshAuditBtn.onclick = async () => {
  if (!isLoggedIn) return;
  await loadAuditEvents();
};

refreshGraphBtn.onclick = async () => {
  await loadWikiGraph();
};

graphFilterInput.oninput = () => {
  graphFilterKeyword = graphFilterInput.value || "";
  if (currentGraphData) {
    renderGraph(currentGraphData);
    renderGraphList();
  }
};

graphMinDegreeSelect.onchange = () => {
  graphFilterMinDegree = Number(graphMinDegreeSelect.value || 0);
  if (currentGraphData) {
    renderGraph(currentGraphData);
    renderGraphList();
  }
};

graphResetLayoutBtn.onclick = () => {
  if (currentGraphData) {
    renderGraph(currentGraphData);
  }
};

graphViewTopBtn.onclick = () => setGraphView("top");
graphViewOrphanBtn.onclick = () => setGraphView("orphan");
graphViewHubBtn.onclick = () => setGraphView("hub");
graphFilterMinDegree = Number(graphMinDegreeSelect.value || 0);
setGraphView(currentGraphView);
initPanelCollapse();

closeSettingsBtn.onclick = () => {
  closeTransientModals();
};

accountBtn.onclick = async () => {
  if (!isLoggedIn) return;
  openModal(accountModal);
  try {
    const mode = await api("/api/auth-mode");
    accountModeText.textContent = `认证方式：Cookie=${mode.cookie_enabled ? "开" : "关"}，API Key=${
      mode.api_key_enabled ? "开" : "关"
    }`;
  } catch (e) {
    accountModeText.textContent = `认证信息加载失败：${e.message}`;
  }
};

closeAccountBtn.onclick = () => {
  closeTransientModals();
};

logoutBtn.onclick = async () => {
  try {
    await api("/api/logout", { method: "POST" });
  } catch (_) {
    document.cookie = "ms_token=; Max-Age=0; path=/";
  }
  closeModal(accountModal);
  setAuthUI(false);
  setStatus("已退出登录");
};

initPanelCollapse();
