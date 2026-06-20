<template>
  <div class="tree-branch" :class="{ 'is-root': depth === 0 }">
    <button
      type="button"
      class="branch-head"
      :style="{ paddingLeft: 8 + depth * 14 + 'px' }"
      @click="expanded = !expanded"
    >
      <span class="chevron">{{ expanded ? "▾" : "▸" }}</span>
      <span class="branch-icon">{{ icon }}</span>
      <span class="branch-label">{{ label }}</span>
      <span v-if="count != null" class="branch-count">({{ count }})</span>
      <span v-if="sourceId" class="branch-source-id">{{ sourceId }}</span>
    </button>
    <div v-if="expanded" class="branch-body">
      <slot />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from "vue";

const props = defineProps({
  label: { type: String, default: "" },
  count: { type: [Number, String], default: null },
  sourceId: { type: String, default: "" },
  depth: { type: Number, default: 0 },
  defaultExpanded: { type: Boolean, default: false },
});

const expanded = ref(props.depth === 0 || props.defaultExpanded);

// 响应 activeDocId 变化：当文档在子树中时自动展开
watch(() => props.defaultExpanded, (val) => {
  if (val) expanded.value = true;
});

const icon = computed(() => {
  if (props.sourceId) return "📦";
  const l = (props.label || "").toLowerCase();
  if (l.includes("原始") || l.includes("source")) return "📄";
  if (l.includes("wiki") || l.includes("摘要")) return "📝";
  if (l.includes("python")) return "🐍";
  if (l.includes("java")) return "☕";
  return "📁";
});
</script>

<style scoped>
.tree-branch {
  user-select: none;
}
.branch-head {
  display: flex;
  align-items: center;
  gap: 4px;
  width: 100%;
  padding: 4px 8px;
  border: none;
  border-radius: var(--radius);
  background: transparent;
  color: var(--fg-muted);
  font-size: 0.82rem;
  cursor: pointer;
  text-align: left;
  transition: background 0.1s, color 0.1s;
}
.branch-head:hover {
  background: var(--bg-hover);
  color: var(--fg-default);
}
.chevron {
  width: 14px;
  flex-shrink: 0;
  font-size: 0.7rem;
  color: var(--fg-subtle);
}
.branch-icon {
  flex-shrink: 0;
  font-size: 0.85rem;
  width: 18px;
  text-align: center;
}
.branch-label {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.branch-count {
  font-size: 0.75rem;
  color: var(--fg-subtle);
  flex-shrink: 0;
}
.branch-source-id {
  font-size: 0.7rem;
  color: var(--fg-subtle);
  background: var(--bg-muted);
  padding: 0 4px;
  border-radius: 3px;
  flex-shrink: 0;
}
.branch-body {
  display: flex;
  flex-direction: column;
}
</style>
