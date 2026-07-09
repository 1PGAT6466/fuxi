"""
shutdown.py — 优雅关机处理器 · 伏羲 v2.1 重构

实现三步清理法（STOP → CANCEL → DRAIN），
以保证伏羲生命体的有序休眠和资源释放。

三步清理法：
  STEP 1 — STOP:   停止所有节律活动（心跳/呼吸/经络流注），
                   停止接收新的请求。
  STEP 2 — CANCEL: 等待正在处理的任务超时，超时后强制取消。
  STEP 3 — DRAIN:  释放数据库连接池、关闭 HTTP 会话、
                   清理临时文件、关闭断路器探活循环。

注册方式：
    from src.bagua.shutdown import register_shutdown_handler
    register_shutdown_handler(app, fuxi_instance)
"""


import asyncio
import logging
import signal
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger("bagua.shutdown")


# ============================================================================
# 信号常量
# ============================================================================

# Unix 信号（Windows 上有限支持）
SIGTERM = getattr(signal, "SIGTERM", 15)
SIGINT = getattr(signal, "SIGINT", 2)

# 默认超时配置（秒）
DEFAULT_GRACE_PERIOD = 5.0       # STOP 阶段等待时间
DEFAULT_CANCEL_TIMEOUT = 10.0    # CANCEL 阶段超时时间
DEFAULT_DRAIN_TIMEOUT = 5.0      # DRAIN 阶段超时时间


# ============================================================================
# 关闭阶段追踪
# ============================================================================

class ShutdownPhase:
    """关机阶段"""
    NOT_STARTED = "not_started"
    STOP = "stop"           # 第一步：停止节律
    CANCEL = "cancel"       # 第二步：取消任务
    DRAIN = "drain"         # 第三步：释放资源
    COMPLETE = "complete"   # 完成
    ERROR = "error"         # 异常


class ShutdownContext:
    """关机上下文：追踪整个关机过程的阶段和状态"""

    def __init__(self):
        self.phase: str = ShutdownPhase.NOT_STARTED
        self.started_at: float = 0.0
        self.completed_at: float = 0.0
        self.errors: List[str] = []
        self.details: Dict[str, Any] = {}

    def start(self) -> None:
        self.started_at = time.time()
        logger.info("=" * 50)
        logger.info("  伏羲 Fuxi · 开始优雅关机")
        logger.info("=" * 50)

    def complete(self) -> None:
        self.completed_at = time.time()
        duration = self.completed_at - self.started_at
        self.phase = ShutdownPhase.COMPLETE
        logger.info(
            "伏羲已休眠 — 关机耗时 %.2fs, 阶段: STOP→CANCEL→DRAIN ✓",
            duration,
        )

    def record_error(self, phase: str, error: str) -> None:
        self.errors.append(f"[{phase}] {error}")
        logger.error("关机 %s 阶段错误: %s", phase, error)


# ============================================================================
# 优雅关机 Handler
# ============================================================================

class GracefulShutdown:
    """优雅关机处理器

    实现标准的三步清理法：
      STOP  → 停止节律活动，拒绝新请求
      CANCEL→ 等待进行中任务完成，超时则强制取消
      DRAIN → 释放所有外部资源（连接池/会话/文件）

    Usage::

        handler = GracefulShutdown(
            fuxi_instance=fuxi,
            grace_period=5.0,
            cancel_timeout=10.0,
            drain_timeout=5.0,
        )
        await handler.shutdown()
    """

    def __init__(
        self,
        fuxi_instance: Any = None,
        app: Any = None,
        grace_period: float = DEFAULT_GRACE_PERIOD,
        cancel_timeout: float = DEFAULT_CANCEL_TIMEOUT,
        drain_timeout: float = DEFAULT_DRAIN_TIMEOUT,
        pending_tasks: Optional[List[asyncio.Task]] = None,
    ) -> None:
        """
        Args:
            fuxi_instance:  伏羲生命体实例
            app:            FastAPI 应用实例
            grace_period:   STOP 阶段等待时间（秒）
            cancel_timeout: CANCEL 阶段超时（秒）
            drain_timeout:  DRAIN 阶段超时（秒）
            pending_tasks:  额外待清理的 asyncio Task 列表
        """
        self._fuxi = fuxi_instance
        self._app = app
        self._grace_period = grace_period
        self._cancel_timeout = cancel_timeout
        self._drain_timeout = drain_timeout
        self._pending_tasks: List[asyncio.Task] = pending_tasks or []
        self._ctx = ShutdownContext()
        self._shutting_down = False

    @property
    def is_shutting_down(self) -> bool:
        """是否正在关机"""
        return self._shutting_down

    # ========================================================================
    # 主入口
    # ========================================================================

    async def shutdown(self) -> ShutdownContext:
        """执行完整的三步关机流程"""
        if self._shutting_down:
            logger.warning("关机已在进行中，跳过重复调用")
            return self._ctx

        self._shutting_down = True
        self._ctx.start()

        try:
            # ── STEP 1: STOP ──
            await self._step_stop()

            # ── STEP 2: CANCEL ──
            await self._step_cancel()

            # ── STEP 3: DRAIN ──
            await self._step_drain()

            self._ctx.complete()
        except Exception as e:  # TODO: Narrow exception type
            self._ctx.phase = ShutdownPhase.ERROR
            self._ctx.record_error("shutdown", str(e))
            logger.critical("关机流程异常: %s", e, exc_info=True)

        self._shutting_down = False
        return self._ctx

    # ========================================================================
    # STEP 1: STOP — 停止节律活动
    # ========================================================================

    async def _step_stop(self) -> None:
        """第一步：停止所有节律活动，拒绝新请求"""
        self._ctx.phase = ShutdownPhase.STOP
        logger.info("━━━ STEP 1/3: STOP — 停止节律活动 ━━━")

        # 1a. 标记应用为关闭状态（拒绝新请求）
        if self._app is not None:
            try:
                self._app.state.shutting_down = True
                logger.info("  → 已标记应用状态为 shutting_down，拒绝新请求")
            except Exception as e:  # TODO: Narrow exception type
                self._ctx.record_error("STOP", f"标记应用状态失败: {e}")

        # 1b. 停止伏羲生命体（调用现有 sleep 方法）
        if self._fuxi is not None:
            try:
                await self._fuxi.sleep()
                logger.info("  → 伏羲生命体已进入休眠")
            except Exception as e:  # TODO: Narrow exception type
                logger.warning("  → 伏羲休眠异常（继续关机）: %s", e)

        # 1c. 停止八卦模块的探活循环
        await self._stop_all_bagua()

        # 1d. 停止经络流注
        await self._stop_meridian_rhythm()

        # 1e. 等待短暂缓冲期，让正在处理的任务感知到关闭信号
        logger.info("  → 等待 %.1fs 缓冲期...", self._grace_period)
        await asyncio.sleep(self._grace_period)

        logger.info("  ✓ STOP 阶段完成")

    # ========================================================================
    # STEP 2: CANCEL — 取消进行中的任务
    # ========================================================================

    async def _step_cancel(self) -> None:
        """第二步：取消所有进行中的异步任务"""
        self._ctx.phase = ShutdownPhase.CANCEL
        logger.info("━━━ STEP 2/3: CANCEL — 取消进行中任务 ━━━")

        # 2a. 收集所有待取消的任务
        all_tasks = self._collect_pending_tasks()

        if not all_tasks:
            logger.info("  → 无进行中任务，跳过")
            logger.info("  ✓ CANCEL 阶段完成")
            return

        logger.info("  → 发现 %d 个进行中任务，等待完成...", len(all_tasks))

        # 2b. 给任务一段完成时间
        try:
            done, pending = await asyncio.wait(
                all_tasks,
                timeout=self._cancel_timeout,
                return_when=asyncio.ALL_COMPLETED,
            )
            logger.info("  → %d 个任务正常完成", len(done))
        except asyncio.TimeoutError:
            pending = all_tasks
            logger.warning("  → 等待超时")

        # 2c. 强制取消未完成的任务
        if pending:
            logger.warning("  → 强制取消 %d 个未完成任务", len(pending))
            for task in pending:
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                    except Exception as e:  # TODO: Narrow exception type
                        self._ctx.record_error("CANCEL", f"任务取消失败: {e}")

        # 2d. 取消八卦探活循环
        await self._cancel_all_bagua_recovery_loops()

        logger.info("  ✓ CANCEL 阶段完成")

    # ========================================================================
    # STEP 3: DRAIN — 释放外部资源
    # ========================================================================

    async def _step_drain(self) -> None:
        """第三步：释放所有外部资源"""
        self._ctx.phase = ShutdownPhase.DRAIN
        logger.info("━━━ STEP 3/3: DRAIN — 释放外部资源 ━━━")

        # 3a. 关闭数据库连接池
        await self._drain_connection_pool()

        # 3b. 关闭 aiohttp 会话
        await self._drain_http_sessions()

        # 3c. 清理临时文件
        await self._drain_temp_files()

        # 3d. 关闭断路器探活循环
        await self._drain_circuit_breakers()

        # 3e. 重置八卦健康状态注册表
        self._drain_gua_registry()

        # 3f. 日志刷新
        self._flush_logs()

        # 等待 DRAIN 缓冲
        await asyncio.sleep(min(1.0, self._drain_timeout))

        logger.info("  ✓ DRAIN 阶段完成")

    # ========================================================================
    # 辅助方法
    # ========================================================================

    async def _stop_all_bagua(self) -> None:
        """停止所有已注册的八卦模块"""
        try:
            gua_instances = _get_all_gua_instances()
            for name, gua in gua_instances.items():
                try:
                    if hasattr(gua, "stop"):
                        gua.stop()
                        logger.info("  → [八卦] %s 已停止", name)
                except Exception as e:  # TODO: Narrow exception type
                    self._ctx.record_error("STOP", f"卦 {name} 停止失败: {e}")
        except Exception as e:  # TODO: Narrow exception type
            logger.debug("  → 八卦停止跳过: %s", e)

    async def _stop_meridian_rhythm(self) -> None:
        """停止经络流注和节律调度器"""
        if self._fuxi is None:
            return
        try:
            if hasattr(self._fuxi, "rhythm") and self._fuxi.rhythm:
                await self._fuxi.rhythm.stop()
                logger.info("  → 经络流注已停止")
        except Exception as e:  # TODO: Narrow exception type
            logger.debug("  → 经络流注停止跳过: %s", e)

        try:
            if hasattr(self._fuxi, "stem_scheduler") and self._fuxi.stem_scheduler:
                await self._fuxi.stem_scheduler.stop()
                logger.info("  → 天干调度已停止")
        except Exception as e:  # TODO: Narrow exception type
            logger.debug("  → 天干调度停止跳过: %s", e)

        try:
            if hasattr(self._fuxi, "five_elements") and self._fuxi.five_elements:
                await self._fuxi.five_elements.stop()
                logger.info("  → 五行平衡已停止")
        except Exception as e:  # TODO: Narrow exception type
            logger.debug("  → 五行平衡停止跳过: %s", e)

    def _collect_pending_tasks(self) -> List[asyncio.Task]:
        """收集所有进行中的 asyncio Task"""
        tasks = list(self._pending_tasks)

        # 收集当前事件循环中除自身外的所有任务
        try:
            loop = asyncio.get_event_loop()
            current = asyncio.current_task()
            for task in asyncio.all_tasks(loop):
                if task is not current and not task.done():
                    tasks.append(task)
        except RuntimeError:
            pass

        return tasks

    async def _cancel_all_bagua_recovery_loops(self) -> None:
        """取消所有八卦的恢复探活循环

        调用 task.cancel() 后必须 await task 以确保任务正确终止。
        捕获 CancelledError 是正常行为。
        """
        try:
            gua_instances = _get_all_gua_instances()
            for name, gua in gua_instances.items():
                try:
                    recovery_task = getattr(gua, "_recovery_task", None)
                    if recovery_task and not recovery_task.done():
                        recovery_task.cancel()
                        try:
                            await recovery_task
                        except asyncio.CancelledError:
                            pass
                        except Exception as exc:  # TODO: Narrow exception type
                            logger.debug(
                                "  → [八卦/%s] 探活循环取消失败: %s", name, exc
                            )
                        else:
                            logger.debug("  → [八卦/%s] 探活循环已取消", name)
                except Exception as exc:  # TODO: Narrow exception type
                    logger.debug("  → [八卦/%s] 恢复探活取消失败: %s", name, exc)
                    pass

            # 也取消健康检查任务
            for name, gua in gua_instances.items():
                try:
                    health_task = getattr(gua, "_health_task", None)
                    if health_task and not health_task.done():
                        health_task.cancel()
                        try:
                            await health_task
                        except asyncio.CancelledError:
                            pass
                        except Exception as exc:  # TODO: Narrow exception type
                            logger.debug("  → [八卦/%s] 健康任务取消失败: %s", name, exc)
                            pass
                except Exception as exc:  # TODO: Narrow exception type
                    logger.debug("  → [八卦/%s] 任务获取失败: %s", name, exc)
                    pass
        except Exception as exc:  # TODO: Narrow exception type
            logger.debug("  → 八卦实例获取失败: %s", exc)
            pass

    async def _drain_connection_pool(self) -> None:
        """释放数据库连接池"""
        try:
            from src.infra.connection_pool import get_connection_pool
            pool = get_connection_pool()
            pool.close_all()
            logger.info("  → 数据库连接池已关闭")
        except Exception as e:  # TODO: Narrow exception type
            self._ctx.record_error("DRAIN", f"连接池关闭失败: {e}")

    async def _drain_http_sessions(self) -> None:
        """关闭持久化 HTTP 会话"""
        # 尝试关闭 aiohttp 会话（如有全局实例）
        import sys
        for mod_name, mod in list(sys.modules.items()):
            for attr_name in dir(mod):
                attr = getattr(mod, attr_name)
                if hasattr(attr, "close") and type(attr).__name__ == "ClientSession":
                    try:
                        await attr.close()
                        logger.debug("  → 已关闭 HTTP 会话: %s.%s", mod_name, attr_name)
                    except Exception:  # TODO: Narrow exception type
                        pass

    async def _drain_temp_files(self) -> None:
        """清理临时文件"""
        try:
            import tempfile
            import os
            temp_dir = tempfile.gettempdir()
            # 清理伏羲相关的临时文件
            count = 0
            for root, dirs, files in os.walk(temp_dir):
                for f in files:
                    if f.startswith("fuxi_") or f.startswith("伏羲_"):
                        try:
                            os.remove(os.path.join(root, f))
                            count += 1
                        except Exception:  # TODO: Narrow exception type
                            pass
            if count > 0:
                logger.info("  → 已清理 %d 个临时文件", count)
            else:
                logger.debug("  → 无临时文件需清理")
        except Exception as e:  # TODO: Narrow exception type
            logger.debug("  → 临时文件清理跳过: %s", e)

    async def _drain_circuit_breakers(self) -> None:
        """重置断路器状态"""
        try:
            from src.infra.circuit_breaker import _circuit_breakers
            for name, cb in _circuit_breakers.items():
                if hasattr(cb, "reset"):
                    cb.reset()
            logger.debug("  → 断路器已重置 (%d 个)", len(_circuit_breakers))
        except Exception:  # TODO: Narrow exception type
            pass

        # 同时清理健康检查跟踪的断路器状态
        try:
            from src.infra.health_check import _circuit_open_times
            _circuit_open_times.clear()
        except Exception:  # TODO: Narrow exception type
            pass

    def _drain_gua_registry(self) -> None:
        """清理八卦健康注册表"""
        try:
            from src.infra.health_check import _gua_registry
            _gua_registry.clear()
            logger.debug("  → 八卦注册表已清理")
        except Exception:  # TODO: Narrow exception type
            pass

    def _flush_logs(self) -> None:
        """刷新所有日志处理器"""
        try:
            for handler in logging.getLogger().handlers:
                handler.flush()
            logger.debug("  → 日志已刷新")
        except Exception:  # TODO: Narrow exception type
            pass


# ============================================================================
# 辅助：获取八卦实例
# ============================================================================

def _get_all_gua_instances() -> Dict[str, Any]:
    """获取所有八卦实例"""
    # 优先从健康检查注册表获取
    try:
        from src.infra.health_check import _gua_registry
        if _gua_registry:
            return dict(_gua_registry)
    except Exception:  # TODO: Narrow exception type
        pass
    return {}


# ============================================================================
# 信号处理注册
# ============================================================================

# 全局 shutdown handler 实例
_shutdown_handler: Optional[GracefulShutdown] = None


def get_shutdown_handler() -> Optional[GracefulShutdown]:
    """获取全局 shutdown handler"""
    return _shutdown_handler


def register_shutdown_handler(
    app: Any,
    fuxi_instance: Any = None,
    grace_period: float = DEFAULT_GRACE_PERIOD,
    cancel_timeout: float = DEFAULT_CANCEL_TIMEOUT,
    drain_timeout: float = DEFAULT_DRAIN_TIMEOUT,
) -> GracefulShutdown:
    """注册优雅关机 handler 到 FastAPI 应用

    同时注册 OS 信号处理。

    Args:
        app:             FastAPI 应用实例
        fuxi_instance:   伏羲生命体实例
        grace_period:    STOP 阶段等待秒数
        cancel_timeout:  CANCEL 阶段超时秒数
        drain_timeout:   DRAIN 阶段超时秒数

    Returns:
        GracefulShutdown 实例

    Usage::

        from src.bagua.shutdown import register_shutdown_handler

        async def _start_fuxi():
            fuxi = Fuxi()
            await fuxi.born()
            register_shutdown_handler(app, fuxi)
    """
    global _shutdown_handler

    handler = GracefulShutdown(
        fuxi_instance=fuxi_instance,
        app=app,
        grace_period=grace_period,
        cancel_timeout=cancel_timeout,
        drain_timeout=drain_timeout,
    )
    _shutdown_handler = handler

    # 注册到 FastAPI shutdown 事件
    @app.on_event("shutdown")
    async def _on_shutdown():
        logger.info("[Shutdown] FastAPI shutdown 事件触发")
        # 如果 fuxi 的 sleep 还没被调用，在这里兜底
        await handler.shutdown()

    # 注册 OS 信号处理（Unix/Linux 环境）
    _register_signal_handlers(handler)

    logger.info(
        "优雅关机 handler 已注册 — 超时配置: STOP=%.1fs, CANCEL=%.1fs, DRAIN=%.1fs",
        grace_period, cancel_timeout, drain_timeout,
    )

    return handler


def _register_signal_handlers(handler: GracefulShutdown) -> None:
    """注册 OS 信号处理器"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        # 无事件循环（测试/同步环境），跳过
        logger.debug("无事件循环，跳过 OS 信号注册")
        return

    def _signal_handler():
        logger.info("收到终止信号，触发优雅关机...")
        asyncio.ensure_future(handler.shutdown())

    try:
        loop.add_signal_handler(SIGTERM, _signal_handler)
        loop.add_signal_handler(SIGINT, _signal_handler)
        logger.debug("OS 信号处理已注册 (SIGTERM, SIGINT)")
    except NotImplementedError:
        # Windows 不支持 add_signal_handler
        logger.debug("当前平台不支持 add_signal_handler (Windows)")
        # 在 Windows 上，uvicorn 会自行处理 SIGINT/SIGTERM
    except Exception as e:  # TODO: Narrow exception type
        logger.debug("信号注册跳过: %s", e)
