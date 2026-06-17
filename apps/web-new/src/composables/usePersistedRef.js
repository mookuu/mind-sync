/** 持久化 ref：值变化时自动写入 localStorage，初始化时从 localStorage 读取 */
import { ref, watch } from "vue";

export function usePersistedRef(key, defaultValue) {
  const stored = localStorage.getItem(key);
  const data = ref(stored !== null ? JSON.parse(stored) : defaultValue);

  watch(data, (val) => {
    localStorage.setItem(key, JSON.stringify(val));
  }, { deep: true });

  return data;
}
