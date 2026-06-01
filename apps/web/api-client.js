/** Shared API client (loaded before app.js). */
(function () {
  let csrfHeaderName = "x-csrf-token";

  function readCookie(name) {
    const raw = document.cookie || "";
    const prefix = `${name}=`;
    for (const part of raw.split(";").map((p) => p.trim())) {
      if (part.startsWith(prefix)) {
        return decodeURIComponent(part.slice(prefix.length));
      }
    }
    return "";
  }

  async function api(path, options = {}) {
    const method = String(options.method || "GET").toUpperCase();
    const headers = {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    };
    if (["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
      const csrfToken = readCookie("ms_csrf");
      if (csrfToken) headers[csrfHeaderName] = csrfToken;
    }
    const res = await fetch(path, { ...options, method, headers, credentials: "include" });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const err = new Error(data.detail || `HTTP ${res.status}`);
      err.status = res.status;
      err.data = data;
      throw err;
    }
    return data;
  }

  window.MindSyncApi = {
    api,
    readCookie,
    getCsrfHeaderName: () => csrfHeaderName,
    setCsrfHeaderName: (name) => {
      if (name && String(name).trim()) csrfHeaderName = String(name).trim().toLowerCase();
    },
  };
})();
