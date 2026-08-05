"""
伏羲插件系统 Phase 3 API
全自动集成管线

作者: AI助手
日期: 2026-07-17
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

# v2.2 安全修复: 插件系统端点要求管理员认证
from src.auth.auth_middleware import require_role_dep

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/plugins/phase3",
    tags=["插件系统 Phase 3"],
    dependencies=[Depends(require_role_dep("admin"))],
)


# ============ 请求/响应模型 ============


class FullPipelineRequest(BaseModel):
    """全自动集成请求"""

    plugin_path: str
    manifest: Dict[str, Any]
    skip_sandbox: bool = False
    auto_confirm: bool = True


# ============ API 端点 ============


@router.post("/pipeline")
async def run_full_pipeline(request: FullPipelineRequest):
    """
    运行完整集成管线

    全自动流程:
    1. 验证 manifest
    2. 安装插件
    3. 沙箱验证（可选）
    4. 分析插件
    5. 生成集成代码
    6. 执行集成
    7. 激活插件
    8. 健康检查
    """
    try:
        from src.core.plugin_auto_pipeline import PluginAutoPipeline, generate_pipeline_report

        pipeline = PluginAutoPipeline()
        result = pipeline.run_full_pipeline(
            plugin_path=request.plugin_path,
            manifest=request.manifest,
            skip_sandbox=request.skip_sandbox,
            auto_confirm=request.auto_confirm,
        )

        report = generate_pipeline_report(result)

        return {
            "success": result.success,
            "plugin_name": result.plugin_name,
            "total_duration_ms": result.total_duration_ms,
            "integration_id": result.integration_id,
            "error": result.error,
            "report": report,
            "steps": [
                {"name": s.name, "status": s.status, "duration_ms": s.duration_ms, "error": s.error}
                for s in result.steps
            ],
        }

    except Exception as e:
        logger.error(f"管线执行失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def get_integration_history(limit: int = 50):
    """获取集成历史"""
    try:
        from src.core.plugin_manager import get_plugin_manager

        pm = get_plugin_manager()
        plugins = pm.list_plugins()

        return {
            "plugins": [
                {
                    "name": p.get("name"),
                    "version": p.get("version"),
                    "type": p.get("type"),
                    "status": p.get("status"),
                    "installed_at": p.get("installed_at"),
                    "updated_at": p.get("updated_at"),
                }
                for p in plugins[:limit]
            ],
            "count": len(plugins),
        }

    except Exception as e:
        logger.error(f"获取历史失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_integration_stats():
    """获取集成统计"""
    try:
        from src.core.plugin_manager import get_plugin_manager

        pm = get_plugin_manager()
        all_plugins = pm.list_plugins()

        # 统计各状态插件数量
        status_counts = {}
        type_counts = {}

        for p in all_plugins:
            status = p.get("status", "unknown")
            ptype = p.get("type", "unknown")

            status_counts[status] = status_counts.get(status, 0) + 1
            type_counts[ptype] = type_counts.get(ptype, 0) + 1

        return {"total_plugins": len(all_plugins), "by_status": status_counts, "by_type": type_counts}

    except Exception as e:
        logger.error(f"获取统计失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
