from pathlib import Path

from .base import SourceSpec
from .github_repo import GitHubRepoAdapter
from .local_repo import LocalRepoAdapter
from .smb_repo import SmbRepoAdapter
from .web_page import WebPageAdapter


def resolve_source_root(spec: SourceSpec) -> Path:
    t = (spec.source_type or "local").lower()
    if t == "local":
        return LocalRepoAdapter().resolve_root(spec)
    if t == "github":
        return GitHubRepoAdapter().resolve_root(spec)
    if t == "web":
        return WebPageAdapter().resolve_root(spec)
    if t == "smb":
        return SmbRepoAdapter().resolve_root(spec)
    raise ValueError(f"未知源类型: {t}")
