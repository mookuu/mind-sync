<template>
  <div>
    <template v-for="item in node.children || []" :key="item.path">
      <TreeBranch
        v-if="item.type === 'dir'"
        :label="item.name"
        :depth="depth"
        :default-expanded="treeContains(item, props.activeDocId)"
      >
        <TreeNode
          v-for="child in item.children || []"
          :key="child.path || child.name"
          :node="child"
          :depth="depth + 1"
          :active-doc-id="props.activeDocId"
          @select="$emit('select', $event)"
        />
      </TreeBranch>
      <button
        v-else-if="item.type === 'file'"
        type="button"
        class="file-item"
        :class="{ active: activeId === item.doc_id || String(props.activeDocId) === String(item.doc_id) }"
        :style="{ paddingLeft: 8 + depth * 14 + 'px' }"
        :title="item.path"
        @click="$emit('select', item.doc_id); activeId = item.doc_id"
      >
        <span class="file-icon">{{ langIcon(item.lang) }}</span>
        <span class="file-name">{{ item.title || item.name }}</span>
      </button>
    </template>
  </div>
</template>

<script setup>
import { ref, computed } from "vue";
import TreeBranch from "./TreeBranch.vue";

const props = defineProps({
  node: { type: Object, default: () => ({}) },
  depth: { type: Number, default: 1 },
  activeDocId: { type: [String, Number], default: null },
});

defineEmits(["select"]);

const activeId = ref(null);

// 检查子树是否包含 activeDocId
function treeContains(node, targetId) {
  if (!node || !node.children) return false;
  for (const item of node.children) {
    if (item.type === 'file' && String(item.doc_id) === String(targetId)) return true;
    if (item.type === 'dir' && treeContains(item, targetId)) return true;
  }
  return false;
}

function langIcon(lang) {
  if (lang === "markdown") return "📄";
  if (lang === "python") return "🐍";
  if (lang === "java") return "☕";
  return "📄";
}
</script>

<style scoped>
.file-item {
  display: flex;
  align-items: center;
  gap: 4px;
  width: 100%;
  padding: 3px 8px;
  border: none;
  border-radius: var(--radius);
  background: transparent;
  color: var(--fg-muted);
  font-size: 0.8rem;
  cursor: pointer;
  text-align: left;
  transition: background 0.1s, color 0.1s;
}
.file-item:hover {
  background: var(--bg-hover);
  color: var(--fg-default);
}
.file-item.active {
  color: var(--accent-fg);
  background: var(--accent-bg);
}
.file-icon {
  flex-shrink: 0;
  width: 18px;
  text-align: center;
  font-size: 0.82rem;
}
.file-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
