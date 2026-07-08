<template>
  <div class="skeleton" :style="{ height: height || '16px', width: width || '100%', borderRadius: radius || 'var(--radius)' }"></div>
</template>

<script setup>
defineProps({
  width: { type: String, default: "" },
  height: { type: String, default: "16px" },
  radius: { type: String, default: "" },
});
</script>

<style scoped>
.skeleton {
  background: linear-gradient(90deg, var(--bg-muted) 25%, var(--bg-hover) 50%, var(--bg-muted) 75%);
  background-size: 200% 100%;
  animation: skeleton-shimmer 1.5s ease-in-out infinite;
}
@keyframes skeleton-shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
</style>
