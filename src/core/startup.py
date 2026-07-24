"""
伏羲 v1.44 — 核心启动/停止逻辑
=============================
从 server.py 拆分的 Fuxi 生命体管理: 启动、八卦注册、关机。
"""
import os
import gc
import sys
import logging
import asyncio
from typing import Any, Optional

from fastapi import FastAPI

_DEFAULT_ENGINE: str = os.getenv("FUXI_ENGINE", "v2").lower()
_DEFAULT_INTENT_MODE: str = os.getenv("FUXI_INTENT_MODE", "rule_based").lower()
_fuxi_instance = None
_message_queue_instance: Optional[Any] = None  # 全局消息队列实例

# ── P1 GC 调优：定期GC触发与内存监控 ──
_gc_task: Optional[asyncio.Task] = None
_gc_interval: int = 300  # 每5分钟触发一次GC
_memory_warn_threshold_mb: int = 512  # 内存告警阈值 512MB
_last_gc_stats: dict = {}


def _setup_python_malloc():
    """在启动时设置 PYTHONMALLOC=malloc 以减少内存碎片"""
    if os.environ.get("PYTHONMALLOC") is None:
        os.environ["PYTHONMALLOC"] = "malloc"
        logging.getLogger("server").info(
            "[GC] PYTHONMALLOC 已设置为 malloc（减少内存碎片）"
        )
    else:
        logging.getLogger("server").info(
            f"[GC] PYTHONMALLOC 已由环境变量设置: {os.environ['PYTHONMALLOC']}"
        )


def _get_memory_usage_mb() -> float:
    """获取当前进程内存使用（MB）"""
    try:
        import psutil
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / (1024 * 1024)
    except ImportError:
        return -1.0


async def _periodic_gc_collector():
    """定期GC收集器：每 _gc_interval 秒触发一次"""
    logger = logging.getLogger("server")
    global _last_gc_stats
    
    while True:
        try:
            await asyncio.sleep(_gc_interval)
            
            # 收集 GC 前统计
            gen0_before = gc.get_count()[0]
            
            # 执行 full GC
            collected = gc.collect()
            
            # 收集内存信息
            mem_mb = _get_memory_usage_mb()
            
            _last_gc_stats = {
                "collected_objects": collected,
                "gen0_objects_before": gen0_before,
                "memory_mb": round(mem_mb, 2),
                "gc_thresholds": gc.get_threshold(),
            }
            
            logger.debug(
                f"[GC] 定期回收: {collected} 个对象, "
                f"Gen0前: {gen0_before}, 内存: {mem_mb:.1f}MB"
            )
            
            # 内存告警
            if mem_mb > _memory_warn_threshold_mb:
                logger.warning(
                    f"[GC] ⚠️ 内存使用超过阈值: {mem_mb:.1f}MB > {_memory_warn_threshold_mb}MB"
                )
                
        except asyncio.CancelledError:
            logger.info("[GC] 定期GC收集器已停止")
            break
        except Exception as e:
            logger.error(f"[GC] 定期收集异常: {e}", exc_info=True)


def get_gc_stats() -> dict:
    """获取GC统计信息"""
    global _last_gc_stats
    mem_mb = _get_memory_usage_mb()
    return {
        "enabled": gc.isenabled(),
        "last_stats": _last_gc_stats,
        "current_memory_mb": round(mem_mb, 2) if mem_mb > 0 else "psutil 未安装",
        "thresholds": gc.get_threshold(),
        "gc_count": gc.get_count(),
        "python_malloc": os.environ.get("PYTHONMALLOC", "未设置"),
    }


def get_fuxi_instance():
    """获取当前 Fuxi 实例（可能为 None）"""
    return _fuxi_instance


def get_message_queue() -> Optional[Any]:
    """获取全局消息队列实例（可能为 None）"""
    return _message_queue_instance


async def start_fuxi(app: FastAPI) -> None:
    """启动伏羲生命体 — v2.1 八卦体系

    引擎路由：
      - v2（默认）: 八卦 QianGua + IntentBus
      - v1: 旧版 hypothalamus.fuxi.Fuxi（保留兼容）
    """
    global _fuxi_instance, _message_queue_instance, _gc_task
    import time as _time
    
    # ── P1: 启动时内存分配器优化 ──
    _setup_python_malloc()
    engine = os.getenv("FUXI_ENGINE", "v2").lower()
    intent_mode = os.getenv("FUXI_INTENT_MODE", "rule_based").lower()

    # ── P1 修复: 对话历史持久化 ──
    try:
        from src.db.conversation_db import init_conversation_db
        init_conversation_db()
        logging.getLogger("server").info("[Fuxi] 对话持久化数据库已初始化")
    except (ImportError, OSError) as e:
        logging.getLogger("server").warning(f"[Fuxi] 对话持久化数据库初始化失败（服务继续启动）: {e}")

    try:
        if engine == "v2":
            from src.bagua.qian import QianGua
            from src.bagua.intent_bus import get_intent_bus

            intent_bus = get_intent_bus()
            _fuxi_instance = QianGua(intent_bus=intent_bus, intent_mode=intent_mode)
            _fuxi_instance.start()
            _fuxi_instance.start_beating()

            app.state.fuxi = _fuxi_instance
            app.state.intent_bus = intent_bus
            app.state.fuxi_born_at = _time.time()
            app.state.engine = "v2"
            app.state.intent_mode = intent_mode

            logging.getLogger("server").info(f"[Fuxi] 引擎: v2 (Bagua) | intent_mode: {intent_mode}")
            logging.getLogger("server").info(f"[Fuxi] 伏羲八卦体系已苏醒 ☰")

            _register_bagua_guas(app, intent_bus)

        elif engine == "v1":
            from src.hypothalamus.fuxi import Fuxi
            _fuxi_instance = Fuxi()
            app.state.fuxi = _fuxi_instance
            app.state.meridian = _fuxi_instance.meridian
            app.state.fuxi_born_at = _time.time()
            app.state.engine = "v1"
            app.state.intent_mode = intent_mode
            await _fuxi_instance.born()
            logging.getLogger("server").info(f"[Fuxi] 引擎: v1 (Legacy) | intent_mode: {intent_mode}")

        else:
            raise ValueError(f"未知引擎版本: {engine}，支持 v1/v2")

        # ---- 初始化消息队列（P0 修复） ----
        await _init_message_queue(app)
        
        # ── P1: 启动定期GC收集器 ──
        _gc_task = asyncio.create_task(_periodic_gc_collector())
        logging.getLogger("server").info(
            f"[GC] 定期GC收集器已启动（间隔 {_gc_interval}s，内存告警阈值 {_memory_warn_threshold_mb}MB）"
        )

        _register_shutdown_handler(app)

    except ImportError as e:
        logging.getLogger("server").critical(f"[Fuxi] 无法导入伏羲模块，服务无法启动: {e}", exc_info=True)
        raise
    except (RuntimeError, ValueError, OSError, AttributeError) as e:
        logging.getLogger("server").error(f"[Fuxi] 启动失败: {e}", exc_info=True)
        # 不阻止服务器启动，部分功能不可用


async def stop_fuxi(app: FastAPI) -> None:
    """休眠伏羲 — v2.1"""
    global _fuxi_instance, _message_queue_instance, _gc_task
    engine = getattr(app.state, "engine", "v2")
    if _fuxi_instance:
        if engine == "v2":
            _fuxi_instance.stop()
            logging.getLogger("server").info("[Fuxi] 八卦体系已停止 ☰")
        else:
            await _fuxi_instance.sleep()
            logging.getLogger("server").info("[Fuxi] 伏羲已休眠")

    # 停止定期GC收集器
    if _gc_task:
        _gc_task.cancel()
        try:
            await _gc_task
        except asyncio.CancelledError:
            pass
        _gc_task = None
        logging.getLogger("server").info("[GC] 定期GC收集器已停止")
    
    # 关闭消息队列
    if _message_queue_instance:
        await _message_queue_instance.close()
        _message_queue_instance = None
        logging.getLogger("server").info("[MQ] 消息队列已关闭")


def _register_bagua_guas(app: FastAPI, intent_bus: Any) -> None:
    """注册八卦所有卦到 IntentBus"""
    gua_registry = {
        "坤": ("src.bagua.kun", "KunGua"),
        "震(zhen)": ("src.bagua.zhen", "ZhenGua"),
        "巽(xun)": ("src.bagua.xun", "XunGua"),
        "坎(kan)": ("src.bagua.kan", "KanGua"),
        "离(li)": ("src.bagua.li", "LiGua"),
        "艮(gen)": ("src.bagua.gen", "GenGua"),
        "兑(dui)": ("src.bagua.dui", "DuiGua"),
    }

    for register_name, (module_path, class_name) in gua_registry.items():
        try:
            mod = __import__(module_path, fromlist=[class_name])
            cls = getattr(mod, class_name)
            instance = cls(intent_bus=intent_bus)
            instance.start()
            instance.register_to_bus(name=register_name)
            logging.getLogger("server").info(f"[Bagua] {register_name} 已注册到 IntentBus")
        except (ImportError, AttributeError, RuntimeError) as e:
            logging.getLogger("server").warning(f"[Bagua] {register_name} 注册失败（服务继续启动）: {e}")


def _register_shutdown_handler(app: FastAPI) -> None:
    """v2.1: 注册三步清理法关机 handler"""
    try:
        from src.bagua.shutdown import register_shutdown_handler
        register_shutdown_handler(
            app=app,
            fuxi_instance=_fuxi_instance,
            grace_period=5.0,
            cancel_timeout=10.0,
            drain_timeout=5.0,
        )
        logging.getLogger("server").info("[Shutdown] 优雅关机 handler 已注册 (STOP→CANCEL→DRAIN)")
    except ImportError:
        logging.getLogger("server").warning("[Shutdown] bagua.shutdown 模块未找到，跳过优雅关机注册")
    except (RuntimeError, AttributeError, TypeError) as e:
        logging.getLogger("server").warning("[Shutdown] 关机 handler 注册失败: %s", e)


async def _init_message_queue(app: FastAPI) -> None:
    """初始化消息队列（P0 核心缺陷修复）

    从 src.services.message_queue 加载 MessageQueue，
    自动探测 Redis 可用性：
      - Redis 可用 → RedisStreamBackend（分布式、持久化）
      - Redis 不可用 → MemoryQueueBackend（降级、内存）
    """
    global _message_queue_instance
    logger = logging.getLogger("server")
    try:
        from src.services.message_queue import MessageQueue

        _message_queue_instance = MessageQueue(name="fuxi")
        await _message_queue_instance.initialize()

        app.state.message_queue = _message_queue_instance
        app.state.mq_backend = _message_queue_instance.backend_type

        health = await _message_queue_instance.health()
        logger.info(
            "[MQ] 消息队列已就绪 — backend=%s status=%s",
            health["backend"], health["status"],
        )
    except Exception as e:
        logger.warning("[MQ] 消息队列初始化失败（服务继续运行，消息功能不可用）: %s", e)
