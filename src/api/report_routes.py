"""
报告生成 API 路由 (Report Routes)
===================================
伏羲自运转 Phase 3 — 报告管理 API：
  - GET  /api/ops/reports                — 获取报告列表
  - GET  /api/ops/reports/{report_id}    — 获取报告详情
  - POST /api/ops/reports/generate       — 手动生成报告
  - GET  /api/ops/reports/templates      — 获取报告模板
  - GET  /api/ops/reports/{report_id}/content — 获取报告内容
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# v2.2 安全修复: 报告管理端点要求管理员认证
from src.auth.auth_middleware import require_role_dep

logger = logging.getLogger("fuxi.reporter.api")

router = APIRouter(
    prefix="/api/ops/reports",
    tags=["报告管理"],
    dependencies=[Depends(require_role_dep("admin"))],
)


def _get_generator():
    """延迟获取报告生成器实例"""
    from src.autonomous.reporter.generator import get_report_generator

    return get_report_generator()


class ReportGenerateRequest(BaseModel):
    """手动生成报告请求"""

    report_type: str = "daily"  # daily | weekly
    template_name: Optional[str] = None


@router.get("")
async def list_reports(
    report_type: Optional[str] = Query(None, description="报告类型: daily | weekly"),
    limit: int = Query(default=50, ge=1, le=200, description="返回数量"),
    offset: int = Query(default=0, ge=0, description="偏移量"),
):
    """获取报告列表"""
    generator = _get_generator()
    result = generator.list_reports(report_type, limit, offset)
    return {
        "status": "ok",
        **result,
    }


@router.get("/templates")
async def get_templates() -> JSONResponse:
    """获取可用报告模板"""
    generator = _get_generator()
    templates = generator.get_available_templates()
    return {
        "status": "ok",
        "templates": [{"name": name, "description": desc} for name, desc in templates.items()],
        "total": len(templates),
    }


@router.post("/generate")
async def generate_report(request: ReportGenerateRequest) -> JSONResponse:
    """手动生成报告"""
    generator = _get_generator()

    if request.report_type not in ("daily", "weekly"):
        raise HTTPException(status_code=400, detail=f"无效的报告类型: {request.report_type}，支持 daily 和 weekly")

    result = await generator.generate(
        report_type=request.report_type,
        template_name=request.template_name,
    )

    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result.get("message", "报告生成失败"))

    return result


@router.get("/{report_id}")
async def get_report(report_id: str) -> JSONResponse:
    """获取报告详情"""
    generator = _get_generator()
    report = generator.get_report(report_id)

    if not report:
        raise HTTPException(status_code=404, detail=f"报告不存在: {report_id}")

    return {
        "status": "ok",
        "report": report,
    }


@router.get("/{report_id}/content")
async def get_report_content(
    report_id: str,
    format: str = Query(default="markdown", description="格式: markdown | html"),
):
    """获取报告内容（Markdown 或 HTML）"""
    generator = _get_generator()

    if format not in ("markdown", "html"):
        raise HTTPException(status_code=400, detail=f"无效的格式: {format}，支持 markdown 和 html")

    content = await generator.get_report_content(report_id, format)

    if content is None:
        raise HTTPException(status_code=404, detail=f"报告内容不存在: {report_id}")

    if format == "html":
        from fastapi.responses import HTMLResponse

        return HTMLResponse(content=content)

    return {
        "status": "ok",
        "report_id": report_id,
        "format": format,
        "content": content,
    }
