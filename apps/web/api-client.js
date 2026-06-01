/** Shared API client (loaded before app.js). */
(function () {
  let csrfHeaderName = "x-csrf-token";
  var DEFAULT_TIMEOUT_MS = 120_000;

  function readCookie(name) {
    var raw = document.cookie || "";
    var prefix = name + "=";
    for (var _i = 0, _a = raw.split(";").map(function (p) { return p.trim(); }); _i < _a.length; _i++) {
      var part = _a[_i];
      if (part.startsWith(prefix)) {
        return decodeURIComponent(part.slice(prefix.length));
      }
    }
    return "";
  }

  function apiErrorClass(status) {
    if (status >= 500) return "server";
    if (status === 429) return "rate_limit";
    if (status === 401 || status === 403) return "auth";
    if (status >= 400) return "client";
    return "";
  }

  async function api(path, options) {
    if (options === void 0) { options = {}; }
    var method = String(options.method || "GET").toUpperCase();
    var timeout = options.timeout || DEFAULT_TIMEOUT_MS;
    var headers = Object.assign({ "Content-Type": "application/json" }, options.headers || {});

    if (["POST", "PUT", "PATCH", "DELETE"].indexOf(method) !== -1) {
      var csrfToken = readCookie("ms_csrf");
      if (csrfToken) { headers[csrfHeaderName] = csrfToken; }
    }

    // Timeout via AbortController
    var controller = new AbortController();
    var timerId = setTimeout(function () { controller.abort(); }, timeout);
    var fetchOpts = { method: method, headers: headers, credentials: "include", signal: controller.signal };
    // Copy over any extra options (body, etc.) but not our custom ones
    for (var k in options) {
      if (options.hasOwnProperty(k) && k !== "method" && k !== "headers" && k !== "timeout") {
        fetchOpts[k] = options[k];
      }
    }

    var res;
    try {
      res = await fetch(path, fetchOpts);
    } catch (fetchErr) {
      clearTimeout(timerId);
      var errMsg = fetchErr.name === "AbortError"
        ? "\u8bf7\u6c42\u8d85\u65f6\uff08" + (timeout / 1000).toFixed(0) + "\u79d2\uff09\uff1a" + path
        : "\u7f51\u7edc\u8bf7\u6c42\u5931\u8d25\uff1a" + (fetchErr.message || "\u65e0\u6cd5\u8fde\u63a5\u5230\u670d\u52a1\u5668");
      var err2 = new Error(errMsg);
      err2.status = 0;
      err2.data = {};
      err2.is_network_error = true;
      throw err2;
    } finally {
      clearTimeout(timerId);
    }

    var data = await res.json().catch(function () { return ({}); });
    if (!res.ok) {
      var err3 = new Error(data.detail || ("HTTP " + res.status));
      err3.status = res.status;
      err3.data = data;
      err3.error_category = apiErrorClass(res.status);
      throw err3;
    }
    return data;
  }

  window.MindSyncApi = {
    api: api,
    readCookie: readCookie,
    getCsrfHeaderName: function () { return csrfHeaderName; },
    setCsrfHeaderName: function (name) {
      if (name && String(name).trim()) { csrfHeaderName = String(name).trim().toLowerCase(); }
    },
    DEFAULT_TIMEOUT_MS: DEFAULT_TIMEOUT_MS,
  };
})();
