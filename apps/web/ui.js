/* mind-sync UI shell: views, document library, modular settings */

let currentSyncPreset = "all";
let customSyncSourceIds = [];
let availableSources = [];

function switchView(viewId) {
  document.querySelectorAll(".nav-item").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.view === viewId);
  });
  document.querySelectorAll(".sub-nav").forEach((sub) => sub.classList.remove("open"));
  document.querySelectorAll(".view").forEach((el) => {
    el.classList.toggle("hidden", el.id !== `view-${viewId}`);
    el.classList.toggle("active", el.id === `view-${viewId}`);
  });
  if (viewId === "purpose") {
    loadPurposePreview();
  }
  const parentMap = { sync: "sync", "sync-sources": "sync", "sync-vault": "sync", "sync-audit": "sync" };
  const parentKey = parentMap[viewId];
  if (parentKey) {
    const parent = document.querySelector(`.parent-item[data-view='${parentKey}']`);
    if (parent) parent.classList.add("active");
    const subnav = document.getElementById(`subnav-${parentKey}`);
    if (subnav) subnav.classList.add("open");
  }
  if (viewId === "sync" || viewId === "sync-control") {
    loadSettings();
    loadSyncStatus();
  }
  if (viewId === "sync-sources") {
    loadSourcesSettingsList();
    loadSettingsExtended();
  }
  if (viewId === "sync-vault") {
    loadVaultStatus();
  }
  if (viewId === "sync-audit") {
    loadAuditEvents();
  }
}

function bindViewNav() {
  document.querySelectorAll(".nav-item:not(.parent-item)").forEach((btn) => {
    btn.onclick = () => {
      if (!isLoggedIn) return;
      switchView(btn.dataset.view);
    };
  });
  let activeSubParent = null;
  function closeAllSubnavs() {
    document.querySelectorAll(".sub-nav").forEach((s) => s.classList.remove("open"));
    document.querySelectorAll(".parent-item").forEach((p) => p.classList.toggle("active", false));
  }
  document.querySelectorAll(".parent-item").forEach((parent) => {
    const subnav = document.getElementById(`subnav-${parent.dataset.view}`);
    if (!subnav) return;
    parent.addEventListener("click", (e) => {
      e.stopPropagation();
      if (subnav.classList.contains("open")) {
        subnav.classList.remove("open");
        parent.classList.remove("active");
        activeSubParent = null;
      } else {
        closeAllSubnavs();
        subnav.classList.add("open");
        parent.classList.add("active");
        activeSubParent = parent.dataset.view;
      }
    });
    parent.addEventListener("mouseenter", () => {
      if (window.innerWidth <= 900) return;
      closeAllSubnavs();
      subnav.classList.add("open");
      parent.classList.add("active");
      activeSubParent = parent.dataset.view;
    });
    parent.addEventListener("mouseleave", () => {
      if (window.innerWidth <= 900) return;
      const isHoveringSub = subnav.matches(":hover");
      const childHovered = subnav.querySelector(".sub-nav-item:hover");
      if (!isHoveringSub && !childHovered && !subnav.querySelector(".sub-nav-item.sub-active")) {
        setTimeout(() => {
          if (!subnav.matches(":hover")) {
            subnav.classList.remove("open");
            parent.classList.remove("active");
            activeSubParent = null;
          }
        }, 150);
      }
    });
  });
  document.querySelectorAll(".sub-nav").forEach((sub) => {
    sub.addEventListener("mouseleave", () => {
      if (window.innerWidth <= 900) return;
      const parent = sub.closest(".sidebar-nav")?.querySelector(`.parent-item[data-view="${sub.id.replace("subnav-", "")}"]`);
      if (parent && !parent.matches(":hover") && !sub.querySelector(".sub-nav-item.sub-active")) {
        setTimeout(() => {
          if (!sub.matches(":hover") && !parent.matches(":hover")) {
            sub.classList.remove("open");
            parent.classList.remove("active");
            activeSubParent = null;
          }
        }, 150);
      }
    });
  });
  document.querySelectorAll(".sub-nav-item").forEach((item) => {
    item.addEventListener("click", () => {
      document.querySelectorAll(".sub-nav-item").forEach((s) => s.classList.remove("active", "sub-active"));
      item.classList.add("active", "sub-active");
      const section = item.dataset.section;
      const viewMap = {
        "library-all": "library",
        "library-recent": "library",
        "sync-control": "sync",
        "sync-sources": "sync-sources",
        "sync-vault": "sync-vault",
        "sync-audit": "sync-audit",
      };
      switchView(viewMap[section] || section);
    });
  });
}

function renderSyncPresets(presets, selectedPreset) {
  const box = document.getElementById("syncPresetList");
  if (!box) return;
  box.innerHTML = "";
  currentSyncPreset = selectedPreset || "all";
  const isDefault = currentSyncPreset === "all" || currentSyncPreset === "";
  const allPreset = presets.find((p) => p.id === "all");
  const otherPresets = presets.filter((p) => p.id !== "all" && p.id !== "custom");

  // 默认 checkbox（master toggle）
  const allLabel = document.createElement("label");
  allLabel.className = `preset-option${isDefault ? " selected" : ""}`;
  allLabel.innerHTML = `
    <input type="checkbox" ${isDefault ? "checked" : ""} />
    <div>
      <div>${allPreset ? allPreset.label : "全部同步"}</div>
      <div class="preset-desc">同步 sources.yaml 中所有已配置来源</div>
    </div>`;
  allLabel.querySelector("input").onchange = (e) => {
    const checked = e.target.checked;
    allLabel.classList.toggle("selected", checked);
    document.querySelectorAll(".preset-option:not(#presetAll)").forEach((el) => {
      el.style.opacity = checked ? "0.4" : "1";
      el.style.pointerEvents = checked ? "none" : "auto";
      const cb = el.querySelector("input[type=checkbox]");
      if (cb) cb.disabled = checked;
    });
    const customBox = document.getElementById("syncCustomPaths");
    if (customBox) {
      customBox.style.opacity = checked ? "0.4" : "1";
      customBox.style.pointerEvents = checked ? "none" : "auto";
    }
    currentSyncPreset = checked ? "all" : "custom";
  };
  allLabel.id = "presetAll";
  box.appendChild(allLabel);

  // 其他 preset 选项
  for (const p of otherPresets) {
    const label = document.createElement("label");
    label.className = "preset-option";
    label.style.opacity = isDefault ? "0.4" : "1";
    label.style.pointerEvents = isDefault ? "none" : "auto";
    const checked = p.id === currentSyncPreset;
    label.innerHTML = `
      <input type="checkbox" value="${p.id}" ${checked ? "checked" : ""} ${isDefault ? "disabled" : ""} />
      <div>
        <div>${p.label}</div>
        <div class="preset-desc">${p.description || ""}</div>
      </div>`;
    label.querySelector("input").onchange = (e) => {
      label.classList.toggle("selected", e.target.checked);
    };
    box.appendChild(label);
  }

  // 自定义路径区域
  const customBox = document.getElementById("syncCustomPaths");
  if (customBox) {
    customBox.classList.remove("hidden");
    customBox.style.opacity = isDefault ? "0.4" : "1";
    customBox.style.pointerEvents = isDefault ? "none" : "auto";
  }

  // 初始化：默认选中时灰掉其他
  if (isDefault) {
    document.querySelectorAll(".preset-option:not(#presetAll)").forEach((el) => {
      el.style.opacity = "0.4";
      el.style.pointerEvents = "none";
      const cb = el.querySelector("input[type=checkbox]");
      if (cb) cb.disabled = true;
    });
  }
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
    label.className = "source-checkbox-item";
    const checked = isSourceKeySelected(s, selectedIds) ? "checked" : "";
    const name = sourceSyncLabel(s);
    const spath = s.path || "";
    const status = s.exists ? "" : " ❌ 路径缺失";
    label.innerHTML = `
      <input type="checkbox" value="${sourceSyncKey(s)}" ${checked} style="margin-top:4px" />
      <div>
        <div class="source-checkbox-name">${name}${status}</div>
        <div class="source-checkbox-path">${spath}</div>
      </div>`;
    box.appendChild(label);
  }
}

function getCustomSourceSelection() {
  const box = document.getElementById("syncCustomSources");
  if (!box) return [];
  return [...box.querySelectorAll("input[type=checkbox]:checked")].map((el) => el.value);
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
    await loadSettingsExtended();
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

  if (settingsBtn) {
    settingsBtn.onclick = () => {
      if (isLoggedIn) switchView("purpose");
    };
  }

  const addCustomPathBtn = document.getElementById("addCustomPathBtn");
  const customPathInput = document.getElementById("customPathInput");
  const customPathError = document.getElementById("customPathError");
  const customPathList = document.getElementById("customPathList");
  const dirPickerModal = document.getElementById("dirPickerModal");
  const dirPickerPath = document.getElementById("dirPickerPath");
  const dirPickerGo = document.getElementById("dirPickerGo");
  const dirPickerList = document.getElementById("dirPickerList");
  const dirPickerError = document.getElementById("dirPickerError");
  const dirPickerSelect = document.getElementById("dirPickerSelect");
  const dirPickerCancel = document.getElementById("dirPickerCancel");
  let dirPickerCurrentPath = "/home/moku/projects";

  async function loadDirPicker(path) {
    dirPickerError.textContent = "";
    dirPickerList.innerHTML = "<li class='subtle' style='padding:8px'>加载中…</li>";
    try {
      const data = await api(`/api/admin/browse-dir?path=${encodeURIComponent(path)}`);
      dirPickerCurrentPath = data.current;
      dirPickerPath.value = data.current;
      dirPickerList.innerHTML = `<li class="tree-dir-head" data-path="${data.parent}" style="cursor:pointer;color:var(--accent-fg)">
        ⬆ ${data.parent}
      </li>`;
      for (const e of data.entries) {
        const li = document.createElement("li");
        li.className = "tree-dir-head";
        li.dataset.path = e.path;
        li.textContent = `📁 ${e.name}`;
        li.style.cursor = "pointer";
        li.onclick = () => loadDirPicker(e.path);
        dirPickerList.appendChild(li);
      }
      if (!data.entries.length) dirPickerList.innerHTML += "<li class='subtle' style='padding:8px'>（空目录）</li>";
    } catch (e) {
      dirPickerError.textContent = e.message || "加载失败";
      dirPickerList.innerHTML = "";
    }
  }

  if (addCustomPathBtn && customPathInput) {
    addCustomPathBtn.onclick = async () => {
      let path = customPathInput.value.trim();
      if (!path) {
        openModal(dirPickerModal);
        await loadDirPicker(dirPickerCurrentPath);
        return;
      }
      customPathError.textContent = "";
      addCustomPathBtn.disabled = true;
      addCustomPathBtn.textContent = "验证中…";
      try {
        const data = await api("/api/admin/sources/custom", {
          method: "POST", body: JSON.stringify({ path }),
        });
        if (customPathList) {
          const li = document.createElement("li");
          li.className = "sync-order-item";
          li.innerHTML = `
            <span class="sync-order-label">📁 ${data.source.id}</span>
            <span class="subtle">${data.source.path}</span>
          `;
          customPathList.appendChild(li);
        }
        customPathInput.value = "";
        await reloadSourcesConfig();
        settingsStatus.textContent = `已添加源: ${data.source.id}`;
      } catch (e) {
        customPathError.textContent = e.message || "添加失败，请检查路径";
      } finally {
        addCustomPathBtn.disabled = false;
        addCustomPathBtn.textContent = "添加";
      }
    };
    customPathInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") addCustomPathBtn.click();
    });
  }

  if (dirPickerGo && dirPickerPath) {
    dirPickerGo.onclick = () => loadDirPicker(dirPickerPath.value.trim() || dirPickerCurrentPath);
    dirPickerPath.addEventListener("keydown", (e) => { if (e.key === "Enter") dirPickerGo.click(); });
  }
  if (dirPickerSelect) {
    dirPickerSelect.onclick = async () => {
      const selectedPath = dirPickerCurrentPath;
      closeModal(dirPickerModal);
      customPathInput.value = selectedPath;
      addCustomPathBtn.click();
    };
  }
  if (dirPickerCancel) dirPickerCancel.onclick = () => closeModal(dirPickerModal);

  function buildSettingsBody() {
    return {
      auto_sync_enabled: !!autoSyncEnabled.checked,
      auto_sync_interval_minutes: Number(autoSyncInterval.value || 60),
      sync_preset: currentSyncPreset,
    };
  }
  [autoSyncEnabled, autoSyncInterval].forEach((el) => {
    if (el) el.addEventListener("change", () => {
      const body = buildSettingsBody();
      if (currentSyncPreset === "custom") body.sync_source_ids = getCustomSourceSelection();
      api("/api/settings", { method: "POST", body: JSON.stringify(body) }).catch(() => {});
    });
  });

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
    const ok = await showConfirm(
      "🔃 全量重建",
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
  patchAuthUI();
  const reloadSourcesBtn = document.getElementById("reloadSourcesBtn");
  if (reloadSourcesBtn) reloadSourcesBtn.onclick = () => reloadSourcesConfig();
  switchView("library");
  bootstrapAuthState();
}

initUI();
