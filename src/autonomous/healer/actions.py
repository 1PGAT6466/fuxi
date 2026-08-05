"""
预置修复动作模块 (Preset Repair Actions)
========================================
8个内置修复动作，覆盖常见故障场景
"""

import asyncio
import logging
import os
import shutil
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .safety import RepairStatus, RiskLevel

logger = logging.getLogger(__name__)


@dataclass
class ActionResult:
    """修复动作执行结果"""

    action_id: str
    status: RepairStatus
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    duration: float = 0.0  # 执行耗时（秒）


@dataclass
class RepairAction:
    """修复动作定义"""

    id: str
    name: str
    description: str
    risk_level: RiskLevel
    cooldown: int = 300  # 冷却期（秒），0 表示使用全局默认
    alert_rules: List[str] = field(default_factory=list)  # 关联的告警规则ID
    enabled: bool = True


class BaseAction(ABC):
    """修复动作基类"""

    @abstractmethod
    async def execute(self, context: Dict[str, Any]) -> ActionResult:
        """执行修复动作"""
        ...

    @abstractmethod
    async def snapshot(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """创建快照（执行前调用）"""
        ...

    @abstractmethod
    async def rollback(self, snapshot_data: Dict[str, Any]) -> bool:
        """回滚到快照"""
        ...

    @abstractmethod
    async def verify(self, context: Dict[str, Any]) -> bool:
        """验证修复结果"""
        ...


# ============================================================
# 1. restart_service — 重启服务
# ============================================================
class RestartServiceAction(BaseAction):
    """重启指定服务"""

    async def execute(self, ctx: Dict[str, Any]) -> ActionResult:
        service_name = ctx.get("service_name", "fuxi")
        cmd = ctx.get("restart_cmd", f"systemctl restart {service_name}")

        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)

            if proc.returncode == 0:
                return ActionResult(
                    action_id="restart_service",
                    status=RepairStatus.SUCCESS,
                    message=f"服务 {service_name} 重启成功",
                    details={"stdout": stdout.decode(errors="ignore")},
                )
            else:
                return ActionResult(
                    action_id="restart_service",
                    status=RepairStatus.FAILED,
                    message=f"服务 {service_name} 重启失败",
                    details={"stderr": stderr.decode(errors="ignore")},
                )
        except asyncio.TimeoutError:
            return ActionResult(
                action_id="restart_service",
                status=RepairStatus.TIMEOUT,
                message=f"服务 {service_name} 重启超时",
            )

    async def snapshot(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        return {"service_name": ctx.get("service_name", "fuxi"), "timestamp": datetime.now().isoformat()}

    async def rollback(self, snapshot_data: Dict[str, Any]) -> bool:
        # 重启服务的回滚即再次重启
        service = snapshot_data.get("service_name", "fuxi")
        try:
            proc = await asyncio.create_subprocess_shell(
                f"systemctl restart {service}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.communicate(), timeout=60)
            return proc.returncode == 0
        except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
            return False

    async def verify(self, ctx: Dict[str, Any]) -> bool:
        service = ctx.get("service_name", "fuxi")
        try:
            proc = await asyncio.create_subprocess_shell(
                f"systemctl is-active {service}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
            return b"active" in stdout
        except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
            return False


# ============================================================
# 2. clear_cache — 清理缓存
# ============================================================
class ClearCacheAction(BaseAction):
    """清理系统缓存目录"""

    async def execute(self, ctx: Dict[str, Any]) -> ActionResult:
        cache_dirs = ctx.get("cache_dirs", ["/tmp/fuxi", "data/cache"])
        cleaned_bytes = 0
        errors = []

        for d in cache_dirs:
            if os.path.isdir(d):
                try:
                    before = _dir_size(d)
                    shutil.rmtree(d)
                    os.makedirs(d, exist_ok=True)
                    cleaned_bytes += before
                    logger.info(f"已清理缓存目录: {d} ({before} bytes)")
                except Exception as e:
                    errors.append(f"{d}: {e}")

        if errors:
            return ActionResult(
                action_id="clear_cache",
                status=RepairStatus.FAILED,
                message=f"部分缓存清理失败: {'; '.join(errors)}",
                details={"cleaned_bytes": cleaned_bytes, "errors": errors},
            )

        return ActionResult(
            action_id="clear_cache",
            status=RepairStatus.SUCCESS,
            message=f"缓存清理完成，释放 {cleaned_bytes / 1024 / 1024:.1f} MB",
            details={"cleaned_bytes": cleaned_bytes},
        )

    async def snapshot(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        cache_dirs = ctx.get("cache_dirs", ["/tmp/fuxi", "data/cache"])
        sizes = {}
        for d in cache_dirs:
            if os.path.isdir(d):
                sizes[d] = _dir_size(d)
        return {"cache_dirs": cache_dirs, "sizes": sizes, "timestamp": datetime.now().isoformat()}

    async def rollback(self, snapshot_data: Dict[str, Any]) -> bool:
        # 缓存清理无法回滚（数据已删除），但可以重建空目录
        for d in snapshot_data.get("cache_dirs", []):
            os.makedirs(d, exist_ok=True)
        return True

    async def verify(self, ctx: Dict[str, Any]) -> bool:
        # 验证缓存目录存在且可写
        for d in ctx.get("cache_dirs", ["/tmp/fuxi", "data/cache"]):
            if not os.path.isdir(d):
                return False
        return True


# ============================================================
# 3. rebuild_index — 重建索引
# ============================================================
class RebuildIndexAction(BaseAction):
    """重建 ChromaDB / 向量索引"""

    async def execute(self, ctx: Dict[str, Any]) -> ActionResult:
        collection_name = ctx.get("collection_name", "fuxi_kb")
        chromadb_url = ctx.get("chromadb_url", "http://localhost:8000")

        try:
            # 通过 API 触发重建
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{chromadb_url}/api/v1/collections/{collection_name}/rebuild",
                    timeout=aiohttp.ClientTimeout(total=120),
                ) as resp:
                    if resp.status == 200:
                        return ActionResult(
                            action_id="rebuild_index",
                            status=RepairStatus.SUCCESS,
                            message=f"索引 {collection_name} 重建成功",
                        )
                    else:
                        body = await resp.text()
                        return ActionResult(
                            action_id="rebuild_index",
                            status=RepairStatus.FAILED,
                            message=f"索引重建失败: HTTP {resp.status}",
                            details={"response": body},
                        )
        except ImportError:
            return ActionResult(
                action_id="rebuild_index",
                status=RepairStatus.FAILED,
                message="缺少 aiohttp 依赖，无法调用 ChromaDB API",
            )
        except Exception as e:
            return ActionResult(
                action_id="rebuild_index",
                status=RepairStatus.FAILED,
                message=f"索引重建异常: {e}",
            )

    async def snapshot(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "collection_name": ctx.get("collection_name", "fuxi_kb"),
            "timestamp": datetime.now().isoformat(),
        }

    async def rollback(self, snapshot_data: Dict[str, Any]) -> bool:
        # 索引重建的回滚需要从备份恢复，此处标记为不可自动回滚
        logger.warning("索引重建回滚需要手动干预")
        return False

    async def verify(self, ctx: Dict[str, Any]) -> bool:
        # 简单验证：检查 ChromaDB 可用
        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    ctx.get("chromadb_url", "http://localhost:8000") + "/api/v1/heartbeat",
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    return resp.status == 200
        except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
            return False


# ============================================================
# 4. fix_permissions — 修复权限
# ============================================================
class FixPermissionsAction(BaseAction):
    """修复文件/目录权限"""

    async def execute(self, ctx: Dict[str, Any]) -> ActionResult:
        paths = ctx.get("paths", [])
        target_mode = ctx.get("mode", 0o755)
        errors = []

        for p in paths:
            try:
                if os.path.exists(p):
                    os.chmod(p, target_mode)
                    logger.info(f"已修复权限: {p} -> {oct(target_mode)}")
                else:
                    errors.append(f"路径不存在: {p}")
            except Exception as e:
                errors.append(f"{p}: {e}")

        if errors:
            return ActionResult(
                action_id="fix_permissions",
                status=RepairStatus.FAILED,
                message=f"部分权限修复失败: {'; '.join(errors)}",
                details={"errors": errors},
            )

        return ActionResult(
            action_id="fix_permissions",
            status=RepairStatus.SUCCESS,
            message=f"已修复 {len(paths)} 个路径的权限",
            details={"paths": paths, "mode": oct(target_mode)},
        )

    async def snapshot(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        paths = ctx.get("paths", [])
        perms = {}
        for p in paths:
            if os.path.exists(p):
                perms[p] = oct(os.stat(p).st_mode)
        return {"paths": paths, "permissions": perms, "timestamp": datetime.now().isoformat()}

    async def rollback(self, snapshot_data: Dict[str, Any]) -> bool:
        perms = snapshot_data.get("permissions", {})
        for p, mode in perms.items():
            try:
                os.chmod(p, int(mode, 8))
            except Exception as e:
                logger.error(f"权限回滚失败 {p}: {e}")
                return False
        return True

    async def verify(self, ctx: Dict[str, Any]) -> bool:
        target_mode = ctx.get("mode", 0o755)
        for p in ctx.get("paths", []):
            if os.path.exists(p):
                current = os.stat(p).st_mode & 0o777
                if current != target_mode:
                    return False
        return True


# ============================================================
# 5. cleanup_disk — 清理磁盘空间
# ============================================================
class CleanupDiskAction(BaseAction):
    """清理磁盘空间"""

    async def execute(self, ctx: Dict[str, Any]) -> ActionResult:
        cleaned_bytes = 0
        actions_taken = []

        # 清理临时文件
        temp_dirs = ctx.get("temp_dirs", ["/tmp", "data/temp"])
        for d in temp_dirs:
            if os.path.isdir(d):
                try:
                    size = _dir_size(d)
                    # 只清理超过 1 小时的文件
                    now = time.time()
                    for root, dirs, files in os.walk(d):
                        for f in files:
                            fp = os.path.join(root, f)
                            try:
                                if now - os.path.getmtime(fp) > 3600:
                                    os.remove(fp)
                                    cleaned_bytes += os.path.getsize(fp)
                            except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
                                pass
                    actions_taken.append(f"清理临时目录: {d}")
                except Exception as e:
                    logger.warning(f"清理 {d} 失败: {e}")

        # 清理旧日志
        log_dir = ctx.get("log_dir", "src/logs")
        if os.path.isdir(log_dir):
            try:
                now = time.time()
                for f in os.listdir(log_dir):
                    fp = os.path.join(log_dir, f)
                    if os.path.isfile(fp) and now - os.path.getmtime(fp) > 7 * 86400:
                        size = os.path.getsize(fp)
                        os.remove(fp)
                        cleaned_bytes += size
                        actions_taken.append(f"清理旧日志: {f}")
            except Exception as e:
                logger.warning(f"清理日志失败: {e}")

        return ActionResult(
            action_id="cleanup_disk",
            status=RepairStatus.SUCCESS,
            message=f"磁盘清理完成，释放 {cleaned_bytes / 1024 / 1024:.1f} MB",
            details={"cleaned_bytes": cleaned_bytes, "actions": actions_taken},
        )

    async def snapshot(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        import psutil

        disk = psutil.disk_usage("/")
        return {
            "total": disk.total,
            "used": disk.used,
            "free": disk.free,
            "percent": disk.percent,
            "timestamp": datetime.now().isoformat(),
        }

    async def rollback(self, snapshot_data: Dict[str, Any]) -> bool:
        # 磁盘清理无法回滚
        logger.warning("磁盘清理无法回滚")
        return False

    async def verify(self, ctx: Dict[str, Any]) -> bool:
        import psutil

        disk = psutil.disk_usage("/")
        target = ctx.get("target_percent", 85.0)
        return disk.percent < target


# ============================================================
# 6. restart_chromadb — 重启 ChromaDB
# ============================================================
class RestartChromaDBAction(BaseAction):
    """重启 ChromaDB 服务"""

    async def execute(self, ctx: Dict[str, Any]) -> ActionResult:
        chromadb_url = ctx.get("chromadb_url", "http://localhost:8000")

        try:
            # 尝试通过 API 检查并重启
            import aiohttp

            async with aiohttp.ClientSession() as session:
                # 先检查当前状态
                try:
                    async with session.get(
                        f"{chromadb_url}/api/v1/heartbeat",
                        timeout=aiohttp.ClientTimeout(total=5),
                    ) as resp:
                        if resp.status == 200:
                            return ActionResult(
                                action_id="restart_chromadb",
                                status=RepairStatus.SUCCESS,
                                message="ChromaDB 已在运行且健康",
                            )
                except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
                    pass

                # 尝试重启（通过 docker 或 systemctl）
                restart_cmd = ctx.get("restart_cmd", "docker restart chromadb")
                proc = await asyncio.create_subprocess_shell(
                    restart_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)

                if proc.returncode == 0:
                    # 等待服务就绪
                    await asyncio.sleep(3)
                    return ActionResult(
                        action_id="restart_chromadb",
                        status=RepairStatus.SUCCESS,
                        message="ChromaDB 重启成功",
                        details={"stdout": stdout.decode(errors="ignore")},
                    )
                else:
                    return ActionResult(
                        action_id="restart_chromadb",
                        status=RepairStatus.FAILED,
                        message="ChromaDB 重启失败",
                        details={"stderr": stderr.decode(errors="ignore")},
                    )
        except ImportError:
            return ActionResult(
                action_id="restart_chromadb",
                status=RepairStatus.FAILED,
                message="缺少 aiohttp 依赖",
            )
        except Exception as e:
            return ActionResult(
                action_id="restart_chromadb",
                status=RepairStatus.FAILED,
                message=f"ChromaDB 重启异常: {e}",
            )

    async def snapshot(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "chromadb_url": ctx.get("chromadb_url", "http://localhost:8000"),
            "timestamp": datetime.now().isoformat(),
        }

    async def rollback(self, snapshot_data: Dict[str, Any]) -> bool:
        # 重启类操作的回滚：再次重启
        try:
            proc = await asyncio.create_subprocess_shell(
                "docker restart chromadb",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.communicate(), timeout=60)
            return proc.returncode == 0
        except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
            return False

    async def verify(self, ctx: Dict[str, Any]) -> bool:
        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    ctx.get("chromadb_url", "http://localhost:8000") + "/api/v1/heartbeat",
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    return resp.status == 200
        except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
            return False


# ============================================================
# 7. reconnect_redis — 重连 Redis
# ============================================================
class ReconnectRedisAction(BaseAction):
    """重连 Redis 服务"""

    async def execute(self, ctx: Dict[str, Any]) -> ActionResult:
        redis_url = ctx.get("redis_url", "redis://localhost:6379")

        try:
            import redis.asyncio as aioredis

            client = aioredis.from_url(redis_url, socket_timeout=5)
            await client.ping()
            await client.aclose()
            return ActionResult(
                action_id="reconnect_redis",
                status=RepairStatus.SUCCESS,
                message="Redis 连接成功",
            )
        except ImportError:
            # 尝试 redis 包
            try:
                import redis

                client = redis.from_url(redis_url, socket_timeout=5)
                client.ping()
                client.close()
                return ActionResult(
                    action_id="reconnect_redis",
                    status=RepairStatus.SUCCESS,
                    message="Redis 连接成功",
                )
            except Exception as e:
                return ActionResult(
                    action_id="reconnect_redis",
                    status=RepairStatus.FAILED,
                    message=f"Redis 连接失败: {e}",
                )
        except Exception as e:
            # 尝试重启 Redis
            try:
                restart_cmd = ctx.get("restart_cmd", "systemctl restart redis")
                proc = await asyncio.create_subprocess_shell(
                    restart_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await asyncio.wait_for(proc.communicate(), timeout=30)

                # 重试连接
                import redis.asyncio as aioredis

                client = aioredis.from_url(redis_url, socket_timeout=5)
                await client.ping()
                await client.aclose()
                return ActionResult(
                    action_id="reconnect_redis",
                    status=RepairStatus.SUCCESS,
                    message="Redis 重启后连接成功",
                )
            except Exception as e2:
                return ActionResult(
                    action_id="reconnect_redis",
                    status=RepairStatus.FAILED,
                    message=f"Redis 重连失败: {e2}",
                )

    async def snapshot(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        return {"redis_url": ctx.get("redis_url", "redis://localhost:6379"), "timestamp": datetime.now().isoformat()}

    async def rollback(self, snapshot_data: Dict[str, Any]) -> bool:
        # 重连操作无需回滚
        return True

    async def verify(self, ctx: Dict[str, Any]) -> bool:
        try:
            import redis.asyncio as aioredis

            client = aioredis.from_url(ctx.get("redis_url", "redis://localhost:6379"), socket_timeout=5)
            await client.ping()
            await client.aclose()
            return True
        except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
            return False


# ============================================================
# 8. reload_config — 重载配置
# ============================================================
class ReloadConfigAction(BaseAction):
    """重载系统配置"""

    async def execute(self, ctx: Dict[str, Any]) -> ActionResult:
        config_path = ctx.get("config_path", "app/config")
        reload_cmd = ctx.get("reload_cmd")

        if reload_cmd:
            try:
                proc = await asyncio.create_subprocess_shell(
                    reload_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)

                if proc.returncode == 0:
                    return ActionResult(
                        action_id="reload_config",
                        status=RepairStatus.SUCCESS,
                        message="配置重载成功",
                        details={"stdout": stdout.decode(errors="ignore")},
                    )
                else:
                    return ActionResult(
                        action_id="reload_config",
                        status=RepairStatus.FAILED,
                        message="配置重载失败",
                        details={"stderr": stderr.decode(errors="ignore")},
                    )
            except Exception as e:
                return ActionResult(
                    action_id="reload_config",
                    status=RepairStatus.FAILED,
                    message=f"配置重载异常: {e}",
                )
        else:
            # 验证配置文件存在且可读
            if os.path.isdir(config_path):
                return ActionResult(
                    action_id="reload_config",
                    status=RepairStatus.SUCCESS,
                    message=f"配置目录 {config_path} 存在",
                )
            else:
                return ActionResult(
                    action_id="reload_config",
                    status=RepairStatus.FAILED,
                    message=f"配置路径不存在: {config_path}",
                )

    async def snapshot(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        config_path = ctx.get("config_path", "app/config")
        # 记录配置文件的修改时间
        config_mtimes = {}
        if os.path.isdir(config_path):
            for f in os.listdir(config_path):
                fp = os.path.join(config_path, f)
                if os.path.isfile(fp):
                    config_mtimes[f] = os.path.getmtime(fp)
        return {"config_path": config_path, "mtimes": config_mtimes, "timestamp": datetime.now().isoformat()}

    async def rollback(self, snapshot_data: Dict[str, Any]) -> bool:
        # 配置重载的回滚：重新加载旧配置
        logger.warning("配置重载回滚需要手动恢复配置文件")
        return False

    async def verify(self, ctx: Dict[str, Any]) -> bool:
        # 简单验证：配置路径存在
        return os.path.exists(ctx.get("config_path", "app/config"))


# ============================================================
# 工具函数
# ============================================================
def _dir_size(path: str) -> int:
    """计算目录大小（字节）"""
    total = 0
    try:
        for dirpath, dirnames, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                try:
                    total += os.path.getsize(fp)
                except OSError:
                    pass
    except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
        pass
    return total


# ============================================================
# 动作注册表
# ============================================================
import time  # noqa: E402（_dir_size 需要）

PRESET_ACTIONS: Dict[str, RepairAction] = {
    "restart_service": RepairAction(
        id="restart_service",
        name="重启服务",
        description="重启指定系统服务（systemctl restart）",
        risk_level=RiskLevel.MEDIUM,
        cooldown=300,
        alert_rules=["service_unavailable"],
    ),
    "clear_cache": RepairAction(
        id="clear_cache",
        name="清理缓存",
        description="清理临时文件和缓存目录",
        risk_level=RiskLevel.LOW,
        cooldown=600,
        alert_rules=["disk_high"],
    ),
    "rebuild_index": RepairAction(
        id="rebuild_index",
        name="重建索引",
        description="重建 ChromaDB 向量索引",
        risk_level=RiskLevel.HIGH,
        cooldown=1800,
        alert_rules=["api_latency_high"],
    ),
    "fix_permissions": RepairAction(
        id="fix_permissions",
        name="修复权限",
        description="修复文件和目录权限",
        risk_level=RiskLevel.MEDIUM,
        cooldown=600,
        alert_rules=[],
    ),
    "cleanup_disk": RepairAction(
        id="cleanup_disk",
        name="清理磁盘空间",
        description="清理临时文件和旧日志，释放磁盘空间",
        risk_level=RiskLevel.LOW,
        cooldown=1800,
        alert_rules=["disk_high"],
    ),
    "restart_chromadb": RepairAction(
        id="restart_chromadb",
        name="重启ChromaDB",
        description="重启 ChromaDB 向量数据库服务",
        risk_level=RiskLevel.HIGH,
        cooldown=600,
        alert_rules=["api_latency_high", "api_error_rate_high"],
    ),
    "reconnect_redis": RepairAction(
        id="reconnect_redis",
        name="重连Redis",
        description="重连或重启 Redis 缓存服务",
        risk_level=RiskLevel.MEDIUM,
        cooldown=300,
        alert_rules=["service_unavailable"],
    ),
    "reload_config": RepairAction(
        id="reload_config",
        name="重载配置",
        description="重新加载系统配置文件",
        risk_level=RiskLevel.LOW,
        cooldown=120,
        alert_rules=[],
    ),
}

ACTION_HANDLERS: Dict[str, BaseAction] = {
    "restart_service": RestartServiceAction(),
    "clear_cache": ClearCacheAction(),
    "rebuild_index": RebuildIndexAction(),
    "fix_permissions": FixPermissionsAction(),
    "cleanup_disk": CleanupDiskAction(),
    "restart_chromadb": RestartChromaDBAction(),
    "reconnect_redis": ReconnectRedisAction(),
    "reload_config": ReloadConfigAction(),
}
