<template>
  <div class="view-pane">
    <div class="view-header"><h2>📦 同步素材</h2></div>

    <!-- 同步范围 -->
    <section class="settings-section">
      

      <template v-if="dataLoaded">
      <div class="preset-list">
        <!-- 同步范围：radio button -->
        <div class="sync-range-radios">
          <label class="preset-option radio-option" :class="{ selected: isAll }">
            <input type="radio" name="syncRange" :checked="isAll" @change="onToggleAll" />
            <div>
              <div class="preset-label">全部同步 <span class="shared-tag">同步所有共享库和个人库</span></div>
            </div>
          </label>
          <label class="preset-option radio-option" :class="{ selected: !isAll }">
            <input type="radio" name="syncRange" :checked="!isAll" @change="onToggleCustom" />
            <div>
              <div class="preset-label">自定义 <span class="shared-tag">自定义同步库</span></div>
            </div>
          </label>
        </div>

        <div v-show="!isAll">
        <!-- ===== 全局知识库（折叠） ===== -->
        <div v-if="sharedPresets.length > 0" class="section-label collapsible" @click="toggleSection('shared')">
          <span class="chevron">{{ sectionExpanded.shared ? '▾' : '▸' }}</span>
          <span>📚 全局知识库</span>
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
            :class="{ 'path-invalid-row': p.path_exists === false }"
            :style="isAll ? disabledStyle : (p.path_exists === false ? disabledStyle : {})"
          >
            <label class="preset-option" :class="{ selected: customPresetIds.includes(p.id), 'path-invalid': p.path_exists === false }">
              <input
                type="checkbox"
                :value="p.id"
                :checked="customPresetIds.includes(p.id)"
                :disabled="isAll"
                @change="onTogglePreset(p.id)"
              />
              <div>
                <div class="preset-label">{{ p.label }}<span v-if="p.shared" class="shared-tag">共享中</span><span v-if="p.description" class="shared-tag">{{ p.description }}</span></div>
                <div class="preset-desc" :class="{ 'path-invalid': p.path && p.path_exists === false }">
                  {{ displayPath(p.path || '') }}
                  <span v-if="p.path && p.path_exists === false" class="path-invalid-tag" title="此路径在服务器上不存在，请删除或更新">⚠ 路径无效</span>
                </div>
              </div>
            </label>
            <button
              v-if="isAdmin"
              class="btn btn-ghost btn-sm share-source-btn"
              :title="p.shared ? '取消共享' : '共享给角色用户'"
              :disabled="isAll || sharing === p.id"
              @click="toggleGlobalShare(p)"
            >{{ p.shared ? '🔓' : '🔒' }}</button>
            <button
              v-if="isAdmin"
              class="btn btn-ghost btn-sm delete-source-btn"
              title="删除此库"
              :disabled="isAll || deleting === p.id"
              @click="deleteSharedSource(p)"
            >✕</button>
          </div>

          <!-- 添加全局库（admin only） -->
          <div v-if="isAdmin" class="custom-path-row" style="margin-top:8px">
            <input v-model="customPath" type="text" placeholder="输入文件夹路径，如 ~/data/mind-sync-data/xxx" class="custom-path-input" />
            <button class="btn btn-ghost" @click="openDirPicker">📁 浏览</button>
            <button class="btn btn-primary" @click="addCustomPath" :disabled="addingPath">{{ addingPath ? "验证中…" : "添加" }}</button>
          </div>
          <p v-if="pathMsg" class="status-msg" :class="{ error: pathError }">{{ pathMsg }}</p>
        </template>

        <!-- ===== 管理员：我的知识库（折叠） ===== -->
        <div v-if="isAdmin" class="section-label collapsible" @click="toggleSection('my_private')" style="margin-top:8px">
          <span class="chevron">{{ sectionExpanded.my_private ? '▾' : '▸' }}</span>
          <span>🔒 我的知识库</span>
          <span class="subtle">仅自己可见</span>
          <button class="btn btn-ghost btn-xs" @click.stop="toggleSection('my_private')" style="margin-left:auto">
            {{ sectionExpanded.my_private ? '收起' : '展开' }}
          </button>
        </div>
        <template v-if="isAdmin && sectionExpanded.my_private">
          <template v-for="group in myPrivateSources" :key="group.owner || '__ungrouped__'">
            <div
              v-for="p in group.sources"
              :key="p.sync_key || p.id"
              class="preset-row"
              :class="{ 'path-invalid-row': p.path_exists === false }"
              :style="isAll ? disabledStyle : (p.path_exists === false ? disabledStyle : {})"
            >
              <label class="preset-option" :class="{ selected: customPresetIds.includes(p.sync_key || p.id), 'path-invalid': p.path_exists === false }">
                <input
                  type="checkbox"
                  :value="p.sync_key || p.id"
                  :checked="customPresetIds.includes(p.sync_key || p.id)"
                  :disabled="isAll"
                  @change="onTogglePreset(p.sync_key || p.id)"
                />
                <div>
                  <div class="preset-label">{{ p.label }}<span v-if="p.shared" class="shared-tag">共享中</span></div>
                  <div class="preset-desc" :class="{ 'path-invalid': p.path && p.path_exists === false }">
                    {{ displayPath(p.path || p.description || '') }}
                    <span v-if="p.path && p.path_exists === false" class="path-invalid-tag" title="此路径在服务器上不存在">⚠ 路径无效</span>
                  </div>
                </div>
              </label>
              <button
                v-if="!p.is_default"
                class="btn btn-ghost btn-sm share-source-btn"
                :title="p.shared ? '取消共享' : '共享给其他用户'"
                :disabled="isAll || sharing === p.id"
                @click="toggleShare(p)"
              >{{ p.shared ? '🔓' : '🔒' }}</button>
              <button
                v-if="!p.is_default || p.path_exists === false"
                class="btn btn-ghost btn-sm delete-source-btn"
                title="删除"
                :disabled="isAll || deleting === p.id"
                @click="deletePrivateSource(p)"
              >✕</button>
            </div>
          </template>
          <!-- 管理员添加自己的私有库 -->
          <div class="custom-path-row" style="margin-top:8px">
            <input v-model="privatePath" type="text" placeholder="输入文件夹路径，如 ~/data/mind-sync-data/xxx" class="custom-path-input" />
            <button class="btn btn-ghost" @click="openPrivateDirPicker">📁 浏览</button>
            <button class="btn btn-primary" @click="addPrivateSource" :disabled="addingPrivate">
              {{ addingPrivate ? "添加中…" : "添加" }}
            </button>
          </div>
          <p v-if="privateMsg" class="status-msg" :class="{ error: privateError }">{{ privateMsg }}</p>
        </template>

        <!-- ===== 个人知识库 / 我的知识库（折叠，管理员不显示此区） ===== -->
        <div v-if="!isAdmin" class="section-label collapsible" @click="toggleSection('private')" style="margin-top:8px">
          <span class="chevron">{{ sectionExpanded.private ? '▾' : '▸' }}</span>
          <span>🔒 我的知识库</span>
          <span class="subtle">仅自己可见</span>
          <button class="btn btn-ghost btn-xs" @click.stop="toggleSection('private')" style="margin-left:auto">
            {{ sectionExpanded.private ? '收起' : '展开' }}
          </button>
        </div>
        <template v-if="!isAdmin && sectionExpanded.private">
          <template v-for="group in groupedPrivateSources" :key="group.owner || '__ungrouped__'">
            <div
              v-for="p in group.sources"
              :key="p.id"
              class="preset-row"
              :class="{ 'path-invalid-row': p.path_exists === false }"
              :style="{}"
            >
              <label class="preset-option" :class="{ selected: customPresetIds.includes(p.sync_key || p.id), 'path-invalid': p.path_exists === false }">
                <input
                  type="checkbox"
                  :value="p.sync_key || p.id"
                  :checked="customPresetIds.includes(p.sync_key || p.id)"
                  :disabled="false"
                  @change="onTogglePreset(p.sync_key || p.id)"
                />
                <div>
                  <div class="preset-label">{{ p.label }}<span v-if="p.shared" class="shared-tag">共享中</span></div>
                  <div class="preset-desc" :class="{ 'path-invalid': p.path && p.path_exists === false }">
                    {{ displayPath(p.path || p.description || '') }}
                    <span v-if="p.path && p.path_exists === false" class="path-invalid-tag">⚠ 路径无效</span>
                  </div>
                </div>
              </label>
              <button
                v-if="!p.is_default"
                class="btn btn-ghost btn-sm share-source-btn"
                :title="p.shared ? '取消共享' : '共享给其他用户'"
                :disabled="isAll || sharing === p.id"
                @click="toggleShare(p)"
              >{{ p.shared ? '🔓' : '🔒' }}</button>
              <button
                v-if="!p.is_default || p.path_exists === false"
                class="btn btn-ghost btn-sm delete-source-btn"
                title="删除"
                :disabled="isAll || deleting === p.id"
                @click="deletePrivateSource(p)"
              >✕</button>
            </div>
          </template>

          <!-- 添加私有库：仅非管理员 -->
          <div v-if="!isAdmin" class="custom-path-row" style="margin-top:8px">
            <input v-model="privatePath" type="text" placeholder="输入文件夹路径，如 ~/data/mind-sync-data/xxx" class="custom-path-input" />
            <button class="btn btn-ghost" @click="openPrivateDirPicker">📁 浏览</button>
            <button class="btn btn-primary" @click="addPrivateSource" :disabled="addingPrivate">
              {{ addingPrivate ? "添加中…" : "添加" }}
            </button>
          </div>
          <p v-if="privateMsg" class="status-msg" :class="{ error: privateError }">{{ privateMsg }}</p>
        </template>

        <!-- ===== 共享知识库 ===== -->
        <div v-if="groupedSharedPublicSources.length > 0" class="section-label collapsible" @click="toggleSection('shared_public')" style="margin-top:8px">
          <span class="chevron">{{ sectionExpanded.shared_public ? '▾' : '▸' }}</span>
          <span>🌐 共享知识库</span>
          <span class="subtle">其他用户共享的个人库</span>
          <button class="btn btn-ghost btn-xs" @click.stop="toggleSection('shared_public')" style="margin-left:auto">
            {{ sectionExpanded.shared_public ? '收起' : '展开' }}
          </button>
        </div>
        <template v-if="sectionExpanded.shared_public">
          <template v-for="group in groupedSharedPublicSources" :key="group.owner || '__ungrouped__'">
            <div class="owner-group-label" v-if="group.owner">
              <span class="owner-label">👤 {{ formatOwnerLabel(group.owner) }}</span>
              <span v-if="group.deletedAt > 0" class="deleted-owner-tag">已注销，共享截止 {{ formatDeadline(group.deletedAt) }}</span>
            </div>
            <div
              v-for="p in group.sources"
              :key="p.id"
              class="preset-row"
              :class="{ 'path-invalid-row': p.path_exists === false }"
              :style="{}"
            >
              <label class="preset-option" :class="{ selected: customPresetIds.includes(p.sync_key || p.id), 'path-invalid': p.path_exists === false }">
                <input
                  type="checkbox"
                  :value="p.sync_key || p.id"
                  :checked="customPresetIds.includes(p.sync_key || p.id)"
                  :disabled="false"
                  @change="onTogglePreset(p.sync_key || p.id)"
                />
                <div>
                  <div class="preset-label">{{ p.label }}</div>
                  <div class="preset-desc" :class="{ 'path-invalid': p.path && p.path_exists === false }">
                    {{ displayPath(p.path || p.description || '') }}
                    <span v-if="p.path && p.path_exists === false" class="path-invalid-tag">⚠ 路径无效</span>
                  </div>
                </div>
              </label>
            </div>
          </template>
        </template>
        </div>
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
import { ref, computed, onMounted, onUnmounted, onActivated, watch } from "vue";
import { useRoute } from "vue-router";
import api from "../api/index.js";
import { toast } from "../composables/toast.js";
import { useSyncSettings } from "../composables/useSyncSettings.js";

const route = useRoute();
const {
  syncPreset, syncSourceIds, syncPresets, availableSources,
  load, reload, setPreset, setCustomSources,
} = useSyncSettings();

// 用于在「全部同步」灰掉时保留勾选显示
const backupIds = ref([]);
// 非管理员本地「全部同步」模式（不修改后端 preset）
const LOCAL_ALL_KEY = "sync_local_all";
const localAllMode = ref(localStorage.getItem(LOCAL_ALL_KEY) !== "false");
// localAllMode 变化时持久化
watch(localAllMode, (val) => {
  localStorage.setItem(LOCAL_ALL_KEY, val ? "true" : "false");
});

// 折叠状态（持久化到 localStorage，刷新后保留）
const sectionExpanded = ref(JSON.parse(localStorage.getItem('sync_sections') || '{"shared":false,"private":false,"my_private":false}'));
watch(sectionExpanded, (val) => {
  localStorage.setItem('sync_sections', JSON.stringify(val));
}, { deep: true });
function toggleSection(name) {
  sectionExpanded.value[name] = !sectionExpanded.value[name];
}

// 个人知识库分组展开/折叠状态
const privateGroupExpanded = ref(JSON.parse(localStorage.getItem('sync_private_groups') || '{}'));
watch(privateGroupExpanded, (val) => {
  localStorage.setItem('sync_private_groups', JSON.stringify(val));
}, { deep: true });
function togglePrivateGroup(owner) {
  const current = privateGroupExpanded.value[owner];
  privateGroupExpanded.value[owner] = current === false ? true : false;
}

// Sync range
const isAll = computed(() => isAdmin.value ? syncPreset.value === "all" : localAllMode.value);
const otherPresets = computed(() => syncPresets.value.filter((p) => p.id !== "all" && p.id !== "custom"));

const customPresetIds = computed(() => {
  try {
    if (isAll.value) return (backupIds.value || []);
    // 非管理员且管理员设为全部同步时：显示全部库为预勾选
    if (!isAdmin.value && syncPreset.value === "all") {
      return (sharedPresets.value || []).map(p => p.id);
    }
    // 默认库始终勾选
    const ids = [...(syncSourceIds.value || [])];
    for (const did of defaultPresetIds.value) {
      if (!ids.includes(did)) ids.push(did);
    }
    return ids;
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
const userHomeDir = ref("");
const dataLoaded = ref(false);

// User display names map
const userDisplayNames = ref({});
function userDisplayName(username) {
  const u = userDisplayNames.value[username];
  return u ? u.dn : username;
}

function userRole(username) {
  const u = userDisplayNames.value[username];
  return u ? u.role : '';
}

function formatOwnerLabel(username) {
  const u = userDisplayNames.value[username];
  if (u && u.dn) {
    if (u.dn === username) return username;
    return `${u.dn}(${username})`;
  }
  for (const s of (privateSources.value || [])) {
    if (s.owner === username && s.owner_display_name) {
      const dn2 = s.owner_display_name;
      if (dn2 === username) return username;
      return `${dn2}(${username})`;
    }
  }
  return username;
}

function getOwnerRoleLabel(username) {
  if (username === currentUser.value) return '当前用户';
  const role = userRole(username);
  if (role === 'admin') return '管理员';
  return '成员';
}

async function loadUserDisplayNames() {
  if (!isAdmin.value) return;
  try {
    const data = await api("/api/admin/users");
    const map = {};
    for (const u of (data.users || [])) {
      map[u.username] = { dn: u.display_name || u.username, role: u.role };
    }
    userDisplayNames.value = map;
  } catch {
    // ignore
  }
}

// Private sources
const privateSources = ref([]);
const privatePath = ref("");
const addingPrivate = ref(false);
const privateMsg = ref("");
const privateError = ref(false);

function backupKey() {
  return `sync_all_backup_${currentUser.value || 'anon'}`;
}

function naturalSort(a, b) {
  return String(a || '').localeCompare(String(b || ''), undefined, { numeric: true, sensitivity: 'base' });
}

function displayPath(path) {
  if (!path) return "";
  // /home/moku/... → ~/...
  // /data/users/... → ~/data/mind-sync-data/users/...（旧容器路径转显示）
  // /data/... → ~/data/mind-sync-data/...（容器内 /data 映射到宿主机 ~/data/mind-sync-data）
  return path
    .replace(/^\/home\/moku\//, "~/")
    .replace(/^\/data\/users\//, "~/data/mind-sync-data/users/")
    .replace(/^\/data\//, "~/data/mind-sync-data/");
}

const sharedPresets = computed(() => {
  try {
    const base = (otherPresets.value || []);
    // 合并后端预设，去重
    const seen = new Set(base.map(p => p.id));
    const merged = [...base];

    // 非管理员：只显示已共享的全局库（shared=true）
    let filtered = merged.filter(p => p && !p.owner);
    if (!isAdmin.value) {
      filtered = filtered.filter(p => p.shared === true);
    }

    // 排序：Obsidian/Web快照/Wiki 固定在最前，其余按 label 字母序
    const pinIds = ["obsidian", "web_snapshots", "wiki"];
    const pinned = [];
    const rest = [];
    for (const p of filtered) {
      if (pinIds.includes(p.id)) pinned.push(p);
      else rest.push(p);
    }
    rest.sort((a, b) => naturalSort(a.label || a.id, b.label || b.id));
    const sorted = [...pinned, ...rest];

    // 仅在后端未提供 path_exists 时从 availableSources 补充
    const srcMap = {};
    for (const s of (availableSources.value || [])) {
      srcMap[s.id] = s;
    }
    return sorted.map(p => ({
      ...p,
      path_exists: p.path_exists !== undefined ? p.path_exists : (srcMap[p.id] ? srcMap[p.id].path_exists : undefined),
    }));
  } catch {
    return [];
  }
});

const privateSourceList = computed(() => {
  try {
    return (privateSources.value || []).map(p => ({
      ...p,
      label: (p.label || p.id || "").replace(/\s*\(local\)\s*$|\s*:本地\s*$/i, ""),
      path: p.path || "",
    }));
  } catch {
    return [];
  }
});

// 按 owner 分组（个人库）
const groupedPrivateSources = computed(() => {
  if (isAdmin.value) return groupByOwnerList(privateSourceList.value.filter(p => p.owner && p.owner !== currentUser.value));
  return groupByOwnerList(privateSourceList.value.filter(p => p.owner === currentUser.value));
});

const myPrivateSources = computed(() => {
  if (!isAdmin.value) return [];
  return groupByOwnerList(privateSourceList.value.filter(p => p.owner === currentUser.value));
});

function groupByOwnerList(list) {
  const groups = {};
  for (const p of list) {
    const owner = p.owner || "__ungrouped__";
    if (!groups[owner]) groups[owner] = { owner: p.owner || "", sources: [] };
    groups[owner].sources.push(p);
  }
  for (const g of Object.values(groups)) {
    g.sources.sort((a, b) => naturalSort(a.label || a.id, b.label || b.id));
  }
  return Object.values(groups);
}



// 共享知识库：非管理员可见的其他用户共享库
const groupedSharedPublicSources = computed(() => {
  const allSources = privateSources.value || [];
  const sharedFromOthers = allSources.filter(s => s.shared && s.owner && s.owner !== currentUser.value);
  if (!sharedFromOthers.length) return [];
  const groups = {};
  for (const p of sharedFromOthers) {
    const owner = p.owner || "__ungrouped__";
    if (!groups[owner]) groups[owner] = { owner, sources: [], deletedAt: p.owner_deleted_at || 0 };
    groups[owner].sources.push({
      ...p,
      label: (p.label || p.id || "").replace(/\s*\(local\)\s*$|\s*:本地\s*$/i, ""),
      path: p.path || "",
    });
  }
  // 每个分组内的库按 label 字母序排列
  for (const g of Object.values(groups)) {
    g.sources.sort((a, b) => naturalSort(a.label || a.id, b.label || b.id));
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
        // 非管理员：自己的库 + 其他用户共享的库
        privateSources.value = data.sources.filter(s => s && (s.is_owned || s.shared));
      }
    } else {
      privateSources.value = [];
    }
  } catch {
    privateSources.value = [];
  }
}

function onToggleAll() {
  // 切换到全部同步
  backupIds.value = [...syncSourceIds.value];
  localStorage.setItem(backupKey(), JSON.stringify(backupIds.value));
  if (isAdmin.value) {
    setPreset("all");
  } else {
    localAllMode.value = true;
  }
}

function onToggleCustom() {
  // 切换到自定义：恢复之前保存的选择
  if (isAdmin.value) {
    setCustomSources(backupIds.value);
  }
  localStorage.removeItem(backupKey());
  if (!isAdmin.value) {
    localAllMode.value = false;
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
const sharing = ref("");
const showDirPicker = ref(false);
const showPrivateDirPicker = ref(false);
const dirCurrentPath = ref("/home/moku");
const dirParent = ref("");
const dirEntries = ref([]);
const dirSelected = ref("");
const dirError = ref("");

const confirmDelete = ref(null); // { label, id, isPrivate }

// 目录选择器目标标记：'admin' 或 'private'
const pickerTarget = ref("private");

async function deleteSharedSource(p) {
  showDirPicker.value = false; // 关闭其他弹窗
  confirmDelete.value = { label: p.label, id: p.id, isPrivate: false };
}

async function deletePrivateSource(p) {
  showDirPicker.value = false; // 关闭其他弹窗
  confirmDelete.value = { label: p.label, id: p.id, isPrivate: true };
}

async function toggleShare(p) {
  sharing.value = p.id;
  try {
    const data = await api(`/api/user/sources/${encodeURIComponent(p.id)}/share`, { method: "PUT" });
    p.shared = data.shared;
    await reload();
    await loadPrivateSources();
  } catch (e) {
    // ignore
  } finally {
    sharing.value = "";
  }
}

async function toggleGlobalShare(p) {
  sharing.value = p.id;
  try {
    const data = await api(`/api/admin/sources/${encodeURIComponent(p.sync_key || p.id)}/share`, { method: "POST" });
    p.shared = data.shared;
    await reload();
    await loadPrivateSources();
  } catch (e) {
    toast.error(e.message || "操作失败");
  } finally {
    sharing.value = "";
  }
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
  const oldPreset = syncPreset.value;
  const pathParts = path.replace(/\\/g, '/').split('/').filter(Boolean);
  const newSourceId = pathParts[pathParts.length - 1] || '';
  try {
    await api("/api/admin/sources/custom", { method: "POST", body: { path } });
    customPath.value = "";
    await reload();
    // 新增的库不自动勾选：如原为「全部同步」则转为自定义并排除新库
    if (oldPreset === 'all') {
      const allIds = syncPresets.value
        .filter(p => p.id !== 'all' && p.id !== 'custom' && p.id !== `${newSourceId}:local`)
        .map(p => p.id);
      await setCustomSources(allIds);
    }
  } catch (e) {
    pathMsg.value = e.message || "添加失败";
    pathError.value = true;
    toast.error(e.message || "添加失败");
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
  const oldPreset = syncPreset.value;
  const pathParts = path.replace(/\\/g, '/').split('/').filter(Boolean);
  const newSourceId = pathParts[pathParts.length - 1] || '';
  try {
    await api("/api/user/sources", { method: "POST", body: { path } });
    privatePath.value = "";
    await reload();
    await loadPrivateSources();
    // 新增的库不自动勾选
    if (oldPreset === 'all') {
      const allIds = syncPresets.value
        .filter(p => p.id !== 'all' && p.id !== 'custom' && p.id !== `${newSourceId}:local`)
        .map(p => p.id);
      await setCustomSources(allIds);
    }
  } catch (e) {
    privateMsg.value = e.message || "添加失败";
    privateError.value = true;
  } finally {
    addingPrivate.value = false;
  }
}

async function openDirPicker() {
  confirmDelete.value = null; // 关闭其他弹窗
  showDirPicker.value = true;
  pickerTarget.value = "admin";
  dirSelected.value = "";
  dirError.value = "";
  await loadDir(customPath.value.trim() || "/home/moku");
}

async function openPrivateDirPicker() {
  confirmDelete.value = null; // 关闭其他弹窗
  showDirPicker.value = true;
  pickerTarget.value = "private";
  dirSelected.value = "";
  dirError.value = "";
  // 始终从用户专属目录开始浏览，不受上次输入的错误路径影响
  const defaultPath = currentUser.value
    ? `/home/moku/data/mind-sync-data/users/${currentUser.value}`
    : "/home/moku";
  await loadDir(defaultPath);
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

// 全局 ESC 关闭弹窗
function onGlobalKeydown(e) {
  if (e.key === 'Escape') {
    confirmDelete.value = null;
    showDirPicker.value = false;
  }
}

onMounted(() => {
  document.addEventListener('keydown', onGlobalKeydown);
  loadAuthState().then(() => {
    loadUserDisplayNames();
    load().then(() => {
      // 从 localStorage 恢复备份勾选状态
      const saved = localStorage.getItem(backupKey());
      if (saved) {
        try { backupIds.value = JSON.parse(saved); } catch { backupIds.value = []; }
      }
      loadPrivateSources().finally(() => {
        dataLoaded.value = true;
        if (route.query.mode === "custom" && isAll.value) {
          onToggleCustom();
        }
      });
    });
  });
});

onUnmounted(() => {
  document.removeEventListener('keydown', onGlobalKeydown);
});

// 从其他页面切回时刷新数据（如素材管理页修改共享状态后）
onActivated(() => {
  load().then(() => loadPrivateSources());
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
.share-source-btn {
  position: absolute;
  right: 36px;
  top: 50%;
  transform: translateY(-50%);
  opacity: 0;
  transition: opacity 0.15s;
  z-index: 1;
  font-size: 0.8rem;
  padding: 2px 6px;
}
.preset-row:hover .delete-source-btn,
.preset-row:hover .share-source-btn { opacity: 0.4; }
.preset-row:hover .delete-source-btn:hover { opacity: 1; color: var(--danger-fg); }
.preset-row:hover .share-source-btn:hover { opacity: 1; }
.preset-label { font-size: 0.9rem; font-weight: 500; display: flex; align-items: center; gap: 6px; }
.shared-tag { font-size: 0.7rem; color: var(--fg-subtle); font-weight: 400; opacity: 0.7; }
.role-tag { font-size: 0.7rem; color: var(--fg-subtle); font-weight: 400; opacity: 0.6; margin-left: 4px; }
.preset-desc { font-size: 0.78rem; color: var(--fg-subtle); margin-top: 1px; font-family: var(--font-mono); }
.preset-desc.path-invalid { color: var(--danger-fg, #dc2626); opacity: 0.6; }
.preset-row.path-invalid-row { opacity: 0.5; }
.preset-row.path-invalid-row .delete-source-btn,
.preset-row.path-invalid-row .share-source-btn { pointer-events: auto; }
.path-invalid-tag {
  display: inline-block;
  margin-left: 6px;
  font-size: 0.7rem;
  color: var(--danger-fg, #dc2626);
  background: rgba(220, 38, 38, 0.1);
  padding: 1px 5px;
  border-radius: 3px;
  white-space: nowrap;
}

.owner-group-label {
  padding: 6px 2px 2px;
  font-size: 0.82rem;
  font-weight: 500;
  color: var(--fg-muted);
}
.deleted-owner-tag { font-size: 0.7rem; color: var(--fg-subtle); margin-left: 4px; }
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

/* Sync range radios */
.sync-range-radios {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
}
.sync-range-radios .radio-option {
  flex: 1;
  justify-content: center;
  text-align: center;
}
.sync-range-radios .radio-option input[type="radio"] {
  margin-top: 3px;
}
</style>
