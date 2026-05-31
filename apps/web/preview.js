/* Document preview: Markdown (markdown-it + GFM) + syntax highlighting */

const PREVIEW_LANG_MAP = {
  markdown: "markdown",
  md: "markdown",
  python: "python",
  py: "python",
  java: "java",
  javascript: "javascript",
  js: "javascript",
  json: "json",
  yaml: "yaml",
  yml: "yaml",
  bash: "bash",
  shell: "bash",
  sh: "bash",
  text: "plaintext",
  txt: "plaintext",
  plaintext: "plaintext",
  plain: "plaintext",
  test: "plaintext",
  output: "plaintext",
  prompt: "plaintext",
  example: "plaintext",
  sample: "plaintext",
  note: "plaintext",
  info: "plaintext",
  tip: "plaintext",
  none: "plaintext",
  tree: "plaintext",
  ascii: "plaintext",
  diagram: "plaintext",
};

const TEXT_LIKE_LANGS = new Set([
  "text",
  "txt",
  "plaintext",
  "plain",
  "test",
  "prompt",
  "example",
  "sample",
  "note",
  "info",
  "tip",
  "none",
]);

const MONO_LANGS = new Set(["tree", "ascii", "diagram", "hierarchy", "output"]);

let markdownItConfigured = false;
let markdownItInstance = null;
let previewDocContext = null;

function previewHljsReady() {
  return typeof hljs !== "undefined" && typeof hljs.highlight === "function";
}

function previewMarkdownItReady() {
  return typeof MindSyncMarkdown !== "undefined" && typeof MindSyncMarkdown.createRenderer === "function";
}

function stripFrontmatter(text) {
  const raw = String(text || "");
  if (!raw.startsWith("---")) return raw;
  const end = raw.indexOf("\n---", 3);
  if (end === -1) return raw;
  return raw.slice(end + 4).replace(/^\s*\n/, "");
}

function normalizeLang(language) {
  const lang = String(language || "plaintext").trim().toLowerCase();
  return PREVIEW_LANG_MAP[lang] || lang || "plaintext";
}

function isExternalAssetSrc(src) {
  return /^(https?:|data:|mailto:)/i.test(String(src || "").trim());
}

function buildAssetUrl(src) {
  const raw = String(src || "").trim();
  if (!raw || isExternalAssetSrc(raw)) return raw;
  const ctx = previewDocContext;
  if (!ctx) return raw;
  if (ctx.docId != null) {
    return `/api/document/${ctx.docId}/asset?src=${encodeURIComponent(raw)}`;
  }
  if (ctx.wikiPath) {
    return `/api/wiki-asset?path=${encodeURIComponent(ctx.wikiPath)}&src=${encodeURIComponent(raw)}`;
  }
  return raw;
}

function buildImageHtml(alt, url) {
  const u = String(url || "").trim();
  const altText = escapeHtml(alt || "");
  const src = isExternalAssetSrc(u) ? u : buildAssetUrl(u);
  const img = `<img class="md-image" src="${escapeHtml(src)}" alt="${altText}" loading="lazy" onerror="this.classList.add('md-image-error')" />`;
  const caption = altText ? `<figcaption class="md-figure-caption">${altText}</figcaption>` : "";
  return `<figure class="md-figure">${img}${caption}</figure>`;
}

function highlightCodeText(code, language) {
  const lang = normalizeLang(language);
  if (!previewHljsReady()) {
    return escapeHtml(code);
  }
  try {
    if (hljsSupports(language)) {
      return hljs.highlight(code, { language: lang }).value;
    }
    return escapeHtml(code);
  } catch (_) {
    return escapeHtml(code);
  }
}

function hljsSupports(language) {
  const lang = normalizeLang(language);
  return previewHljsReady() && lang !== "plaintext" && !!hljs.getLanguage(lang);
}

function isExplicitTextLikeLang(language) {
  const raw = String(language || "").trim().toLowerCase();
  const lang = normalizeLang(language);
  return TEXT_LIKE_LANGS.has(raw) || TEXT_LIKE_LANGS.has(lang);
}

function isAsciiTreeOrDiagram(text) {
  const s = String(text || "");
  if (!s.trim()) return false;
  if (/[├└│─┌┐┘┴┬┤]/.test(s)) return true;
  if (/^[\s|]*(?:[+|\\]--|L--)/m.test(s)) return true;
  const lines = s.split("\n").filter((line) => line.trim());
  if (lines.length < 2) return false;
  const treeLines = lines.filter((line) => /[├└│─]|\+\-\-|\|\-\-|L\-\-/.test(line)).length;
  return treeLines >= 2 || (treeLines >= 1 && lines.length >= 3);
}

function looksLikeProseLine(line) {
  const s = String(line || "").trim();
  if (!s) return false;
  if (/^(`{3,}|#|<\/?[a-z])/i.test(s)) return false;
  if (/^(import |from |def |class |function |const |let |var |#include|public |private |return |if \(|for \(|while \(|@\w+|SELECT |INSERT )/.test(s)) {
    return false;
  }
  if (/[\u4e00-\u9fff]/.test(s)) return true;
  if (/[。；！？]$/.test(s)) return true;
  if (/^(Severity:|File:|Problem:|任务：|你是|请)/.test(s)) return true;
  return false;
}

function looksLikeProseBlock(text) {
  const lines = String(text || "").split("\n").map((l) => l.trim()).filter(Boolean);
  if (!lines.length) return false;
  if (isAsciiTreeOrDiagram(text)) return false;
  const proseLines = lines.filter((l) => looksLikeProseLine(l)).length;
  const codeLike = lines.some((l) => /[{}();]|=>|^\s*#/.test(l) && !/[\u4e00-\u9fff]/.test(l));
  return proseLines >= Math.max(1, Math.ceil(lines.length * 0.6)) && !codeLike;
}

/** 列表项下 6+ 空格缩进的中文段落会被 Markdown 误判为代码块，改为引用块 */
function normalizeListIndentedProse(text) {
  const lines = String(text || "").replace(/\r\n/g, "\n").split("\n");
  const out = [];
  let listContext = false;
  for (const line of lines) {
    if (/^\s*(?:[-*+]|\d+\.|[a-zA-Z]\.)\s+\S/.test(line)) {
      listContext = true;
      out.push(line);
      continue;
    }
    if (line.trim() === "") {
      out.push(line);
      continue;
    }
    const indented = line.match(/^(\s{6,})(.+)$/);
    if (indented && listContext && looksLikeProseLine(indented[2])) {
      out.push(`> ${indented[2]}`);
      continue;
    }
    if (/^#{1,6}\s/.test(line) || (/^\S/.test(line) && !/^>\s/.test(line))) {
      listContext = false;
    }
    out.push(line);
  }
  return out.join("\n");
}

/** 列表项内缩进的 ```lang 围栏 dedent 到行首，否则解析器无法识别 */
function normalizeIndentedFences(text) {
  const lines = String(text || "").replace(/\r\n/g, "\n").split("\n");
  const out = [];
  let i = 0;
  while (i < lines.length) {
    const open = lines[i].match(/^(\s+)```([^\n`]*)?\s*$/);
    if (open) {
      const indent = open[1];
      const lang = (open[2] || "").trim();
      out.push(lang ? `\`\`\`${lang}` : "```");
      i += 1;
      while (i < lines.length) {
        const line = lines[i];
        const close = line.match(/^(\s*)```\s*$/);
        if (close && close[1].length >= indent.length) {
          out.push("```");
          i += 1;
          break;
        }
        out.push(line.startsWith(indent) ? line.slice(indent.length) : line);
        i += 1;
      }
      continue;
    }
    out.push(lines[i]);
    i += 1;
  }
  return out.join("\n");
}

function prepareMarkdownBody(text) {
  const body = stripFrontmatter(text || "");
  return normalizeIndentedFences(normalizeListIndentedProse(body));
}

function wrapTextBlock(code, extraClass = "", language = "") {
  const langLabel = String(language || "").trim();
  const langAttr = langLabel ? ` data-lang="${escapeHtml(langLabel)}"` : "";
  const cls = extraClass ? `md-text-block ${extraClass}` : "md-text-block";
  return `<pre class="${cls}"${langAttr}><code>${escapeHtml(code || "")}</code></pre>\n`;
}

function wrapMonospaceBlock(code, extraClass = "", language = "") {
  const langLabel = String(language || "").trim();
  const langAttr = langLabel ? ` data-lang="${escapeHtml(langLabel)}"` : "";
  const cls = extraClass ? `md-monospace-block ${extraClass}` : "md-monospace-block";
  return `<pre class="${cls}"${langAttr}><code>${escapeHtml(code || "")}</code></pre>\n`;
}

function wrapCodeBlock(code, language, extraClass = "") {
  const rawLang = String(language || "").trim();
  const lang = normalizeLang(language);
  const rawLower = rawLang.toLowerCase();

  if (MONO_LANGS.has(rawLower) || isAsciiTreeOrDiagram(code)) {
    return wrapMonospaceBlock(code, extraClass, rawLang || "tree");
  }
  if (isExplicitTextLikeLang(language)) {
    return wrapTextBlock(code, extraClass, rawLang || lang);
  }
  if (hljsSupports(language)) {
    const highlighted = highlightCodeText(code, lang);
    return `<pre class="code-block ${extraClass}"><code class="language-${escapeHtml(lang)} hljs">${highlighted}</code></pre>\n`;
  }
  return wrapMonospaceBlock(code, extraClass, rawLang || lang);
}

function renderFenceLikeBlock(code, language, extraClass) {
  return wrapCodeBlock(code, language, extraClass);
}

function configureMarkdownIt() {
  if (markdownItConfigured || !previewMarkdownItReady()) return;
  markdownItConfigured = true;

  const md = MindSyncMarkdown.createRenderer();
  const defaultLinkOpen =
    md.renderer.rules.link_open
    || ((tokens, idx, options, env, self) => self.renderToken(tokens, idx, options));

  md.renderer.rules.fence = (tokens, idx) => {
    const token = tokens[idx];
    const info = token.info ? String(token.info).trim() : "";
    const lang = info.split(/\s+/)[0] || "";
    return renderFenceLikeBlock(token.content, lang, "md-fenced");
  };

  md.renderer.rules.code_block = (tokens, idx) => {
    return renderFenceLikeBlock(tokens[idx].content, "", "md-indented");
  };

  md.renderer.rules.code_inline = (tokens, idx) => {
    return `<code class="inline-code">${escapeHtml(tokens[idx].content || "")}</code>`;
  };

  md.renderer.rules.image = (tokens, idx) => {
    const token = tokens[idx];
    const alt = token.content || "";
    const href = token.attrGet("src") || "";
    return buildImageHtml(alt, href);
  };

  md.renderer.rules.link_open = (tokens, idx, options, env, self) => {
    const href = tokens[idx].attrGet("href") || "#";
    if (isExternalAssetSrc(href)) {
      tokens[idx].attrSet("target", "_blank");
      tokens[idx].attrSet("rel", "noopener noreferrer");
    }
    return defaultLinkOpen(tokens, idx, options, env, self);
  };

  md.renderer.rules.table_open = () => '<div class="md-table-wrap"><table>\n';
  md.renderer.rules.table_close = () => "</table></div>\n";

  markdownItInstance = md;
}

function setDocImageToolbarVisible(visible) {
  const toolbar = document.querySelector(".doc-toolbar");
  if (toolbar) toolbar.classList.toggle("hidden", !visible);
}

function rewritePreviewImages(container) {
  if (!container) return;
  container.querySelectorAll("img").forEach((img) => {
    const src = img.getAttribute("src") || "";
    if (!src || isExternalAssetSrc(src)) return;
    if (!src.startsWith("/api/document/") && !src.startsWith("/api/wiki-asset")) {
      img.setAttribute("src", buildAssetUrl(src));
    }
    img.classList.add("md-image");
    img.loading = "lazy";
    if (!img.getAttribute("onerror")) {
      img.onerror = () => {
        img.classList.add("md-image-error");
      };
    }
    if (img.closest(".md-figure")) return;
    const figure = document.createElement("figure");
    figure.className = "md-figure";
    img.replaceWith(figure);
    figure.appendChild(img);
    const alt = (img.getAttribute("alt") || "").trim();
    if (alt) {
      const caption = document.createElement("figcaption");
      caption.className = "md-figure-caption";
      caption.textContent = alt;
      figure.appendChild(caption);
    }
  });
}

function fixMisclassifiedProseBlocks(container) {
  if (!container) return;
  container.querySelectorAll("pre").forEach((pre) => {
    if (
      pre.classList.contains("code-block")
      || pre.classList.contains("md-text-block")
      || pre.classList.contains("md-monospace-block")
    ) {
      return;
    }
    const code = pre.querySelector("code");
    const text = (code ? code.textContent : pre.textContent) || "";
    if (isAsciiTreeOrDiagram(text)) {
      pre.classList.add("md-monospace-block");
      return;
    }
    if (!looksLikeProseBlock(text)) return;
    const box = document.createElement("div");
    box.className = "md-prose-box";
    box.textContent = text.trim();
    pre.replaceWith(box);
  });
}

function parseMarkdown(content) {
  const prepared = prepareMarkdownBody(content);
  if (previewMarkdownItReady()) {
    configureMarkdownIt();
    try {
      return markdownItInstance.render(prepared);
    } catch (err) {
      console.warn("markdown-it render failed, fallback", err);
    }
  }
  return renderMarkdownFallback(prepared);
}

function renderMarkdownFallback(text) {
  if (!text) return "";
  const lines = text.replace(/\r\n/g, "\n").split("\n");
  const out = [];
  let i = 0;
  let inFence = false;
  let fenceLang = "";
  let fenceLines = [];

  while (i < lines.length) {
    const line = lines[i];
    const fenceMatch = line.match(/^```([^\n`]*)?\s*$/);
    if (fenceMatch) {
      if (!inFence) {
        inFence = true;
        fenceLang = (fenceMatch[1] || "").trim();
        fenceLines = [];
      } else {
        out.push(wrapCodeBlock(fenceLines.join("\n"), fenceLang, "md-fenced"));
        inFence = false;
      }
      i += 1;
      continue;
    }
    if (inFence) {
      fenceLines.push(line);
      i += 1;
      continue;
    }
    const imageMatch = line.match(/^!\[([^\]]*)\]\(([^)]+)\)\s*$/);
    if (imageMatch) {
      out.push(buildImageHtml(imageMatch[1], imageMatch[2]));
      i += 1;
      continue;
    }
    if (/^#{1,6}\s+/.test(line)) {
      const level = line.match(/^#+/)[0].length;
      out.push(`<h${level}>${renderInlineMarkdown(line.replace(/^#+\s+/, ""))}</h${level}>`);
    } else if (/^>\s?/.test(line)) {
      out.push(`<blockquote>${renderInlineMarkdown(line.replace(/^>\s?/, ""))}</blockquote>`);
    } else {
      const listLine = renderListLine(line);
      if (listLine) {
        out.push(/^\s*\d+\./.test(line) ? `<ol>${listLine}</ol>` : `<ul>${listLine}</ul>`);
      } else if (line.trim() === "") {
        out.push("");
      } else {
        out.push(`<p>${renderInlineMarkdown(line)}</p>`);
      }
    }
    i += 1;
  }
  if (inFence && fenceLines.length) {
    out.push(wrapCodeBlock(fenceLines.join("\n"), fenceLang, "md-fenced"));
  }
  return out.filter(Boolean).join("\n");
}

function renderInlineMarkdown(line) {
  let s = escapeHtml(line);
  s = s.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (_, alt, url) => buildImageHtml(alt, url));
  s = s.replace(/`([^`]+)`/g, "<code class=\"inline-code\">$1</code>");
  s = s.replace(/~~(.*?)~~/g, "<del>$1</del>");
  s = s.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
  s = s.replace(/\*(.*?)\*/g, "<em>$1</em>");
  s = s.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_, label, url) => {
    const external = isExternalAssetSrc(url);
    const target = external ? ' target="_blank" rel="noopener noreferrer"' : "";
    return `<a href="${escapeHtml(url)}"${target}>${label}</a>`;
  });
  return s;
}

function renderListLine(line) {
  const task = line.match(/^\s*[-*+]\s+\[([ xX])\]\s+(.*)$/);
  if (task) {
    const checked = task[1].toLowerCase() === "x";
    return `<li class="task-item${checked ? " done" : ""}"><input type="checkbox" disabled${checked ? " checked" : ""} /> ${renderInlineMarkdown(task[2])}</li>`;
  }
  const bullet = line.match(/^\s*[-*+]\s+(.*)$/);
  if (bullet) {
    return `<li>${renderInlineMarkdown(bullet[1])}</li>`;
  }
  const ordered = line.match(/^\s*\d+\.\s+(.*)$/);
  if (ordered) {
    return `<li>${renderInlineMarkdown(ordered[1])}</li>`;
  }
  return null;
}

function renderCodeFilePreview(content, lang) {
  return wrapCodeBlock(content || "", lang || "plaintext", "code-file");
}

function renderDocumentBody(doc) {
  const lang = doc.lang || "text";
  if (lang === "markdown") {
    return parseMarkdown(doc.content || "");
  }
  return renderCodeFilePreview(doc.content || "", lang);
}

function renderDocumentPreview(doc, searchTerm) {
  previewDocContext = {
    docId: doc.id,
    sourceId: doc.source_id,
    relPath: doc.rel_path,
  };
  const breadcrumb = document.getElementById("docBreadcrumb");
  docMeta.textContent = `${doc.source_id} / ${doc.rel_path} (${doc.lang})`;
  if (breadcrumb) {
    breadcrumb.textContent = `${doc.source_id} / ${doc.rel_path}`;
  }
  docContent.className = "doc-content";
  docContent.classList.add(doc.lang === "markdown" ? "doc-markdown" : "doc-code");
  docContent.innerHTML = renderDocumentBody(doc);
  setDocImageToolbarVisible(doc.lang === "markdown");
  if (doc.lang === "markdown") {
    fixMisclassifiedProseBlocks(docContent);
    rewritePreviewImages(docContent);
    applyImageEnhanceState();
  }
  highlightInElement(docContent, searchTerm);
  currentMatchIndex = -1;
  updateMatchNav();
  if (typeof revealLibraryDocument === "function") {
    revealLibraryDocument(doc.source_id, doc.rel_path, doc.lang);
  }
  if (getSearchMarks().length) {
    scrollToMatch(0);
  }
}

function renderWikiMarkdown(content, wikiPath) {
  previewDocContext = { wikiPath: wikiPath || "" };
  docContent.className = "doc-content doc-markdown";
  docContent.innerHTML = parseMarkdown(content || "");
  setDocImageToolbarVisible(true);
  fixMisclassifiedProseBlocks(docContent);
  rewritePreviewImages(docContent);
  applyImageEnhanceState();
}

const IMAGE_ENHANCE_KEY = "mindsync.image.enhance";

function applyImageEnhanceState() {
  const toggle = document.getElementById("imageEnhanceToggle");
  let enabled = true;
  try {
    const saved = localStorage.getItem(IMAGE_ENHANCE_KEY);
    enabled = saved !== "0";
  } catch (_) {
    enabled = true;
  }
  if (toggle) toggle.checked = enabled;
  if (docContent) docContent.classList.toggle("doc-image-enhanced", enabled);
}

function initImageEnhanceToggle() {
  const toggle = document.getElementById("imageEnhanceToggle");
  if (!toggle) return;
  applyImageEnhanceState();
  toggle.onchange = () => {
    try {
      localStorage.setItem(IMAGE_ENHANCE_KEY, toggle.checked ? "1" : "0");
    } catch (_) {
      // ignore
    }
    applyImageEnhanceState();
  };
}

initImageEnhanceToggle();
