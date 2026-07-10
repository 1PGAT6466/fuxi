"""
伏羲 v1.44 — 核心启动/停止逻辑
=============================
从 server.py 拆分的 Fuxi 生命体管理: 启动、八卦注册、关机。
"""
import os
import logging
# REMOVED: unused import - Path
from typing import Any

from fastapi import FastAPI

_DEFAULT_ENGINE: str = os.getenv("FUXI_ENGINE", "v2").lower()
_DEFAULT_INTENT_MODE: str = os.getenv("FUXI_INTENT_MODE", "rule_based").lower()
_fuxi_instance = None


def get_fuxi_instance():
    """获取当前 Fuxi 实例（可能为 None）"""
    return _fuxi_instance


async def start_fuxi(app: FastAPI) -> None:
    """启动伏羲生命体 — v2.1 八卦体系

    引擎路由：
      - v2（默认）: 八卦 QianGua + IntentBus
      - v1: 旧版 hypothalamus.fuxi.Fuxi（保留兼容）
    """
    global _fuxi_instance
    import time as _time
    engine = os.getenv("FUXI_ENGINE", "v2").lower()
    intent_mode = os.getenv("FUXI_INTENT_MODE", "rule_based").lower()

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

        _register_shutdown_handler(app)

    except ImportError as e:
        logging.getLogger("server").critical(f"[Fuxi] 无法导入伏羲模块，服务无法启动: {e}", exc_info=True)
        raise
    except (RuntimeError, ValueError, OSError, AttributeError) as e:
        logging.getLogger("server").error(f"[Fuxi] 启动失败: {e}", exc_info=True)
        # 不阻止服务器启动，部分功能不可用


async def stop_fuxi(app: FastAPI) -> None:
    """休眠伏羲 — v2.1"""
    global _fuxi_instance
    engine = getattr(app.state, "engine", "v2")
    if _fuxi_instance:
        if engine == "v2":
            _fuxi_instance.stop()
            logging.getLogger("server").info("[Fuxi] 八卦体系已停止 ☰")
        else:
            await _fuxi_instance.sleep()
            logging.getLogger("server").info("[Fuxi] 伏羲已休眠")


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
