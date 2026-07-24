# 第十三组：搜索功能

## 第十三组：搜索功能

### 63. 搜索无结果时 toast 快速点击堆积

**症状**：快速多次点击搜索按钮，每次搜索无结果都弹 toast.info("未找到匹配结果")，屏幕堆积多条相同 toast。

**根因**：Toast.vue 的 `addToast()` 每次收到 `mind-toast` 事件都无条件 push 新条目，无去重逻辑。

**修复**：在 `addToast()` 中添加去重检查——匹配列表中是否已有相同 message + type 的活跃 toast，若有则跳过：

```javascript
// apps/web-new/src/components/Toast.vue
function addToast(message, type = "info", duration = 4000) {
  const dup = toasts.value.find(t => t.message === message && t.type === type);
  if (dup) return;  // 去重
  const id = ++nextId;
  toasts.value.push({ id, message, type });
  if (duration > 0) {
    setTimeout(() => dismiss(id), duration);
  }
}
```

**教训**：UI 组件的事件消费者应具备幂等性。频繁触发的 toast、notification 等提示类组件，必须有去重或防抖机制，否则快速操作会导致 UI 刷屏，反而干扰用户。相同 message+type 只保留一条是合理的默认行为。

---

### 64. 搜索结果缓存跨用户共享

**症状**：管理员搜索后登出，成员登入后看到管理员的搜索结果（query + items 都恢复）。

**根因**：`Search.vue` 中 `SEARCH_CACHE_KEY` 是全局常量 `'mind_sync_last_search'`，所有用户共用同一 localStorage key。App.vue 的页面记录已按用户隔离（`pageKey()` / `docKey()`），但搜索结果缓存遗漏了。

**修复**：参照 App.vue 的做法，将常量改为函数，按 `displayName` 生成带用户后缀的 key：

```javascript
// apps/web-new/src/views/Search.vue
import { useAuth } from "../composables/useAuth.js";
const { displayName } = useAuth();

function searchCacheKey() {
  return displayName.value
    ? `mind_sync_last_search_${displayName.value}`
    : 'mind_sync_last_search';
}

// 替换所有 SEARCH_CACHE_KEY → searchCacheKey()
```

**教训**：用户状态隔离必须全覆盖。页面记录（page key）、文档缓存（doc key）、搜索结果（search key）——所有持久化到 localStorage 的用户数据都要按用户 ID 隔离。一处遗漏就会导致跨用户数据泄漏。

---

### 65. 搜索无结果缓存未恢复——空数组 length=0 为 falsy

**症状**：管理员搜索某关键字无结果 → 登出 → 重登，搜索页面被清空，query 丢失。但搜索有结果时登出登入能正常恢复。

**根因**：`restoreCachedSearch()` 中用 `cached.items?.length` 判断是否恢复缓存：

```javascript
// 原代码
if (cached && cached.q && cached.items?.length && cached.ts && ...) {
```

搜索无结果时 `items` 是空数组 `[]`，`[].length === 0` 在 JS 中是 **falsy**，条件短路 → 缓存不会被恢复。但 `items: []` 本身是合法的已搜索状态（无结果也是结果），不应被过滤掉。

**修复**：改用 `Array.isArray()` 判断 items 是否为数组（包括空数组）：

```javascript
if (cached && cached.q && Array.isArray(cached.items) && cached.ts && ...) {
```

**教训**：用 `.length` 做存在性检查时要警惕 falsy 边缘情况。空数组 `[]`、空字符串 `""`、数字 `0` 的 `.length` 都是 `0`（falsy）。正确做法是用 `Array.isArray()`、`typeof x === 'string'` 等类型判断代替 `.length` 作为存在性守卫。这也呼应了通用原则 #11「空值判语义」——空数组可能是有效状态，需结合上下文判断。

---

### 66. sync/rebuild 清搜索缓存漏了带用户名的键

**症状**：用户 `alice` 触发增量同步或全量重建后，切回搜索页仍看到旧的搜索结果（含过期 doc_id），点击文档返回 404。用户 `bob` 不受影响。

**根因**：`Search.vue` 在 #64 中已将搜索缓存键改为 `mind_sync_last_search_{username}`，但 `SyncControl.vue` 和 `Library.vue` 清除缓存时仍使用硬编码裸键 `'mind_sync_last_search'`。用户登录后 `displayName` 有值 → Search 写入带后缀的键 → SyncControl/Library 清的却是裸键 → 两处键名不匹配，缓存清不掉。

```javascript
// Search.vue — 写入带用户名后缀
function searchCacheKey() {
  return displayName.value
    ? `mind_sync_last_search_${displayName.value}`  // → mind_sync_last_search_alice
    : 'mind_sync_last_search';
}

// SyncControl.vue — 清除硬编码裸键（bug）
localStorage.removeItem('mind_sync_last_search');   // ← 永远清不到 alice 的缓存

// Library.vue — 同样
const SEARCH_CACHE_KEY = 'mind_sync_last_search';   // ← 同样
```

**修复**：`SyncControl.vue` 和 `Library.vue` 改为与 `Search.vue` 一致的 `searchCacheKey()` 函数，从 `useAuth()` 获取 `displayName` 拼接键名。同时满足两条业务约束：

1. **用户级隔离**：`alice` 重建只清 `alice` 自己的缓存，`bob` 不受影响
2. **裸键兜底**：匿名/未登录场景保留 `mind_sync_last_search` 裸键作为防御

**教训**：修复多组件一致的逻辑（如缓存键生成）时，必须全局搜索所有引用点一并修改。一处提取为函数而另一处仍硬编码，会导致**键名漂移**——写入方和清除方使用不同的 key，缓存永远清不掉。这也印证了通用原则「一处提取，处处统一」——如果某个值在 ≥2 处出现，应提取为共享函数/常量。


---
