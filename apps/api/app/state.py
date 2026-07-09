"""Shared app state: singletons that multiple routers depend on."""
from .services.scheduler import AutoSyncScheduler
from .services.sync_engine import is_sync_running, restore_last_sync_summary, run_sync_job
from .db import load_settings_map

SCHEDULER = AutoSyncScheduler(
    load_settings=load_settings_map,
    is_sync_running=is_sync_running,
    run_sync_job=lambda: run_sync_job("auto"),
)
