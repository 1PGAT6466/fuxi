"""
api.py — 平台 API 路由
注册平台级端点
"""
import logging
from fastapi import FastAPI

from .registry import get_registry
from .gateway import get_gateway

logger = logging.getLogger("platform.api")


def register_platform_routes(app: FastAPI) -> None:
    registry = get_registry()
    gateway = get_gateway(registry)
    app.include_router(gateway.router)
    logger.info("Platform routes registered")
