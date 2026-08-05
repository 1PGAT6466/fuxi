"""
伏羲插件管理 API
提供插件的安装、激活、停用、卸载等管理接口

作者: AI助手
日期: 2026-07-16
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from pydantic import BaseModel

# v2.2 安全修复: 插件管理端点要求管理员认证
from src.auth.auth_middleware import require_role_dep

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/plugins",
    tags=["插件管理"],
    dependencies=[Depends(require_role_dep("admin"))],
)


# ============ 请求/响应模型 ============


class InstallRequest(BaseModel):
    """安装请求"""

    plugin_path: str  # 插件源目录路径
    manifest: Dict[str, Any]  # manifest.json 内容


class PluginResponse(BaseModel):
    """插件响应"""

    success: bool
    plugin: Optional[str] = None
    steps: List[Dict[str, Any]] = []
    error: Optional[str] = None


# ============ API 端点 ============


@router.get("/installed")
async def list_installed(request: Request, status: Optional[str] = None):
    """列出已安装的插件"""
    pm = request.app.state.plugin_manager
    plugins = pm.list_plugins(status)

    # 统一返回格式：默认返回 {success, data, message}
    from src.api.response import success

    return success(data={"plugins": plugins, "count": len(plugins)}, message="获取插件列表成功")


@router.get("/installed/{plugin_name}")
async def get_plugin(plugin_name: str, request: Request):
    """获取插件详情"""
    pm = request.app.state.plugin_manager
    plugin = pm.get_plugin(plugin_name)
    if not plugin:
        raise HTTPException(status_code=404, detail=f"插件 {plugin_name} 未找到")
    return plugin


@router.post("/install")
async def install_plugin(request: Request, body: InstallRequest):
    """安装插件"""
    from src.core.plugin_hooks import get_hook_manager

    pm = request.app.state.plugin_manager
    hm = get_hook_manager()

    # 执行 pre_install 钩子
    hm.execute_hook("pre_install", {"manifest": body.manifest})

    # 安装插件
    result = pm.install(body.plugin_path, body.manifest)

    if result["success"]:
        # 执行 post_install 钩子
        hm.execute_hook("post_install", {"manifest": body.manifest})

        # 触发事件
        hm.emit("plugin_installed", {"plugin": body.manifest["name"]})

    return result


@router.post("/activate/{plugin_name}")
async def activate_plugin(plugin_name: str, request: Request):
    """激活插件"""
    from src.core.plugin_hooks import get_hook_manager

    # 从 app.state 获取 plugin_manager（已绑定 app 实例）
    pm = request.app.state.plugin_manager
    hm = get_hook_manager()

    # 执行 pre_activate 钩子
    hm.execute_hook("pre_activate", {"plugin": plugin_name})

    # 激活插件（使用已绑定的 app）
    result = pm.activate(plugin_name)

    if result["success"]:
        # 执行 post_activate 钩子
        hm.execute_hook("post_activate", {"plugin": plugin_name})

        # 触发事件
        hm.emit("plugin_activated", {"plugin": plugin_name})

    return result


@router.post("/deactivate/{plugin_name}")
async def deactivate_plugin(plugin_name: str, request: Request):
    """停用插件"""
    from src.core.plugin_hooks import get_hook_manager
    from src.core.plugin_manager import get_plugin_manager

    pm = request.app.state.plugin_manager
    hm = get_hook_manager()

    # 执行 pre_deactivate 钩子
    hm.execute_hook("pre_deactivate", {"plugin": plugin_name})

    # 停用插件
    result = pm.deactivate(plugin_name)

    if result["success"]:
        # 执行 post_deactivate 钩子
        hm.execute_hook("post_deactivate", {"plugin": plugin_name})

        # 注销钩子和事件
        hm.unregister_hooks(plugin_name)
        hm.unsubscribe_all(plugin_name)

    return result


@router.post("/uninstall/{plugin_name}")
async def uninstall_plugin(plugin_name: str, request: Request, keep_data: bool = False):
    """卸载插件"""
    from src.core.plugin_hooks import get_hook_manager
    from src.core.plugin_manager import get_plugin_manager

    pm = request.app.state.plugin_manager
    hm = get_hook_manager()

    # 执行 pre_uninstall 钩子
    hm.execute_hook("pre_uninstall", {"plugin": plugin_name})

    # 卸载插件
    result = pm.uninstall(plugin_name, keep_data)

    if result["success"]:
        # 执行 post_uninstall 钩子
        hm.execute_hook("post_uninstall", {"plugin": plugin_name})

        # 注销所有钩子和事件
        hm.unregister_hooks(plugin_name)
        hm.unsubscribe_all(plugin_name)

    return result


@router.get("/health/{plugin_name}")
async def plugin_health(plugin_name: str, request: Request):
    """插件健康检查"""
    pm = request.app.state.plugin_manager
    return pm.health_check(plugin_name)


@router.get("/events/history")
async def event_history(limit: int = 100):
    """获取事件历史"""
    from src.core.plugin_hooks import get_hook_manager

    hm = get_hook_manager()
    return {"events": hm.get_event_history(limit)}


@router.get("/hooks")
async def list_hooks():
    """列出所有已注册的钩子"""
    from src.core.plugin_hooks import get_hook_manager

    hm = get_hook_manager()

    hooks = {}
    for hook_name in [
        "pre_install",
        "post_install",
        "pre_activate",
        "post_activate",
        "pre_deactivate",
        "post_deactivate",
        "pre_uninstall",
        "post_uninstall",
    ]:
        hooks[hook_name] = hm.get_hooks(hook_name)

    return {"hooks": hooks}


@router.get("/routes")
async def list_routes():
    """列出所有已注册的插件路由"""
    from src.core.plugin_hooks import get_route_registrar

    rr = get_route_registrar()
    return {"routes": rr.get_registered_routes()}
