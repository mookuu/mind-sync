/* mind-sync UI shell: views, document library, modular settings */

let currentSyncPreset = "all";
let customSyncSourceIds = [];
let availableSources = [];
let syncSourceOrder = [];

function switchView(viewId) {
  document.querySelectorAll(".nav-item").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.view === viewId);
  });
  document.querySelectorAll(".view").forEach((el) => {
    el.classList.toggle("hidden", el.id !== `view-${viewId}`);
    el.classList.toggle("active", el.id === `view-${viewId}`);
  });
}

function bindViewNav() {
  document.querySelectorAll(".nav-item").forEach((btn) => {
    btn.onclick = () => {
      if (!isLoggedIn) return;
      switchView(btn.dataset.view);
    };
  });
}

function bindSettingsTabs() {
  document.querySelectorAll(".settings-tab").forEach((tab) => {
    tab.onclick = () => {
      const id = tab.dataset.settingsTab;
      document.querySelectorAll(".settings-tab").forEach((t) => t.classList.toggle("active", t === tab));
      document.querySelectorAll(".settings-pane").forEach((pane) => {
        pane.classList.toggle("active", pane.id === `settingsTab-${id}`);
        pane.classList.toggle("hidden", pane.id !== `settingsTab-${id}`);
      });
      if (id === "sources") loadSourcesSettingsList();
      if (id === "vault") loadVaultStatus();
      if (id === "purpose") loadPurposePreview();
      if (id === "audit") loadAuditEvents();
    };
  });
}

function renderSyncPresets(presets, selectedPreset) {
  const box = document.getElementById("syncPresetList");
  if (!box) return;
  box.innerHTML = "";
  currentSyncPreset = selectedPreset || "all";
  for (const p of presets || []) {
    const label = document.createElement("label");
    label.className = `preset-option${p.id === currentSyncPreset ? " selected" : ""}`;
    label.innerHTML = `
      <input type="radio" name="syncPreset" value="${p.id}" ${p.id === currentSyncPreset ? "checked" : ""} />
      <div>
        <div>${p.label}</div>
        <div class="preset-desc">${p.description || ""}</div>
      </div>`;
    label.querySelector("input").onchange = () => {
      currentSyncPreset = p.id;
      document.querySelectorAll(".preset-option").forEach((el) => el.classList.remove("selected"));
      label.classList.add("selected");
      const customBox = document.getElementById("syncCustomSources");
      if (customBox) customBox.classList.toggle("hidden", currentSyncPreset !== "custom");
    };
    box.appendChild(label);
  }
  const customBox = document.getElementById("syncCustomSources");
  if (customBox) customBox.classList.toggle("hidden", currentSyncPreset !== "custom");
}

function sourceSyncKey(s) {
  return s.sync_key || `${s.id}:${s.type || "local"}`;
}

function sourceSyncLabel(s) {
  return s.label || `${s.id}${s.type ? ` (${s.type})` : ""}`;
}

function expandSyncKeys(rawKeys, sources) {
  const out = [];
  const seen = new Set();
  for (const key of rawKeys || []) {
    const chunk = String(key || "").trim();
    if (!chunk) continue;
    const colon = chunk.lastIndexOf(":");
    const typed = colon > 0 && ["local", "github", "web"].includes(chunk.slice(colon + 1));
    if (typed) {
      if (!seen.has(chunk)) {
        out.push(chunk);
        seen.add(chunk);
      }
      continue;
    }
    const matches = (sources || []).filter((s) => s.id === chunk);
    for (const s of matches) {
      const sk = sourceSyncKey(s);
      if (!seen.has(sk)) {
        out.push(sk);
        seen.add(sk);
      }
    }
  }
  return out;
}

function isSourceKeySelected(s, selectedKeys) {
  const selected = new Set(selectedKeys || []);
  const sk = sourceSyncKey(s);
  if (selected.has(sk)) return true;
  if (selected.has(s.id)) {
    const hasTyped = [...selected].some((k) => String(k).startsWith(`${s.id}:`));
    return !hasTyped;
  }
  return false;
}

function renderCustomSourceCheckboxes(sources, selectedIds) {
  const box = document.getElementById("syncCustomSources");
  if (!box) return;
  box.innerHTML = "<div class='field-label'>勾选要同步的来源</div>";
  for (const s of sources || []) {
    const label = document.createElement("label");
    const checked = isSourceKeySelected(s, selectedIds) ? "checked" : "";
    label.innerHTML = `<input type="checkbox" value="${sourceSyncKey(s)}" ${checked} /> ${sourceSyncLabel(s)}${s.exists ? "" : " (路径缺失)"}`;
    box.appendChild(label);
  }
}

function getCustomSourceSelection() {
  const box = document.getElementById("syncCustomSources");
  if (!box) return [];
  return [...box.querySelectorAll("input[type=checkbox]:checked")].map((el) => el.value);
}

function renderSyncOrderList(orderIds, sources) {
  const list = document.getElementById("syncOrderList");
  if (!list) return;
  list.innerHTML = "";
  const byKey = Object.fromEntries((sources || []).map((s) => [sourceSyncKey(s), s]));
  const defaultKeys = (sources || []).map(sourceSyncKey);
  let keys = expandSyncKeys(orderIds && orderIds.length ? orderIds.slice() : defaultKeys, sources);
  for (const sk of defaultKeys) {
    if (!keys.includes(sk)) keys.push(sk);
  }
  syncSourceOrder = keys;
  keys.forEach((key, index) => {
    const s = byKey[key];
    const li = document.createElement("li");
    li.className = "sync-order-item";
    const label = s ? sourceSyncLabel(s) : key;
    li.innerHTML = `
      <span class="sync-order-label">${label}</span>
      <span class="sync-order-actions">
        <button type="button" class="btn btn-sm sync-order-up" data-index="${index}" ${index === 0 ? "disabled" : ""}>↑</button>
        <button type="button" class="btn btn-sm sync-order-down" data-index="${index}" ${index === keys.length - 1 ? "disabled" : ""}>↓</button>
      </span>`;
    list.appendChild(li);
  });
  list.querySelectorAll(".sync-order-up").forEach((btn) => {
    btn.onclick = () => {
      const i = Number(btn.dataset.index);
      if (i <= 0) return;
      [syncSourceOrder[i - 1], syncSourceOrder[i]] = [syncSourceOrder[i], syncSourceOrder[i - 1]];
      renderSyncOrderList(syncSourceOrder, sources);
    };
  });
  list.querySelectorAll(".sync-order-down").forEach((btn) => {
    btn.onclick = () => {
      const i = Number(btn.dataset.index);
      if (i >= syncSourceOrder.length - 1) return;
      [syncSourceOrder[i + 1], syncSourceOrder[i]] = [syncSourceOrder[i], syncSourceOrder[i + 1]];
      renderSyncOrderList(syncSourceOrder, sources);
    };
  });
}

async function loadVaultStatus() {
  const el = document.getElementById("vaultStatusText");
  const action = document.getElementById("vaultActionStatus");
  if (!el) return;
  try {
    const data = await api("/api/vault-status");
    if (!data.configured) {
      el.textContent = "未配置 VAULT_GIT_URL。在 .env 中设置后重启 API，可将 wiki 与 purpose 同步到私有 Git 仓。";
      document.getElementById("vaultPullBtn")?.setAttribute("disabled", "true");
      document.getElementById("vaultPushBtn")?.setAttribute("disabled", "true");
      return;
    }
    document.getElementById("vaultPullBtn")?.removeAttribute("disabled");
    document.getElementById("vaultPushBtn")?.removeAttribute("disabled");
    el.textContent = `已配置：${data.url || ""}（分支 ${data.branch || "main"}）· 本地 ${data.has_clone ? "已克隆" : "未克隆"}`;
    if (action && !action.textContent) action.textContent = "";
  } catch (e) {
    el.textContent = `加载失败: ${e.message}`;
  }
}

async function loadSourcesSettingsList() {
  const list = document.getElementById("sourcesList");
  if (!list) return;
  try {
    const data = await api("/api/sources");
    availableSources = data.sources || [];
    list.innerHTML = "";
    for (const s of availableSources) {
      const li = document.createElement("li");
      li.innerHTML = `<div><b>${s.id}</b> <span class="${s.exists ? "ok" : "missing"}">${s.exists ? "● 可访问" : "● 路径缺失"}</span></div>
        <div class="subtle">${s.type || "local"} · order=${s.order ?? "—"} · ${s.path || ""}</div>
        <div class="subtle">${(s.include || []).join(", ")}</div>`;
      list.appendChild(li);
    }
    renderCustomSourceCheckboxes(availableSources, customSyncSourceIds);
  } catch (e) {
    list.innerHTML = `<li class="subtle">加载失败: ${e.message}</li>`;
  }
}

async function reloadSourcesConfig() {
  const statusEl = document.getElementById("reloadSourcesStatus");
  const btn = document.getElementById("reloadSourcesBtn");
  if (!btn) return;
  try {
    btn.disabled = true;
    if (statusEl) statusEl.textContent = "重新加载中…";
    const data = await api("/api/admin/sources/reload", { method: "POST" });
    const count = data.count ?? (data.sources || []).length;
    if (statusEl) statusEl.textContent = `已加载 ${count} 个源`;
    await loadSourcesSettingsList();
    if (typeof loadSourcesFilter === "function") await loadSourcesFilter();
  } catch (e) {
    if (statusEl) statusEl.textContent = `失败: ${e.message}`;
  } finally {
    if (btn && window.MindSyncAuth?.canWrite !== false) btn.removeAttribute("disabled");
  }
}

function setTreeExpanded(toggleBtn, bodyEl, expanded) {
  if (!toggleBtn || !bodyEl) return;
  bodyEl.classList.toggle("hidden", !expanded);
  const chevron = toggleBtn.querySelector(".chevron");
  if (chevron) chevron.textContent = expanded ? "▾" : "▸";
}

function bindTreeToggle(toggleBtn, bodyEl) {
  toggleBtn.onclick = (e) => {
    e.stopPropagation();
    const expanded = bodyEl.classList.contains("hidden");
    setTreeExpanded(toggleBtn, bodyEl, expanded);
  };
}

function treeFileIcon(name) {
  const ext = (String(name || "").split(".").pop() || "").toLowerCase();
  const icons = {
    md: "📄",
    py: "🐍",
    java: "☕",
    js: "📜",
    ts: "📘",
    json: "📋",
    yaml: "⚙",
    yml: "⚙",
  };
  return icons[ext] || "📄";
}

function renderTreeNodes(container, nodes, depth, sourceId, langId) {
  for (const node of nodes || []) {
    if (node.type === "dir") {
      const dirWrap = document.createElement("div");
      dirWrap.className = "tree-dir";
      const dirBtn = document.createElement("button");
      dirBtn.type = "button";
      dirBtn.className = "tree-dir-head";
      dirBtn.style.paddingLeft = `${depth * 12 + 8}px`;
      dirBtn.dataset.sourceId = sourceId;
      dirBtn.dataset.langId = langId;
      dirBtn.dataset.path = node.path || node.name;
      dirBtn.innerHTML = `<span class="chevron">▸</span><span class="tree-dir-icon">📁</span><span>${node.name}</span>`;
      const dirBody = document.createElement("div");
      dirBody.className = "tree-dir-body hidden";
      dirBody.dataset.path = node.path || node.name;
      bindTreeToggle(dirBtn, dirBody);
      renderTreeNodes(dirBody, node.children || [], depth + 1, sourceId, langId);
      dirWrap.appendChild(dirBtn);
      dirWrap.appendChild(dirBody);
      container.appendChild(dirWrap);
    } else if (node.type === "file") {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "tree-item tree-file";
      btn.style.paddingLeft = `${depth * 12 + 20}px`;
      btn.innerHTML = `<span class="tree-file-icon">${treeFileIcon(node.name)}</span><span>${node.name}</span>`;
      btn.title = node.path;
      btn.dataset.path = node.path;
      btn.dataset.docId = String(node.doc_id);
      btn.dataset.sourceId = sourceId;
      btn.dataset.langId = langId;
      btn.onclick = async (e) => {
        e.stopPropagation();
        document.querySelectorAll(".tree-file.active").forEach((el) => el.classList.remove("active"));
        btn.classList.add("active");
        await openLibraryDocument(node);
      };
      container.appendChild(btn);
    }
  }
}

async function openLibraryDocument(node) {
  const breadcrumb = document.getElementById("docBreadcrumb");
  try {
    const doc = await api(`/api/document/${node.doc_id}`);
    if (breadcrumb) breadcrumb.textContent = `${doc.source_id} / ${doc.rel_path}`;
    renderDocumentPreview(doc, "");
    switchView("library");
  } catch (e) {
    setStatus(`打开文档失败: ${e.message}`);
  }
}

function cssEscape(value) {
  if (typeof CSS !== "undefined" && typeof CSS.escape === "function") {
    return CSS.escape(String(value));
  }
  return String(value).replace(/\\/g, "\\\\").replace(/"/g, '\\"');
}

function revealLibraryDocument(sourceId, relPath, lang) {
  const tree = document.getElementById("libraryTree");
  if (!tree || !sourceId || !relPath) return;

  const normPath = String(relPath).replace(/\\/g, "/");
  const langId = lang || "";

  const fileBtnPreview = tree.querySelector(
    `.tree-file[data-source-id="${cssEscape(sourceId)}"][data-path="${cssEscape(normPath)}"]`
  );
  if (fileBtnPreview) {
    const section = fileBtnPreview.closest(".lib-section");
    if (section) {
      const secBtn = section.querySelector(".lib-section-head");
      const secBody = section.querySelector(".lib-section-body");
      if (secBtn && secBody) setTreeExpanded(secBtn, secBody, true);
    }
    const flatLang = fileBtnPreview.closest(".lib-section")?.querySelector(
      `.lib-lang-head[data-source-id="${cssEscape(sourceId)}"][data-lang-id="${cssEscape(langId)}"]`
    );
    if (flatLang) {
      setTreeExpanded(flatLang, flatLang.nextElementSibling, true);
    }
  }

  const srcBtn = tree.querySelector(`.lib-source-head[data-source-id="${cssEscape(sourceId)}"]`);
  if (srcBtn) {
    setTreeExpanded(srcBtn, srcBtn.nextElementSibling, true);
  }

  const langBtn = tree.querySelector(
    `.lib-lang-head[data-source-id="${cssEscape(sourceId)}"][data-lang-id="${cssEscape(langId)}"]`
  );
  if (langBtn) {
    setTreeExpanded(langBtn, langBtn.nextElementSibling, true);
  }

  const parts = normPath.split("/").filter(Boolean);
  let acc = "";
  for (let i = 0; i < parts.length - 1; i += 1) {
    acc = acc ? `${acc}/${parts[i]}` : parts[i];
    const dirBtn = tree.querySelector(
      `.tree-dir-head[data-source-id="${cssEscape(sourceId)}"][data-path="${cssEscape(acc)}"]`
    );
    if (dirBtn) {
      setTreeExpanded(dirBtn, dirBtn.nextElementSibling, true);
    }
  }

  const fileBtn = tree.querySelector(
    `.tree-file[data-source-id="${cssEscape(sourceId)}"][data-path="${cssEscape(normPath)}"]`
  );
  if (fileBtn) {
    document.querySelectorAll(".tree-file.active").forEach((el) => el.classList.remove("active"));
    fileBtn.classList.add("active");
    fileBtn.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }
}

async function loadLibrary() {
  const tree = document.getElementById("libraryTree");
  if (!tree) return;
  tree.innerHTML = "<p class='subtle' style='padding:12px'>加载中…</p>";
  try {
    const data = await api("/api/library?category=all");
    tree.innerHTML = "";
    if (!data.sections || !data.sections.length) {
      tree.innerHTML = "<p class='subtle' style='padding:12px'>暂无文档，请先同步索引。</p>";
      return;
    }
    for (const section of data.sections) {
      const sec = document.createElement("div");
      sec.className = "lib-section";
      const secBtn = document.createElement("button");
      secBtn.type = "button";
      secBtn.className = "lib-section-head";
      secBtn.innerHTML = `<span class="chevron">▸</span> ${section.label} (${section.count ?? section.sources?.reduce((n, s) => n + (s.count || 0), 0) ?? 0})`;
      const secBody = document.createElement("div");
      secBody.className = "lib-section-body hidden";
      bindTreeToggle(secBtn, secBody);

      const renderLangGroup = (container, sourceId, lang) => {
        const langWrap = document.createElement("div");
        langWrap.className = "lib-lang";
        const langBtn = document.createElement("button");
        langBtn.type = "button";
        langBtn.className = "lib-lang-head";
        langBtn.dataset.sourceId = sourceId;
        langBtn.dataset.langId = lang.id;
        langBtn.innerHTML = `<span class="chevron">▸</span> ${lang.label} <span class="subtle">(${lang.count})</span>`;
        const langBody = document.createElement("div");
        langBody.className = "lib-tree hidden";
        bindTreeToggle(langBtn, langBody);
        renderTreeNodes(langBody, lang.tree || [], 0, sourceId, lang.id);
        langWrap.appendChild(langBtn);
        langWrap.appendChild(langBody);
        container.appendChild(langWrap);
      };

      if (section.flat && section.languages) {
        const sourceId = section.source_id || "wiki";
        for (const lang of section.languages || []) {
          renderLangGroup(secBody, sourceId, lang);
        }
      } else {
        for (const source of section.sources || []) {
          const srcWrap = document.createElement("div");
          srcWrap.className = "lib-source";
          srcWrap.dataset.sourceId = source.id;
          const srcBtn = document.createElement("button");
          srcBtn.type = "button";
          srcBtn.className = "lib-source-head";
          srcBtn.dataset.sourceId = source.id;
          srcBtn.innerHTML = `<span class="chevron">▸</span> ${source.label} <span class="subtle">(${source.count})</span>`;
          const srcBody = document.createElement("div");
          srcBody.className = "lib-source-body hidden";
          bindTreeToggle(srcBtn, srcBody);

          for (const lang of source.languages || []) {
            renderLangGroup(srcBody, source.id, lang);
          }
          srcWrap.appendChild(srcBtn);
          srcWrap.appendChild(srcBody);
          secBody.appendChild(srcWrap);
        }
      }
      sec.appendChild(secBtn);
      sec.appendChild(secBody);
      tree.appendChild(sec);
    }
  } catch (e) {
    tree.innerHTML = `<p class='subtle' style='padding:12px'>加载失败: ${e.message}</p>`;
  }
}

function updateSyncScopeText(settingsData) {
  const el = document.getElementById("syncScopeText");
  if (!el || !settingsData) return;
  const preset = settingsData.sync_preset || "all";
  const presets = settingsData.sync_presets || [];
  const label = presets.find((p) => p.id === preset)?.label || preset;
  const ids = settingsData.sync_selected_source_ids || [];
  el.textContent = ids.length
    ? `同步范围：${label}（${ids.join(", ")}）`
    : `同步范围：${label}`;
}

async function loadSettingsExtended() {
  await loadSettings();
  try {
    const st = await api("/api/settings");
    renderSyncPresets(st.sync_presets, st.sync_preset);
    const srcList = availableSources.length ? availableSources : (await api("/api/sources")).sources || [];
    if (!availableSources.length) availableSources = srcList;
    customSyncSourceIds = expandSyncKeys(st.sync_source_ids || st.sync_selected_keys || [], srcList);
    renderCustomSourceCheckboxes(srcList, customSyncSourceIds);
    updateSyncScopeText(st);
    renderSyncOrderList(
      expandSyncKeys(st.sync_source_order || st.sync_effective_order || [], srcList),
      srcList,
    );
  } catch (_) {
    // ignore
  }
}

function patchAuthUI() {
  const loginError = document.getElementById("loginError");

  const origBootstrap = bootstrapAuthState;
  bootstrapAuthState = async function () {
    await origBootstrap();
    if (isLoggedIn) {
      await loadLibrary();
      await loadSettingsExtended();
      switchView("library");
    }
  };

  const origLogin = loginBtn.onclick;
  loginBtn.onclick = async () => {
    if (loginError) loginError.classList.add("hidden");
    await origLogin();
    if (isLoggedIn) {
      await loadLibrary();
      await loadSettingsExtended();
      switchView("library");
    } else if (loginError && loginStatus.textContent.includes("失败")) {
      loginError.textContent = loginStatus.textContent;
      loginError.classList.remove("hidden");
    }
  };

  pwdInput?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") loginBtn.click();
  });
  document.getElementById("user")?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") loginBtn.click();
  });

  settingsBtn.onclick = async () => {
    if (!isLoggedIn) return;
    openModal(settingsModal);
    settingsStatus.textContent = "";
    document.querySelectorAll(".settings-tab").forEach((t, i) => {
      t.classList.toggle("active", i === 0);
    });
    document.querySelectorAll(".settings-pane").forEach((p, i) => {
      p.classList.toggle("active", i === 0);
      p.classList.toggle("hidden", i !== 0);
    });
    await loadSettingsExtended();
    await loadPurposePreview();
  };

  saveSettingsBtn.onclick = async () => {
    try {
      settingsStatus.textContent = "保存中…";
      const body = {
        auto_sync_enabled: !!autoSyncEnabled.checked,
        auto_sync_interval_minutes: Number(autoSyncInterval.value || 60),
        sync_preset: currentSyncPreset,
      };
      if (currentSyncPreset === "custom") {
        body.sync_source_ids = getCustomSourceSelection();
      }
      if (syncSourceOrder.length) {
        body.sync_source_order = syncSourceOrder;
      }
      const data = await api("/api/settings", { method: "POST", body: JSON.stringify(body) });
      settingsStatus.textContent = `已保存 · 同步范围: ${data.sync_preset}`;
      updateSyncScopeText(data);
      await loadSettings();
    } catch (e) {
      settingsStatus.textContent = `保存失败: ${e.message}`;
    }
  };

  if (savePurposeBtn) {
    savePurposeBtn.onclick = async () => {
      if (!isLoggedIn) return;
      await savePurposeContent();
    };
  }

  const globalSearch = document.getElementById("globalSearch");
  if (globalSearch) {
    globalSearch.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && globalSearch.value.trim()) {
        qInput.value = globalSearch.value.trim();
        switchView("search");
        searchBtn.click();
      }
    });
  }

  const vaultPullBtn = document.getElementById("vaultPullBtn");
  const vaultPushBtn = document.getElementById("vaultPushBtn");
  if (vaultPullBtn) {
    vaultPullBtn.onclick = async () => {
      if (!isLoggedIn) return;
      const st = document.getElementById("vaultActionStatus");
      try {
        if (st) st.textContent = "拉取中…";
        const data = await api("/api/vault-sync", {
          method: "POST",
          body: JSON.stringify({ pull: true, push: false }),
        });
        if (st) st.textContent = data.pull?.skipped ? "未配置远程" : "拉取完成";
        await loadVaultStatus();
      } catch (e) {
        if (st) st.textContent = `拉取失败: ${e.message}`;
      }
    };
  }
  if (vaultPushBtn) {
    vaultPushBtn.onclick = async () => {
      if (!isLoggedIn) return;
      const st = document.getElementById("vaultActionStatus");
      try {
        if (st) st.textContent = "推送中…";
        const data = await api("/api/vault-sync", {
          method: "POST",
          body: JSON.stringify({ pull: false, push: true }),
        });
        if (st) st.textContent = data.push?.skipped ? "未配置远程" : "推送完成";
      } catch (e) {
        if (st) st.textContent = `推送失败: ${e.message}`;
      }
    };
  }

  syncBtn.onclick = async () => {
    if (!isLoggedIn) return;
    try {
      setStatus("同步中…");
      const vaultPushOnSync = document.getElementById("vaultPushOnSync")?.checked;
      await api("/api/sync", {
        method: "POST",
        body: JSON.stringify({
          use_saved_defaults: true,
          vault_pull: true,
          vault_push: !!vaultPushOnSync,
        }),
      });
      await waitForIndexJob("sync");
    } catch (e) {
      setStatus(`同步失败: ${e.message}`);
    }
  };

  const rebuildBtn = document.getElementById("rebuildBtn");
  rebuildBtn?.addEventListener("click", async () => {
    if (!isLoggedIn) return;
    const ok = window.confirm(
      "将按当前同步范围清空索引并强制重扫所有文件（不拉取 GitHub/Web/Vault）。确定继续？"
    );
    if (!ok) return;
    try {
      setStatus("全量重建中…");
      await api("/api/rebuild-index", {
        method: "POST",
        body: JSON.stringify({ use_saved_defaults: true }),
      });
      await waitForIndexJob("rebuild");
    } catch (e) {
      setStatus(`全量重建失败: ${e.message}`);
    }
  });
}

async function waitForIndexJob(expectedMode) {
  switchView("sync");
  const label = expectedMode === "rebuild" ? "全量重建" : "同步";
  const deadline = Date.now() + 15 * 60 * 1000;
  while (Date.now() < deadline) {
    await new Promise((r) => setTimeout(r, 2000));
    const status = await loadSyncStatus();
    if (!status) return;
    if (status.running) {
      setStatus(`${label}中… ${status.current_source || ""} (${status.processed_files}/${status.total_files})`);
      continue;
    }
    setStatus(status.error ? `${label}失败: ${status.error}` : `${label}完成`);
    await loadLibrary();
    await loadSettingsExtended();
    await loadWikiGraph();
    return;
  }
}

function initUI() {
  bindViewNav();
  bindSettingsTabs();
  patchAuthUI();
  const reloadSourcesBtn = document.getElementById("reloadSourcesBtn");
  if (reloadSourcesBtn) reloadSourcesBtn.onclick = () => reloadSourcesConfig();
  switchView("library");
  bootstrapAuthState();
}

initUI();
