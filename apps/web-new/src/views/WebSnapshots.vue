<template>
  <div class="view-pane">
    <div class="view-header"><h2>🌍 Web 快照管理</h2></div>
    <p class="subtle">管理 type:web 源，添加后通过同步控制页面执行抓取。</p>

    <div class="toolbar">
      <button class="btn btn-primary btn-sm" @click="openAdd">＋ 添加快照</button>
      <button class="btn btn-ghost btn-sm" @click="refresh">↻ 刷新</button>
    </div>

    <table class="snapshot-table" v-if="snapshots.length">
      <thead>
        <tr><th>ID</th><th>URL</th><th>存储路径</th><th>操作</th></tr>
      </thead>
      <tbody>
        <tr v-for="s in snapshots" :key="s.id">
          <td><strong>{{ s.label }}</strong></td>
          <td class="url-cell">{{ s.url }}</td>
          <td class="path-cell">{{ displayPath(s.path) }}</td>
          <td>
            <button class="btn btn-ghost btn-xs btn-danger-text" @click="confirmDelete(s)" :disabled="deleting === s.id">删除</button>
          </td>
        </tr>
      </tbody>
    </table>
    <p v-else class="subtle" style="padding:20px">暂无 Web 快照</p>

    <!-- 添加弹窗 -->
    <div v-if="showAdd" class="modal-overlay" @click.self="showAdd = false">
      <div class="modal modal-sm">
        <div class="modal-header"><h4>添加 Web 快照</h4><button class="btn btn-ghost btn-sm" @click="showAdd = false">✕</button></div>
        <div class="modal-body">
          <div class="field">
            <label>快照 ID</label>
            <input v-model="newSnap.id" type="text" placeholder="如 my-docs" />
          </div>
          <div class="field">
            <label>URL</label>
            <input v-model="newSnap.url" type="text" placeholder="https://example.com/docs" />
          </div>
          <div class="field">
            <label>存储路径（可选）</label>
            <input v-model="newSnap.path" type="text" placeholder="默认：~/data/mind-sync-data/web_snapshots" />
          </div>
          <p v-if="addMsg" class="status-msg" :class="{ error: addError }">{{ addMsg }}</p>
        </div>
        <div class="modal-footer">
          <button class="btn btn-ghost" @click="showAdd = false">取消</button>
          <button class="btn btn-primary" @click="doAdd" :disabled="adding">添加</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import api from "../api/index.js";

const snapshots = ref([]);
const showAdd = ref(false);
const adding = ref(false);
const addMsg = ref("");
const addError = ref(false);
const deleting = ref("");

const newSnap = ref({ id: "", url: "", path: "" });

function displayPath(p) {
  if (!p) return "";
  return p.replace(/^\/home\/moku\//, "~/").replace(/^\/data\//, "~/data/mind-sync-data/");
}

async function load() {
  try {
    const data = await api("/api/admin/web-snapshots");
    snapshots.value = data.snapshots || [];
  } catch {
    snapshots.value = [];
  }
}

async function refresh() { await load(); }

function openAdd() {
  newSnap.value = { id: "", url: "", path: "" };
  addMsg.value = "";
  addError.value = false;
  showAdd.value = true;
}

async function doAdd() {
  const id = newSnap.value.id.trim();
  const url = newSnap.value.url.trim();
  if (!id || !url) {
    addMsg.value = "ID 和 URL 不能为空";
    addError.value = true;
    return;
  }
  adding.value = true;
  try {
    await api("/api/admin/web-snapshots", { method: "POST", body: { id, url, path: newSnap.value.path.trim() } });
    showAdd.value = false;
    await load();
  } catch (e) {
    addMsg.value = e.message || "添加失败";
    addError.value = true;
  } finally {
    adding.value = false;
  }
}

function confirmDelete(s) {
  if (!confirm(`确认删除快照「${s.label}」？`)) return;
  deleting.value = s.id;
  api(`/api/admin/web-snapshots/${encodeURIComponent(s.id)}`, { method: "DELETE" })
    .then(() => load())
    .catch(e => alert(e.message || "删除失败"))
    .finally(() => { deleting.value = ""; });
}

onMounted(load);
</script>

<style scoped>
.snapshot-table { width: 100%; border-collapse: collapse; margin-top: 12px; }
.snapshot-table th, .snapshot-table td { text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--border-muted); font-size: 0.85rem; }
.snapshot-table th { font-weight: 600; color: var(--fg-muted); font-size: 0.78rem; }
.url-cell { font-family: var(--font-mono); font-size: 0.78rem; max-width: 400px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.path-cell { font-family: var(--font-mono); font-size: 0.78rem; color: var(--fg-subtle); }
.toolbar { display: flex; gap: 8px; margin: 12px 0; }
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 100; }
.modal { background: var(--bg-card); border: 1px solid var(--border-default); border-radius: var(--radius-lg); max-height: 80vh; display: flex; flex-direction: column; box-shadow: var(--shadow-lg); }
.modal-sm { width: 480px; }
.modal-header { display: flex; justify-content: space-between; align-items: center; padding: 14px 16px; border-bottom: 1px solid var(--border-muted); }
.modal-header h4 { font-size: 1rem; font-weight: 600; }
.modal-body { padding: 12px 16px; overflow-y: auto; flex: 1; }
.modal-footer { display: flex; justify-content: flex-end; gap: 8px; padding: 10px 16px; border-top: 1px solid var(--border-muted); }
.field { margin-bottom: 12px; }
.field label { display: block; font-size: 0.82rem; font-weight: 500; color: var(--fg-muted); margin-bottom: 4px; }
.field input { width: 100%; padding: 8px 10px; font-size: 0.9rem; border: 1px solid var(--border-default); border-radius: var(--radius); background: var(--bg-card); color: var(--fg-default); }
.status-msg { margin-top: 8px; font-size: 0.85rem; }
.status-msg.error { color: var(--danger-fg); }
.btn-danger-text { color: var(--danger-fg); }
.btn-danger-text:hover { background: rgba(220, 38, 38, 0.1); }
</style>
