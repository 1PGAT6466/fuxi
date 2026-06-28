#!/usr/bin/env python3
"""自动备份脚本 — cron 每天凌晨2点执行"""
import sqlite3, shutil, os
from pathlib import Path
from datetime import datetime

BASE = Path("/home/feng-shaoxuan/kb-server/data")
BACKUP = BASE / "auto_backups"
BACKUP.mkdir(parents=True, exist_ok=True)

ts = datetime.now().strftime("%Y%m%d_%H%M")
keep_days = 7  # 保留最近7天

for db_name in ["worldtree.db", "wiki.db", "chunks.db"]:
    src = BASE / db_name
    if src.exists():
        dest = BACKUP / f"{db_name}.{ts}"
        shutil.copy2(src, dest)
        print(f"[备份] {db_name} → {dest.name}")

# 清理旧备份
now = datetime.now().timestamp()
for f in BACKUP.glob("*.db.*"):
    age = now - f.stat().st_mtime
    if age > keep_days * 86400:
        f.unlink()
        print(f"[清理] 过期备份: {f.name}")

print(f"完成 — 保留 {keep_days} 天以内的备份")
