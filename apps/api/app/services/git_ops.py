"""Git helpers for GitHub sources and vault sync."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger("mind-sync.git")


def git_env(token: str | None = None) -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("GIT_TERMINAL_PROMPT", "0")
    if token and token.strip():
        env["GIT_CONFIG_COUNT"] = "1"
        env["GIT_CONFIG_KEY_0"] = "http.extraHeader"
        env["GIT_CONFIG_VALUE_0"] = f"Authorization: Bearer {token.strip()}"
    return env


def run_git(cwd: Path, *args: str, env: dict[str, str] | None = None, timeout: int = 300) -> tuple[int, str, str]:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        env=env or os.environ.copy(),
        timeout=timeout,
    )
    return proc.returncode, (proc.stdout or "").strip(), (proc.stderr or "").strip()


def ensure_clone(url: str, dest: Path, *, branch: str = "main", shallow: bool = True, token: str | None = None) -> dict[str, Any]:
    dest = dest.resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)
    env = git_env(token)
    if (dest / ".git").is_dir():
        return pull_repo(dest, branch=branch, token=token)
    if dest.exists() and not (dest / ".git").is_dir():
        shutil.rmtree(dest)
    cmd = ["clone"]
    if shallow:
        cmd.extend(["--depth", "1"])
    if branch:
        cmd.extend(["--branch", branch])
    cmd.extend([url, str(dest)])
    code, out, err = run_git(dest.parent, *cmd, env=env)
    if code != 0:
        return {"ok": False, "action": "clone", "path": str(dest), "error": err or out}
    return {"ok": True, "action": "clone", "path": str(dest), "branch": branch}


def pull_repo(repo_dir: Path, *, branch: str = "main", token: str | None = None) -> dict[str, Any]:
    repo_dir = repo_dir.resolve()
    if not (repo_dir / ".git").is_dir():
        return {"ok": False, "action": "pull", "path": str(repo_dir), "error": "not a git repository"}
    env = git_env(token)
    code, _, err = run_git(repo_dir, "fetch", "origin", branch, env=env)
    if code != 0:
        return {"ok": False, "action": "pull", "path": str(repo_dir), "error": err}
    run_git(repo_dir, "checkout", branch, env=env)
    code, out, err = run_git(repo_dir, "pull", "--ff-only", "origin", branch, env=env)
    if code != 0:
        code, out, err = run_git(repo_dir, "pull", "--ff-only", env=env)
    if code != 0:
        return {"ok": False, "action": "pull", "path": str(repo_dir), "error": err or out}
    return {"ok": True, "action": "pull", "path": str(repo_dir), "branch": branch}


def commit_and_push(
    repo_dir: Path,
    message: str,
    *,
    branch: str = "main",
    token: str | None = None,
    paths: list[str] | None = None,
) -> dict[str, Any]:
    repo_dir = repo_dir.resolve()
    if not (repo_dir / ".git").is_dir():
        return {"ok": False, "action": "push", "error": "not a git repository"}
    env = git_env(token)
    if paths:
        for p in paths:
            run_git(repo_dir, "add", p, env=env)
    else:
        run_git(repo_dir, "add", "-A", env=env)
    code, out, err = run_git(repo_dir, "status", "--porcelain", env=env)
    if code != 0:
        return {"ok": False, "action": "push", "error": err}
    if not out.strip():
        return {"ok": True, "action": "push", "committed": False, "message": "nothing to commit"}
    code, _, err = run_git(repo_dir, "commit", "-m", message, env=env)
    if code != 0:
        return {"ok": False, "action": "push", "error": err}
    code, _, err = run_git(repo_dir, "push", "origin", branch, env=env)
    if code != 0:
        return {"ok": False, "action": "push", "error": err}
    return {"ok": True, "action": "push", "committed": True, "branch": branch}


def copy_tree(src: Path, dest: Path) -> None:
    if not src.exists():
        return
    dest.mkdir(parents=True, exist_ok=True)
    for item in src.rglob("*"):
        if item.is_dir():
            continue
        rel = item.relative_to(src)
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, target)
