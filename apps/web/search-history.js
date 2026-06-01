/** Search history + sort helpers (localStorage). */
(function () {
  const KEY = "mindsync.search.history";
  const MAX = 20;

  function loadHistory() {
    try {
      const raw = localStorage.getItem(KEY);
      const arr = raw ? JSON.parse(raw) : [];
      return Array.isArray(arr) ? arr : [];
    } catch (_) {
      return [];
    }
  }

  function saveHistory(items) {
    try {
      localStorage.setItem(KEY, JSON.stringify(items.slice(0, MAX)));
    } catch (_) {
      // ignore
    }
  }

  function recordSearch(term) {
    const q = (term || "").trim();
    if (!q) return;
    const items = loadHistory().filter((x) => x !== q);
    items.unshift(q);
    saveHistory(items);
  }

  function renderDatalist(datalistEl) {
    if (!datalistEl) return;
    datalistEl.innerHTML = "";
    for (const q of loadHistory()) {
      const opt = document.createElement("option");
      opt.value = q;
      datalistEl.appendChild(opt);
    }
  }

  window.MindSyncSearch = {
    loadHistory,
    recordSearch,
    renderDatalist,
    getSort: () => {
      const el = document.getElementById("searchSort");
      return el && el.value ? el.value : "relevance";
    },
  };
})();
