<template>
  <div class="view-pane">
    <div class="view-header"><h2>📦 素材管理</h2></div>

    <!-- 同步范围 -->
    <section class="settings-section">
      <h3>同步范围</h3>
      <p class="subtle">勾选要同步的来源，修改后立即生效</p>

      <div class="preset-list">
        <!-- 全部来源（master toggle） -->
        <label class="preset-option" :class="{ selected: isAll }">
          <input type="checkbox" :checked="isAll" @change="onToggleAll" />
          <div>
            <div class="preset-label">全部同步</div>
            <div class="preset-desc">同步 sources.yaml 中所有已配置来源</div>
          </div>
        </label>

        <!-- 共享来源（管理员配置） -->
        <div class="section-label">
          <span>📚 共享知识库</span>
          <span class="subtle">管理员配置，团队成员可见</span>
        </div>
        <div
          v-for="p in sharedPresets"
          :key="p.id"
          class="preset-row"
          :style="isAll ? disabledStyle : {}"
        >
          <label class="preset-option" :class="{ selected: !isAll && customPresetIds.includes(p.id) }">
            <input
              type="checkbox"
              :value="p.id"
              :checked="customPresetIds.includes(p.id)"
              :disabled="isAll"
              @change="onTogglePreset(p.id)"
            />
            <div>
              <div class="preset-label">{{ p.label }}</div>
              <div class="preset-desc">{{ p.description || "" }}</div>
            </div>
          </label>
          <button
            v-if="!defaultPresetIds.includes(p.id) && isAdmin"
            class="btn btn-ghost btn-sm delete-source-btn"
            title="删除此共享来源"
            :disabled="isAll || deleting === p.id"
            @click="deleteSharedSource(p)"
          >✕</button>
        </div>

        <!-- 我的私有来源 -->
        <div class="section-label" style="margin-top:8px">
          <span>🔒 我的知识库</span>
          <span class="subtle">仅自己可见</span>
        </div>
        <div class="custom-path-row">
          <input v-model="privatePath" type="text" placeholder="输入服务器文件夹路径" class="custom-path-input" />
          <button class="btn btn-ghost" @click="openPrivateDirPicker">📁 浏览</button>
          <button class="btn btn-primary" @click="addPrivateSource" :disabled="addingPrivate">
            {{ addingPrivate ? "添加中…" : "添加" }}
          </button>
        </div>
        <p v-if="privateMsg" class="status-msg" :class="{ error: privateError }">{{ privateMsg }}</p>
        <div
          v-for="p in myPrivatePresets"
          :key="p.id"
          class="preset-row"
          :style="isAll ? disabledStyle : {}"
        >
          <label class="preset-option" :class="{ selected: !isAll && customPresetIds.includes(p.id) }">
            <input
              type="checkbox"
              :value="p.id"
              :checked="customPresetIds.includes(p.id)"
              :disabled="isAll"
              @change="onTogglePreset(p.id)"
            />
            <div>
              <div class="preset-label">{{ p.label }}</div>
              <div class="preset-desc">{{ p.description || "" }}</div>
            </div>
          </label>
          <button
            class="btn btn-ghost btn-sm delete-source-btn"
            title="删除我的私有来源"
            :disabled="isAll || deleting === p.id"
            @click="deletePrivateSource(p)"
          >✕</button>
        </div>
      </div>

      <!-- 删除确认弹窗 -->
      <div v-if="confirmDelete" class="modal-overlay" @click.self="confirmDelete = null">
        <div class="confirm-dialog">
          <p>确认删除「<strong>{{ confirmDelete.label }}</strong>」？</p>
          <p class="subtle">此操作不可撤销</p>
          <div class="btn-row" style="justify-content:flex-end;margin-top:12px">
            <button class="btn btn-ghost" @click="confirmDelete = null">取消</button>
            <button class="btn btn-danger btn-sm" @click="doDelete" :disabled="deleting === confirmDelete.id">
              {{ deleting === confirmDelete.id ? "删除中…" : "确认删除" }}
            </button>
          </div>
        </div>
      </div>

    </section>

    <!-- 自定义路径（管理员添加共享源） -->
    <section class="settings-section" v-if="isAdmin">
      <h3>添加共享来源</h3>
      <p class="subtle">手动输入文件夹路径（添加为共享知识库）</p>
      <div class="custom-path-row">
        <input v-model="customPath" type="text" placeholder="输入文件夹路径，如 /sources/my-notes" class="custom-path-input" />
        <button class="btn btn-ghost" @click="openDirPicker">📁 浏览</button>
        <button class="btn btn-primary" @click="addCustomPath" :disabled="addingPath">{{ addingPath ? "验证中…" : "添加" }}</button>
      </div>
      <p v-if="pathMsg" class="status-msg" :class="{ error: pathError }">{{ pathMsg }}</p>

      <!-- 目录选择弹窗 -->
      <div v-if="showDirPicker" class="modal-overlay" @click.self="showDirPicker = false">
        <div class="modal">
          <div class="modal-header">
            <h4>选择文件夹</h4>
            <button class="btn btn-ghost btn-sm" @click="showDirPicker = false">✕</button>
          </div>
          <div class="modal-body">
            <div class="dir-browse-row">
              <input v-model="dirCurrentPath" type="text" class="dir-path-input" />
              <button class="btn btn-sm btn-ghost" @click="loadDir(dirCurrentPath)">跳转</button>
            </div>
            <ul class="dir-list">
              <li class="dir-item parent" @click="loadDir(dirParent)">⬆ ..</li>
              <li v-for="entry in dirEntries" :key="entry.path" class="dir-item"
                :class="{ selected: dirSelected === entry.path }"
                @click="dirSelected = entry.path"
                @dblclick="loadDir(entry.path)"
              >📁 {{ entry.name }}</li>
              <li v-if="!dirEntries.length" class="dir-empty">（空目录）</li>
            </ul>
            <p v-if="dirError" class="status-msg error">{{ dirError }}</p>
          </div>
          <div class="modal-footer">
            <span class="subtle">双击进入子目录，单击选中</span>
            <button class="btn btn-primary btn-sm" :disabled="!dirSelected" @click="confirmDirSelect">选择此文件夹</button>
          </div>
        </div>
      </div>
    </section>

  </div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import api from "../api/index.js";
import { useSyncSettings } from "../composables/useSyncSettings.js";

const {
  syncPreset, syncSourceIds, syncPresets,
  load, reload, setPreset, setCustomSources,
} = useSyncSettings();

// 用于在「全部同步」灰掉时保留勾选显示
const backupIds = ref([]);

// Sync range
const isAll = computed(() => syncPreset.value === "all");
const otherPresets = computed(() => syncPresets.value.filter((p) => p.id !== "all" && p.id !== "custom"));

const customPresetIds = computed(() => {
  try {
    return isAll.value ? (backupIds.value || []) : (syncSourceIds.value || []);
  } catch {
    return [];
  }
});
const defaultPresetIds = computed(() => ["obsidian", "web_snapshots", "wiki"]);

const disabledStyle = computed(() => ({
  opacity: "0.4",
  pointerEvents: "none",
}));

// Auth state
const isAdmin = ref(false);
const currentUser = ref(null);

// Private sources
const privateSources = ref([]);
const privatePath = ref("");
const addingPrivate = ref(false);
const privateMsg = ref("");
const privateError = ref(false);

const sharedPresets = computed(() => {
  try {
    return (otherPresets.value || []).filter(p => p && (!p.owner || p.owner === currentUser.value));
  } catch {
    return [];
  }
});

const myPrivatePresets = computed(() => {
  try {
    return (privateSources.value || []).filter(p => p && p.is_owned);
  } catch {
    return [];
  }
});

async function loadAuthState() {
  try {
    const me = await api("/api/user/me");
    currentUser.value = me.username;
    isAdmin.value = me.role === "admin";
  } catch {
    isAdmin.value = false;
    currentUser.value = null;
  }
}

async function loadPrivateSources() {
  try {
    const data = await api("/api/user/sources");
    if (data && Array.isArray(data.sources)) {
      privateSources.value = data.sources.filter(s => s && s.is_owned);
    } else {
      privateSources.value = [];
    }
  } catch {
    privateSources.value = [];
  }
}

function onToggleAll() {
  if (isAll.value) {
    setCustomSources(backupIds.value);
  } else {
    backupIds.value = [...syncSourceIds.value];
    setPreset("all");
  }
}

function onTogglePreset(id) {
  let ids = [...syncSourceIds.value];
  const idx = ids.indexOf(id);
  if (idx >= 0) ids.splice(idx, 1);
  else ids.push(id);
  setCustomSources(ids);
}

// Admin shared source path
const customPath = ref("");
const addingPath = ref(false);
const pathMsg = ref("");
const pathError = ref(false);

const deleting = ref("");
const showDirPicker = ref(false);
const showPrivateDirPicker = ref(false);
const dirCurrentPath = ref("/sources");
const dirParent = ref("");
const dirEntries = ref([]);
const dirSelected = ref("");
const dirError = ref("");

const confirmDelete = ref(null); // { label, id, isPrivate }

async function deleteSharedSource(p) {
  confirmDelete.value = { label: p.label, id: p.id, isPrivate: false };
}

async function deletePrivateSource(p) {
  confirmDelete.value = { label: p.label, id: p.id, isPrivate: true };
}

async function doDelete() {
  if (!confirmDelete.value) return;
  const p = confirmDelete.value;
  confirmDelete.value = null;
  deleting.value = p.id;
  try {
    if (p.isPrivate) {
      await api(`/api/user/sources/${encodeURIComponent(p.id)}`, { method: "DELETE" });
    } else {
      await api("/api/admin/sources/delete", { method: "POST", body: { id: p.id } });
    }
    await reload();
    await loadPrivateSources();
  } catch (e) {
    if (e.message && !e.message.includes("Internal Server Error")) {
      alert(`删除失败: ${e.message || "未知错误"}`);
    }
  } finally {
    deleting.value = "";
  }
}

async function addCustomPath() {
  let path = customPath.value.trim();
  if (!path) {
    pathMsg.value = "请输入或选择文件夹路径";
    pathError.value = true;
    return;
  }
  pathMsg.value = "";
  pathError.value = false;
  addingPath.value = true;
  try {
    await api("/api/admin/sources/custom", { method: "POST", body: { path } });
    pathMsg.value = `已添加：${path}`;
    customPath.value = "";
    await reload();
  } catch (e) {
    pathMsg.value = e.message || "添加失败";
    pathError.value = true;
  } finally {
    addingPath.value = false;
  }
}

async function addPrivateSource() {
  let path = privatePath.value.trim();
  if (!path) {
    privateMsg.value = "请输入或选择文件夹路径";
    privateError.value = true;
    return;
  }
  privateMsg.value = "";
  privateError.value = false;
  addingPrivate.value = true;
  try {
    await api("/api/user/sources", { method: "POST", body: { path } });
    privateMsg.value = `已添加私有来源：${path}`;
    privatePath.value = "";
    await reload();
    await loadPrivateSources();
  } catch (e) {
    privateMsg.value = e.message || "添加失败";
    privateError.value = true;
  } finally {
    addingPrivate.value = false;
  }
}

async function openDirPicker() {
  showDirPicker.value = true;
  dirSelected.value = "";
  dirError.value = "";
  await loadDir(customPath.value.trim() || "/sources");
}

async function openPrivateDirPicker() {
  showDirPicker.value = true;
  dirSelected.value = "";
  dirError.value = "";
  await loadDir(privatePath.value.trim() || "/sources");
}

async function loadDir(path) {
  if (!path) return;
  dirError.value = "";
  dirCurrentPath.value = path;
  try {
    const data = await api(`/api/admin/browse-dir?path=${encodeURIComponent(path)}`);
    dirParent.value = data.parent || "";
    dirEntries.value = data.entries || [];
  } catch (e) {
    dirError.value = e.message || "加载失败";
    dirEntries.value = [];
  }
}

function confirmDirSelect() {
  if (dirSelected.value) {
    // Determine which field to populate based on which picker is active
    if (showDirPicker.value && customPath.value !== undefined) {
      // For admin: check if customPath has focus
    }
    privatePath.value = dirSelected.value;
    showDirPicker.value = false;
  }
}

onMounted(() => {
  loadAuthState().then(() => {
    load().then(() => loadPrivateSources());
  });
});
</script>

<style scoped>
.settings-section {
  margin-top: 20px;
}
.settings-section h3 {
  font-size: 1rem;
  font-weight: 600;
  margin-bottom: 8px;
}
.field-label {
  font-size: 0.85rem;
  font-weight: 500;
  color: var(--fg-muted);
  margin-bottom: 8px;
}
.section-label {
  display: flex;
  align-items: baseline;
  gap: 6px;
  padding: 8px 0 2px;
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--fg-muted);
  border-bottom: 1px solid var(--border-muted);
  margin-bottom: 4px;
}

/* Sync range */
.preset-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 12px;
}
.preset-option {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid var(--border-default);
  border-radius: var(--radius);
  cursor: pointer;
  transition: background 0.12s, border-color 0.12s;
}
.preset-option:hover { background: var(--bg-muted); }
.preset-option.selected { border-color: var(--accent-emphasis); background: var(--accent-bg); }
.preset-option input[type="checkbox"] { margin-top: 3px; }
.preset-row { position: relative; display: flex; align-items: center; }
.preset-row .preset-option { flex: 1; }
.delete-source-btn {
  position: absolute;
  right: 2px;
  top: 50%;
  transform: translateY(-50%);
  opacity: 0;
  transition: opacity 0.15s;
  z-index: 1;
}
.preset-row:hover .delete-source-btn { opacity: 0.4; }
.preset-row:hover .delete-source-btn:hover { opacity: 1; color: var(--danger-fg); }
.preset-label { font-size: 0.9rem; font-weight: 500; }
.preset-desc { font-size: 0.78rem; color: var(--fg-subtle); margin-top: 1px; font-family: var(--font-mono); }

/* Custom path */
.custom-path-row {
  display: flex;
  gap: 6px;
  align-items: center;
}
.custom-path-input {
  flex: 1;
  min-width: 200px;
}

/* Dir picker modal */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}
.modal {
  background: var(--bg-card);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  width: 520px;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  box-shadow: var(--shadow-lg);
}
.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 16px;
  border-bottom: 1px solid var(--border-muted);
}
.modal-header h4 { font-size: 1rem; font-weight: 600; }
.modal-body {
  padding: 12px 16px;
  overflow-y: auto;
  flex: 1;
}
.dir-browse-row {
  display: flex;
  gap: 6px;
  margin-bottom: 10px;
}
.dir-path-input {
  flex: 1;
  font-family: var(--font-mono);
  font-size: 0.8rem;
}
.dir-list {
  list-style: none;
  max-height: 300px;
  overflow-y: auto;
  border: 1px solid var(--border-muted);
  border-radius: var(--radius);
}
.dir-item {
  padding: 6px 10px;
  font-size: 0.85rem;
  cursor: pointer;
  transition: background 0.1s;
}
.dir-item:hover { background: var(--bg-hover); }
.dir-item.selected { background: var(--accent-bg); color: var(--accent-fg); }
.dir-item.parent { color: var(--fg-subtle); font-weight: 500; }
.dir-empty { padding: 20px; text-align: center; color: var(--fg-subtle); font-size: 0.82rem; }
.modal-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  border-top: 1px solid var(--border-muted);
}

.confirm-dialog {
  background: var(--bg-card);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  padding: 24px;
  max-width: 400px;
  box-shadow: var(--shadow-lg);
}
.status-msg { margin-top: 6px; font-size: 0.85rem; color: var(--fg-muted); }
.status-msg.error { color: var(--danger-fg); }
</style>
