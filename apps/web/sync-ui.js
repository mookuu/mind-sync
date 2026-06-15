/** Sync status, audit, lint, settings loaders (depends on app-shared.js). */
async function runWikiLint() {
  if (!isLoggedIn || !runLintBtn) return;
  runLintBtn.disabled = true;
  if (lintStatus) lintStatus.textContent = "Lint 运行中…";
  if (lintSummary) {
    lintSummary.classList.add("hidden");
    lintSummary.textContent = "";
  }
  try {
    const data = await api("/api/lint", { method: "POST", body: JSON.stringify({ stale_days: 180 }) });
    const issues = data.issues || [];
    const reportPath = data.report_path || data.path || "";
    if (lintStatus) {
      lintStatus.textContent = `Lint 完成：${issues.length} 个问题${reportPath ? ` · 报告 ${reportPath}` : ""}`;
    }
    if (lintSummary) {
      const preview = issues.slice(0, 12).map((item) => `[${item.type}] ${item.source_id}/${item.rel_path} — ${item.detail}`).join("\n");
      lintSummary.textContent = preview || "未发现问题。";
      lintSummary.classList.remove("hidden");
    }
  } catch (e) {
    if (lintStatus) lintStatus.textContent = `Lint 失败: ${e.message}`;
  } finally {
    runLintBtn.disabled = false;
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
      lastAutoSyncText.textContent = `最近一次自动同步状态：${last.status || "idle"}（尚未执行）`;
    } else if (last.status === "running") {
      lastAutoSyncText.textContent = "最近一次自动同步状态：进行中";
    } else {
      const t = last.finished_at ? new Date(last.finished_at * 1000).toLocaleString() : "--";
      const status = last.status || "unknown";
      const detail = last.error
        ? `失败（${last.error}）`
        : `成功（新增/更新 ${last.indexed || 0}，跳过 ${last.skipped || 0}，删除 ${last.deleted || 0}）`;
      lastAutoSyncText.textContent = `最近一次自动同步状态：${status} @ ${t} ${detail}`;
    }
  } catch (e) {
    // ignore before login
  }
}

function formatSyncTrigger(trigger) {
  if (trigger === "auto") return "自动";
  if (trigger === "manual") return "手动";
  return trigger || "未知";
}

function formatSyncCounts(indexed, skipped, deleted, cleared, mode) {
  if (mode === "rebuild") {
    return `清空 ${cleared || 0}，重建 ${indexed || 0}，超大跳过 ${skipped || 0}，删除 ${deleted || 0}`;
  }
  return `新增/更新 ${indexed || 0}，跳过 ${skipped || 0}，删除 ${deleted || 0}`;
}

function formatJobMode(mode) {
  return mode === "rebuild" ? "全量重建" : "增量同步";
}

function renderSyncPanel(status = {}) {
  const mode = status.job_mode || status.last_completed?.mode || "sync";
  const modeLabel = formatJobMode(mode);
  if (status.running) {
    const src = status.current_source || "准备中";
    const prog = `${status.processed_files || 0}/${status.total_files || 0}`;
    syncProgressText.textContent = `当前${modeLabel}：${src} (${prog}) — ${formatSyncCounts(
      status.indexed,
      status.skipped,
      status.deleted,
      status.cleared,
      mode
    )}`;
    syncProgressText.classList.add("sync-active");
  } else {
    syncProgressText.textContent = `当前任务：空闲`;
    syncProgressText.classList.remove("sync-active");
  }

  const last = status.last_completed || {};
  const backoff = (status.source_backoff || []).filter((b) => b.in_backoff);
  if (!last.finished_at) {
    lastSyncSummaryText.textContent = backoff.length
      ? `最近一次索引任务：尚未执行 · ${backoff.length} 个源在退避冷却`
      : "最近一次索引任务：尚未执行";
    if (backoff.length && syncProgressText) {
      const detail = backoff.map((b) => `${b.source_id}(${b.seconds_remaining}s)`).join(", ");
      syncProgressText.textContent = `${syncProgressText.textContent} · 退避: ${detail}`;
    }
    return;
  }
  const when = formatAuditTime(last.finished_at);
  const trigger = formatSyncTrigger(last.trigger);
  const lastMode = formatJobMode(last.mode || "sync");
  const counts = formatSyncCounts(last.indexed, last.skipped, last.deleted, last.cleared, last.mode);
  if (last.status === "failed" || last.error) {
    lastSyncSummaryText.textContent = `最近一次${lastMode}：失败（${trigger}） @ ${when} — ${counts}；${last.error || "未知错误"}`;
    return;
  }
  const warn = (status.warnings || last.warnings || []).length
    ? `；警告 ${(status.warnings || last.warnings).length} 条`
    : "";
  lastSyncSummaryText.textContent = `最近一次${lastMode}：成功（${trigger}） @ ${when} — ${counts}${warn}`;
  if (backoff.length) {
    const detail = backoff.map((b) => `${b.source_id}(${b.seconds_remaining}s)`).join(", ");
    lastSyncSummaryText.textContent += ` · 退避: ${detail}`;
  }
  if ((status.warnings || []).length) {
    syncProgressText.textContent = `${syncProgressText.textContent} · ${status.warnings[0]}`;
  }
}

async function loadSyncStatus() {
  if (!isLoggedIn) return null;
  try {
    const status = await api("/api/sync-status");
    renderSyncPanel(status);
    return status;
  } catch (e) {
    return null;
  }
}

const AUDIT_EVENT_LABELS = {
  login_failed: "登录失败",
  login_success: "登录成功",
  logout: "退出登录",
  settings_updated: "设置变更",
  purpose_updated: "研究方向更新",
  sync_requested: "同步请求",
  sync_completed: "同步完成",
  sources_reloaded: "重载 sources.yaml",
  sources_custom_added: "添加自定义源",
  rebuild_requested: "全量重建请求",
  rebuild_completed: "全量重建完成",
};

function formatAuditEventType(eventType) {
  return AUDIT_EVENT_LABELS[eventType] || eventType || "未知事件";
}

function formatAuditTime(ts) {
  const n = Number(ts);
  if (!Number.isFinite(n) || n <= 0) return "--";
  return new Date(n * 1000).toLocaleString();
}

function renderAuditEvents(items = []) {
  auditList.innerHTML = "";
  auditListTitle.textContent = `最近审计 (${items.length} 条)`;
  if (!items.length) {
    const li = document.createElement("li");
    li.textContent = "暂无审计记录";
    auditList.appendChild(li);
    return;
  }
  for (const item of items) {
    const li = document.createElement("li");
    const eventType = String(item.event_type || "");
    const typeClass = eventType.replace(/[^a-z0-9_]/gi, "");
    li.innerHTML = `
      <div class="audit-top">
        <span class="audit-type ${escapeHtml(typeClass)}">${escapeHtml(formatAuditEventType(eventType))}</span>
        <span class="audit-meta">${escapeHtml(formatAuditTime(item.created_at))}</span>
      </div>
      <div class="audit-meta">${escapeHtml(item.actor || "unknown")} · ${escapeHtml(item.ip || "unknown")}</div>
      <div class="audit-detail">${escapeHtml(item.detail || "")}</div>
    `;
    auditList.appendChild(li);
  }
}

async function loadAuditEvents() {
  if (!isLoggedIn) return;
  auditStatus.textContent = "加载中...";
  try {
    const data = await api("/api/audit-events?limit=30");
    const items = data.items || [];
    renderAuditEvents(items);
    auditStatus.textContent = `显示最近 ${items.length} 条（只读）`;
  } catch (e) {
    auditList.innerHTML = "";
    auditListTitle.textContent = "最近审计";
    auditStatus.textContent = `加载失败: ${e.message}`;
  }
}
