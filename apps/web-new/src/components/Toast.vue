<template>
  <Teleport to="body">
    <div class="toast-container">
      <TransitionGroup name="toast">
        <div
          v-for="t in toasts"
          :key="t.id"
          class="toast"
          :class="'toast-' + t.type"
          @click="dismiss(t.id)"
        >
          <span class="toast-msg">{{ t.message }}</span>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from "vue";

const toasts = ref([]);
let nextId = 0;

function addToast(message, type = "info", duration = 4000) {
  const id = ++nextId;
  toasts.value.push({ id, message, type });
  if (duration > 0) {
    setTimeout(() => dismiss(id), duration);
  }
}

function dismiss(id) {
  toasts.value = toasts.value.filter(t => t.id !== id);
}

function onToastEvent(e) {
  addToast(e.detail.message, e.detail.type, e.detail.duration);
}

onMounted(() => window.addEventListener("mind-toast", onToastEvent));
onUnmounted(() => window.removeEventListener("mind-toast", onToastEvent));
</script>

<style scoped>
.toast-container {
  position: fixed;
  top: 16px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 9999;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  pointer-events: none;
}
.toast {
  pointer-events: auto;
  padding: 10px 20px;
  border-radius: var(--radius);
  font-size: 0.88rem;
  cursor: pointer;
  box-shadow: var(--shadow-md);
  max-width: 480px;
  text-align: center;
}
.toast-success {
  background: var(--success-bg, #dcfce7);
  color: var(--success-fg, #166534);
  border: 1px solid rgba(22,163,74,0.3);
}
.toast-error {
  background: var(--danger-bg, #fee2e2);
  color: var(--danger-fg, #991b1b);
  border: 1px solid rgba(220,38,38,0.3);
}
.toast-warning {
  background: var(--warning-bg, #fef3c7);
  color: var(--warning-fg, #92400e);
  border: 1px solid rgba(245,158,11,0.3);
}
.toast-info {
  background: var(--accent-bg, #ebf4ff);
  color: var(--accent-fg, #2b6cb0);
  border: 1px solid rgba(59,130,246,0.3);
}
.toast-msg { word-break: break-word; }

/* Transition */
.toast-enter-active { transition: all 0.25s ease-out; }
.toast-leave-active { transition: all 0.2s ease-in; }
.toast-enter-from { opacity: 0; transform: translateY(-12px); }
.toast-leave-to { opacity: 0; transform: translateY(-8px); }
</style>
