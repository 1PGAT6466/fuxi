"""服务市场 API — 外部插件聚合"""

import logging

from fastapi import APIRouter, Body, Query
from src.services.plugin_aggregator import aggregator

logger = logging.getLogger("api.market")

router = APIRouter(prefix="/api/market", tags=["market"])


# 全局缓存
_market_cache = {"data": None, "time": 0}
_CACHE_TTL = 300  # 5分钟缓存


@router.get("/services")
async def get_market_services(
    category: str = Query("", description="分类筛选"),
    search: str = Query("", description="搜索关键词"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """获取服务市场列表（外部插件聚合）"""
    import time

    # 检查缓存
    now = time.time()
    if _market_cache["data"] and now - _market_cache["time"] < _CACHE_TTL:
        plugins = _market_cache["data"]
    else:
        plugins = await aggregator.get_all_plugins(category=category, search=search)
        _market_cache["data"] = plugins
        _market_cache["time"] = now

    # 分页
    start = (page - 1) * page_size
    end = start + page_size
    page_items = plugins[start:end]

    return {
        "items": [
            {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "author": p.author,
                "category": p.category,
                "source": p.source,
                "version": p.version,
                "icon": p.icon,
                "install_url": p.install_url,
                "homepage": p.homepage,
                "downloads": p.downloads,
                "rating": p.rating,
                "tags": p.tags,
                "installed": p.installed,
            }
            for p in page_items
        ],
        "total": len(plugins),
        "page": page,
        "page_size": page_size,
    }


@router.get("/services/{service_id:path}")
async def get_market_service(service_id: str):
    """获取单个服务详情"""
    # 先从缓存获取
    if service_id in aggregator._plugin_cache:
        p = aggregator._plugin_cache[service_id]
        return {
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "author": p.author,
            "category": p.category,
            "source": p.source,
            "version": p.version,
            "icon": p.icon,
            "install_url": p.install_url,
            "homepage": p.homepage,
            "downloads": p.downloads,
            "rating": p.rating,
            "tags": p.tags,
            "installed": p.installed,
        }

    # 从全量列表查找
    plugins = await aggregator.get_all_plugins()
    for p in plugins:
        if p.id == service_id:
            return {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "author": p.author,
                "category": p.category,
                "source": p.source,
                "version": p.version,
                "icon": p.icon,
                "install_url": p.install_url,
                "homepage": p.homepage,
                "downloads": p.downloads,
                "rating": p.rating,
                "tags": p.tags,
                "installed": p.installed,
            }
    return None


# 已安装服务存储（模拟）
_installed_services: dict = {}


@router.get("/installed")
async def get_installed_services():
    """获取已安装的服务列表"""
    items = list(_installed_services.values())
    return {"items": items, "total": len(items)}


@router.post("/install")
async def install_service(data: dict = Body(...)):
    """安装服务"""
    service_id = data.get("service_id", "")
    if not service_id:
        return {"success": False, "error": "缺少 service_id"}

    # 从缓存查找插件
    plugin = None
    if service_id in aggregator._plugin_cache:
        plugin = aggregator._plugin_cache[service_id]
    else:
        # 缓存没有，尝试从全量列表查找（会触发缓存加载）
        plugins = await aggregator.get_all_plugins()
        for p in plugins:
            if p.id == service_id:
                plugin = p
                break

    if not plugin:
        return {"success": False, "error": f"服务 {service_id} 不存在"}

    # 模拟安装
    _installed_services[service_id] = {
        "id": plugin.id,
        "name": plugin.name,
        "description": plugin.description,
        "author": plugin.author,
        "category": plugin.category,
        "source": plugin.source,
        "version": plugin.version,
        "icon": plugin.icon,
        "install_url": plugin.install_url,
        "homepage": plugin.homepage,
        "installed": True,
        "installed_at": "2026-07-16T13:43:00Z",
    }

    logger.info(f"[Market] 安装服务: {service_id}")
    return {"success": True, "message": f"服务 {plugin.name} 安装成功"}


@router.post("/uninstall")
async def uninstall_service(data: dict = Body(...)):
    """卸载服务"""
    service_id = data.get("service_id", "")
    if not service_id:
        return {"success": False, "error": "缺少 service_id"}

    if service_id in _installed_services:
        del _installed_services[service_id]
        logger.info(f"[Market] 卸载服务: {service_id}")
        return {"success": True, "message": f"服务 {service_id} 卸载成功"}

    return {"success": False, "error": f"服务 {service_id} 未安装"}


@router.get("/categories")
async def get_categories():
    """获取可用分类"""
    return {
        "categories": [
            {"key": "ai", "label": "AI/ML"},
            {"key": "database", "label": "数据库"},
            {"key": "ui", "label": "UI 组件"},
            {"key": "tool", "label": "开发工具"},
        ]
    }
