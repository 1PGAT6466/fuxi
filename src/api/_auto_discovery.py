"""
_auto_discovery.py — 伏羲 v2.1 服务路由自动发现

扫描 src/api/ 目录下所有 .py 文件，自动发现 APIRouter 实例，
按文件名映射生成挂载前缀，替代 server.py 中手写的 include_router 列表。

使用方式:
    # in server.py
    from src.api._auto_discovery import auto_discover_routers
    auto_discover_routers(app)

规则:
  - admin.py         → /api/admin
  - chat.py          → /api/chat
  - documents.py     → /api/documents
  - search.py        → /api/search
  - wiki.py          → /api/wiki
  - system_routes.py → /api/system (去掉 "_routes" 后缀)
  - files_alias.py   → /api-files (特殊映射)
  - feedback.py      → /api/feedback
  - graph.py         → /api/graph
  - metadata.py      → /api/metadata
  - worldtree.py     → /api/worldtree
  - v2_routes.py     → /api (特殊映射)
  - auth_routes.py   → /api/auth (保留手动注册)
  - evaluation.py    → /api/eval (保留手动注册)
  - evolution.py     → /api/evolution (保留手动注册)
  - dashboard.py     → /api/dashboard

跳过:
  - __init__.py, auth.py, response.py
  - _auto_discovery.py 自身
  - 特殊路由: /api/mcp/*, /api/eval/*, /login, /static, /metrics

特别处理:
  - server.py 中特殊路由（proxy/loader, mcp, metrics, login, static 等）保留手动注册
"""

import importlib
import inspect
import logging
import os
import pkgutil
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, FastAPI

logger = logging.getLogger("auto_discovery")

# ── 文件名 → 前缀映射 ──
# 自动根据文件名生成: foo.py → /api/foo
# 特殊映射在此表覆盖
_PREFIX_OVERRIDES: Dict[str, str] = {
    "system_routes.py": "/api/system",
    "v2_routes.py": "/api",
    "files_alias.py": "/api-files",
    "files_view.py": "/api",
}

# 跳过列表 — 不自动注册
_SKIP_FILES: set = {
    "__init__.py",
    "_auto_discovery.py",
    "auth.py",          # 中间件定义，非路由
    "response.py",       # 工具模块，非路由
    # 以下保留手动注册（特殊逻辑或已在 server.py 中 inline 注册）
    "auth_routes.py",    # server.py 中手动 include
    "evaluation.py",     # 有独立的 /api/eval 前缀，server.py 中手动 include
    "evolution.py",      # server.py 中手动 include
    # v2.1 新增路由 — 已在 server.py 中手动注册
    "services.py",
    "notifications.py",
    "unified_search.py",
    "user_preferences.py",
    "feature_flags_ws.py",
    # v1.44 Phase 1 Fix: 手动注册以避免路径冲突
    "rag.py",
    "kb.py",
}

# ── 已发现的 router 信息 ──
_discovered_routers: List[dict] = []


def _file_to_prefix(filename: str) -> str:
    """根据文件名生成挂载前缀"""
    if filename in _PREFIX_OVERRIDES:
        return _PREFIX_OVERRIDES[filename]

    name = filename.replace(".py", "")
    # 去掉 _routes 后缀
    if name.endswith("_routes"):
        name = name[:-7]  # remove "_routes"
    return f"/api/{name}"


def _find_routers_in_module(module) -> List[APIRouter]:
    """在模块中查找所有 APIRouter 实例"""
    routers = []
    for name, obj in inspect.getmembers(module):
        if isinstance(obj, APIRouter):
            routers.append((name, obj))
    return routers


def discover_routers(api_dir: Optional[Path] = None) -> Dict[str, APIRouter]:
    """
    扫描 src/api/ 目录，发现所有 APIRouter 实例。

    Returns:
        Dict[prefix, router] — 前缀 → APIRouter 的映射
    """
    if api_dir is None:
        api_dir = Path(__file__).parent

    discovered: Dict[str, APIRouter] = {}

    for entry in sorted(os.listdir(api_dir)):
        if not entry.endswith(".py"):
            continue
        if entry in _SKIP_FILES:
            continue
        if entry.startswith("_"):
            continue  # skip _private modules

        module_path = f"src.api.{entry[:-3]}"
        try:
            module = importlib.import_module(module_path)
        except Exception as e:
            logger.warning(f"[AutoDiscovery] 跳过 {entry}（导入失败）: {e}")
            continue

        routers: List[tuple] = _find_routers_in_module(module)
        if not routers:
            logger.debug(f"[AutoDiscovery] {entry} 中未找到 APIRouter，跳过")
            continue

        prefix = _file_to_prefix(entry)

        for var_name, router in routers:
            # 对 v2_routes 不挂前缀（它自己管理）
            actual_prefix = prefix
            if entry == "v2_routes.py":
                actual_prefix = ""  # v2_router already has prefixes in its own paths
            if entry == "files_alias.py":
                actual_prefix = "/api-files"
            if entry == "files_view.py":
                actual_prefix = ""  # files_view has /api/view, /api/download, /api/antenna prefixes

            discovered[actual_prefix] = (router, var_name, entry)
            logger.info(
                f"[AutoDiscovery] ✓ {entry}::{var_name} → prefix='{actual_prefix}'"
            )

    return discovered


def auto_discover_routers(app: FastAPI, api_dir: Optional[Path] = None) -> int:
    """
    自动发现并注册所有服务路由到 FastAPI 应用。

    Returns:
        int — 成功注册的路由数量
    """
    global _discovered_routers
    discovered = discover_routers(api_dir)

    registered = 0
    for prefix, (router, var_name, source_file) in discovered.items():
        try:
            app.include_router(router, prefix="")  # all routes use absolute paths
            registered += 1
        except Exception as e:
            logger.error(
                f"[AutoDiscovery] 注册失败 {source_file}::{var_name} (prefix={prefix}): {e}"
            )

    # 保存发现信息供 services 端点使用
    _discovered_routers = [
        {
            "source_file": source_file,
            "var_name": var_name,
            "prefix": prefix,
            "router_tags": getattr(router, "tags", []),
        }
        for prefix, (router, var_name, source_file) in discovered.items()
    ]

    logger.info(
        f"[AutoDiscovery] 自动发现完成: {registered}/{len(discovered)} 个路由已注册"
    )
    return registered


def get_discovered_router_info() -> List[dict]:
    """返回已发现的路由信息（供 /api/services 使用）"""
    return list(_discovered_routers)
