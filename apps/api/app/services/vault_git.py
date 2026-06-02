"""Sync wiki + purpose to a dedicated Git vault repository."""

from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import settings
from ..db import DATA_DIR, WIKI_DIR
from .git_ops import commit_and_push, copy_tree, ensure_clone, pull_repo

logger = logging.getLogger("mind-sync.vault")


def vault_worktree() -> Path:
    return DATA_DIR / "vault-git"


def purpose_path() -> Path:
    return DATA_DIR / "purpose.md"


def _vault_configured() -> bool:
    return bool((settings.vault_git_url or "").strip())


def pull_vault() -> dict[str, Any]:
    url = (settings.vault_git_url or "").strip()
    if not url:
        return {"ok": True, "skipped": True, "reason": "VAULT_GIT_URL not set"}
    branch = (settings.vault_git_branch or "main").strip() or "main"
    work = vault_worktree()
    token = (settings.github_token or "").strip() or None
    if (work / ".git").is_dir():
        result = pull_repo(work, branch=branch, token=token)
    else:
        result = ensure_clone(url, work, branch=branch, shallow=False, token=token)
    if not result.get("ok"):
        return result
    vault_wiki = work / "wiki"
    vault_purpose = work / "purpose.md"
    if vault_wiki.is_dir():
        if WIKI_DIR.exists():
            logger.warning(
                "vault pull replaces local wiki at %s — ensure backup if needed",
                WIKI_DIR,
            )
            shutil.rmtree(WIKI_DIR)
        copy_tree(vault_wiki, WIKI_DIR)
    if vault_purpose.is_file():
        shutil.copy2(vault_purpose, purpose_path())
    manifest = work / "sources-manifest.json"
    if manifest.is_file():
        shutil.copy2(manifest, DATA_DIR / "sources-manifest.json")
    return {"ok": True, "action": "vault_pull", "path": str(work)}


def push_vault(message: str | None = None) -> dict[str, Any]:
    url = (settings.vault_git_url or "").strip()
    if not url:
        return {"ok": True, "skipped": True, "reason": "VAULT_GIT_URL not set"}
    branch = (settings.vault_git_branch or "main").strip() or "main"
    work = vault_worktree()
    token = (settings.github_token or "").strip() or None
    if not (work / ".git").is_dir():
        init = ensure_clone(url, work, branch=branch, shallow=False, token=token)
        if not init.get("ok"):
            return init
    vault_wiki = work / "wiki"
    if WIKI_DIR.exists():
        if vault_wiki.exists():
            shutil.rmtree(vault_wiki)
        copy_tree(WIKI_DIR, vault_wiki)
    if purpose_path().is_file():
        shutil.copy2(purpose_path(), work / "purpose.md")
    manifest_path = DATA_DIR / "sources-manifest.json"
    if manifest_path.is_file():
        shutil.copy2(manifest_path, work / "sources-manifest.json")
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    msg = message or f"vault sync {ts}"
    return commit_and_push(work, msg, branch=branch, token=token)


def vault_status() -> dict[str, Any]:
    work = vault_worktree()
    return {
        "configured": _vault_configured(),
        "url": (settings.vault_git_url or "").strip() or None,
        "branch": settings.vault_git_branch,
        "worktree": str(work),
        "has_clone": (work / ".git").is_dir(),
        "wiki_dir": str(WIKI_DIR),
    }


def write_sources_manifest(source_stats: list[dict[str, Any]]) -> None:
    path = DATA_DIR / "sources-manifest.json"
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "sources": source_stats,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
