"""
伏羲插件系统 Phase 1 API
提供插件分析、集成、沙箱验证等接口

作者: AI助手
日期: 2026-07-17
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel

# v2.2 安全修复: 插件系统端点要求管理员认证
from src.auth.auth_middleware import require_role_dep

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/plugins/phase1",
    tags=["插件系统 Phase 1"],
    dependencies=[Depends(require_role_dep("admin"))],
)


# ============ 请求/响应模型 ============


class AnalyzeRequest(BaseModel):
    """分析请求"""

    plugin_path: str
    manifest: Dict[str, Any]


class IntegrateRequest(BaseModel):
    """集成请求"""

    plugin_name: str
    plugin_path: str
    auto_confirm: bool = False


class SandboxRequest(BaseModel):
    """沙箱验证请求"""

    plugin_path: str
    manifest: Dict[str, Any]


# ============ API 端点 ============


@router.post("/analyze")
async def analyze_plugin(request: AnalyzeRequest):
    """分析插件"""
    from src.core.plugin_analyzer import PluginAnalyzer

    analyzer = PluginAnalyzer()
    result = analyzer.analyze_plugin(request.plugin_path, request.manifest)

    return {
        "plugin_name": result.plugin_name,
        "plugin_type": result.plugin_type,
        "symbols_count": len(result.symbols),
        "integration_points": len(result.integration_points),
        "conflicts": len(result.conflicts),
        "complexity_score": result.complexity_score,
        "risk_level": result.risk_level,
        "recommendations": result.recommendations,
        "integration_points_detail": [
            {
                "type": p.type,
                "name": p.name,
                "description": p.description,
                "confidence": p.confidence,
                "action": p.action,
            }
            for p in result.integration_points
        ],
        "conflicts_detail": [
            {"type": c.type, "severity": c.severity, "description": c.description, "resolution": c.resolution}
            for c in result.conflicts
        ],
    }


@router.post("/integrate")
async def generate_integration(request: IntegrateRequest):
    """生成集成代码"""
    try:
        from src.core.plugin_analyzer import PluginAnalyzer
        from src.core.plugin_integrator import PluginIntegrator, generate_integration_summary

        # 先分析
        analyzer = PluginAnalyzer()
        analysis = analyzer.analyze_plugin(request.plugin_path, {"name": request.plugin_name})

        # 生成集成计划
        integrator = PluginIntegrator()
        plan = integrator.generate_integration_plan(analysis)

        # 生成代码
        codes = integrator.generate_integration_code(plan, request.plugin_path)

        # 生成摘要
        summary = generate_integration_summary(plan, codes)

        return {
            "plugin_name": request.plugin_name,
            "plan": {
                "steps": plan.steps,
                "estimated_time": plan.estimated_time,
                "risk_level": plan.risk_level,
                "requires_confirmation": plan.requires_confirmation,
            },
            "codes": [
                {
                    "file_path": c.file_path,
                    "content": c.content,
                    "action": c.action,
                    "description": c.description,
                    "requires_confirmation": c.requires_confirmation,
                }
                for c in codes
            ],
            "summary": summary,
        }
    except Exception as e:
        logger.error(f"集成代码生成失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sandbox")
async def sandbox_validate(request: SandboxRequest):
    """沙箱验证"""
    from src.core.plugin_sandbox import PluginSandbox, generate_sandbox_report

    sandbox = PluginSandbox()
    result = sandbox.validate(request.plugin_path, request.manifest)

    report = generate_sandbox_report(result)

    return {
        "plugin_name": result.plugin_name,
        "passed": result.passed,
        "tests_passed": result.tests_passed,
        "tests_failed": result.tests_failed,
        "tests_total": result.tests_total,
        "security_issues": result.security_issues,
        "performance_issues": result.performance_issues,
        "errors": result.errors,
        "warnings": result.warnings,
        "execution_time": result.execution_time,
        "report": report,
    }


@router.post("/index/build")
async def build_code_index(force: bool = False):
    """构建代码索引（后台异步执行）"""
    import threading

    from src.core.plugin_code_index import CodeIndex

    def _build():
        try:
            index = CodeIndex()
            index.build_index(force=force)
        except Exception as e:
            logger.error(f"代码索引构建失败: {e}")

    # 后台线程执行
    thread = threading.Thread(target=_build, daemon=True)
    thread.start()

    return {"status": "started", "message": "代码索引构建已在后台启动，完成后可通过 /index/search 查询"}


@router.get("/index/search")
async def search_code_index(query: str, top_k: int = 10):
    """搜索代码索引"""
    from src.core.plugin_code_index import CodeIndex

    index = CodeIndex()
    results = index.search(query, top_k=top_k)

    return {"query": query, "results": results, "count": len(results)}


@router.get("/index/symbol/{symbol_name}")
async def get_symbol_info(symbol_name: str):
    """获取符号信息"""
    from src.core.plugin_code_index import CodeIndex

    index = CodeIndex()
    result = index.get_symbol_info(symbol_name)

    if not result:
        raise HTTPException(status_code=404, detail=f"符号 {symbol_name} 未找到")

    return result
