const loginBtn = document.getElementById("loginBtn");
const syncBtn = document.getElementById("syncBtn");
const searchBtn = document.getElementById("searchBtn");
const pwdInput = document.getElementById("pwd");
const qInput = document.getElementById("q");
const sourceFilter = document.getElementById("sourceFilter");
const typeFilter = document.getElementById("typeFilter");
const askInput = document.getElementById("askQ");
const askBtn = document.getElementById("askBtn");
const saveInsight = document.getElementById("saveInsight");
const askMeta = document.getElementById("askMeta");
const askAnswer = document.getElementById("askAnswer");
const settingsBtn = document.getElementById("settingsBtn");
const settingsModal = document.getElementById("settingsModal");
const closeSettingsBtn = document.getElementById("closeSettingsBtn");
const saveSettingsBtn = document.getElementById("saveSettingsBtn");
const autoSyncEnabled = document.getElementById("autoSyncEnabled");
const autoSyncInterval = document.getElementById("autoSyncInterval");
const settingsStatus = document.getElementById("settingsStatus");
const loginStatus = document.getElementById("loginStatus");
const nextAutoSyncText = document.getElementById("nextAutoSyncText");
const lastAutoSyncText = document.getElementById("lastAutoSyncText");
const results = document.getElementById("results");
const docMeta = document.getElementById("docMeta");
const docContent = document.getElementById("docContent");
let autoSyncTimer = null;

function setStatus(text) {
  loginStatus.textContent = text;
}

async function api(path, options = {}) {
  const res = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    credentials: "include",
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail || `HTTP ${res.status}`);
  }
  return data;
}

function renderSimpleMarkdown(text) {
  if (!text) return "";
  const escaped = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  return escaped
    .replace(/^###\s+(.*)$/gm, "<h4>$1</h4>")
    .replace(/^##\s+(.*)$/gm, "<h3>$1</h3>")
    .replace(/^#\s+(.*)$/gm, "<h2>$1</h2>")
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\n/g, "<br/>");
}

window.onclick = (e) => {
  if (e.target === settingsModal) {
    settingsModal.classList.add("hidden");
  }
};

async function loadSourcesFilter() {
  try {
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
      lastAutoSyncText.textContent = "最近一次自动同步状态：--";
    } else if (last.status === "running") {
      lastAutoSyncText.textContent = "最近一次自动同步状态：进行中";
    } else {
      const t = last.finished_at ? new Date(last.finished_at * 1000).toLocaleString() : "--";
      const status = last.status || "unknown";
      const detail = last.error
        ? `失败（${last.error}）`
        : `成功（indexed=${last.indexed || 0}, skipped=${last.skipped || 0}, deleted=${last.deleted || 0}）`;
      lastAutoSyncText.textContent = `最近一次自动同步状态：${status} @ ${t} ${detail}`;
    }
  } catch (e) {
    // ignore before login
  }
}

loginBtn.onclick = async () => {
  try {
    await api("/api/login", {
      method: "POST",
      body: JSON.stringify({ password: pwdInput.value }),
    });
    setStatus("登录成功");
    await loadSourcesFilter();
    await loadSettings();
    if (autoSyncTimer) clearInterval(autoSyncTimer);
    autoSyncTimer = setInterval(() => {
      loadSettings();
    }, 15000);
  } catch (e) {
    setStatus(`登录失败: ${e.message}`);
  }
};

syncBtn.onclick = async () => {
  try {
    setStatus("同步中...");
    await api("/api/sync", { method: "POST" });
    const deadline = Date.now() + 15 * 60 * 1000;
    while (Date.now() < deadline) {
      await new Promise((r) => setTimeout(r, 2000));
      const status = await api("/api/sync-status");
      if (status.running) {
        if (status.current_source) {
          setStatus(
            `同步中... ${status.current_source} (${status.processed_files}/${status.total_files})`
          );
        } else {
          setStatus("同步中...正在索引");
        }
        continue;
      }
      if (status.error) {
        setStatus(`同步失败: ${status.error}`);
      } else {
        setStatus(`同步完成：新增/更新 ${status.indexed}，跳过 ${status.skipped}，删除 ${status.deleted}`);
      }
      await loadSettings();
      return;
    }
    setStatus("同步超时：请稍后重试");
  } catch (e) {
    setStatus(`同步失败: ${e.message}`);
  }
};

searchBtn.onclick = async () => {
  const q = qInput.value.trim();
  if (!q) return;
  results.innerHTML = "";
  docMeta.textContent = "";
  docContent.textContent = "";
  try {
    const params = new URLSearchParams({ q });
    if (sourceFilter.value) params.set("source_id", sourceFilter.value);
    if (typeFilter.value) params.set("file_type", typeFilter.value);
    const data = await api(`/api/search?${params.toString()}`);
    for (const item of data.items) {
      const li = document.createElement("li");
      li.innerHTML = `<div><b>${item.source_id}</b> / ${item.rel_path}</div><div>${item.snippet || ""}</div>`;
      li.onclick = async () => {
        const doc = await api(`/api/document/${item.id}`);
        docMeta.textContent = `${doc.source_id} / ${doc.rel_path} (${doc.lang})`;
        if (doc.lang === "markdown") {
          docContent.innerHTML = renderSimpleMarkdown(doc.content);
        } else {
          docContent.textContent = doc.content;
        }
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

askBtn.onclick = async () => {
  const question = askInput.value.trim();
  if (!question) return;
  askMeta.textContent = "";
  askAnswer.textContent = "";
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
    askMeta.textContent = `模型: ${data.model_used} | LLM: ${data.used_llm ? "是" : "否"}${
      data.saved_path ? ` | 已保存: ${data.saved_path}` : ""
    }`;
    askAnswer.innerHTML = renderSimpleMarkdown(data.answer || "");
    setStatus("问答完成");
  } catch (e) {
    setStatus(`问答失败: ${e.message}`);
  }
};

askInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") askBtn.onclick();
});

settingsBtn.onclick = async () => {
  settingsModal.classList.remove("hidden");
  await loadSettings();
  settingsStatus.textContent = "";
};

closeSettingsBtn.onclick = () => {
  settingsModal.classList.add("hidden");
};

saveSettingsBtn.onclick = async () => {
  try {
    settingsStatus.textContent = "保存中...";
    const data = await api("/api/settings", {
      method: "POST",
      body: JSON.stringify({
        auto_sync_enabled: !!autoSyncEnabled.checked,
        auto_sync_interval_minutes: Number(autoSyncInterval.value || 60),
      }),
    });
    settingsStatus.textContent = `已保存：自动同步=${data.auto_sync_enabled ? "开" : "关"}，间隔=${data.auto_sync_interval_minutes}分钟`;
    await loadSettings();
  } catch (e) {
    settingsStatus.textContent = `保存失败: ${e.message}`;
  }
};
