<template>
  <div class="view-pane">
    <div class="view-header"><h2>📦 素材管理</h2></div>

    <!-- 同步范围 -->
    <section class="settings-section">
      <h3>同步范围</h3>
      <p class="subtle">勾选要同步的来源，修改后立即生效</p>

      <template v-if="dataLoaded">
      <div class="preset-list">
        <!-- 全部来源（master toggle） -->
        <label class="preset-option" :class="{ selected: isAll }">
          <input type="checkbox" :checked="isAll" @change="onToggleAll" />
          <div>
            <div class="preset-label">全部同步</div>
            <div class="preset-desc">{{ isAdmin ? '同步全部共享知识库' : '同步我的全部知识库' }}</div>
          </div>
        </label>

        <!-- ===== 共享知识库（折叠） ===== -->
        <div class="section-label collapsible" @click="toggleSection('shared')">
          <span class="chevron">{{ sectionExpanded.shared ? '▾' : '▸' }}</span>
          <span>📚 共享知识库</span>
          <span class="subtle">管理员配置，{{ isAdmin ? '可管理' : '只读' }}</span>
          <button v-if="isAdmin" class="btn btn-ghost btn-xs" @click.stop="toggleSection('shared')" style="margin-left:auto">
            {{ sectionExpanded.shared ? '收起' : '展开' }}
          </button>
        </div>
        <template v-if="sectionExpanded.shared">
          <div
            v-for="p in sharedPresets"
            :key="p.id"
            class="preset-row"
            :style="isAll || !isAdmin ? disabledStyle : {}"
          >
            <label class="preset-option" :class="{ selected: customPresetIds.includes(p.id) }">
              <input
                type="checkbox"
                :value="p.id"
                :checked="customPresetIds.includes(p.id)"
                :disabled="isAll || !isAdmin"
                @change="onTogglePreset(p.id)"
              />
              <div>
                <div class="preset-label">{{ p.label }}</div>
                <div class="preset-desc">{{ p.description || p.path || "" }}</div>
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

          <!-- 添加共享来源（admin only） -->
          <div v-if="isAdmin" class="custom-path-row" style="margin-top:8px">
            <input v-model="customPath" type="text" placeholder="输入文件夹路径，如 /sources/my-notes" class="custom-path-input" />
            <button class="btn btn-ghost" @click="openDirPicker">📁 浏览</button>
            <button class="btn btn-primary" @click="addCustomPath" :disabled="addingPath">{{ addingPath ? "验证中…" : "添加" }}</button>
          </div>
          <p v-if="pathMsg" class="status-msg" :class="{ error: pathError }">{{ pathMsg }}</p>
        </template>

        <!-- ===== 个人知识库 / 我的知识库（折叠） ===== -->
        <div class="section-label collapsible" @click="toggleSection('private')" style="margin-top:8px">
          <span class="chevron">{{ sectionExpanded.private ? '▾' : '▸' }}</span>
          <span>{{ isAdmin ? '👥 个人知识库' : '🔒 我的知识库' }}</span>
          <span class="subtle">{{ isAdmin ? '所有用户的个人目录' : '仅自己可见' }}</span>
          <button class="btn btn-ghost btn-xs" @click.stop="toggleSection('private')" style="margin-left:auto">
            {{ sectionExpanded.private ? '收起' : '展开' }}
          </button>
        </div>
        <template v-if="sectionExpanded.private">
          <!-- 按 owner 分组的私有来源列表 -->
          <template v-for="group in groupedPrivateSources" :key="group.owner || '__ungrouped__'">
            <div class="owner-group-label" v-if="group.owner">
              <span class="owner-label">{{ isAdmin ? '👤 ' : '🔒 ' }}个人知识库 {{ group.owner }}</span>
            </div>
            <div
              v-for="p in group.sources"
              :key="p.id"
              class="preset-row"
              :class="{ 'admin-row': isAdmin }"
              :style="isAdmin ? {} : (isAll ? disabledStyle : {})"
            >
              <!-- 管理员：只查看和删除，没有 checkbox -->
              <template v-if="isAdmin">
                <div class="preset-info preset-info-admin">
                  <div class="preset-label">{{ p.label }}</div>
                  <div class="preset-desc">{{ p.path || p.description || '' }}</div>
                </div>
              </template>
              <!-- 非管理员：checkbox + 信息 + 删除 -->
              <template v-else>
                <label class="preset-option" :class="{ selected: customPresetIds.includes(p.id) }">
                  <input
                    type="checkbox"
                    :value="p.id"
                    :checked="customPresetIds.includes(p.id)"
                    :disabled="isAll"
                    @change="onTogglePreset(p.id)"
                  />
                  <div>
                    <div class="preset-label">{{ p.label }}</div>
                    <div class="preset-desc">{{ p.path || p.description || '' }}</div>
                  </div>
                </label>
              </template>
              <button
                v-if="!p.is_default"
                class="btn btn-ghost btn-sm delete-source-btn"
                title="删除"
                :disabled="isAll || deleting === p.id"
                @click="deletePrivateSource(p)"
              >✕</button>
            </div>
          </template>

          <!-- 添加私有来源：仅非管理员 -->
          <div v-if="!isAdmin" class="custom-path-row" style="margin-top:8px">
            <input v-model="privatePath" type="text" placeholder="输入服务器文件夹路径" class="custom-path-input" />
            <button class="btn btn-ghost" @click="openPrivateDirPicker">📁 浏览</button>
            <button class="btn btn-primary" @click="addPrivateSource" :disabled="addingPrivate">
              {{ addingPrivate ? "添加中…" : "添加" }}
            </button>
          </div>
          <p v-if="privateMsg" class="status-msg" :class="{ error: privateError }">{{ privateMsg }}</p>
        </template>
      </div>
      </template>

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

    <!-- 目录选择弹窗（共享于 admin 和 private） -->
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

// 折叠状态
const sectionExpanded = ref({ shared: false, private: false });
function toggleSection(name) {
  sectionExpanded.value[name] = !sectionExpanded.value[name];
}

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
const dataLoaded = ref(false);

// Private sources
const privateSources = ref([]);
const privatePath = ref("");
const addingPrivate = ref(false);
const privateMsg = ref("");
const privateError = ref(false);

const BACKUP_KEY = "sync_all_backup";

const sharedPresets = computed(() => {
  try {
    // fallback: 确保默认预设始终在列表中（即使后端不全）
    const fallbackPresets = [
      { id: "obsidian", label: "Obsidian 剪藏", description: "Obsidian Web Clipper" },
      { id: "web_snapshots", label: "Web 快照", description: "type: web 抓取并转换的 Markdown" },
      { id: "wiki", label: "Wiki", description: "摘要与问答沉淀目录" },
    ];
    const base = (otherPresets.value || []);
    // 合并后端预设 + fallback，去重
    const seen = new Set(base.map(p => p.id));
    const merged = [...base];
    for (const fb of fallbackPresets) {
      if (!seen.has(fb.id)) merged.push(fb);
    }
    // 排除有 owner 的个人库条目
    return merged.filter(p => p && !p.owner);
  } catch {
    return [];
  }
});

const privateSourceList = computed(() => {
  try {
    return (privateSources.value || []).map(p => ({
      ...p,
      label: (p.label || p.id || "").replace(/\s*\(local\)\s*$/i, ""),
      path: p.path || "",
    }));
  } catch {
    return [];
  }
});

// 按 owner 分组
const groupedPrivateSources = computed(() => {
  const list = privateSourceList.value;
  const groups = {};
  for (const p of list) {
    const owner = p.owner || "__ungrouped__";
    if (!groups[owner]) groups[owner] = { owner: p.owner || "", sources: [] };
    groups[owner].sources.push(p);
  }
  return Object.values(groups);
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
      if (isAdmin.value) {
        // 管理员看到所有用户的个人目录（有 owner 的才是个人库，共享库无 owner）
        privateSources.value = (data.sources || []).filter(s => s && s.owner);
      } else {
        privateSources.value = data.sources.filter(s => s && s.is_owned);
      }
    } else {
      privateSources.value = [];
    }
  } catch {
    privateSources.value = [];
  }
}

function onToggleAll() {
  if (isAll.value) {
    // 从全部同步切回自定义：恢复之前保存的选择
    setCustomSources(backupIds.value);
    localStorage.removeItem(BACKUP_KEY);
  } else {
    backupIds.value = [...syncSourceIds.value];
    // 持久化备份，F5 刷新后仍能保持灰掉时的勾选状态
    localStorage.setItem(BACKUP_KEY, JSON.stringify(backupIds.value));
    if (isAdmin.value) {
      // 全部同步 = 同步全部共享源（后端 preset=all）
      setPreset("all");
    } else {
      // 非管理员：选中所有自己的私有源
      const myIds = privateSourceList.value.map(p => p.id).filter(Boolean);
      setCustomSources(myIds);
    }
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

// 目录选择器目标标记：'admin' 或 'private'
const pickerTarget = ref("private");

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
  pickerTarget.value = "admin";
  dirSelected.value = "";
  dirError.value = "";
  await loadDir(customPath.value.trim() || "/sources");
}

async function openPrivateDirPicker() {
  showDirPicker.value = true;
  pickerTarget.value = "private";
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
    if (pickerTarget.value === "admin") {
      customPath.value = dirSelected.value;
    } else {
      privatePath.value = dirSelected.value;
    }
    showDirPicker.value = false;
  }
}

onMounted(() => {
  loadAuthState().then(() => {
    load().then(() => {
      // 如果当前是「全部同步」模式，从 localStorage 恢复备份勾选状态
      if (syncPreset.value === "all") {
        const saved = localStorage.getItem(BACKUP_KEY);
        if (saved) {
          try { backupIds.value = JSON.parse(saved); } catch { backupIds.value = []; }
        }
      }
      loadPrivateSources().finally(() => { dataLoaded.value = true; });
    });
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
.section-label.collapsible {
  cursor: pointer;
  user-select: none;
}
.section-label.collapsible:hover {
  color: var(--fg-default);
}
.section-label .chevron {
  font-size: 0.7rem;
  width: 14px;
  flex-shrink: 0;
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
.preset-row.admin-row { padding: 8px 0; min-height: 36px; }
.preset-info {
  flex: 1;
  padding: 2px 0;
}
.preset-info-admin {
  padding: 2px 12px;
  border: 1px solid var(--border-muted);
  border-radius: var(--radius);
  background: var(--bg-muted);
  margin-right: 8px;
}
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

.owner-group-label {
  padding: 6px 2px 2px;
  font-size: 0.82rem;
  font-weight: 500;
  color: var(--fg-muted);
}
.owner-label {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

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
