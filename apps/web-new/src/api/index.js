// Global flag: set to a callback that runs on 401 to redirect to login
let onUnauthorized = null;

export function setOnUnauthorized(cb) {
  onUnauthorized = cb;
}

export function clearAuthCookies() {
  document.cookie = "ms_token=; path=/; max-age=0";
  document.cookie = "ms_csrf=; path=/; max-age=0";
}

async function request(path, options = {}) {
  const BASE = "";
  const url = `${BASE}${path}`;
  const { body, method = "GET", ...rest } = options;
  const headers = { ...rest.headers };
  if (body && !(body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }
  // CSRF: attach token from cookie
  const csrfCookie = document.cookie
    .split("; ")
    .find((c) => c.startsWith("ms_csrf="));
  if (csrfCookie) {
    const token = csrfCookie.split("=")[1];
    if (token) {
      headers["x-csrf-token"] = token;
    }
  }
  const res = await fetch(url, {
    method,
    headers,
    body: body ? (typeof body === "string" ? body : JSON.stringify(body)) : undefined,
    credentials: "include",
    ...rest,
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const err = await res.json();
      detail = err.detail || detail;
    } catch {
      // ignore parse error
    }
    // Global 401 → session expired or invalid, redirect to login
    if (res.status === 401 && onUnauthorized) {
      clearAuthCookies();
      onUnauthorized();
    }
    throw new Error(detail);
  }
  const text = await res.text();
  return text ? JSON.parse(text) : null;
}

export function api(path, options) {
  return request(path, options);
}

export default api;
