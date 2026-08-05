"""
伏羲插件系统 Phase 2 API
半自动集成执行

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
    prefix="/api/plugins/phase2",
    tags=["插件系统 Phase 2"],
    dependencies=[Depends(require_role_dep("admin"))],
)


# ============ 请求/响应模型 ============


class ExecuteIntegrationRequest(BaseModel):
    """执行集成请求"""

    plugin_name: str
    plugin_path: str
    auto_confirm: bool = False


class RollbackRequest(BaseModel):
    """回滚请求"""

    backup_id: str
    plugin_name: str


# ============ API 端点 ============


@router.post("/execute")
async def execute_integration(request: ExecuteIntegrationRequest):
    """
    执行插件集成

    流程:
    1. 分析插件
    2. 生成集成代码
    3. 创建备份
    4. 执行集成
    5. 返回结果
    """
    try:
        # Step 1: 分析插件（读取 manifest.json 获取完整信息）
        import json
        from pathlib import Path

        from src.core.plugin_analyzer import PluginAnalyzer
        from src.core.plugin_auto_integrator import PluginAutoIntegrator, generate_integration_report
        from src.core.plugin_integrator import PluginIntegrator

        manifest_path = Path(request.plugin_path) / "manifest.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        else:
            manifest = {"name": request.plugin_name, "type": "api"}

        analyzer = PluginAnalyzer()
        analysis = analyzer.analyze_plugin(request.plugin_path, manifest)

        # Step 2: 生成集成代码
        integrator = PluginIntegrator()
        plan = integrator.generate_integration_plan(analysis)
        codes = integrator.generate_integration_code(plan, request.plugin_path)

        # 转换为字典格式
        codes_dict = [
            {
                "file_path": c.file_path,
                "content": c.content,
                "action": c.action,
                "description": c.description,
                "requires_confirmation": c.requires_confirmation,
            }
            for c in codes
        ]

        # Step 3: 执行集成
        auto_integrator = PluginAutoIntegrator()
        result = auto_integrator.execute_integration(
            plugin_name=request.plugin_name,
            plugin_path=request.plugin_path,
            codes=codes_dict,
            auto_confirm=request.auto_confirm,
        )

        # Step 4: 生成报告
        report = generate_integration_report(result)

        return {
            "success": result.success,
            "plugin_name": result.plugin_name,
            "steps_total": result.steps_total,
            "steps_completed": result.steps_completed,
            "steps_failed": result.steps_failed,
            "steps_skipped": result.steps_skipped,
            "backup_id": result.backup_id,
            "error": result.error,
            "report": report,
            "steps": [
                {"name": s.name, "action": s.action, "target_file": s.target_file, "status": s.status, "error": s.error}
                for s in result.steps
            ],
        }

    except Exception as e:
        logger.error(f"集成执行失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rollback")
async def rollback_integration(request: RollbackRequest):
    """
    回滚集成

    使用备份ID恢复到集成前的状态
    """
    try:
        from src.core.plugin_auto_integrator import PluginAutoIntegrator

        integrator = PluginAutoIntegrator()
        success = integrator.rollback(request.backup_id, request.plugin_name)

        return {
            "success": success,
            "backup_id": request.backup_id,
            "plugin_name": request.plugin_name,
            "message": "回滚成功" if success else "回滚失败",
        }

    except Exception as e:
        logger.error(f"回滚失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{plugin_name}")
async def get_integration_status(plugin_name: str):
    """获取插件集成状态"""
    try:
        from src.core.plugin_manager import get_plugin_manager

        pm = get_plugin_manager()
        plugin = pm.get_plugin(plugin_name)

        if not plugin:
            raise HTTPException(status_code=404, detail=f"插件 {plugin_name} 未找到")

        return {
            "plugin_name": plugin_name,
            "status": plugin.get("status", "unknown"),
            "version": plugin.get("version"),
            "type": plugin.get("type"),
            "installed_at": plugin.get("installed_at"),
            "updated_at": plugin.get("updated_at"),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取状态失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def list_integrated_plugins():
    """列出所有已集成的插件"""
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
                }
                for p in plugins
            ],
            "count": len(plugins),
        }

    except Exception as e:
        logger.error(f"列出插件失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
