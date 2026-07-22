<template>
  <div v-if="visible && notices.length" class="notify-bar" :class="{ highlight: hasHighlight }">
    <div class="notify-scroll">
      <span
        v-for="n in notices"
        :key="n.id"
        class="notify-item"
        :class="{ 'notify-highlight': n.highlight }"
        @click="onClick(n)"
      >
        {{ n.message }}
      </span>
    </div>
    <button class="notify-close" @click="dismiss">✕</button>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from "vue";
import { useRouter } from "vue-router";
import api from "../api/index.js";

const router = useRouter();
const notices = ref([]);
const visible = ref(true);
const knownIds = new Set();

const hasHighlight = computed(() => notices.value.some(n => n.highlight));

let pollTimer = null;

async function loadNotices() {
  try {
    const data = await api("/api/user/notifications");
    const items = data.notifications || [];
    knownIds.clear();
    for (const n of items) knownIds.add(n.id);
    notices.value = items;
    window.dispatchEvent(new CustomEvent("mind-notify-count", { detail: { count: notices.value.length } }));
  } catch {
    // ignore
  }
}

function onClick(n) {
  if (n.action_link) {
    router.push(n.action_link);
  }
  // 标记已读
  api(`/api/user/notifications/${n.id}/read`, { method: "POST" }).catch(() => {});
  notices.value = notices.value.filter(item => item.id !== n.id);
}

function dismiss() {
  visible.value = false;
}

onMounted(() => {
  loadNotices();
  pollTimer = setInterval(loadNotices, 5_000);
});

onUnmounted(() => {
  clearInterval(pollTimer);
});
</script>

<style scoped>
.notify-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 16px;
  background: var(--bg-muted);
  border-bottom: 1px solid var(--border-default);
  font-size: 0.82rem;
  color: var(--fg-muted);
  overflow: hidden;
}
.notify-bar.highlight {
  background: var(--warning-bg, #fef3c7);
  color: var(--warning-fg, #92400e);
  border-bottom-color: rgba(245,158,11,0.3);
}
.notify-scroll {
  flex: 1;
  overflow: hidden;
  white-space: nowrap;
}
.notify-item {
  display: inline-block;
  margin-right: 32px;
  cursor: pointer;
}
.notify-item:hover {
  text-decoration: underline;
}
.notify-highlight {
  font-weight: 600;
}
.notify-close {
  flex-shrink: 0;
  border: none;
  background: transparent;
  color: inherit;
  cursor: pointer;
  font-size: 0.9rem;
  padding: 2px 6px;
}
</style>
