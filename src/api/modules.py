"""
统一功能模块管理 API
整合：内置服务 + 外部插件 + 功能开关
提供：列表、详情、启用/禁用、配置、使用入口
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger("api.modules")

router = APIRouter(prefix="/api/modules", tags=["功能模块"])

# ============ 数据存储 ============
DATA_DIR = Path(__file__).parent.parent.parent / "data"
MODULES_FILE = DATA_DIR / "enabled_modules.json"

# 内置服务定义
BUILTIN_SERVICES = [
    {
        "id": "ai-tools",
        "name": "AI 工具集",
        "icon": "🤖",
        "category": "ai",
        "type": "builtin",
        "description": "文本摘要、智能翻译、关键词提取、实体识别、文本分类",
        "version": "2.1.0",
        "endpoints": [
            {"path": "/api/ai/summarize", "method": "POST", "name": "文本摘要"},
            {"path": "/api/ai/translate", "method": "POST", "name": "智能翻译"},
            {"path": "/api/ai/keywords", "method": "POST", "name": "关键词提取"},
            {"path": "/api/ai/entities", "method": "POST", "name": "实体识别"},
            {"path": "/api/ai/classify", "method": "POST", "name": "文本分类"},
        ],
        "config_schema": {
            "default_source_lang": {"type": "string", "default": "zh", "description": "默认源语言"},
            "default_target_lang": {"type": "string", "default": "en", "description": "默认目标语言"},
        },
    },
    {
        "id": "data-analytics",
        "name": "数据分析",
        "icon": "📊",
        "category": "analytics",
        "type": "builtin",
        "description": "数据统计、趋势分析、报表生成",
        "version": "1.0.0",
        "endpoints": [
            {"path": "/api/analytics/overview", "method": "GET", "name": "数据概览"},
            {"path": "/api/analytics/trends", "method": "GET", "name": "趋势分析"},
        ],
        "config_schema": {},
    },
    {
        "id": "dxf-viewer",
        "name": "DXF 工程浏览器",
        "icon": "📐",
        "category": "engineering",
        "type": "builtin",
        "description": "DXF 图纸查看、标注、测量",
        "version": "1.0.0",
        "endpoints": [
            {"path": "/api/dxf/view", "method": "POST", "name": "查看图纸"},
            {"path": "/api/dxf/analyze", "method": "POST", "name": "分析图纸"},
        ],
        "config_schema": {},
    },
    {
        "id": "doc-tools",
        "name": "文档工具",
        "icon": "📄",
        "category": "document",
        "type": "builtin",
        "description": "文档解析、格式转换、内容提取",
        "version": "1.0.0",
        "endpoints": [
            {"path": "/api/docs/parse", "method": "POST", "name": "解析文档"},
            {"path": "/api/docs/convert", "method": "POST", "name": "格式转换"},
        ],
        "config_schema": {},
    },
    {
        "id": "semantic-search",
        "name": "语义搜索",
        "icon": "🔍",
        "category": "search",
        "type": "builtin",
        "description": "向量语义搜索，结果更精准",
        "version": "1.0.0",
        "endpoints": [
            {"path": "/api/search", "method": "GET", "name": "搜索"},
            {"path": "/api/search", "method": "POST", "name": "高级搜索"},
        ],
        "config_schema": {
            "top_k": {"type": "number", "default": 10, "description": "返回结果数"},
            "similarity_threshold": {"type": "number", "default": 0.7, "description": "相似度阈值"},
        },
    },
    {
        "id": "auto-index",
        "name": "自动索引",
        "icon": "⚡",
        "category": "automation",
        "type": "builtin",
        "description": "上传文档后自动触发向量化索引",
        "version": "1.0.0",
        "endpoints": [],
        "config_schema": {
            "auto_index_enabled": {"type": "boolean", "default": True, "description": "启用自动索引"},
        },
    },
    {
        "id": "wiki",
        "name": "公开 Wiki",
        "icon": "📚",
        "category": "knowledge",
        "type": "builtin",
        "description": "允许所有用户创建和编辑 Wiki 页面",
        "version": "1.0.0",
        "endpoints": [
            {"path": "/api/wiki", "method": "GET", "name": "Wiki 列表"},
            {"path": "/api/wiki", "method": "POST", "name": "创建 Wiki"},
        ],
        "config_schema": {
            "public_edit": {"type": "boolean", "default": False, "description": "允许公开编辑"},
        },
    },
    {
        "id": "auto-eval",
        "name": "自动评测",
        "icon": "📈",
        "category": "quality",
        "type": "builtin",
        "description": "每日定时运行 RAG 质量评测并生成报告",
        "version": "1.0.0",
        "endpoints": [
            {"path": "/api/evaluation/run", "method": "POST", "name": "运行评测"},
            {"path": "/api/evaluation/report", "method": "GET", "name": "评测报告"},
        ],
        "config_schema": {
            "schedule": {"type": "string", "default": "0 2 * * *", "description": "定时任务表达式"},
        },
    },
    {
        "id": "rate-limit",
        "name": "速率限制",
        "icon": "🚦",
        "category": "security",
        "type": "builtin",
        "description": "启用 API 请求速率限制，防止滥用",
        "version": "1.0.0",
        "endpoints": [],
        "config_schema": {
            "max_requests_per_minute": {"type": "number", "default": 60, "description": "每分钟最大请求数"},
        },
    },
    {
        "id": "advanced-cache",
        "name": "高级缓存",
        "icon": "💾",
        "category": "performance",
        "type": "builtin",
        "description": "启用 Redis 多级缓存策略",
        "version": "1.0.0",
        "endpoints": [],
        "config_schema": {
            "cache_ttl": {"type": "number", "default": 3600, "description": "缓存过期时间(秒)"},
        },
    },
    {
        "id": "ai-chat-v2",
        "name": "AI 对话 v2",
        "icon": "💬",
        "category": "ai",
        "type": "builtin",
        "description": "启用新版对话引擎，支持多轮上下文记忆",
        "version": "2.0.0",
        "endpoints": [
            {"path": "/api/chat", "method": "POST", "name": "对话"},
        ],
        "config_schema": {
            "memory_window": {"type": "number", "default": 10, "description": "记忆窗口大小"},
        },
    },
]


def _load_enabled_modules() -> Dict[str, Any]:
    """加载已启用的模块配置"""
    if MODULES_FILE.exists():
        try:
            return json.loads(MODULES_FILE.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"加载模块配置失败: {e}")
    return {}


def _save_enabled_modules(config: Dict[str, Any]) -> None:
    """保存已启用的模块配置"""
    MODULES_FILE.parent.mkdir(parents=True, exist_ok=True)
    MODULES_FILE.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")


# ============ API 端点 ============


@router.get("")
async def list_modules():
    """获取所有功能模块（内置 + 外部插件）"""
    enabled_config = _load_enabled_modules()

    # 内置服务
    modules = []
    for svc in BUILTIN_SERVICES:
        module = {**svc}
        module["enabled"] = enabled_config.get(svc["id"], {}).get("enabled", True)  # 默认启用
        module["config"] = enabled_config.get(svc["id"], {}).get("config", {})
        modules.append(module)

    # 外部插件
    try:
        from src.core.plugin_manager import get_plugin_manager

        pm = get_plugin_manager()
        plugins = pm.list_plugins()
        for p in plugins:
            modules.append(
                {
                    "id": p["name"],
                    "name": p.get("display_name", p["name"]),
                    "icon": "📦",
                    "category": "plugin",
                    "type": "plugin",
                    "description": p.get("description", ""),
                    "version": p["version"],
                    "endpoints": [
                        {"path": r["path"], "method": r["method"], "name": r.get("description", "")}
                        for r in p.get("manifest", {}).get("routes", [])
                    ],
                    "config_schema": p.get("manifest", {}).get("config_schema", {}),
                    "enabled": p["status"] == "active",
                    "config": p.get("config", {}),
                    "status": p["status"],
                }
            )
    except Exception as e:
        logger.warning(f"获取插件列表失败: {e}")

    return {
        "modules": modules,
        "total": len(modules),
        "categories": list(set(m["category"] for m in modules)),
    }


@router.get("/{module_id}")
async def get_module(module_id: str):
    """获取单个模块详情"""
    enabled_config = _load_enabled_modules()

    # 先查内置服务
    for svc in BUILTIN_SERVICES:
        if svc["id"] == module_id:
            module = {**svc}
            module["enabled"] = enabled_config.get(module_id, {}).get("enabled", True)
            module["config"] = enabled_config.get(module_id, {}).get("config", {})
            return module

    # 再查外部插件
    try:
        from src.core.plugin_manager import get_plugin_manager

        pm = get_plugin_manager()
        plugin = pm.get_plugin(module_id)
        if plugin:
            return {
                "id": plugin["name"],
                "name": plugin.get("display_name", plugin["name"]),
                "icon": "📦",
                "category": "plugin",
                "type": "plugin",
                "description": plugin.get("description", ""),
                "version": plugin["version"],
                "endpoints": [
                    {"path": r["path"], "method": r["method"], "name": r.get("description", "")}
                    for r in plugin.get("manifest", {}).get("routes", [])
                ],
                "config_schema": plugin.get("manifest", {}).get("config_schema", {}),
                "enabled": plugin["status"] == "active",
                "config": plugin.get("config", {}),
                "status": plugin["status"],
            }
    except Exception as e:
        logger.warning(f"获取插件详情失败: {e}")

    raise HTTPException(404, f"模块 {module_id} 不存在")


@router.put("/{module_id}/toggle")
async def toggle_module(module_id: str, data: dict = Body(...)):
    """启用/禁用模块"""
    enabled = data.get("enabled", True)
    enabled_config = _load_enabled_modules()

    # 检查是否是内置服务
    is_builtin = any(s["id"] == module_id for s in BUILTIN_SERVICES)

    if is_builtin:
        if module_id not in enabled_config:
            enabled_config[module_id] = {"enabled": enabled, "config": {}}
        else:
            enabled_config[module_id]["enabled"] = enabled
        _save_enabled_modules(enabled_config)
        return {"success": True, "message": f"模块 {module_id} 已{'启用' if enabled else '禁用'}"}

    # 外部插件：调用插件管理器
    try:
        from src.core.plugin_manager import get_plugin_manager

        pm = get_plugin_manager()

        if enabled:
            result = pm.activate(module_id)
        else:
            result = pm.deactivate(module_id)

        if result["success"]:
            return {"success": True, "message": f"插件 {module_id} 已{'激活' if enabled else '停用'}"}
        else:
            raise HTTPException(400, result["error"])
    except Exception as e:
        raise HTTPException(500, str(e))


@router.put("/{module_id}/config")
async def update_module_config(module_id: str, data: dict = Body(...)):
    """更新模块配置"""
    config = data.get("config", {})
    enabled_config = _load_enabled_modules()

    # 检查是否是内置服务
    is_builtin = any(s["id"] == module_id for s in BUILTIN_SERVICES)

    if is_builtin:
        if module_id not in enabled_config:
            enabled_config[module_id] = {"enabled": True, "config": config}
        else:
            enabled_config[module_id]["config"] = config
        _save_enabled_modules(enabled_config)
        return {"success": True, "message": f"模块 {module_id} 配置已更新"}

    # 外部插件：调用插件管理器
    try:
        from src.core.plugin_manager import get_plugin_manager

        pm = get_plugin_manager()
        pm.registry.update_config(module_id, config)
        return {"success": True, "message": f"插件 {module_id} 配置已更新"}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/{module_id}/health")
async def check_module_health(module_id: str):
    """检查模块健康状态"""
    # 检查是否是内置服务
    is_builtin = any(s["id"] == module_id for s in BUILTIN_SERVICES)

    if is_builtin:
        # 内置服务：检查端点是否可用
        for svc in BUILTIN_SERVICES:
            if svc["id"] == module_id:
                return {
                    "status": "ok",
                    "module": module_id,
                    "type": "builtin",
                    "endpoints": len(svc["endpoints"]),
                }

    # 外部插件：调用插件管理器
    try:
        from src.core.plugin_manager import get_plugin_manager

        pm = get_plugin_manager()
        return pm.health_check(module_id)
    except Exception as e:
        return {"status": "error", "module": module_id, "error": str(e)}
