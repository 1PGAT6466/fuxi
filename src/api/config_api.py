"""
配置中心 API — 系统配置管理
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException, Query

logger = logging.getLogger("api.config")

router = APIRouter(prefix="/api/config", tags=["配置中心"])

# ============ 配置定义 ============

CONFIG_SCHEMA = {
    "system": {
        "name": "系统配置",
        "items": [
            {
                "key": "FUXI_APP_NAME",
                "name": "应用名称",
                "type": "string",
                "default": "伏羲·内世界",
                "description": "系统显示名称",
            },
            {
                "key": "FUXI_VERSION",
                "name": "版本号",
                "type": "string",
                "default": "1.44",
                "description": "当前版本",
                "readonly": True,
            },
            {
                "key": "FUXI_ENV",
                "name": "运行环境",
                "type": "select",
                "options": ["production", "development", "testing"],
                "default": "production",
                "description": "运行环境",
            },
            {
                "key": "FUXI_DEBUG",
                "name": "调试模式",
                "type": "boolean",
                "default": False,
                "description": "启用调试模式",
            },
        ],
    },
    "server": {
        "name": "服务器配置",
        "items": [
            {
                "key": "FUXI_HOST",
                "name": "监听地址",
                "type": "string",
                "default": "0.0.0.0",
                "description": "服务器监听地址",
            },
            {
                "key": "FUXI_PORT",
                "name": "监听端口",
                "type": "number",
                "default": 8080,
                "description": "服务器监听端口",
            },
            {
                "key": "FUXI_WORKERS",
                "name": "工作进程数",
                "type": "number",
                "default": 1,
                "description": "工作进程数量",
            },
        ],
    },
    "llm": {
        "name": "LLM 配置",
        "items": [
            {
                "key": "MIMO_API_KEY",
                "name": "MiMo API Key",
                "type": "password",
                "default": "",
                "description": "MiMo API 密钥",
            },
            {
                "key": "MIMO_MODEL",
                "name": "MiMo 模型",
                "type": "string",
                "default": "mimo-v2.5",
                "description": "使用的 MiMo 模型",
            },
            {
                "key": "LLM_TEMPERATURE",
                "name": "温度",
                "type": "number",
                "default": 0.3,
                "min": 0,
                "max": 2,
                "description": "生成温度",
            },
            {
                "key": "LLM_MAX_TOKENS",
                "name": "最大 Token",
                "type": "number",
                "default": 4096,
                "description": "最大生成 Token 数",
            },
        ],
    },
    "rag": {
        "name": "RAG 配置",
        "items": [
            {
                "key": "CHROMADB_PATH",
                "name": "ChromaDB 路径",
                "type": "string",
                "default": "data/chromadb",
                "description": "ChromaDB 数据目录",
            },
            {"key": "CHUNK_SIZE", "name": "分块大小", "type": "number", "default": 512, "description": "文档分块大小"},
            {
                "key": "CHUNK_OVERLAP",
                "name": "分块重叠",
                "type": "number",
                "default": 50,
                "description": "文档分块重叠大小",
            },
            {"key": "TOP_K", "name": "检索数量", "type": "number", "default": 10, "description": "默认检索结果数量"},
            {
                "key": "SIMILARITY_THRESHOLD",
                "name": "相似度阈值",
                "type": "number",
                "default": 0.7,
                "min": 0,
                "max": 1,
                "description": "相似度阈值",
            },
        ],
    },
    "storage": {
        "name": "存储配置",
        "items": [
            {
                "key": "UPLOAD_DIR",
                "name": "上传目录",
                "type": "string",
                "default": "data/uploads",
                "description": "文件上传目录",
            },
            {
                "key": "MAX_FILE_SIZE",
                "name": "最大文件大小",
                "type": "number",
                "default": 104857600,
                "description": "最大上传文件大小（字节）",
            },
            {
                "key": "ALLOWED_EXTENSIONS",
                "name": "允许的扩展名",
                "type": "string",
                "default": ".pdf,.doc,.docx,.txt,.md,.csv,.json",
                "description": "允许的文件扩展名",
            },
        ],
    },
    "security": {
        "name": "安全配置",
        "items": [
            {
                "key": "FUXI_JWT_SECRET",
                "name": "JWT 密钥",
                "type": "password",
                "default": "",
                "description": "JWT 签名密钥",
            },
            {
                "key": "JWT_EXPIRE_MINUTES",
                "name": "JWT 过期时间",
                "type": "number",
                "default": 1440,
                "description": "JWT 过期时间（分钟）",
            },
            {
                "key": "RATE_LIMIT_PER_MINUTE",
                "name": "每分钟限流",
                "type": "number",
                "default": 60,
                "description": "每分钟最大请求数",
            },
        ],
    },
}


def _get_config_value(key: str, default: Any = None) -> Any:
    """获取配置值（优先环境变量，其次默认值）"""
    return os.getenv(key, str(default))


def _set_config_value(key: str, value: Any) -> None:
    """设置配置值（写入 .env 文件）"""
    env_file = Path(".env")

    # 读取现有内容
    lines = []
    if env_file.exists():
        lines = env_file.read_text(encoding="utf-8").splitlines()

    # 查找并更新
    found = False
    for i, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[i] = f"{key}={value}"
            found = True
            break

    # 如果不存在，添加
    if not found:
        lines.append(f"{key}={value}")

    # 写入文件
    env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # 更新环境变量
    os.environ[key] = str(value)


# ============ API 端点 ============


@router.get("/schema")
async def get_config_schema():
    """获取配置定义"""
    return {
        "status": "success",
        "data": CONFIG_SCHEMA,
    }


@router.get("")
async def get_config(category: Optional[str] = Query(None)):
    """获取当前配置"""
    config = {}

    for cat_key, cat_data in CONFIG_SCHEMA.items():
        if category and cat_key != category:
            continue

        config[cat_key] = {
            "name": cat_data["name"],
            "items": [],
        }

        for item in cat_data["items"]:
            value = _get_config_value(item["key"], item.get("default", ""))
            config[cat_key]["items"].append(
                {
                    **item,
                    "value": value,
                }
            )

    return {
        "status": "success",
        "data": config,
    }


@router.put("/{key}")
async def update_config(key: str, data: Dict = Body(...)):
    """更新配置项"""
    value = data.get("value")

    # 查找配置项定义
    item_def = None
    for cat_data in CONFIG_SCHEMA.values():
        for item in cat_data["items"]:
            if item["key"] == key:
                item_def = item
                break

    if not item_def:
        raise HTTPException(404, f"配置项 {key} 不存在")

    if item_def.get("readonly"):
        raise HTTPException(400, f"配置项 {key} 是只读的")

    # 类型验证
    if item_def["type"] == "number":
        try:
            value = float(value)
            if "min" in item_def and value < item_def["min"]:
                raise HTTPException(400, f"值不能小于 {item_def['min']}")
            if "max" in item_def and value > item_def["max"]:
                raise HTTPException(400, f"值不能大于 {item_def['max']}")
        except ValueError:
            raise HTTPException(400, "值必须是数字")
    elif item_def["type"] == "boolean":
        value = str(value).lower() in ("true", "1", "yes")

    # 保存配置
    _set_config_value(key, value)

    return {
        "status": "success",
        "message": f"配置项 {key} 已更新",
        "data": {"key": key, "value": value},
    }


@router.post("/reset")
async def reset_config(category: Optional[str] = Query(None)):
    """重置配置为默认值"""
    reset_count = 0

    for cat_key, cat_data in CONFIG_SCHEMA.items():
        if category and cat_key != category:
            continue

        for item in cat_data["items"]:
            if item.get("readonly"):
                continue

            default = item.get("default", "")
            _set_config_value(item["key"], default)
            reset_count += 1

    return {
        "status": "success",
        "message": f"已重置 {reset_count} 个配置项为默认值",
    }
