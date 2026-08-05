"""
伏羲 v1.44 — Feature Flags API 模块

实现：
- GET /api/feature-flags - 获取功能开关
- PUT /api/feature-flags - 更新功能开关
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from src.api.response import error, server_error, success
from src.auth.rbac import require_role

logger = logging.getLogger("api.feature_flags")

router = APIRouter()


def _get_feature_flags_file() -> Path:
    """获取功能开关文件路径"""
    from src.config import DATA_DIR

    return Path(DATA_DIR) / "feature_flags.json"


@router.get("/api/feature-flags")
@require_role("user")
async def get_feature_flags(request: Request):
    """获取功能开关"""
    try:
        feature_flags_file = _get_feature_flags_file()

        feature_flags = {}
        if feature_flags_file.exists():
            content = feature_flags_file.read_text(encoding="utf-8-sig")
            if content.strip():
                feature_flags = json.loads(content)

        return success(data=feature_flags)
    except Exception as e:
        logger.error(f"获取功能开关失败: {e}")
        return server_error(detail=str(e))


@router.put("/api/feature-flags")
@require_role("admin")
async def update_feature_flags(request: Request):
    """更新功能开关"""
    try:
        body = await request.json()

        feature_flags_file = _get_feature_flags_file()

        # 读取现有功能开关
        feature_flags = {}
        if feature_flags_file.exists():
            content = feature_flags_file.read_text(encoding="utf-8-sig")
            if content.strip():
                feature_flags = json.loads(content)

        # 更新功能开关
        feature_flags.update(body)

        # 保存功能开关
        feature_flags_file.write_text(json.dumps(feature_flags, ensure_ascii=False, indent=2), encoding="utf-8")

        return success(data=feature_flags, message="功能开关已更新")
    except Exception as e:
        logger.error(f"更新功能开关失败: {e}")
        return server_error(detail=str(e))
