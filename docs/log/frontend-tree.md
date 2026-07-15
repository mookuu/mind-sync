# 第八组：前端树组件

## 第八组：前端树组件

### 39. 语言分组树导致目录结构失真

**症状**：文档库树中同一个源的目录结构被拆成多份（Python 树、Java 树、Markdown 树），每份只显示该语言的文件，整体结构与源的实际目录不一致。

**根因**：`_build_lang_groups` 按 `lang` 字段分组文档，每组独立构建一棵树。共享的目录路径在每个语言组里被复制一份但内容不全。

```python
# 旧逻辑：按语言分组 → 每个语言独立一棵树
by_lang: dict[str, list] = {}
for doc in docs:
    by_lang.setdefault(doc["lang"], []).append(doc)
for lang, lang_docs in by_lang.items():
    lang_groups.append({"tree": _build_lang_tree(lang_docs)})
```

**修复**：改为 `_build_lang_tree(docs)` 直接构建统一目录树，所有文件共享同一棵树，`lang` 保留为文件属性用于图标显示。

API 响应结构：`"languages": [...]` → `"tree": [...]`（源级别直接挂树，去掉中间语言分组层）。

**教训**：分组视图不应破坏原始层级结构。如果分组会导致路径重复且内容不完整，说明分组维度选错了——应该在保留源目录树的前提下通过颜色/图标区分文件类型。

---

### 40. TreeNode 不渲染根级文件

**症状**：源的根目录下的文件（如 `README.md`）在树中不可见。

**根因**：TreeNode 模板遍历 `node.children` 来渲染子节点：

```html
<template v-for="item in node.children || []" :key="item.path">
  <TreeBranch v-if="item.type === 'dir'" ...>
  <button v-else-if="item.type === 'file'" ...>
</template>
```

当 `node` 本身是文件（`type === 'file'`）时，`node.children` 为 `undefined`，`v-for` 无事可迭代 → 文件不渲染。

**修复**：在 TreeNode 模板开头加顶层文件节点的渲染分支：

```html
<button v-if="node.type === 'file'" type="button" class="file-item" ...>
  <span class="file-icon">{{ langIcon(node.lang) }}</span>
  <span class="file-name">{{ node.title || node.name }}</span>
</button>
<template v-else v-for="item in node.children || []" ...>
```

同时更新 `treeContains` 函数，检查节点自身是否匹配（不仅是 children）。

**教训**：递归组件的边界条件最容易遗漏——顶层节点和递归节点的数据结构可能不同，组件必须同时处理两种形状。

---

### 41. TreeBranch defaultExpanded 不响应 prop 变化

**症状**：从搜索页点击结果跳转到文档库后，侧边栏树的祖先节点不会自动展开到目标文档。

**根因**：TreeBranch 的 `expanded` 由 `ref(props.depth === 0 || props.defaultExpanded)` 初始化，但之后 `defaultExpanded` prop 变化时，`expanded` 不会更新。

```javascript
const expanded = ref(props.depth === 0 || props.defaultExpanded);
// props.defaultExpanded 后续变化 → expanded 不响应
```

**修复**：添加 `watch` 监听 prop 变化：

```javascript
import { watch } from "vue";
watch(() => props.defaultExpanded, (val) => {
  if (val) expanded.value = true;
});
```

**教训**：Vue 的 `ref(initialValue)` 只在组件创建时执行一次。如果需要响应 prop 变化，必须显式 `watch`。

---

### 42. 侧边栏树缓存导致过期数据

**症状**：删除库后切回文档库，已展开的树仍显示被删除的库，需要手动点击两次（收起→展开）才能刷新。

**根因**：`catTrees` 是 Vue 响应式变量，数据加载后就一直存在内存中。`toggleCatTree` 中的 `if (catTrees[catKey]) return` 阻止了重新加载。删除库后虽然 DB 数据已清，但内存中的 `catTrees` 未更新。

**修复**：
1. 移除 `if (catTrees[catKey]) return` 缓存检查
2. 在路由 watcher 中检测从其他页面进入 `/library` 时，自动收起再展开已展开的树
3. 引入 API 响应的 `etag` 指纹，etag 未变时跳过 DOM 重建（保留性能优化）

**教训**：内存缓存的数据没有过期机制就会成为过期数据源。缓存的正确做法是「缓存 + 失效策略」，而不是「缓存没有任何失效策略」。

---
