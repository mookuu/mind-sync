# 第九组：UI 优化与缓存策略

## 第九组：UI 优化与缓存策略

### 43. 代码文件 escapeHtml 未调用 highlight.js

**症状**：代码文件（如 `.py`、`.java`）在文档阅读区显示为纯文本灰色块，无任何语法高亮颜色。HTML 中有 `class="language-python"` 但无 `<span class="hljs-*">` 标签。

**根因**：`Library.vue` 的 `renderedContent` 对非 markdown 文件只用了 `escapeHtml` 转义，包了一层 `<pre class="hljs"><code class="language-xxx">`，但从未调用 `hljs.highlight()`。

```javascript
// 错误：只转义，不高亮
const content = markdownIt.utils.escapeHtml(doc.content || "");
return `<pre class="hljs"><code class="language-${codeLang}">${content}</code></pre>`;
```

**修复**：从 `markdown-it.js` 导出 `hljs`，代码文件路径调用 `hljs.highlight()`：

```javascript
import { hljs } from "../markdown-it.js";
// ...
return `<pre class="hljs"><code class="language-${codeLang}">${hljs.highlight(content, { language: codeLang, ignoreIllegals: true }).value}</code></pre>`;
```

**教训**：CSS 类名只是样式约定，不等于实际高亮行为。highlight.js 的 `class="language-xxx"` + `class="hljs"` 只是约定，实际颜色来自 `<span>` 标签——必须调用 `hljs.highlight()` 才会生成这些 span。

---

### 44. 浏览器 confirm() 风格不统一

**症状**：全量重建使用 `confirm("全量重建将清空索引...")` 弹出浏览器原生对话框，与系统其他确认操作（删除用户、删除库、重置密码）的组件式 modal 风格不一致。

**修复**：替换为 Vue 组件式弹窗：

```html
<div v-if="showRebuildConfirm" class="modal-overlay" @click.self="showRebuildConfirm = false">
  <div class="confirm-dialog">
    <p>确认执行<strong>全量重建</strong>？</p>
    <p class="subtle">将清空全部索引并强制重扫所有文件...</p>
    <div class="btn-row">
      <button class="btn btn-ghost" @click="showRebuildConfirm = false">取消</button>
      <button class="btn btn-danger btn-sm" @click="doRebuild">确认重建</button>
    </div>
  </div>
</div>
```

**教训**：项目中应保持交互模式统一。`confirm()` / `alert()` / `prompt()` 是不可定制、不可主题化的浏览器原生控件，只适合快速原型。生产代码用组件式 modal。

---

### 45. 搜索结果 localStorage 缓存过期

**症状**：全量重建后，从搜索页点击之前的搜索结果跳转到文档 → 404。

**根因**：Search.vue 的 `doSearch` 将搜索结果缓存到 `localStorage`，`restoreCachedSearch` 在页面加载时恢复。rebuild 后文档 ID 变化，缓存中的 ID 已失效。

**修复**：
1. 缓存加 `ts` 时间戳，超过 10 分钟过期
2. 增量同步/全量重建开始时主动 `localStorage.removeItem('mind_sync_last_search')`
3. `Library.vue` 的 `openDoc` 返回 404 时也清缓存（兜底）

**教训**：跨会话缓存的数据必须有失效策略（TTL、事件驱动清除、版本号）。不能依赖"用户会手动刷新"。

---

### 46. 新增库在 preset=all 时自动勾选

**症状**：同步素材添加新库后，其 checkbox 默认处于勾选状态。

**根因**：`syncPreset === "all"` 时，所有源的 checkbox 都显示为已勾选。新增库后 preset 仍为 "all"，新库也被自动勾选。

**修复**：在 `addCustomPath` / `addPrivateSource` 中，若旧 `syncPreset === "all"`，reload 后转为 `"custom"` 模式并将所有源（排除新库）加入自定义列表：

```javascript
if (oldPreset === 'all') {
  const allIds = syncPresets.value
    .filter(p => p.id !== 'all' && p.id !== 'custom' && p.id !== `${newSourceId}:local`)
    .map(p => p.id);
  await setCustomSources(allIds);
}
```

**教训**：「全选」是一种隐式包含，新增条目会被自动纳入。如果需要用户显式 opt-in，应在添加操作后退出全选模式。

---

### 47. 删除/增加库后侧边栏树未同步更新

**症状**：从同步素材删除或增加库后，切回文档库，已展开的分类树仍显示旧数据，需要手动点击两次（收起→展开）刷新。

**根因**：侧边栏 `catTrees` 数据加载后保留在 Vue 内存中。路由切换不销毁 AppSidebar 组件（它在 layout 中），数据不会自动刷新。

**修复**：在 `watch(route.path)` 中检测从非 `/library` 页面进入时，自动收起再展开已展开的分类树，触发重新加载：

```javascript
if (newPath.startsWith('/library') && oldPath && !oldPath.startsWith('/library')) {
  nextTick(() => {
    for (const catKey of ['source', 'summary', 'query']) {
      if (catExpanded[catKey] && catTrees[catKey]) {
        catExpanded[catKey] = false;
        nextTick(() => toggleCatTree(catKey));  // 重新加载
      }
    }
  });
}
```

**教训**：SPA 中不销毁的全局组件需要主动感知数据变化。监听路由变化是一种轻量的事件驱动刷新方式。

---

### 48. 路径无效的库仍展示在文档树

**症状**：同步素材中标为「⚠ 路径无效」的库，在文档库树中仍然显示（count=0）。

**根因**：`build_library_index` 补充空源时未检查路径是否真实存在。

**修复**：在补充空源的循环中加路径存在性检查：

```python
spath = (src.path or "").strip()
if spath and not spath.startswith(("http://", "https://", "git@")):
    if not Path(spath).exists():
        continue  # 路径无效 → 跳过
```

**教训**：展示数据前应做完整性校验。路径无效的源无法提供任何文档，展示出来只会让用户困惑。

---

### 49. etag 缓存提速文档库树加载

**症状**：每次展开分类树都重建 DOM，即使数据未变化也有轻微闪烁。

**优化**：后端在 library API 响应中添加 `etag` 字段（源 ID + 文档数的 MD5 指纹），前端比对——相同则跳过 `catTrees = nodes` 赋值，避免 Vue 触发 DOM 重渲染。

```python
# 后端
etag_src = sorted((sid, len(dlist)) for sid, dlist in by_source.items())
etag = hashlib.md5(json.dumps(etag_src).encode()).hexdigest()[:8]
```

```javascript
// 前端
if (data.etag && catTrees[catKey] && data.etag === catTreesETag[catKey]) {
  return;  // 跳过 DOM 重建
}
catTrees[catKey] = nodes;
catTreesETag[catKey] = data.etag;
```

**教训**：数据变更频率远低于查询频率的场景，用轻量指纹做缓存验证可以消除无意义的 DOM 更新。不增加额外 API 调用，仅需 8 字符的 hash 字段。

---
