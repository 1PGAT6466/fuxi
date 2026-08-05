"""
伏羲插件钩子系统
管理插件的生命周期钩子和事件订阅

作者: AI助手
日期: 2026-07-16
"""

import logging
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ============ 钩子管理器 ============
class HookManager:
    """
    钩子管理器 - 管理插件生命周期钩子

    钩子(Hook)：插件在特定时机被调用的函数
    事件(Event)：系统运行时触发的通知，插件可以订阅
    """

    def __init__(self):
        # 钩子存储：{hook_name: [(plugin_name, handler_func)]}
        self._hooks: Dict[str, List[tuple]] = defaultdict(list)
        # 事件监听器：{event_type: [(plugin_name, handler_func)]}
        self._event_listeners: Dict[str, List[tuple]] = defaultdict(list)
        # 事件历史（用于调试）
        self._event_history: List[Dict[str, Any]] = []
        logger.info("钩子管理器初始化完成")

    # ============ 钩子注册 ============

    def register_hook(self, hook_name: str, plugin_name: str, handler: Callable):
        """
        注册生命周期钩子

        预定义钩子：
        - pre_install: 安装前检查
        - post_install: 安装后初始化
        - pre_activate: 激活前准备
        - post_activate: 激活后注册
        - pre_deactivate: 停用前清理
        - post_deactivate: 停用后清理
        - pre_uninstall: 卸载前清理
        - post_uninstall: 卸载后清理
        """
        valid_hooks = [
            "pre_install",
            "post_install",
            "pre_activate",
            "post_activate",
            "pre_deactivate",
            "post_deactivate",
            "pre_uninstall",
            "post_uninstall",
        ]

        if hook_name not in valid_hooks:
            logger.warning(f"未知钩子: {hook_name}，有效钩子: {valid_hooks}")

        self._hooks[hook_name].append((plugin_name, handler))
        logger.info(f"插件 {plugin_name} 注册钩子: {hook_name}")

    def unregister_hooks(self, plugin_name: str):
        """注销插件的所有钩子"""
        for hook_name in list(self._hooks.keys()):
            self._hooks[hook_name] = [(pn, h) for pn, h in self._hooks[hook_name] if pn != plugin_name]
        logger.info(f"插件 {plugin_name} 的所有钩子已注销")

    def execute_hook(self, hook_name: str, context: Any = None) -> List[Dict[str, Any]]:
        """
        执行钩子

        Args:
            hook_name: 钩子名称
            context: 传递给钩子的上下文

        Returns:
            执行结果列表
        """
        results = []
        handlers = self._hooks.get(hook_name, [])

        if not handlers:
            return results

        logger.info(f"执行钩子 {hook_name}，共 {len(handlers)} 个处理器")

        for plugin_name, handler in handlers:
            try:
                result = handler(context)
                results.append({"plugin": plugin_name, "success": True, "result": result})
                logger.debug(f"钩子 {hook_name} [{plugin_name}] 执行成功")
            except Exception as e:
                results.append({"plugin": plugin_name, "success": False, "error": str(e)})
                logger.error(f"钩子 {hook_name} [{plugin_name}] 执行失败: {e}")

        return results

    # ============ 事件系统 ============

    def subscribe(self, event_type: str, plugin_name: str, handler: Callable):
        """
        订阅系统事件

        预定义事件：
        - knowledge_added: 知识库添加文档
        - knowledge_updated: 知识库更新文档
        - knowledge_deleted: 知识库删除文档
        - search_performed: 搜索操作完成
        - chat_completed: 对话完成
        - plugin_installed: 插件安装完成
        - plugin_activated: 插件激活完成
        - health_check: 健康检查
        - alert_triggered: 告警触发
        """
        self._event_listeners[event_type].append((plugin_name, handler))
        logger.info(f"插件 {plugin_name} 订阅事件: {event_type}")

    def unsubscribe(self, event_type: str, plugin_name: str):
        """取消订阅"""
        self._event_listeners[event_type] = [
            (pn, h) for pn, h in self._event_listeners[event_type] if pn != plugin_name
        ]

    def unsubscribe_all(self, plugin_name: str):
        """取消插件的所有事件订阅"""
        for event_type in list(self._event_listeners.keys()):
            self._event_listeners[event_type] = [
                (pn, h) for pn, h in self._event_listeners[event_type] if pn != plugin_name
            ]

    def emit(self, event_type: str, data: Any = None) -> List[Dict[str, Any]]:
        """
        触发事件

        Args:
            event_type: 事件类型
            data: 事件数据

        Returns:
            处理结果列表
        """
        results = []
        listeners = self._event_listeners.get(event_type, [])

        if not listeners:
            return results

        # 记录事件历史
        self._event_history.append(
            {
                "type": event_type,
                "data": data,
                "listeners": len(listeners),
                "timestamp": __import__("datetime").datetime.now().isoformat(),
            }
        )

        # 限制历史长度
        if len(self._event_history) > 1000:
            self._event_history = self._event_history[-500:]

        logger.info(f"触发事件 {event_type}，共 {len(listeners)} 个监听器")

        for plugin_name, handler in listeners:
            try:
                result = handler(data)
                results.append({"plugin": plugin_name, "success": True, "result": result})
            except Exception as e:
                results.append({"plugin": plugin_name, "success": False, "error": str(e)})
                logger.error(f"事件 {event_type} 处理失败 [{plugin_name}]: {e}")

        return results

    def get_listeners(self, event_type: str) -> List[str]:
        """获取事件的订阅者列表"""
        return [pn for pn, _ in self._event_listeners.get(event_type, [])]

    def get_hooks(self, hook_name: str) -> List[str]:
        """获取钩子的注册者列表"""
        return [pn for pn, _ in self._hooks.get(hook_name, [])]

    def get_event_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取事件历史"""
        return self._event_history[-limit:]


# ============ 路由注册器 ============
class RouteRegistrar:
    """
    路由注册器 - 管理插件的 FastAPI 路由
    """

    def __init__(self):
        self._registered_routes: Dict[str, List[Dict[str, Any]]] = {}

    def register(self, plugin_name: str, app, routes: List[Dict[str, Any]]):
        """
        注册插件路由

        Args:
            plugin_name: 插件名称
            app: FastAPI app 实例
            routes: 路由声明列表
        """
        from fastapi import APIRouter

        router = APIRouter(prefix=f"/api/plugins/{plugin_name}", tags=[f"插件-{plugin_name}"])

        for route in routes:
            path = route.get("path", "/")
            method = route.get("method", "GET").upper()
            handler_name = route.get("handler")

            if handler_name:
                # 从插件模块获取处理函数
                # 这里需要插件模块提供处理函数
                logger.info(f"注册路由: {method} /api/plugins/{plugin_name}{path}")

        app.include_router(router)
        self._registered_routes[plugin_name] = routes
        logger.info(f"插件 {plugin_name} 路由注册完成，共 {len(routes)} 条")

    def unregister(self, plugin_name: str, app):
        """移除插件路由"""
        prefix = f"/api/plugins/{plugin_name}"
        app.routes = [r for r in app.routes if not hasattr(r, "path") or not r.path.startswith(prefix)]
        self._registered_routes.pop(plugin_name, None)
        logger.info(f"插件 {plugin_name} 路由已移除")

    def get_registered_routes(self) -> Dict[str, List[Dict[str, Any]]]:
        """获取所有已注册的路由"""
        return self._registered_routes.copy()


# ============ 全局实例 ============
_hook_manager: Optional[HookManager] = None
_route_registrar: Optional[RouteRegistrar] = None


def get_hook_manager() -> HookManager:
    """获取钩子管理器全局实例"""
    global _hook_manager
    if _hook_manager is None:
        _hook_manager = HookManager()
    return _hook_manager


def get_route_registrar() -> RouteRegistrar:
    """获取路由注册器全局实例"""
    global _route_registrar
    if _route_registrar is None:
        _route_registrar = RouteRegistrar()
    return _route_registrar
