"""
server.py — 数据分析服务入口
服务生命周期管理：启动、停止、路由注册
"""

import logging
from typing import Optional

from fastapi import APIRouter

logger = logging.getLogger("services.data-analytics.server")

_service_running = False
_router: Optional[APIRouter] = None


def get_router() -> APIRouter:
    global _router
    if _router is None:
        from src.services.data_analytics.routes import router
        _router = router
    return _router


def start_service() -> None:
    global _service_running
    if _service_running:
        logger.warning("Data analytics service already running")
        return

    try:
        _service_running = True
        logger.info("Data analytics service started")

    except Exception as e:
        logger.error(f"Failed to start data analytics service: {e}")
        raise


def stop_service() -> None:
    global _service_running
    if not _service_running:
        return

    _service_running = False
    logger.info("Data analytics service stopped")
