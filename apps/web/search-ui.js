/** Search, highlight, browse filters (depends on app-shared.js). */
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
