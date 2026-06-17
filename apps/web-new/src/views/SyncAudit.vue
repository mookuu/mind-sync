<template>
  <div class="view-pane">
    <div class="view-header">
      <h2>📜 审计日志</h2>
    </div>
    <div class="audit-list">
      <div v-for="item in events" :key="item.id || item.created_at" class="audit-card">
        <div class="audit-top">
          <span class="audit-type">{{ formatType(item.event_type) }}</span>
          <span class="audit-time">{{ formatTime(item.created_at) }}</span>
        </div>
        <div class="audit-meta">{{ item.actor || "unknown" }} · {{ item.ip || "unknown" }}</div>
        <div v-if="item.detail" class="audit-detail">{{ item.detail }}</div>
      </div>
      <p v-if="!events.length" class="subtle">暂无审计记录</p>
    </div>
    <p class="status-msg">{{ statusText }}</p>
    <button class="btn btn-ghost btn-sm" @click="refresh">刷新</button>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import api from "../api/index.js";

const events = ref([]);
const statusText = ref("加载中…");

const LABELS = {
  login_failed: "登录失败", login_success: "登录成功", logout: "退出登录",
  settings_updated: "设置变更", purpose_updated: "规则约束更新",
  password_reset: "密码重置",
  sync_requested: "同步请求", sync_completed: "同步完成",
  sources_reloaded: "重载 sources.yaml", sources_custom_added: "添加自定义源",
  rebuild_requested: "全量重建请求", rebuild_completed: "全量重建完成",
};

function formatType(t) {
  return LABELS[t] || t || "未知事件";
}
function formatTime(ts) {
  const n = Number(ts);
  if (!Number.isFinite(n) || n <= 0) return "--";
  return new Date(n * 1000).toLocaleString();
}

async function refresh() {
  statusText.value = "加载中…";
  try {
    const data = await api("/api/audit-events?limit=30");
    events.value = data.items || [];
    statusText.value = `显示最近 ${events.value.length} 条`;
  } catch (e) {
    statusText.value = `加载失败: ${e.message}`;
    events.value = [];
  }
}

onMounted(refresh);
</script>

<style scoped>
.audit-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin: 16px 0;
}
.audit-card {
  border: 1px solid var(--border-default);
  border-radius: var(--radius);
  padding: 10px 14px;
  font-size: 0.85rem;
}
.audit-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.audit-type {
  font-weight: 600;
  font-size: 0.82rem;
  padding: 1px 6px;
  border-radius: 3px;
  background: var(--bg-muted);
}
.audit-time { color: var(--fg-subtle); font-size: 0.8rem; }
.audit-meta { color: var(--fg-subtle); font-size: 0.8rem; margin-top: 2px; }
.audit-detail { color: var(--fg-muted); margin-top: 4px; }
.status-msg { font-size: 0.85rem; color: var(--fg-subtle); margin-bottom: 8px; }
</style>
