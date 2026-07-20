<template>
  <div class="view-pane">
    <div class="view-header" style="display:flex;align-items:center">
      <h2>👥 用户管理</h2>
      <div style="margin-left:auto">
        <button class="btn btn-ghost btn-sm" @click="refresh" :disabled="refreshing" title="刷新">↻</button>
      </div>
    </div>

    <p class="subtle">管理团队用户。新用户会自动创建专属目录和默认私有库。</p>

    <!-- 全局统计 -->
    <div class="stats-grid">
      <div class="stat-card"><div class="stat-value">{{ stats.doc_count ?? '-' }}</div><div class="stat-label">文档总数</div></div>
      <div class="stat-card"><div class="stat-value">{{ stats.src_count ?? '-' }}</div><div class="stat-label">库总数</div></div>
      <div class="stat-card"><div class="stat-value">{{ stats.user_count ?? '-' }}</div><div class="stat-label">用户数</div></div>
      <div class="stat-card"><div class="stat-value">{{ stats.wiki_pages ?? '-' }}</div><div class="stat-label">Wiki 页面</div></div>
      <div class="stat-card"><div class="stat-value">{{ formatBytes(stats.db_size) }}</div><div class="stat-label">数据库</div></div>
    </div>

    <div class="toolbar">
      <button class="btn btn-primary btn-sm" @click="openCreate">＋ 创建用户</button>
    </div>

    <table class="user-table" v-if="users.length">
      <thead>
        <tr>
          <th>用户名</th>
          <th>表示名</th>
          <th>状态</th>
          <th>角色</th>
          <th>源数</th>
          <th>文档数</th>
          <th>专属目录</th>
          <th>创建时间</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="u in users" :key="u.username">
          <td><strong>{{ u.username }}</strong></td>
          <td>{{ u.display_name || u.username }}</td>
          <td>
            <span class="status-badge" :class="u.status === 'locked' ? 'status-locked' : 'status-normal'">
              {{ u.status === 'locked' ? '🔒 锁定' : '✅ 正常' }}
            </span>
          </td>
          <td>
            <select :value="u.role" @change="doChangeRole(u.username, $event.target.value)" class="role-select">
              <option value="member">member</option>
              <option value="admin">admin</option>
            </select>
          </td>
          <td>{{ u.source_count ?? '-' }}</td>
          <td>{{ u.doc_count ?? '-' }}</td>
          <td>{{ u.has_dir ? '✅' : '❌' }}</td>
          <td>{{ formatTime(u.created_at) }}</td>
          <td class="action-cell">
            <button class="btn btn-ghost btn-xs" @click="showResetPwd(u)">重置密码</button>
            <button class="btn btn-ghost btn-xs" @click="confirmDeleteUser(u)">删除</button>
          </td>
        </tr>
      </tbody>
    </table>
    <p v-else class="subtle" style="padding:20px">暂无用户</p>

    <!-- 创建用户弹窗 -->
    <div v-if="showCreate" class="modal-overlay" @click.self="showCreate = false">
      <div class="modal modal-sm">
        <div class="modal-header">
          <h4>创建用户</h4>
          <button class="btn btn-ghost btn-sm" @click="showCreate = false">✕</button>
        </div>
        <div class="modal-body">
          <div class="field">
            <label>用户名</label>
            <input v-model="newUser.username" type="text" placeholder="如 alice" />
          </div>
          <div class="field">
            <label>表示名</label>
            <input v-model="newUser.display_name" type="text" placeholder="如 爱丽丝（可选）" />
          </div>
          <div class="field">
            <label>密码</label>
            <input v-model="newUser.password" type="password" placeholder="至少 4 个字符" />
          </div>
          <div class="field">
            <label>角色</label>
            <select v-model="newUser.role">
              <option value="member">成员 (member)</option>
              <option value="admin">管理员 (admin)</option>
            </select>
          </div>
          <p v-if="createMsg" class="status-msg" :class="{ error: createError }">{{ createMsg }}</p>
        </div>
        <div class="modal-footer">
          <button class="btn btn-ghost" @click="showCreate = false">取消</button>
          <button class="btn btn-primary" @click="doCreateUser" :disabled="creating">
            {{ creating ? "创建中…" : "创建" }}
          </button>
        </div>
      </div>
    </div>

    <!-- 删除确认弹窗 -->
    <div v-if="deleteTarget" class="modal-overlay" @click.self="deleteTarget = null">
      <div class="confirm-dialog">
        <p>确认删除用户「<strong>{{ deleteTarget.username }}</strong>」？</p>
        <p class="subtle">将同时删除该用户的私有库、索引数据和专属目录。此操作不可撤销。</p>
        <div class="btn-row" style="justify-content:flex-end;margin-top:12px">
          <button class="btn btn-ghost" @click="deleteTarget = null">取消</button>
          <button class="btn btn-danger btn-sm" @click="doDeleteUser" :disabled="deleting">
            {{ deleting ? "删除中…" : "确认删除" }}
          </button>
        </div>
      </div>
    </div>

    <!-- 重置密码弹窗 -->
    <div v-if="resetTarget" class="modal-overlay" @click.self="resetTarget = null">
      <div class="modal modal-sm">
        <div class="modal-header">
          <h4>重置密码 — {{ resetTarget.username }}</h4>
          <button class="btn btn-ghost btn-sm" @click="resetTarget = null">✕</button>
        </div>
        <div class="modal-body">
          <div class="field">
            <label>新密码</label>
            <input v-model="resetPassword" type="password" placeholder="至少 4 个字符" @keydown.enter="doResetPassword" />
          </div>
          <div class="field">
            <label>确认新密码</label>
            <input v-model="resetPasswordConfirm" type="password" placeholder="再次输入" @keydown.enter="doResetPassword" />
          </div>
          <p v-if="resetMsg" class="status-msg" :class="{ error: resetError }">{{ resetMsg }}</p>
        </div>
        <div class="modal-footer">
          <button class="btn btn-ghost" @click="resetTarget = null">取消</button>
          <button class="btn btn-primary" @click="doResetPassword" :disabled="resetting">
            {{ resetting ? "重置中…" : "确认重置" }}
          </button>
        </div>
      </div>
    </div>

    <!-- 角色变更确认弹窗 -->
    <div v-if="roleConfirm" class="modal-overlay" @click.self="roleConfirm = null">
      <div class="confirm-dialog">
        <p>确认将「<strong>{{ roleConfirm.username }}</strong>」的角色改为 <strong>{{ roleConfirm.role }}</strong>？</p>
        <div class="btn-row" style="justify-content:flex-end;margin-top:12px">
          <button class="btn btn-ghost" @click="roleConfirm = null">取消</button>
          <button class="btn btn-primary btn-sm" @click="confirmChangeRole">确认</button>
        </div>
      </div>
    </div>

    <!-- 提示弹窗 -->
    <div v-if="alertMsg" class="modal-overlay" @click.self="alertMsg = ''">
      <div class="confirm-dialog">
        <p>{{ alertMsg }}</p>
        <div class="btn-row" style="justify-content:flex-end;margin-top:12px">
          <button class="btn btn-primary btn-sm" @click="alertMsg = ''">确定</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, onActivated } from "vue";
import api from "../api/index.js";

const users = ref([]);
const stats = ref({});
const refreshing = ref(false);
const showCreate = ref(false);
const createMsg = ref("");
const createError = ref(false);
const creating = ref(false);
const deleteTarget = ref(null);
const deleting = ref(false);
const resetTarget = ref(null);
const resetPassword = ref("");
const resetPasswordConfirm = ref("");
const resetting = ref(false);
const resetMsg = ref("");
const resetError = ref(false);
const roleConfirm = ref(null);
const alertMsg = ref("");

function showAlert(msg) {
  alertMsg.value = msg;
}

const newUser = ref({ username: "", password: "", role: "member", display_name: "" });

async function loadUsers() {
  try {
    const [data, s] = await Promise.all([
      api("/api/admin/users"),
      api("/api/admin/stats"),
    ]);
    const docMap = s.user_doc_counts || {};
    const totalDocs = s.doc_count || 0;
    const list = (data.users || []).map(u => ({
      ...u,
      doc_count: u.role === 'admin' ? totalDocs : (docMap[u.username] || 0),
      source_count: u.source_count ?? (u.role === 'admin' ? (s.src_count || 0) : 0),
    }));
    list.sort((a, b) => {
      if (a.role !== b.role) return a.role === 'admin' ? -1 : 1;
      return (a.username || '').localeCompare(b.username || '', undefined, { numeric: true });
    });
    users.value = list;
    stats.value = s;
  } catch {
    users.value = [];
    stats.value = {};
  }
}

async function refresh() {
  refreshing.value = true;
  await loadUsers();
  refreshing.value = false;
}

function formatBytes(bytes) {
  if (!bytes && bytes !== 0) return "-";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

async function doCreateUser() {
  const { username, password, role } = newUser.value;
  if (!username.trim() || !password) {
    createMsg.value = "请填写用户名和密码";
    createError.value = true;
    return;
  }
  creating.value = true;
  createMsg.value = "";
  createError.value = false;
  try {
    await api("/api/admin/users", {
      method: "POST",
      body: { username: username.trim(), password, role, display_name: newUser.value.display_name?.trim() || '' },
    });
    createMsg.value = `用户 ${username} 创建成功`;
    showCreate.value = false;
    newUser.value = { username: "", password: "", role: "member", display_name: "" };
    await loadUsers();
  } catch (e) {
    createMsg.value = e.message || "创建失败";
    createError.value = true;
  } finally {
    creating.value = false;
  }
}

function openCreate() {
  deleteTarget.value = null;
  resetTarget.value = null;
  showCreate.value = true;
}

function confirmDeleteUser(u) {
  showCreate.value = false;
  resetTarget.value = null;
  deleteTarget.value = u;
}

async function doDeleteUser() {
  if (!deleteTarget.value) return;
  const u = deleteTarget.value;
  deleteTarget.value = null;
  deleting.value = true;
  try {
    await api(`/api/admin/users/${encodeURIComponent(u.username)}`, { method: "DELETE" });
    await loadUsers();
  } catch (e) {
    showAlert(`删除失败: ${e.message || "未知错误"}`);
  } finally {
    deleting.value = false;
  }
}

function doChangeRole(username, role) {
  roleConfirm.value = { username, role };
}

async function confirmChangeRole() {
  if (!roleConfirm.value) return;
  const { username, role } = roleConfirm.value;
  roleConfirm.value = null;
  try {
    await api(`/api/admin/users/${encodeURIComponent(username)}/role`, {
      method: "PUT",
      body: { role },
    });
    await loadUsers();
  } catch (e) {
    showAlert(`修改失败: ${e.message || "未知错误"}`);
  }
}

function showResetPwd(u) {
  showCreate.value = false;
  deleteTarget.value = null;
  resetTarget.value = u;
  resetPassword.value = "";
  resetPasswordConfirm.value = "";
  resetMsg.value = "";
  resetError.value = false;
}

async function doResetPassword() {
  if (!resetTarget.value) return;
  if (!resetPassword.value || resetPassword.value.length < 4) {
    resetMsg.value = "密码至少 4 个字符";
    resetError.value = true;
    return;
  }
  if (resetPassword.value !== resetPasswordConfirm.value) {
    resetMsg.value = "两次密码不一致";
    resetError.value = true;
    return;
  }
  resetting.value = true;
  resetMsg.value = "";
  resetError.value = false;
  try {
    await api(`/api/admin/users/${encodeURIComponent(resetTarget.value.username)}/reset-password`, {
      method: "POST",
      body: { new_password: resetPassword.value },
    });
    resetMsg.value = "密码已重置";
    setTimeout(() => { resetTarget.value = null; }, 1200);
  } catch (e) {
    resetMsg.value = e.message || "重置失败";
    resetError.value = true;
  } finally {
    resetting.value = false;
  }
}

function formatTime(t) {
  if (!t) return "-";
  return new Date(t * 1000).toLocaleString();
}

function onGlobalKeydown(e) {
  if (e.key === 'Escape') {
    showCreate.value = false;
    deleteTarget.value = null;
    resetTarget.value = null;
    roleConfirm.value = null;
    alertMsg.value = '';
  }
}

onMounted(() => {
  document.addEventListener('keydown', onGlobalKeydown);
  loadUsers();
});

onActivated(() => {
  loadUsers();
});

onUnmounted(() => {
  document.removeEventListener('keydown', onGlobalKeydown);
});
</script>

<style scoped>
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 10px;
  margin: 16px 0;
}
.stat-card {
  border: 1px solid var(--border-default);
  border-radius: var(--radius);
  padding: 14px;
  text-align: center;
}
.stat-value { font-size: 1.4rem; font-weight: 700; }
.stat-label { font-size: 0.75rem; color: var(--fg-muted); margin-top: 2px; }

.user-table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 12px;
}
.user-table th, .user-table td {
  text-align: left;
  padding: 8px 10px;
  border-bottom: 1px solid var(--border-muted);
  font-size: 0.85rem;
}
.user-table th {
  font-weight: 600;
  color: var(--fg-muted);
  font-size: 0.8rem;
}
.role-select {
  font-size: 0.85rem;
  padding: 2px 6px;
  border: 1px solid var(--border-default);
  border-radius: var(--radius);
  background: var(--bg-card);
  color: var(--fg-default);
}
.status-msg { margin-top: 8px; font-size: 0.85rem; }
.status-msg.error { color: var(--danger-fg); }
.status-badge { font-size: 0.75rem; font-weight: 600; padding: 2px 6px; border-radius: 3px; }
.status-normal { color: #16a34a; background: rgba(22,163,74,0.1); }
.status-locked { color: #dc2626; background: rgba(220,38,38,0.1); }
.confirm-dialog {
  background: var(--bg-card);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  padding: 24px;
  max-width: 420px;
  box-shadow: var(--shadow-lg);
}
.toolbar {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}
.action-cell {
  white-space: nowrap;
  display: flex;
  gap: 4px;
}
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
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  box-shadow: var(--shadow-lg);
}
.modal-sm { width: 400px; }
.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 16px;
  border-bottom: 1px solid var(--border-muted);
}
.modal-header h4 { font-size: 1rem; font-weight: 600; }
.modal-body { padding: 12px 16px; overflow-y: auto; flex: 1; }
.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 10px 16px;
  border-top: 1px solid var(--border-muted);
}
.field { margin-bottom: 12px; }
.field label {
  display: block;
  font-size: 0.82rem;
  font-weight: 500;
  color: var(--fg-muted);
  margin-bottom: 4px;
}
.field input, .field select {
  width: 100%;
  padding: 8px 10px;
  font-size: 0.9rem;
  border: 1px solid var(--border-default);
  border-radius: var(--radius);
  background: var(--bg-card);
  color: var(--fg-default);
}
</style>
