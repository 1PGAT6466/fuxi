"""
伏羲插件集成代码生成器
根据分析结果生成集成代码

作者: AI助手
日期: 2026-07-17
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class IntegrationPlan:
    """集成计划"""

    plugin_name: str
    plugin_type: str
    steps: List[Dict[str, Any]] = field(default_factory=list)
    estimated_time: str = ""  # 预估时间
    risk_level: str = "low"
    requires_confirmation: bool = False


@dataclass
class GeneratedCode:
    """生成的代码"""

    file_path: str
    content: str
    action: str  # create/modify/delete
    description: str
    requires_confirmation: bool = False


class PluginIntegrator:
    """插件集成代码生成器"""

    def __init__(self, fuxi_root: str = "."):
        self.fuxi_root = Path(fuxi_root)

    # ============ 公开接口 ============

    def generate_integration_plan(self, analysis_result: Any) -> IntegrationPlan:
        """
        根据分析结果生成集成计划

        Args:
            analysis_result: PluginAnalyzer.AnalysisResult

        Returns:
            集成计划
        """
        plan = IntegrationPlan(
            plugin_name=analysis_result.plugin_name,
            plugin_type=analysis_result.plugin_type,
            risk_level=analysis_result.risk_level,
        )

        # 根据集成点生成步骤
        logger.info(f"集成点数量: {len(analysis_result.integration_points)}")
        for point in analysis_result.integration_points:
            logger.info(f"处理集成点: type={point.type}, name={point.name}")
            step = self._create_integration_step(point, analysis_result)
            if step:
                logger.info(f"生成步骤: {step.get('type')}")
                plan.steps.append(step)
            else:
                logger.warning(f"集成点 {point.type}:{point.name} 未生成步骤")

        # 根据风险等级决定是否需要确认
        if analysis_result.risk_level in ["high", "critical"]:
            plan.requires_confirmation = True

        # 估算时间
        plan.estimated_time = self._estimate_time(plan.steps)

        return plan

    def generate_integration_code(self, plan: IntegrationPlan, plugin_path: str) -> List[GeneratedCode]:
        """
        生成集成代码

        Args:
            plan: 集成计划
            plugin_path: 插件路径

        Returns:
            生成的代码列表
        """
        codes = []

        for step in plan.steps:
            step_type = step.get("type", "")

            if step_type == "register_route":
                code = self._generate_route_registration(step, plugin_path)
                if code:
                    codes.append(code)

            elif step_type == "register_service":
                code = self._generate_service_registration(step, plugin_path)
                if code:
                    codes.append(code)

            elif step_type == "register_event":
                code = self._generate_event_registration(step, plugin_path)
                if code:
                    codes.append(code)

            elif step_type == "register_hook":
                code = self._generate_hook_registration(step, plugin_path)
                if code:
                    codes.append(code)

            elif step_type == "register_llm":
                code = self._generate_llm_registration(step, plugin_path)
                if code:
                    codes.append(code)

            elif step_type == "register_storage":
                code = self._generate_storage_registration(step, plugin_path)
                if code:
                    codes.append(code)

            elif step_type == "register_ui":
                code = self._generate_ui_registration(step, plugin_path)
                if code:
                    codes.append(code)

            elif step_type == "register_health":
                code = self._generate_health_registration(step, plugin_path)
                if code:
                    codes.append(code)

            elif step_type == "register_config":
                code = self._generate_config_registration(step, plugin_path)
                if code:
                    codes.append(code)

            elif step_type == "register_generic":
                code = self._generate_generic_registration(step, plugin_path)
                if code:
                    codes.append(code)

        return codes

    # ============ 内部方法 ============

    def _create_integration_step(self, point: Any, analysis: Any) -> Optional[Dict[str, Any]]:
        """创建集成步骤"""
        if point.type == "route":
            return {
                "type": "register_route",
                "name": point.name,
                "description": point.description,
                "file_path": point.file_path,
                "line_number": point.line_number,
                "details": point.details,
            }

        elif point.type == "service":
            return {
                "type": "register_service",
                "name": point.name,
                "description": point.description,
                "file_path": point.file_path,
                "line_number": point.line_number,
                "details": point.details,
            }

        elif point.type == "event":
            return {
                "type": "register_event",
                "name": point.name,
                "description": point.description,
                "file_path": point.file_path,
                "line_number": point.line_number,
                "details": point.details,
            }

        elif point.type == "hook":
            return {
                "type": "register_hook",
                "name": point.name,
                "description": point.description,
                "file_path": point.file_path,
                "line_number": point.line_number,
                "details": point.details,
            }

        elif point.type == "llm_provider":
            return {
                "type": "register_llm",
                "name": point.name,
                "description": point.description,
                "file_path": point.file_path,
                "line_number": point.line_number,
                "details": point.details,
            }

        elif point.type == "storage":
            return {
                "type": "register_storage",
                "name": point.name,
                "description": point.description,
                "file_path": point.file_path,
                "line_number": point.line_number,
                "details": point.details,
            }

        elif point.type == "ui_component":
            return {
                "type": "register_ui",
                "name": point.name,
                "description": point.description,
                "file_path": point.file_path,
                "line_number": point.line_number,
                "details": point.details,
            }

        elif point.type == "health":
            return {
                "type": "register_health",
                "name": point.name,
                "description": point.description,
                "file_path": point.file_path,
                "line_number": point.line_number,
                "details": point.details,
            }

        elif point.type == "config":
            return {
                "type": "register_config",
                "name": point.name,
                "description": point.description,
                "file_path": point.file_path,
                "line_number": point.line_number,
                "details": point.details,
            }

        else:
            return {
                "type": "register_generic",
                "name": point.name,
                "description": point.description,
                "file_path": point.file_path,
                "line_number": point.line_number,
                "details": point.details,
            }

        return None

    def _generate_route_registration(self, step: Dict[str, Any], plugin_path: str) -> Optional[GeneratedCode]:
        """生成路由注册代码"""
        plugin_name = step.get("details", {}).get("plugin_name", "unknown")
        method = step.get("details", {}).get("method", "GET").lower()
        path = step.get("details", {}).get("path", "/")
        handler_name = step.get("name", "handler")

        code = f'''
# 自动生成的路由注册代码
# 插件: {plugin_name}
# 路由: {method.upper()} {path}

from fastapi import APIRouter

router = APIRouter(prefix="/api/plugins/{plugin_name}", tags=["插件-{plugin_name}"])

@router.{method}("{path}")
async def {handler_name}():
    """{step.get('description', '')}"""
    # TODO: 实现路由逻辑
    return {{"status": "ok", "plugin": "{plugin_name}"}}
'''

        return GeneratedCode(
            file_path=f"src/api/plugins/{plugin_name}_routes.py",
            content=code,
            action="create",
            description=f"注册路由: {method.upper()} {path}",
            requires_confirmation=False,
        )

    def _generate_service_registration(self, step: Dict[str, Any], plugin_path: str) -> Optional[GeneratedCode]:
        """生成服务注册代码"""
        service_name = step.get("name", "UnknownService")
        plugin_name = step.get("details", {}).get("plugin_name", "unknown")

        code = f'''
# 自动生成的服务注册代码
# 插件: {plugin_name}
# 服务: {service_name}

from src.core.plugin_hooks import get_hook_manager

def register_{service_name.lower()}(app):
    """注册 {service_name} 服务"""
    hm = get_hook_manager()
    
    # 注册激活钩子
    def on_activate(context):
        """激活时启动服务"""
        # TODO: 启动后台服务
        pass
    
    def on_deactivate():
        """停用时停止服务"""
        # TODO: 停止后台服务
        pass
    
    hm.register_hook("post_activate", "{plugin_name}", on_activate)
    hm.register_hook("pre_deactivate", "{plugin_name}", on_deactivate)
'''

        return GeneratedCode(
            file_path=f"src/services/plugins/{plugin_name}_service.py",
            content=code,
            action="create",
            description=f"注册服务: {service_name}",
            requires_confirmation=False,
        )

    def _generate_event_registration(self, step: Dict[str, Any], plugin_path: str) -> Optional[GeneratedCode]:
        """生成事件注册代码"""
        event_type = step.get("details", {}).get("event_type", "unknown")
        handler_name = step.get("name", "on_event")
        plugin_name = step.get("details", {}).get("plugin_name", "unknown")

        code = f'''
# 自动生成的事件注册代码
# 插件: {plugin_name}
# 事件: {event_type}

from src.core.plugin_hooks import get_hook_manager

def register_{handler_name}():
    """注册事件处理器: {event_type}"""
    hm = get_hook_manager()
    
    def {handler_name}(data):
        """处理 {event_type} 事件"""
        # TODO: 实现事件处理逻辑
        print(f"[{plugin_name}] 收到事件: {event_type}, 数据: {{data}}")
    
    hm.subscribe("{event_type}", "{plugin_name}", {handler_name})
'''

        return GeneratedCode(
            file_path=f"src/events/plugins/{plugin_name}_events.py",
            content=code,
            action="create",
            description=f"注册事件处理器: {event_type}",
            requires_confirmation=False,
        )

    def _generate_hook_registration(self, step: Dict[str, Any], plugin_path: str) -> Optional[GeneratedCode]:
        """生成钩子注册代码"""
        hook_name = step.get("name", "unknown")
        plugin_name = step.get("details", {}).get("plugin_name", "unknown")

        code = f'''
# 自动生成的钩子注册代码
# 插件: {plugin_name}
# 钩子: {hook_name}

from src.core.plugin_hooks import get_hook_manager

def register_{hook_name}():
    """注册钩子: {hook_name}"""
    hm = get_hook_manager()
    
    def {hook_name}(context):
        """{hook_name} 钩子实现"""
        # TODO: 实现钩子逻辑
        print(f"[{plugin_name}] 钩子 {hook_name} 执行")
        return True
    
    hm.register_hook("{hook_name}", "{plugin_name}", {hook_name})
'''

        return GeneratedCode(
            file_path=f"src/hooks/plugins/{plugin_name}_hooks.py",
            content=code,
            action="create",
            description=f"注册钩子: {hook_name}",
            requires_confirmation=False,
        )

    def _generate_llm_registration(self, step: Dict[str, Any], plugin_path: str) -> Optional[GeneratedCode]:
        """生成 LLM 提供者注册代码"""
        provider_name = step.get("name", "UnknownProvider")
        plugin_name = step.get("details", {}).get("plugin_name", "unknown")

        code = f'''
# 自动生成的 LLM 提供者注册代码
# 插件: {plugin_name}
# 提供者: {provider_name}

from src.core.plugin_hooks import get_hook_manager

def register_{provider_name.lower()}():
    """注册 LLM 提供者: {provider_name}"""
    hm = get_hook_manager()
    
    def on_activate(context):
        """激活时注册 LLM 提供者"""
        # TODO: 注册到 LLM 管理器
        pass
    
    hm.register_hook("post_activate", "{plugin_name}", on_activate)
'''

        return GeneratedCode(
            file_path=f"src/llm/plugins/{plugin_name}_llm.py",
            content=code,
            action="create",
            description=f"注册 LLM 提供者: {provider_name}",
            requires_confirmation=True,  # LLM 提供者需要确认
        )

    def _generate_storage_registration(self, step: Dict[str, Any], plugin_path: str) -> Optional[GeneratedCode]:
        """生成存储提供者注册代码"""
        storage_name = step.get("name", "UnknownStorage")
        plugin_name = step.get("details", {}).get("plugin_name", "unknown")

        code = f'''
# 自动生成的存储提供者注册代码
# 插件: {plugin_name}
# 提供者: {storage_name}

from src.core.plugin_hooks import get_hook_manager

def register_{storage_name.lower()}():
    """注册存储提供者: {storage_name}"""
    hm = get_hook_manager()
    
    def on_activate(context):
        """激活时注册存储提供者"""
        # TODO: 注册到存储管理器
        pass
    
    hm.register_hook("post_activate", "{plugin_name}", on_activate)
'''

        return GeneratedCode(
            file_path=f"src/storage/plugins/{plugin_name}_storage.py",
            content=code,
            action="create",
            description=f"注册存储提供者: {storage_name}",
            requires_confirmation=True,
        )

    def _generate_ui_registration(self, step: Dict[str, Any], plugin_path: str) -> Optional[GeneratedCode]:
        """生成 UI 组件注册代码"""
        component_name = step.get("name", "UnknownComponent")
        plugin_name = step.get("details", {}).get("plugin_name", "unknown")

        code = f'''
# 自动生成的 UI 组件注册代码
# 插件: {plugin_name}
# 组件: {component_name}

from src.core.plugin_hooks import get_hook_manager

def register_{component_name.lower()}():
    """注册 UI 组件: {component_name}"""
    hm = get_hook_manager()
    
    def on_activate(context):
        """激活时注册 UI 组件"""
        # TODO: 注册到前端路由
        pass
    
    hm.register_hook("post_activate", "{plugin_name}", on_activate)
'''

        return GeneratedCode(
            file_path=f"src/ui/plugins/{plugin_name}_ui.py",
            content=code,
            action="create",
            description=f"注册 UI 组件: {component_name}",
            requires_confirmation=True,
        )

    def _generate_health_registration(self, step: Dict[str, Any], plugin_path: str) -> Optional[GeneratedCode]:
        """生成健康检查注册代码"""
        handler_name = step.get("name", "health_check")
        plugin_name = step.get("details", {}).get("plugin_name", "unknown")

        code = f'''
# 自动生成的健康检查注册代码
# 插件: {plugin_name}

from src.core.plugin_hooks import get_hook_manager

def register_{handler_name}():
    """注册健康检查: {handler_name}"""
    hm = get_hook_manager()
    
    def {handler_name}():
        """健康检查"""
        # TODO: 实现健康检查逻辑
        return {{"status": "ok"}}
    
    hm.register_hook("post_activate", "{plugin_name}", lambda ctx: None)
'''

        return GeneratedCode(
            file_path=f"src/health/plugins/{plugin_name}_health.py",
            content=code,
            action="create",
            description=f"注册健康检查: {handler_name}",
            requires_confirmation=False,
        )

    def _generate_config_registration(self, step: Dict[str, Any], plugin_path: str) -> Optional[GeneratedCode]:
        """生成配置注册代码"""
        config_name = step.get("name", "Config")
        plugin_name = step.get("details", {}).get("plugin_name", "unknown")

        code = f'''
# 自动生成的配置注册代码
# 插件: {plugin_name}

class {config_name}:
    """插件配置"""
    
    # TODO: 定义配置项
    DEFAULT_CONFIG = {{}}
    
    @classmethod
    def get_config(cls) -> dict:
        return cls.DEFAULT_CONFIG.copy()
'''

        return GeneratedCode(
            file_path=f"src/config/plugins/{plugin_name}_config.py",
            content=code,
            action="create",
            description=f"注册配置: {config_name}",
            requires_confirmation=False,
        )

    def _generate_generic_registration(self, step: Dict[str, Any], plugin_path: str) -> Optional[GeneratedCode]:
        """生成通用注册代码"""
        name = step.get("name", "unknown")
        plugin_name = step.get("details", {}).get("plugin_name", "unknown")

        code = f"""
# 自动生成的注册代码
# 插件: {plugin_name}
# 组件: {name}

# TODO: 实现注册逻辑
"""

        return GeneratedCode(
            file_path=f"src/plugins/{plugin_name}/{name}.py",
            content=code,
            action="create",
            description=f"注册组件: {name}",
            requires_confirmation=False,
        )

    def _estimate_time(self, steps: List[Dict[str, Any]]) -> str:
        """估算集成时间"""
        if not steps:
            return "0分钟"

        # 基础时间
        base_minutes = 5

        # 每个步骤增加时间
        step_minutes = {
            "register_route": 3,
            "register_service": 5,
            "register_event": 2,
            "register_hook": 2,
            "register_llm": 10,
            "register_storage": 8,
            "register_ui": 5,
            "register_health": 2,
            "register_config": 2,
            "register_generic": 3,
        }

        total = base_minutes
        for step in steps:
            step_type = step.get("type", "")
            total += step_minutes.get(step_type, 3)

        if total >= 60:
            return f"{total // 60}小时{total % 60}分钟"
        else:
            return f"{total}分钟"


# ============ 辅助函数 ============


def generate_integration_summary(plan: IntegrationPlan, codes: List[GeneratedCode]) -> str:
    """生成集成摘要"""
    summary = f"""
## 插件集成摘要

**插件名称**: {plan.plugin_name}
**插件类型**: {plan.plugin_type}
**风险等级**: {plan.risk_level}
**预估时间**: {plan.estimated_time}
**需要确认**: {'是' if plan.requires_confirmation else '否'}

### 集成步骤

"""
    for i, step in enumerate(plan.steps, 1):
        summary += f"{i}. {step.get('description', '')}\n"

    summary += f"""
### 生成的代码文件

"""
    for code in codes:
        summary += f"- `{code.file_path}`: {code.description}\n"

    return summary
