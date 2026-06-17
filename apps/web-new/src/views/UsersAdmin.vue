<template>
  <div class="view-pane">
    <div class="view-header">
      <h2>👥 用户管理</h2>
    </div>

    <p class="subtle">管理团队用户。新用户会自动创建专属目录和默认私有源。</p>

    <div class="toolbar">
      <button class="btn btn-primary btn-sm" @click="showCreate = true">＋ 创建用户</button>
    </div>

    <table class="user-table" v-if="users.length">
      <thead>
        <tr>
          <th>用户名</th>
          <th>角色</th>
          <th>创建时间</th>
          <th>源数量</th>
          <th>专属目录</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="u in users" :key="u.username">
          <td><strong>{{ u.username }}</strong></td>
          <td>
            <select :value="u.role" @change="changeRole(u.username, $event.target.value)" class="role-select">
              <option value="member">member</option>
              <option value="admin">admin</option>
            </select>
          </td>
          <td>{{ formatTime(u.created_at) }}</td>
          <td>{{ u.source_count }}</td>
          <td>{{ u.has_dir ? '✅' : '❌' }}</td>
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
        <p class="subtle">将同时删除该用户的私有源、索引数据和专属目录。此操作不可撤销。</p>
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
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import api from "../api/index.js";

const users = ref([]);
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

const newUser = ref({ username: "", password: "", role: "member" });

async function loadUsers() {
  try {
    const data = await api("/api/admin/users");
    users.value = data.users || [];
  } catch {
    users.value = [];
  }
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
      body: { username: username.trim(), password, role },
    });
    createMsg.value = `用户 ${username} 创建成功`;
    showCreate.value = false;
    newUser.value = { username: "", password: "", role: "member" };
    await loadUsers();
  } catch (e) {
    createMsg.value = e.message || "创建失败";
    createError.value = true;
  } finally {
    creating.value = false;
  }
}

function confirmDeleteUser(u) {
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
    alert(`删除失败: ${e.message || "未知错误"}`);
  } finally {
    deleting.value = false;
  }
}

async function changeRole(username, role) {
  if (!confirm(`确认将 ${username} 的角色改为 ${role}？`)) return;
  try {
    await api(`/api/admin/users/${encodeURIComponent(username)}/role`, {
      method: "PUT",
      body: { role },
    });
    await loadUsers();
  } catch (e) {
    alert(`修改失败: ${e.message || "未知错误"}`);
  }
}

function showResetPwd(u) {
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

onMounted(loadUsers);
</script>

<style scoped>
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
  text-transform: uppercase;
}
.role-select {
  font-size: 0.85rem;
  padding: 2px 6px;
  border: 1px solid var(--border-default);
  border-radius: var(--radius);
  background: var(--bg-card);
  color: var(--fg-default);
}
.modal-sm {
  width: 400px;
}
.field {
  margin-bottom: 12px;
}
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
.status-msg { margin-top: 8px; font-size: 0.85rem; }
.status-msg.error { color: var(--danger-fg); }
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
</style>
