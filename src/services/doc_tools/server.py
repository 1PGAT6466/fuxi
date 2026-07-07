"""
server.py — 文档工具服务入口
服务生命周期管理：启动、停止、路由注册
"""

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter

logger = logging.getLogger("services.doc-tools.server")

_service_running = False
_router: Optional[APIRouter] = None

# 临时文件目录
TEMP_DIR = Path("temp")


def get_router() -> APIRouter:
    global _router
    if _router is None:
        from src.services.doc_tools.routes import router
        _router = router
    return _router


def start_service() -> None:
    global _service_running
    if _service_running:
        logger.warning("文档工具服务已在运行中")
        return

    try:
        TEMP_DIR.mkdir(parents=True, exist_ok=True)

        # 检查依赖
        try:
            import pypdf
            logger.info(f"pypdf {pypdf.__version__} 可用")
        except ImportError:
            logger.warning("pypdf 未安装 — PDF 功能将受限")

        try:
            from PIL import Image
            logger.info(f"Pillow {Image.__version__} 可用")
        except ImportError:
            logger.warning("Pillow 未安装 — 图片功能将受限")

        try:
            import docx
            logger.info("python-docx 可用")
        except ImportError:
            logger.warning("python-docx 未安装 — DOCX 文本提取功能将受限")

        _service_running = True
        logger.info("文档工具服务已启动")

    except Exception as e:
        logger.error(f"文档工具服务启动失败: {e}")
        raise


def stop_service() -> None:
    global _service_running
    if not _service_running:
        return

    # 清理临时目录
    import shutil
    if TEMP_DIR.exists():
        try:
            shutil.rmtree(str(TEMP_DIR))
            logger.info("临时目录已清理")
        except Exception as e:
            logger.warning(f"清理临时目录失败: {e}")

    _service_running = False
    logger.info("文档工具服务已停止")
