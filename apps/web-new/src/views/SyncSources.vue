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

        <!-- 预设分组 -->
        <div
          v-for="p in otherPresets"
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
              <div class="preset-label">{{ p.label }}<span class="preset-tag" :class="defaultPresetIds.includes(p.id) ? 'tag-default' : 'tag-custom'">{{ defaultPresetIds.includes(p.id) ? '默认' : '自定义' }}</span></div>
              <div class="preset-desc">{{ p.description || "" }}</div>
            </div>
          </label>
          <button
            v-if="!defaultPresetIds.includes(p.id)"
            class="btn btn-ghost btn-sm delete-source-btn"
            title="从 sources.yaml 删除此来源"
            :disabled="isAll || deleting === p.id"
            @click="deleteSource(p)"
          >✕</button>
        </div>
      </div>


    </section>

    <!-- 自定义路径 -->
    <section class="settings-section">
      <h3>自定义路径</h3>
      <p class="subtle">手动输入文件夹路径，或从目录树选择</p>
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
              <li
                class="dir-item parent"
                @click="loadDir(dirParent)"
              >⬆ ..</li>
              <li
                v-for="entry in dirEntries"
                :key="entry.path"
                class="dir-item"
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

const customPresetIds = computed(() => isAll.value ? backupIds.value : syncSourceIds.value);
const defaultPresetIds = computed(() => ["obsidian", "web_snapshots", "wiki"]);

const disabledStyle = computed(() => ({
  opacity: "0.4",
  pointerEvents: "none",
}));

function onToggleAll() {
  if (isAll.value) {
    // 从全部同步切回自定义：恢复之前保存的选择
    setCustomSources(backupIds.value);
  } else {
    // 切到全部同步：保存当前选择到本地备份（DB 会被清空，用备份维持显示）
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

// Custom path
const customPath = ref("");
const addingPath = ref(false);
const pathMsg = ref("");
const pathError = ref(false);

const deleting = ref("");
const showDirPicker = ref(false);
const dirCurrentPath = ref("/sources");
const dirParent = ref("");
const dirEntries = ref([]);
const dirSelected = ref("");
const dirError = ref("");

async function deleteSource(p) {
  if (!window.confirm(`确认从 sources.yaml 删除「${p.label}」？此操作不可撤销。`)) return;
  deleting.value = p.id;
  try {
    await api("/api/admin/sources/delete", { method: "POST", body: { id: p.id } });
    await reload();
  } catch (e) {
    alert(`删除失败: ${e.message || "未知错误"}`);
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
    await api("/api/admin/sources/custom", {
      method: "POST",
      body: { path },
    });
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

async function openDirPicker() {
  showDirPicker.value = true;
  dirSelected.value = "";
  dirError.value = "";
  await loadDir(customPath.value.trim() || "/sources");
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
    customPath.value = dirSelected.value;
    showDirPicker.value = false;
    pathMsg.value = "";
    pathError.value = false;
  }
}

onMounted(async () => {
  await load();
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
.preset-row { display: flex; align-items: center; gap: 4px; }
.preset-row .preset-option { flex: 1; }
.delete-source-btn { opacity: 0.3; transition: opacity 0.15s; flex-shrink: 0; }
.preset-row:hover .delete-source-btn { opacity: 0.8; }
.delete-source-btn:hover { opacity: 1 !important; color: var(--danger-fg); }
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

.status-msg { margin-top: 6px; font-size: 0.85rem; color: var(--fg-muted); }
.status-msg.error { color: var(--danger-fg); }
</style>
