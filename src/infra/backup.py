"""
backup.py — 数据库备份与恢复模块 (v1.50 R4)
==========================================

提供 chunks.db、users.json、chat_sessions.db 的定期自动备份
与按需快照功能。备份存储到 BACKUP_DIR（src/config.py）。

功能：
  1. 定期备份：每 N 分钟自动备份一次（默认 60 分钟）
  2. 按需快照：手动触发备份
  3. 恢复：从最新备份恢复数据
  4. WAL checkpoint：备份前执行 checkpoint 确保数据完整性

使用示例::

    from src.infra.backup import backup_all, restore_latest

    # 自动备份
    backup_all()

    # 从备份恢复
    restore_latest("chunks.db")
"""

import os
import json
import shutil
import sqlite3
import logging
import time
import threading
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger("infra.backup")

# 从 config 获取备份目录
from src.config import BACKUP_DIR, DATA_DIR

BACKUP_DIR = Path(BACKUP_DIR) if not isinstance(BACKUP_DIR, Path) else BACKUP_DIR


def _ensure_backup_dir() -> Path:
    """确保备份目录存在"""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    return BACKUP_DIR


def _timestamp_str() -> str:
    """生成时间戳字符串"""
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _wal_checkpoint(db_path: str) -> None:
    """对 SQLite 数据库执行 WAL checkpoint，将 WAL 数据写入主文件"""
    if not Path(db_path).exists():
        return
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.close()
        logger.debug("[Backup] WAL checkpoint 完成: %s", Path(db_path).name)
    except Exception as e:
        logger.warning("[Backup] WAL checkpoint 失败: %s - %s", Path(db_path).name, e)


def backup_sqlite_db(db_path: str, backup_name: str = None) -> Optional[str]:
    """备份单个 SQLite 数据库文件

    使用 SQLite 的 .backup API 进行在线备份（不阻塞读写）。

    Args:
        db_path:     数据库路径
        backup_name: 备份文件名（不含路径），None 则自动生成

    Returns:
        备份文件路径，失败返回 None
    """
    src_path = Path(db_path)
    if not src_path.exists():
        logger.warning("[Backup] 数据库不存在，跳过: %s", src_path)
        return None

    backup_dir = _ensure_backup_dir()
    ts = _timestamp_str()
    name = backup_name or f"{src_path.stem}_{ts}.bak"
    dest_path = backup_dir / name

    # 先执行 WAL checkpoint 确保数据完整性
    _wal_checkpoint(db_path)

    try:
        src_conn = sqlite3.connect(str(src_path))
        dst_conn = sqlite3.connect(str(dest_path))
        src_conn.backup(dst_conn)
        src_conn.close()
        dst_conn.close()
        logger.info("[Backup] %s → %s (%s)", src_path.name, name,
                    _format_size(dest_path.stat().st_size))
        return str(dest_path)
    except Exception as e:
        logger.error("[Backup] 备份失败 %s: %s", src_path.name, e)
        # 清理失败的部分文件
        if dest_path.exists():
            dest_path.unlink()
        return None


def backup_json_file(json_path: str, backup_name: str = None) -> Optional[str]:
    """备份 JSON 配置文件（如 users.json）

    Args:
        json_path:   JSON 文件路径
        backup_name: 备份文件名，None 则自动生成

    Returns:
        备份文件路径，失败返回 None
    """
    src_path = Path(json_path)
    if not src_path.exists():
        logger.warning("[Backup] JSON 文件不存在，跳过: %s", src_path)
        return None

    backup_dir = _ensure_backup_dir()
    ts = _timestamp_str()
    name = backup_name or f"{src_path.stem}_{ts}.json.bak"
    dest_path = backup_dir / name

    try:
        shutil.copy2(str(src_path), str(dest_path))
        logger.info("[Backup] %s → %s", src_path.name, name)
        return str(dest_path)
    except Exception as e:
        logger.error("[Backup] 备份失败 %s: %s", src_path.name, e)
        return None


def backup_all() -> Dict[str, Optional[str]]:
    """备份所有关键数据文件

    Returns:
        { "chunks.db": "/path/to/backup", "users.json": "/path/to/backup", ... }
    """
    logger.info("[Backup] 开始全量备份...")
    results = {}

    data_dir = Path(DATA_DIR)
    # chunks.db
    chunks_db = data_dir / "chunks.db"
    if chunks_db.exists():
        results["chunks.db"] = backup_sqlite_db(str(chunks_db))
    else:
        results["chunks.db"] = None

    # chat_sessions.db
    chat_db = data_dir / "chat_sessions.db"
    if chat_db.exists():
        results["chat_sessions.db"] = backup_sqlite_db(str(chat_db))
    else:
        results["chat_sessions.db"] = None

    # login_rate.db
    login_db = data_dir / "login_rate.db"
    if login_db.exists():
        results["login_rate.db"] = backup_sqlite_db(str(login_db))
    else:
        results["login_rate.db"] = None

    # audit.db
    audit_db = data_dir / "audit.db"
    if audit_db.exists():
        results["audit.db"] = backup_sqlite_db(str(audit_db))
    else:
        results["audit.db"] = None

    # users.json
    users_json = data_dir / "users.json"
    if users_json.exists():
        results["users.json"] = backup_json_file(str(users_json))
    else:
        results["users.json"] = None

    # user_preferences.json
    prefs_json = data_dir / "user_preferences.json"
    if prefs_json.exists():
        results["user_preferences.json"] = backup_json_file(str(prefs_json))
    else:
        results["user_preferences.json"] = None

    # 清理旧备份（保留最近 7 天）
    _cleanup_old_backups(days=7)

    success_count = sum(1 for v in results.values() if v is not None)
    logger.info("[Backup] 全量备份完成: %d/%d 成功", success_count, len(results))
    return results


def restore_latest(filename: str, backup_dir: str = None) -> bool:
    """从最新备份恢复指定文件

    Args:
        filename:   要恢复的文件名（如 "chunks.db"、"users.json"）
        backup_dir: 备份目录（可选）

    Returns:
        是否恢复成功
    """
    backup_dir = Path(backup_dir or BACKUP_DIR)
    if not backup_dir.exists():
        logger.error("[Backup] 备份目录不存在: %s", backup_dir)
        return False

    # 查找匹配的备份文件（按修改时间排序）
    matches = []
    for f in backup_dir.iterdir():
        if not f.is_file():
            continue
        fname = f.name
        # 匹配: chunks_20260711_001200.bak, users_20260711_001200.json.bak
        if filename in fname or fname.startswith(Path(filename).stem + "_"):
            matches.append(f)

    if not matches:
        logger.warning("[Backup] 未找到 %s 的备份文件", filename)
        return False

    # 最新备份
    matches.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    latest = matches[0]

    target = Path(DATA_DIR) / filename
    try:
        shutil.copy2(str(latest), str(target))
        logger.info("[Backup] 已从 %s 恢复 %s", latest.name, filename)
        return True
    except Exception as e:
        logger.error("[Backup] 恢复失败: %s", e)
        return False


def list_backups(filename: str = None) -> List[Dict]:
    """列出备份文件

    Args:
        filename: 可选的文件名过滤

    Returns:
        [{name, size, age_seconds, path}, ...]
    """
    backup_dir = _ensure_backup_dir()
    results = []
    now = time.time()
    for f in sorted(backup_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if not f.is_file():
            continue
        if filename and filename not in f.name:
            continue
        results.append({
            "name": f.name,
            "size": f.stat().st_size,
            "size_str": _format_size(f.stat().st_size),
            "age_seconds": round(now - f.stat().st_mtime, 1),
            "timestamp_iso": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
            "path": str(f),
        })
    return results


def _cleanup_old_backups(days: int = 7) -> int:
    """清理超过指定天数的旧备份

    Returns:
        删除的文件数
    """
    backup_dir = _ensure_backup_dir()
    cutoff = time.time() - days * 86400
    deleted = 0
    for f in backup_dir.iterdir():
        if f.is_file() and f.stat().st_mtime < cutoff:
            try:
                f.unlink()
                deleted += 1
            except Exception:
                pass
    if deleted > 0:
        logger.info("[Backup] 已清理 %d 个过期备份（超过 %d 天）", deleted, days)
    return deleted


def _format_size(size_bytes: int) -> str:
    """格式化文件大小"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if abs(size_bytes) < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


# ═══════════════════════════════════════════════════════════════
# 定期自动备份
# ═══════════════════════════════════════════════════════════════

_scheduler_started = False


def start_auto_backup(interval_minutes: int = 60) -> None:
    """启动定期自动备份后台任务

    Args:
        interval_minutes: 备份间隔（分钟），默认 60 分钟
    """
    global _scheduler_started
    if _scheduler_started:
        logger.debug("[Backup] 自动备份已在运行，跳过")
        return

    def _run():
        # 延迟 30 秒启动，确保系统初始化完成
        time.sleep(30)
        while True:
            try:
                backup_all()
            except Exception as e:
                logger.error("[Backup] 自动备份异常: %s", e)
            time.sleep(interval_minutes * 60)

    threading.Thread(target=_run, daemon=True, name="auto-backup").start()
    _scheduler_started = True
    logger.info("[Backup] 自动备份已启动，间隔 %d 分钟", interval_minutes)


# 模块加载时启动自动备份（可被环境变量 FUXI_AUTO_BACKUP=false 禁用）
if os.environ.get("FUXI_AUTO_BACKUP", "true").lower() == "true":
    start_auto_backup()
