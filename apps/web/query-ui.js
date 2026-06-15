/** Q&A panel (depends on app-shared.js). */
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
function renderEvidences(evidences = []) {
  evidenceList.innerHTML = "";
  if (!evidences.length) {
    const li = document.createElement("li");
    li.className = "evidence-card";
    li.textContent = "暂无证据。";
    evidenceList.appendChild(li);
    return;
  }
  for (const ev of evidences) {
    const li = document.createElement("li");
    li.className = "evidence-card";
    const confColor = {
      extracted: "var(--success-fg)",
      inferred: "var(--warning-fg)",
      ambiguous: "var(--danger-fg)",
      unverified: "var(--fg-subtle)",
    }[(ev.confidence || "").toLowerCase()] || "var(--fg-muted)";
    li.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:6px">
        <span class="confidence-badge" style="background:${confColor}15;color:${confColor};border:1px solid ${confColor}30">
          ${ev.confidence_label || ev.confidence_level || ev.confidence || "—"}
        </span>
        <button class="ev-open btn btn-sm" data-doc-id="${ev.doc_id}">打开文档</button>
      </div>
      <div style="font-size:13px;margin-bottom:4px"><b>[${ev.ref}]</b> ${ev.source_id}/${ev.rel_path}</div>
      <div class="subtle" style="font-size:12px">${ev.excerpt || ""}</div>
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
