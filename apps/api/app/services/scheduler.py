import logging
import threading
import time
from typing import Any, Callable

logger = logging.getLogger("mind-sync.scheduler")


class AutoSyncScheduler:
    def __init__(
        self,
        load_settings: Callable[[], dict[str, str]],
        is_sync_running: Callable[[], bool],
        run_sync_job: Callable[[], dict[str, Any]],
    ) -> None:
        self._load_settings = load_settings
        self._is_sync_running = is_sync_running
        self._run_sync_job = run_sync_job
        self._lock = threading.Lock()
        self._started = False
        self._last_run = 0.0
        self._last_info: dict[str, Any] = {
            "status": "idle",
            "started_at": None,
            "finished_at": None,
            "indexed": 0,
            "skipped": 0,
            "deleted": 0,
            "error": None,
        }

    @staticmethod
    def parse_bool(raw: str) -> bool:
        return str(raw).strip().lower() in {"1", "true", "yes", "on"}

    def start(self) -> None:
        with self._lock:
            if self._started:
                return
            self._started = True
            self._last_run = time.time()
        threading.Thread(target=self._loop, daemon=True).start()

    def reset_last_run_now(self) -> None:
        with self._lock:
            self._last_run = time.time()

    def build_meta(self, settings_map: dict[str, str]) -> dict[str, Any]:
        enabled = self.parse_bool(settings_map.get("auto_sync_enabled", "false"))
        interval = max(1, min(int(settings_map.get("auto_sync_interval_minutes", "60")), 24 * 60))
        with self._lock:
            last_run = self._last_run
            last_info = dict(self._last_info)
        next_at = (last_run + interval * 60) if enabled and last_run > 0 else None
        return {
            "auto_sync_enabled": enabled,
            "auto_sync_interval_minutes": interval,
            "next_auto_sync_at": next_at,
            "last_auto_sync": last_info,
        }

    def _loop(self) -> None:
        while True:
            time.sleep(20)
            try:
                st = self._load_settings()
                enabled = self.parse_bool(st.get("auto_sync_enabled", "false"))
                interval = int(st.get("auto_sync_interval_minutes", "60"))
                interval = max(1, min(interval, 24 * 60))
                if not enabled:
                    continue

                now = time.time()
                if self._is_sync_running():
                    continue

                with self._lock:
                    if self._last_run <= 0:
                        self._last_run = now
                        continue
                    if now - self._last_run < interval * 60:
                        continue
                    self._last_run = now
                    self._last_info["status"] = "running"
                    self._last_info["started_at"] = now
                    self._last_info["finished_at"] = None
                    self._last_info["error"] = None

                summary = self._run_sync_job()
                with self._lock:
                    self._last_info["status"] = "success" if not summary.get("error") else "failed"
                    self._last_info["finished_at"] = time.time()
                    self._last_info["indexed"] = summary.get("indexed", 0)
                    self._last_info["skipped"] = summary.get("skipped", 0)
                    self._last_info["deleted"] = summary.get("deleted", 0)
                    self._last_info["error"] = summary.get("error")
            except Exception as exc:
                logger.exception("auto sync scheduler loop failed: %s", exc)
                with self._lock:
                    self._last_info["status"] = "failed"
                    self._last_info["finished_at"] = time.time()
                    self._last_info["error"] = str(exc)
                continue
