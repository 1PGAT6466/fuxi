"""
server.py — DXF看图服务入口
服务生命周期管理：启动、停止、路由注册
"""

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter

logger = logging.getLogger("services.dxf-viewer.server")

_service_running = False
_router: Optional[APIRouter] = None


def get_router() -> APIRouter:
    global _router
    if _router is None:
        from src.services.dxf_viewer.api import router
        _router = router
    return _router


def start_service() -> None:
    global _service_running
    if _service_running:
        logger.warning("DXF viewer service already running")
        return

    try:
        from src.services.dxf_viewer.parser import EZDXF_AVAILABLE
        if not EZDXF_AVAILABLE:
            logger.warning(
                "ezdxf not installed — service will have limited functionality"
            )

        Path("data/services/dxf-viewer").mkdir(parents=True, exist_ok=True)
        _service_running = True
        logger.info("DXF viewer service started")

    except Exception as e:
        logger.error(f"Failed to start DXF viewer service: {e}")
        raise


def stop_service() -> None:
    global _service_running
    if not _service_running:
        return

    _service_running = False
    logger.info("DXF viewer service stopped")
