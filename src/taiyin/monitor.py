"""
monitor.py — 太阴·监控
setup_error_handlers
"""
import logging
from typing import Dict

logger = logging.getLogger("taiyin.monitor")


def setup_error_handlers(app):
    """设置错误处理器"""
    try:
        from fastapi import FastAPI, Request
        from fastapi.responses import JSONResponse

        @app.exception_handler(Exception)
        # FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
        async def global_exception_handler(request: Request, exc: Exception):
            logger.error(f"[Monitor] 未处理异常: {exc}")
            return JSONResponse(
                status_code=500,
                content={"error": "内部服务器错误", "detail": str(exc)[:200]},
            )

        @app.exception_handler(404)
        # FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
        async def not_found_handler(request: Request, exc):
            return JSONResponse(
                status_code=404,
                content={"error": "未找到", "path": str(request.url)},
            )

        logger.info("[Monitor] 错误处理器已设置")
    except ImportError:
        logger.warning("[Monitor] FastAPI未安装，跳过错误处理器设置")
