"""
ai_tools/__init__.py — AI智能工具服务入口
导出 start_service / stop_service / get_router
"""

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter

logger = logging.getLogger("services.ai-tools")

_service_running = False
_router: Optional[APIRouter] = None


def get_router() -> APIRouter:
    """获取 AI 工具服务路由"""
    global _router
    if _router is None:
        from src.services.ai_tools.routes import router
        _router = router
    return _router


def start_service() -> None:
    """启动 AI 工具服务"""
    global _service_running
    if _service_running:
        logger.warning("AI 工具服务已在运行")
        return

    try:
        # 检查 LLM 环境变量
        import os
        api_key = os.getenv("MIMO_API_KEY") or os.getenv("SILICONFLOW_API_KEY")
        base_url = os.getenv("MIMO_BASE_URL") or os.getenv("SILICONFLOW_BASE_URL")
        if api_key:
            logger.info(f"LLM 配置已就绪: base_url={base_url or '(default)'}")
        else:
            logger.warning("未找到 MIMO_API_KEY 或 SILICONFLOW_API_KEY，LLM 调用将降级")

        # 确保数据目录存在
        Path("data/services/ai-tools").mkdir(parents=True, exist_ok=True)
        _service_running = True
        logger.info("AI 工具服务已启动")

    except Exception as e:  # TODO: Narrow exception type
        logger.error(f"AI 工具服务启动失败: {e}")
        raise


def stop_service() -> None:
    """停止 AI 工具服务"""
    global _service_running
    if not _service_running:
        return
    _service_running = False
    logger.info("AI 工具服务已停止")


__all__ = ["start_service", "stop_service", "get_router"]
