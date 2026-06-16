const routes = [
  {
    path: "/",
    redirect: "/library",
  },
  {
    path: "/library",
    name: "library",
    component: () => import("../views/Library.vue"),
    meta: { title: "文档库", parent: "library" },
  },
  {
    path: "/search",
    name: "search",
    component: () => import("../views/Search.vue"),
    meta: { title: "搜索", parent: null },
  },
  {
    path: "/qa",
    name: "qa",
    component: () => import("../views/QA.vue"),
    meta: { title: "知识查询", parent: null },
  },
  {
    path: "/graph",
    name: "graph",
    component: () => import("../views/Graph.vue"),
    meta: { title: "Wiki 图谱", parent: null },
  },
  {
    path: "/sync/control",
    name: "sync-control",
    component: () => import("../views/SyncControl.vue"),
    meta: { title: "同步控制", parent: "sync" },
  },
  {
    path: "/sync/sources",
    name: "sync-sources",
    component: () => import("../views/SyncSources.vue"),
    meta: { title: "仓库管理", parent: "sync" },
  },
  {
    path: "/sync/vault",
    name: "sync-vault",
    component: () => import("../views/SyncVault.vue"),
    meta: { title: "全局", parent: "sync" },
  },
  {
    path: "/sync/purpose",
    name: "sync-purpose",
    component: () => import("../views/SyncPurpose.vue"),
    meta: { title: "规则约束", parent: "sync" },
  },
  {
    path: "/sync/audit",
    name: "sync-audit",
    component: () => import("../views/SyncAudit.vue"),
    meta: { title: "审计", parent: "sync" },
  },
  {
    path: "/account",
    name: "account",
    component: () => import("../views/Account.vue"),
    meta: { title: "账户", parent: null },
  },
];

export default routes;
