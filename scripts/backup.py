"""mind-sync 数据备份脚本

用法:
    python scripts/backup.py                    # 备份到默认目录 ./backups/
    python scripts/backup.py --output /path/to/backup

备份内容:
    - mind_sync.db          (SQLite 数据库)
    - sources.yaml          (源配置)
    - data/wiki/            (Wiki 页面)
    - data/purpose.md       (规则约束)
    - data/jieba_dict.txt   (自定义词典)
"""

import sys
import os
import shutil
import argparse
from datetime import datetime
from pathlib import Path


def backup(output_dir: str | None = None) -> str:
    # Determine paths
    script_dir = Path(__file__).resolve().parent.parent  # project root
    data_dir = script_dir / "data"
    sources_file = script_dir / "sources.yaml"

    if output_dir:
        backup_root = Path(output_dir)
    else:
        backup_root = script_dir / "backups"

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = backup_root / f"mind-sync-backup-{timestamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)

    items = []

    # 1. SQLite DB
    db_path = data_dir / "mind_sync.db"
    if db_path.exists():
        shutil.copy2(str(db_path), str(backup_dir / "mind_sync.db"))
        size = db_path.stat().st_size
        items.append(("mind_sync.db", size))
        print(f"  ✅ {db_path.name} ({_fmt_size(size)})")

    # 2. sources.yaml
    if sources_file.exists():
        shutil.copy2(str(sources_file), str(backup_dir / "sources.yaml"))
        size = sources_file.stat().st_size
        items.append(("sources.yaml", size))
        print(f"  ✅ sources.yaml ({_fmt_size(size)})")

    # 3. Wiki pages
    wiki_dir = data_dir / "wiki"
    if wiki_dir.exists():
        wiki_backup = backup_dir / "wiki"
        shutil.copytree(str(wiki_dir), str(wiki_backup))
        total = sum(1 for _ in wiki_backup.rglob("*") if _.is_file())
        items.append(("wiki/", total))
        print(f"  ✅ wiki/ ({total} files)")

    # 4. purpose.md
    purpose = data_dir / "purpose.md"
    if purpose.exists():
        shutil.copy2(str(purpose), str(backup_dir / "purpose.md"))
        print(f"  ✅ purpose.md")

    # 5. jieba dict
    jieba_dict = script_dir / "apps" / "api" / "app" / "data" / "jieba_dict.txt"
    if jieba_dict.exists():
        shutil.copy2(str(jieba_dict), str(backup_dir / "jieba_dict.txt"))
        print(f"  ✅ jieba_dict.txt")

    # Summary
    total_bytes = sum(s for _, s in items if isinstance(s, int))
    print(f"\n📦 备份完成：{backup_dir}")
    print(f"   共 {len(items)} 项，{_fmt_size(total_bytes)}")

    return str(backup_dir)


def _fmt_size(bytes: int) -> str:
    if bytes < 1024:
        return f"{bytes} B"
    if bytes < 1024 * 1024:
        return f"{bytes / 1024:.1f} KB"
    return f"{bytes / (1024 * 1024):.1f} MB"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="mind-sync 数据备份")
    parser.add_argument("--output", "-o", help="备份输出目录（默认 ./backups/）")
    args = parser.parse_args()
    backup(args.output)
