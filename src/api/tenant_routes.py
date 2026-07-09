"""
tenant_routes.py — 租户管理 API
================================
v1.44 Phase 1: 多租户支持

端点：
  GET    /api/admin/tenants          — 列出所有租户
  POST   /api/admin/tenants          — 创建租户
  GET    /api/admin/tenants/{id}     — 获取租户详情
  PUT    /api/admin/tenants/{id}     — 更新租户
  DELETE /api/admin/tenants/{id}     — 删除租户
"""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging

from src.api.auth import require_admin
from src.auth.tenant import get_tenant_manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["租户管理"])


class CreateTenantRequest(BaseModel):
    tenant_id: str
    name: str
    description: str = ""
    settings: Optional[Dict[str, Any]] = None


class UpdateTenantRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    settings: Optional[Dict[str, Any]] = None


@router.get("/api/admin/tenants", dependencies=[Depends(require_admin)])
async def list_tenants(request: Request = None):
    """列出所有租户"""
    try:
        tm = get_tenant_manager()
        include_inactive = request.query_params.get("include_inactive", "false").lower() == "true"
        tenants = tm.list_tenants(include_inactive=include_inactive)

        _wants_v2 = request and (
            request.query_params.get("format") == "v2"
            or request.headers.get("X-API-Format", "").lower() == "v2"
        )
        if _wants_v2:
            from src.api.response import success
            return success(data={"tenants": tenants, "total": len(tenants)}, message="租户列表")
        return {"ok": True, "tenants": tenants, "total": len(tenants)}
    except Exception as e:
        logger.exception(f"list_tenants 失败: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})


@router.post("/api/admin/tenants", dependencies=[Depends(require_admin)])
async def create_tenant(body: CreateTenantRequest, request: Request = None):
    """创建租户"""
    try:
        tm = get_tenant_manager()
        tenant = tm.create_tenant(
            tenant_id=body.tenant_id,
            name=body.name,
            description=body.description,
            settings=body.settings,
        )

        _wants_v2 = request and (
            request.query_params.get("format") == "v2"
            or request.headers.get("X-API-Format", "").lower() == "v2"
        )
        if _wants_v2:
            from src.api.response import success
            return success(data=tenant.to_dict(), message=f"租户 {body.name} 创建成功")
        return {"ok": True, "tenant": tenant.to_dict()}
    except ValueError as e:
        return JSONResponse(status_code=400, content={"error": "参数错误", "detail": str(e)})
    except Exception as e:
        logger.exception(f"create_tenant 失败: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})


@router.get("/api/admin/tenants/{tenant_id}", dependencies=[Depends(require_admin)])
async def get_tenant(tenant_id: str, request: Request = None):
    """获取租户详情"""
    try:
        tm = get_tenant_manager()
        tenant = tm.get_tenant(tenant_id)
        if not tenant:
            return JSONResponse(status_code=404, content={"error": "租户未找到", "detail": f"租户 {tenant_id} 不存在"})

        _wants_v2 = request and (
            request.query_params.get("format") == "v2"
            or request.headers.get("X-API-Format", "").lower() == "v2"
        )
        if _wants_v2:
            from src.api.response import success
            return success(data=tenant.to_dict(), message="租户详情")
        return {"ok": True, "tenant": tenant.to_dict()}
    except Exception as e:
        logger.exception(f"get_tenant 失败: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})


@router.put("/api/admin/tenants/{tenant_id}", dependencies=[Depends(require_admin)])
async def update_tenant(tenant_id: str, body: UpdateTenantRequest, request: Request = None):
    """更新租户"""
    try:
        tm = get_tenant_manager()
        tenant = tm.update_tenant(
            tenant_id=tenant_id,
            name=body.name,
            description=body.description,
            is_active=body.is_active,
            settings=body.settings,
        )
        if not tenant:
            return JSONResponse(status_code=404, content={"error": "租户未找到", "detail": f"租户 {tenant_id} 不存在"})

        _wants_v2 = request and (
            request.query_params.get("format") == "v2"
            or request.headers.get("X-API-Format", "").lower() == "v2"
        )
        if _wants_v2:
            from src.api.response import success
            return success(data=tenant.to_dict(), message=f"租户 {tenant_id} 已更新")
        return {"ok": True, "tenant": tenant.to_dict()}
    except Exception as e:
        logger.exception(f"update_tenant 失败: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})


@router.delete("/api/admin/tenants/{tenant_id}", dependencies=[Depends(require_admin)])
async def delete_tenant(tenant_id: str, request: Request = None):
    """删除租户"""
    try:
        tm = get_tenant_manager()
        success = tm.delete_tenant(tenant_id)
        if not success:
            return JSONResponse(
                status_code=400,
                content={"error": "无法删除租户", "detail": "租户不存在或为默认租户"}
            )

        _wants_v2 = request and (
            request.query_params.get("format") == "v2"
            or request.headers.get("X-API-Format", "").lower() == "v2"
        )
        if _wants_v2:
            from src.api.response import success as resp_success
            return resp_success(data=None, message=f"租户 {tenant_id} 已删除")
        return {"ok": True, "message": f"租户 {tenant_id} 已删除"}
    except Exception as e:
        logger.exception(f"delete_tenant 失败: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})
