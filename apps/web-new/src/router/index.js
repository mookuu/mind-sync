import Library from "../views/Library.vue";
import Search from "../views/Search.vue";
import QA from "../views/QA.vue";
import Graph from "../views/Graph.vue";
import SyncControl from "../views/SyncControl.vue";
import SyncSources from "../views/SyncSources.vue";
import SyncVault from "../views/SyncVault.vue";
import SyncPurpose from "../views/SyncPurpose.vue";
import SyncAudit from "../views/SyncAudit.vue";
import Account from "../views/Account.vue";
import UsersAdmin from "../views/UsersAdmin.vue";
import AdminDashboard from "../views/AdminDashboard.vue";
import ApiKeys from "../views/ApiKeys.vue";

const routes = [
  {
    path: "/",
    redirect: "/library",
  },
  {
    path: "/library",
    name: "library",
    component: Library,
    meta: { title: "文档库", parent: "library" },
  },
  {
    path: "/search",
    name: "search",
    component: Search,
    meta: { title: "搜索", parent: null },
  },
  {
    path: "/qa",
    name: "qa",
    component: QA,
    meta: { title: "知识查询", parent: null },
  },
  {
    path: "/graph",
    name: "graph",
    component: Graph,
    meta: { title: "Wiki 图谱", parent: null, adminOnly: true },
  },
  {
    path: "/sync/control",
    name: "sync-control",
    component: SyncControl,
    meta: { title: "同步控制", parent: "sync" },
  },
  {
    path: "/sync/sources",
    name: "sync-sources",
    component: SyncSources,
    meta: { title: "素材管理", parent: "sync" },
  },
  {
    path: "/sync/vault",
    name: "sync-vault",
    component: SyncVault,
    meta: { title: "仓库管理", parent: "sync" },
  },
  {
    path: "/sync/purpose",
    name: "sync-purpose",
    component: SyncPurpose,
    meta: { title: "规则约束", parent: "sync", adminOnly: true },
  },
  {
    path: "/sync/audit",
    name: "sync-audit",
    component: SyncAudit,
    meta: { title: "操作记录", parent: "sync" },
  },
  {
    path: "/account",
    name: "account",
    component: Account,
    meta: { title: "账户", parent: null },
  },
  {
    path: "/admin/users",
    name: "admin-users",
    component: UsersAdmin,
    meta: { title: "用户管理", parent: "admin", adminOnly: true },
  },
  {
    path: "/admin/dashboard",
    name: "admin-dashboard",
    component: AdminDashboard,
    meta: { title: "系统概览", parent: "admin", adminOnly: true },
  },
  {
    path: "/admin/api-keys",
    name: "admin-api-keys",
    component: ApiKeys,
    meta: { title: "API keys", parent: "admin", adminOnly: true },
  },
];

export default routes;
