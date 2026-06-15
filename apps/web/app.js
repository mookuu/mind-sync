/** Event bindings and bootstrap (feature logic in *-ui.js modules). */
loginBtn.onclick = async () => {
  try {
    const userInput = document.getElementById("user");
    const username = (userInput?.value || "default").trim() || "default";
    const auth = await api("/api/login", {
      method: "POST",
      body: JSON.stringify({ username, password: pwdInput.value }),
    });
    if (auth && typeof auth.csrf_header === "string" && auth.csrf_header.trim()) {
      CSRF_HEADER_NAME = auth.csrf_header.trim().toLowerCase();
    }
    canWrite = auth?.can_write !== false;
    userRole = auth?.role || "admin";
    setAuthUI(true, { canWrite, role: userRole });
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

let allSearchResults = [];
let filteredResults = [];
let currentPage = 1;
let currentPageSize = 10;

function applyLocalFilters() {
  if (!allSearchResults.length) { filteredResults = []; renderPage(); return; }
  let items = [...allSearchResults];
  const cat = document.getElementById("categoryFilter")?.value || "";
  const src = document.getElementById("sourceFilter")?.value || "";
  const typ = document.getElementById("typeFilter")?.value || "";
  if (cat) items = items.filter((i) => String(i.category || "") === cat);
  if (src) items = items.filter((i) => String(i.source_id || "") === src);
  if (typ) items = items.filter((i) => String(i.lang || "") === typ);
  filteredResults = items;
  currentPage = 1;
  renderPage();
  const pageInfo = document.getElementById("pageInfo");
  if (pageInfo) pageInfo.textContent = `${filteredResults.length} / ${allSearchResults.length} 条`;
}

["categoryFilter", "sourceFilter", "typeFilter"].forEach((id) => {
  const el = document.getElementById(id);
  if (el) el.addEventListener("change", applyLocalFilters);
});

function renderPage() {
  results.innerHTML = "";
  const source = filteredResults;
  const total = source.length;
  const totalPages = Math.ceil(total / currentPageSize) || 1;
  const start = (currentPage - 1) * currentPageSize;
  const end = Math.min(start + currentPageSize, total);
  const pageItems = source.slice(start, end);

  for (const item of pageItems) {
    const li = document.createElement("li");
    li.className = "card-result";
    const snippet = (item.snippet || "").replace(/<mark>/g, '<mark class="search-hit">').replace(/<\/mark>/g, "</mark>");
    li.innerHTML = `
      <div class="card-result-head">
        <span class="cat-badge ${item.category === "summary" ? "cat-summary" : item.category === "query" ? "cat-query" : ""}">${categoryBadge(item.category)}</span>
        <b>${item.source_id}</b> / ${item.rel_path}
      </div>
      <div class="card-result-snippet">${snippet || ""}</div>
    `;
    li.onclick = async () => {
      const doc = await api(`/api/document/${item.id}`);
      if (typeof switchView === "function") switchView("library");
      renderDocumentPreview(doc, currentSearchTerm);
    };
    results.appendChild(li);
  }

  const pagination = document.getElementById("pagination");
  const pageInfo = document.getElementById("pageInfo");
  const prevBtn = document.getElementById("prevPageBtn");
  const nextBtn = document.getElementById("nextPageBtn");
  const pageNumbers = document.getElementById("pageNumbers");
  if (!pagination) return;
  if (total === 0) { pagination.classList.add("hidden"); return; }
  pagination.classList.remove("hidden");
  pageInfo.textContent = `${start + 1}-${end} / ${total} 条`;
  if (totalPages > 1) {
    prevBtn.disabled = currentPage <= 1;
    nextBtn.disabled = currentPage >= totalPages;
    prevBtn.classList.remove("hidden");
    nextBtn.classList.remove("hidden");
    pageNumbers.classList.remove("hidden");
  } else {
    prevBtn.classList.add("hidden");
    nextBtn.classList.add("hidden");
    pageNumbers.classList.add("hidden");
  }
  pageNumbers.innerHTML = "";
  const maxVisible = 7;
  let ps = Math.max(1, currentPage - Math.floor(maxVisible / 2));
  let pe = Math.min(totalPages, ps + maxVisible - 1);
  if (pe - ps < maxVisible - 1) ps = Math.max(1, pe - maxVisible + 1);
  for (let i = ps; i <= pe; i++) {
    const btn = document.createElement("span");
    btn.className = `page-num${i === currentPage ? " active" : ""}`;
    btn.textContent = i;
    btn.onclick = () => { currentPage = i; renderPage(); };
    pageNumbers.appendChild(btn);
  }
}

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
  currentPage = 1;
  try {
    const params = new URLSearchParams({ q, limit: "200" });
    const sort = window.MindSyncSearch?.getSort?.() || "relevance";
    if (sort && sort !== "relevance") params.set("sort", sort);
    const data = await api(`/api/search?${params.toString()}`);
    allSearchResults = data.items || [];
    filteredResults = [];
    applyLocalFilters();
  } catch (e) {
    setStatus(`搜索失败: ${e.message}`);
  }
};

document.getElementById("prevPageBtn")?.addEventListener("click", () => { if (currentPage > 1) { currentPage--; renderPage(); } });
document.getElementById("nextPageBtn")?.addEventListener("click", () => { const tp = Math.ceil(filteredResults.length / currentPageSize); if (currentPage < tp) { currentPage++; renderPage(); } });
document.getElementById("pageSizeSelect")?.addEventListener("change", (e) => { currentPageSize = parseInt(e.target.value) || 10; currentPage = 1; renderPage(); });

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

// browse removed — search with pagination replaces category browse

categoryFilter.addEventListener("change", () => {
  if (categoryFilter.value !== "summary") topicFilter.value = "";
});

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

// closeSettingsBtn removed — settings content moved to sync/purpose views

accountBtn.onclick = async () => {
  if (!isLoggedIn) return;
  openModal(accountModal);
  try {
    const mode = await api("/api/auth-mode");
    const roleLabel = mode.can_write ? "管理员（可编辑）" : "只读（浏览/问答）";
    accountModeText.textContent = `用户：${mode.username || "—"} · ${roleLabel} · Cookie=${
      mode.cookie_enabled ? "开" : "关"
    }，API Key=${mode.api_key_enabled ? "开" : "关"}`;
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
