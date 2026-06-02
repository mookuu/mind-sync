/** In-browser wiki markdown editor. */
(function () {
  let currentWikiPath = null;

  function canEditWiki() {
    return window.MindSyncAuth?.canWrite !== false;
  }

  function refreshEditBar() {
    setWikiContext(currentWikiPath);
  }

  function ensureToolbar() {
    let bar = document.getElementById("wikiEditBar");
    if (bar) return bar;
    const docPanel = document.querySelector(".doc-panel");
    if (!docPanel) return null;
    bar = document.createElement("div");
    bar.id = "wikiEditBar";
    bar.className = "wiki-edit-bar hidden";
    bar.innerHTML = `
      <span id="wikiEditPath" class="subtle"></span>
      <button type="button" id="wikiEditBtn" class="btn btn-sm">编辑 Wiki</button>
      <button type="button" id="wikiSaveBtn" class="btn btn-sm btn-primary hidden">保存</button>
      <button type="button" id="wikiCancelBtn" class="btn btn-sm hidden">取消</button>
      <span id="wikiEditStatus" class="subtle"></span>
    `;
    const breadcrumb = document.getElementById("docBreadcrumb");
    if (breadcrumb && breadcrumb.parentNode) {
      breadcrumb.parentNode.insertBefore(bar, breadcrumb.nextSibling);
    } else {
      docPanel.insertBefore(bar, docPanel.firstChild);
    }
    return bar;
  }

  function setWikiContext(path) {
    currentWikiPath = path || null;
    const bar = ensureToolbar();
    if (!bar) return;
    const editBtn = document.getElementById("wikiEditBtn");
    const pathEl = document.getElementById("wikiEditPath");
    if (!currentWikiPath || !String(currentWikiPath).endsWith(".md")) {
      bar.classList.add("hidden");
      return;
    }
    bar.classList.remove("hidden");
    if (pathEl) pathEl.textContent = `wiki / ${currentWikiPath}`;
    if (editBtn) {
      if (canEditWiki()) editBtn.classList.remove("hidden");
      else editBtn.classList.add("hidden");
    }
    document.getElementById("wikiSaveBtn")?.classList.add("hidden");
    document.getElementById("wikiCancelBtn")?.classList.add("hidden");
  }

  async function saveWiki(content) {
    const api = window.MindSyncApi?.api || window.api;
    if (!api || !currentWikiPath) return;
    const status = document.getElementById("wikiEditStatus");
    if (status) status.textContent = "保存中…";
    const data = await api("/api/wiki-content", {
      method: "PUT",
      body: JSON.stringify({ path: currentWikiPath, content }),
    });
    if (status) status.textContent = `已保存 · 索引 ${data.indexed?.indexed ?? 0} 条`;
    if (typeof window.renderWikiMarkdown === "function") {
      window.renderWikiMarkdown(content, currentWikiPath);
    }
    document.getElementById("wikiSaveBtn")?.classList.add("hidden");
    document.getElementById("wikiCancelBtn")?.classList.add("hidden");
    document.getElementById("wikiEditBtn")?.classList.remove("hidden");
  }

  function bind() {
    ensureToolbar();
    document.getElementById("wikiEditBtn")?.addEventListener("click", async () => {
      if (!canEditWiki()) return;
      const api = window.MindSyncApi?.api || window.api;
      const docContent = document.getElementById("docContent");
      if (!api || !currentWikiPath || !docContent) return;
      const data = await api(`/api/wiki-content?path=${encodeURIComponent(currentWikiPath)}`);
      docContent.innerHTML = "";
      const area = document.createElement("textarea");
      area.id = "wikiEditorArea";
      area.className = "wiki-editor-area";
      area.value = data.content || "";
      docContent.appendChild(area);
      document.getElementById("wikiEditBtn")?.classList.add("hidden");
      document.getElementById("wikiSaveBtn")?.classList.remove("hidden");
      document.getElementById("wikiCancelBtn")?.classList.remove("hidden");
    });
    document.getElementById("wikiSaveBtn")?.addEventListener("click", async () => {
      const area = document.getElementById("wikiEditorArea");
      if (!area) return;
      try {
        await saveWiki(area.value);
      } catch (e) {
        const status = document.getElementById("wikiEditStatus");
        if (status) status.textContent = `保存失败: ${e.message}`;
      }
    });
    document.getElementById("wikiCancelBtn")?.addEventListener("click", async () => {
      const api = window.MindSyncApi?.api || window.api;
      if (!api || !currentWikiPath) return;
      const data = await api(`/api/wiki-content?path=${encodeURIComponent(currentWikiPath)}`);
      if (typeof window.renderWikiMarkdown === "function") {
        window.renderWikiMarkdown(data.content || "", currentWikiPath);
      }
      document.getElementById("wikiSaveBtn")?.classList.add("hidden");
      document.getElementById("wikiCancelBtn")?.classList.add("hidden");
      document.getElementById("wikiEditBtn")?.classList.remove("hidden");
    });
  }

  window.MindSyncWikiEditor = { setWikiContext, bind, refreshEditBar };
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bind);
  } else {
    bind();
  }
})();
