import { reactive, toRefs } from "vue";
import api from "../api/index.js";

let loadPromise = null;

const state = reactive({
  syncPreset: "all",
  syncSourceIds: [],
  syncPresets: [],
  availableSources: [],
  loading: false,
  loaded: false,
});

export function useSyncSettings() {
  async function load() {
    if (state.loaded) return;
    if (loadPromise) return loadPromise;
    state.loading = true;
    loadPromise = (async () => {
      try {
        const st = await api("/api/settings");
        state.syncPreset = st.sync_preset || "all";
        state.syncSourceIds = (st.sync_source_ids || []).map(String);
        state.syncPresets = st.sync_presets || [];
        const srcData = await api("/api/sources");
        state.availableSources = srcData.sources || [];
        state.loaded = true;
      } catch {
        // ignore
      } finally {
        state.loading = false;
        loadPromise = null;
      }
    })();
    return loadPromise;
  }

  async function reload() {
    state.loaded = false;
    loadPromise = null;
    await load();
  }

  async function setPreset(preset) {
    state.syncPreset = preset;
    state.syncSourceIds = [];
    await api("/api/settings", {
      method: "POST",
      body: JSON.stringify({ sync_preset: preset, sync_source_ids: [] }),
    });
  }

  async function setCustomSources(sourceIds) {
    state.syncPreset = "custom";
    state.syncSourceIds = sourceIds;
    await api("/api/settings", {
      method: "POST",
      body: JSON.stringify({ sync_preset: "custom", sync_source_ids: sourceIds }),
    });
  }

  function sourceSyncKey(s) {
    return s.sync_key || `${s.id}:${s.type || "local"}`;
  }

  function sourceLabel(s) {
    return s.label || `${s.id}${s.type ? ` (${s.type})` : ""}`;
  }

  return {
    ...toRefs(state),
    load,
    reload,
    setPreset,
    setCustomSources,
    sourceSyncKey,
    sourceLabel,
  };
}
