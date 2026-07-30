"""SMB/Windows 网络共享源适配器。"""
from __future__ import annotations
from pathlib import Path
from .base import SourceAdapter, SourceSpec


def resolve_smb_mount(source: SourceSpec) -> Path:
    """将 SMB 路径转为本地挂载路径。

    输入 path 格式：//server/share/path 或 \\server\share\path
    优先检查已挂载路径 /mnt/server/share/，否则直接使用 UNC 路径（需系统支持）。
    """
    raw = source.path or ""
    raw = raw.replace("\\", "/")
    if raw.startswith("//"):
        # //server/share/path → /mnt/server/share/path
        parts = raw.strip("/").split("/", 2)
        if len(parts) >= 2:
            server, share = parts[0], parts[1]
            subpath = parts[2] if len(parts) > 2 else ""
            mounted = Path(f"/mnt/{server}/{share}/{subpath}")
            if mounted.is_dir():
                return mounted
        return Path(raw)
    return Path(raw)


class SmbRepoAdapter(SourceAdapter):
    """SMB 网络共享适配器。

    支持已挂载的 SMB 共享（/mnt/server/share/）和 UNC 路径（//server/share/path）。
    建议通过 /etc/fstab 或 systemd mount 单元提前挂载以保证稳定访问。
    """

    def resolve_root(self, source: SourceSpec) -> Path:
        return resolve_smb_mount(source)
