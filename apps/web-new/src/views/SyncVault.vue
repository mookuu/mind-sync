<template>
  <div class="view-pane">
    <div class="view-header"><h2>🔐 全局</h2></div>
    <div class="vault-status-card">
      <p class="vault-text">{{ statusText }}</p>
      <div class="vault-actions">
        <button class="btn btn-primary" @click="vaultPull" :disabled="!configured">拉取</button>
        <button class="btn btn-ghost" @click="vaultPush" :disabled="!configured">推送</button>
      </div>
      <p v-if="actionMsg" class="status-msg">{{ actionMsg }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import api from "../api/index.js";

const configured = ref(false);
const statusText = ref("加载中…");
const actionMsg = ref("");

async function loadStatus() {
  try {
    const data = await api("/api/vault-status");
    configured.value = data.configured || false;
    if (!data.configured) {
      statusText.value = "未配置 VAULT_GIT_URL。在 .env 中设置后重启 API，可将 wiki 与 purpose 同步到私有 Git 仓。";
    } else {
      statusText.value = `已配置：${data.url || ""}（分支 ${data.branch || "main"}）· 本地 ${data.has_clone ? "已克隆" : "未克隆"}`;
    }
  } catch (e) {
    statusText.value = `加载失败: ${e.message}`;
  }
}

async function vaultPull() {
  actionMsg.value = "拉取中…";
  try {
    const data = await api("/api/vault-sync", { method: "POST", body: { pull: true, push: false } });
    actionMsg.value = data.pull?.skipped ? "未配置远程" : "拉取完成";
    await loadStatus();
  } catch (e) {
    actionMsg.value = `拉取失败: ${e.message}`;
  }
}

async function vaultPush() {
  actionMsg.value = "推送中…";
  try {
    const data = await api("/api/vault-sync", { method: "POST", body: { pull: false, push: true } });
    actionMsg.value = data.push?.skipped ? "未配置远程" : "推送完成";
  } catch (e) {
    actionMsg.value = `推送失败: ${e.message}`;
  }
}

onMounted(loadStatus);
</script>

<style scoped>
.vault-status-card {
  border: 1px solid var(--border-default);
  border-radius: var(--radius);
  padding: 16px;
  margin-top: 16px;
}
.vault-text { font-size: 0.9rem; margin-bottom: 12px; }
.vault-actions { display: flex; gap: 8px; }
.status-msg { margin-top: 8px; font-size: 0.85rem; color: var(--fg-muted); }
</style>
