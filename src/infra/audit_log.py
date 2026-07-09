"""
audit_log.py — 访问控制审计日志

记录 API 访问的关键操作（登录、登出、权限变更、敏感数据访问）。
写入结构化 JSONL 文件，支持时间窗口查询和统计。
"""
import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("infra.audit_log")

# 审计日志存储目录
_AUDIT_DIR = os.environ.get(
    "FUXI_AUDIT_DIR",
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "audit_logs"),
)

# 最大单文件行数
MAX_LINES_PER_FILE = 10_000

# 写锁（防止多线程并发写入）
_write_lock = threading.Lock()


@dataclass
class AuditEntry:
    """审计日志条目"""
    timestamp: str = ""
    user: str = ""
    action: str = ""          # login | logout | access | permission_change | error
    resource: str = ""        # 访问的 API 路径或资源名
    ip_address: str = ""
    success: bool = True
    details: Dict[str, Any] = field(default_factory=dict)


def _get_log_path() -> Path:
    """获取当前日志文件路径（自动按日期轮转）"""
    date_str = time.strftime("%Y-%m-%d")
    return Path(_AUDIT_DIR) / f"audit_{date_str}.jsonl"


def _rotate_if_needed(path: Path) -> None:
    """如果当前文件行数超过上限，重命名为带编号的归档文件"""
    if not path.exists():
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            line_count = sum(1 for _ in f)
        if line_count >= MAX_LINES_PER_FILE:
            rotated = path.with_suffix(f".{int(time.time())}.jsonl")
            path.rename(rotated)
            logger.info("审计日志轮转: %s → %s (%d 行)", path.name, rotated.name, line_count)
    except Exception:  # TODO: Narrow exception type
        pass


def write_audit(
    user: str = "anonymous",
    action: str = "access",
    resource: str = "",
    ip_address: str = "",
    success: bool = True,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """写入一条审计日志

    Args:
        user:       操作用户名
        action:     操作类型（login, logout, access, permission_change, error）
        resource:   访问资源路径
        ip_address: 客户端 IP
        success:    操作是否成功
        details:    其他明细信息
    """
    entry = AuditEntry(
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
        user=user,
        action=action,
        resource=resource,
        ip_address=ip_address,
        success=success,
        details=details or {},
    )

    with _write_lock:
        path = _get_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        _rotate_if_needed(path)
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "timestamp": entry.timestamp,
                    "user": entry.user,
                    "action": entry.action,
                    "resource": entry.resource,
                    "ip": entry.ip_address,
                    "success": entry.success,
                    "details": entry.details,
                }, ensure_ascii=False) + "\n")
        except Exception as exc:  # TODO: Narrow exception type
            logger.error("审计日志写入失败: %s", exc)


def query_audit(
    user: Optional[str] = None,
    action: Optional[str] = None,
    days: int = 1,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """查询最近的审计日志

    Args:
        user:   筛选用户（None 表示全部）
        action: 筛选操作类型（None 表示全部）
        days:   查询最近 N 天的日志
        limit:  返回最大条数

    Returns:
        [{timestamp, user, action, resource, ip, success, details}, ...]
    """
    results: List[Dict[str, Any]] = []
    cutoff = time.time() - days * 86400

    try:
        audit_dir = Path(_AUDIT_DIR)
        if not audit_dir.exists():
            return results

        # 按文件名倒序（最新日期优先）
        files = sorted(audit_dir.glob("audit_*.jsonl"), reverse=True)
        for fpath in files:
            if len(results) >= limit:
                break
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        entry = json.loads(line)
                        ts_str = entry.get("timestamp", "")
                        try:
                            ts = time.mktime(time.strptime(ts_str[:19], "%Y-%m-%dT%H:%M:%S"))
                        except ValueError:
                            ts = 0
                        if ts < cutoff:
                            continue
                        if user and entry.get("user") != user:
                            continue
                        if action and entry.get("action") != action:
                            continue
                        results.append(entry)
                        if len(results) >= limit:
                            break
            except Exception:  # TODO: Narrow exception type
                continue
    except Exception as exc:  # TODO: Narrow exception type
        logger.warning("审计日志查询失败: %s", exc)

    return results


def get_audit_stats(days: int = 7) -> Dict[str, Any]:
    """获取审计日志统计

    Returns:
        {
            "total_entries": int,
            "by_action": {action: count},
            "unique_users": int,
            "failed_attempts": int,
        }
    """
    stats = {
        "total_entries": 0,
        "by_action": {},
        "unique_users": set(),
        "failed_attempts": 0,
    }
    cutoff = time.time() - days * 86400

    try:
        audit_dir = Path(_AUDIT_DIR)
        if not audit_dir.exists():
            stats["unique_users"] = 0
            return stats

        for fpath in sorted(audit_dir.glob("audit_*.jsonl"), reverse=True):
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        entry = json.loads(line)
                        ts_str = entry.get("timestamp", "")
                        try:
                            ts = time.mktime(time.strptime(ts_str[:19], "%Y-%m-%dT%H:%M:%S"))
                        except ValueError:
                            continue
                        if ts < cutoff:
                            continue
                        stats["total_entries"] += 1
                        action = entry.get("action", "unknown")
                        stats["by_action"][action] = stats["by_action"].get(action, 0) + 1
                        stats["unique_users"].add(entry.get("user", ""))
                        if not entry.get("success", True):
                            stats["failed_attempts"] += 1
            except Exception:  # TODO: Narrow exception type
                continue
    except Exception as exc:  # TODO: Narrow exception type
        logger.warning("审计统计失败: %s", exc)

    stats["unique_users"] = len(stats["unique_users"])
    return dict(stats)


# 审计日志 API 路由（在 system_routes.py 中注册）
def register_audit_routes():
    """注册审计日志路由到全局 health checker"""
    try:
        from src.infra.health_check import get_health_checker
        checker = get_health_checker()
        checker.register_infra_check("audit_log", _check_audit_log_health)
        logger.info("审计日志路由已注册")
    except Exception as e:  # TODO: Narrow exception type
        logger.debug("审计日志路由注册失败: %s", e)


async def _check_audit_log_health() -> Dict[str, Any]:
    """审计日志健康检查"""
    stats = get_audit_stats(days=1)
    return {
        "healthy": True,
        "total_entries_24h": stats.get("total_entries", 0),
        "failed_attempts": stats.get("failed_attempts", 0),
        "timestamp": time.time(),
    }


__all__ = [
    "write_audit",
    "query_audit",
    "get_audit_stats",
    "register_audit_routes",
]
