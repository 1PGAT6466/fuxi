"""
伏羲插件类型定义
定义所有插件类型的基类和接口

作者: AI助手
日期: 2026-07-16
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ============ 插件类型枚举 ============
class PluginType(str, Enum):
    """插件类型"""

    API = "api"  # 扩展 API 路由
    SERVICE = "service"  # 扩展后台服务
    UI = "ui"  # 扩展前端组件
    LLM = "llm"  # 扩展 LLM 能力（远程API）
    STORAGE = "storage"  # 扩展存储后端
    THEME = "theme"  # 主题/界面定制


# ============ 权限等级 ============
class PermissionLevel(int, Enum):
    """权限等级"""

    L0 = 0  # 只读 API + 自身数据（主题、UI组件）
    L1 = 1  # 读写 API + 知识库访问（搜索增强、格式转换）
    L2 = 2  # 读写 API + 外部网络（集成插件：钉钉/飞书）
    L3 = 3  # 管理员 API + 系统配置（运维、监控）


# ============ 插件状态 ============
class PluginStatus(str, Enum):
    """插件状态"""

    INSTALLED = "installed"  # 已安装
    ACTIVE = "active"  # 已激活
    INACTIVE = "inactive"  # 已停用
    ERROR = "error"  # 错误状态


# ============ manifest.json 数据模型 ============
class PluginManifest(BaseModel):
    """插件清单模型"""

    name: str = Field(..., description="插件唯一标识（小写字母+数字+连字符）")
    version: str = Field(..., description="语义化版本号 x.y.z")
    display_name: str = Field(..., description="显示名称")
    description: str = Field("", description="插件描述")
    author: str = Field("", description="作者")
    license: str = Field("MIT", description="许可证")
    type: PluginType = Field(..., description="插件类型")
    fuxi_version: str = Field(">=1.0.0", description="伏羲版本要求")
    dependencies: List[str] = Field(default_factory=list, description="pip依赖列表")
    permissions: PermissionLevel = Field(PermissionLevel.L0, description="权限等级")
    hooks: Dict[str, str] = Field(default_factory=dict, description="钩子函数映射")
    events: List[str] = Field(default_factory=list, description="监听的系统事件列表")
    routes: List[Dict[str, Any]] = Field(default_factory=list, description="API路由声明")
    config_schema: Dict[str, Any] = Field(default_factory=dict, description="配置JSON Schema")
    migrations: List[str] = Field(default_factory=list, description="迁移文件路径")
    health_check: Optional[Dict[str, str]] = Field(None, description="健康检查配置")

    class Config:
        use_enum_values = True


# ============ 插件上下文 ============
class InstallContext(BaseModel):
    """安装上下文 - 传递给安装钩子"""

    plugin_path: str = Field(..., description="插件路径")
    manifest: PluginManifest = Field(..., description="插件清单")
    backup_id: Optional[str] = Field(None, description="备份ID")
    config: Dict[str, Any] = Field(default_factory=dict, description="插件配置")


class ActivateContext(BaseModel):
    """激活上下文 - 传递给激活钩子"""

    manifest: PluginManifest = Field(..., description="插件清单")
    app: Any = Field(None, description="FastAPI app实例")
    config: Dict[str, Any] = Field(default_factory=dict, description="插件配置")


# ============ 插件基类 ============
class FuxiPlugin(ABC):
    """伏羲插件基类 - 所有插件必须继承此类"""

    @abstractmethod
    def get_manifest(self) -> PluginManifest:
        """返回插件清单"""
        ...

    @abstractmethod
    def on_install(self, context: InstallContext) -> bool:
        """安装时回调，返回 True 表示成功"""
        ...

    @abstractmethod
    def on_activate(self, context: ActivateContext) -> bool:
        """激活时回调，返回 True 表示成功"""
        ...

    @abstractmethod
    def on_deactivate(self) -> bool:
        """停用时回调，返回 True 表示成功"""
        ...

    @abstractmethod
    def on_uninstall(self) -> bool:
        """卸载时回调，返回 True 表示成功"""
        ...

    def health_check(self) -> Dict[str, Any]:
        """健康检查（可选实现）"""
        return {"status": "ok"}


# ============ 具体插件类型 ============


class APIPlugin(FuxiPlugin):
    """API 路由插件基类 - 扩展 FastAPI 路由"""

    @abstractmethod
    def register_routes(self, app) -> None:
        """注册 FastAPI 路由"""
        ...

    def get_routes(self) -> List[Dict[str, Any]]:
        """返回路由声明"""
        return []


class ServicePlugin(FuxiPlugin):
    """后台服务插件基类 - 扩展后台任务"""

    @abstractmethod
    def start_service(self) -> None:
        """启动后台服务"""
        ...

    @abstractmethod
    def stop_service(self) -> None:
        """停止后台服务"""
        ...


class LLMPlugin(FuxiPlugin):
    """LLM 能力插件基类 - 扩展远程LLM API"""

    @abstractmethod
    def get_llm_provider(self) -> Any:
        """返回 LLM provider（如 ChatOpenAI 实例）"""
        ...

    @abstractmethod
    def get_embedding_provider(self) -> Any:
        """返回嵌入 provider"""
        ...


class StoragePlugin(FuxiPlugin):
    """存储后端插件基类 - 扩展存储能力"""

    @abstractmethod
    def get_storage_client(self) -> Any:
        """返回存储客户端"""
        ...


class UIPlugin(FuxiPlugin):
    """UI 组件插件基类 - 扩展前端界面"""

    @abstractmethod
    def get_component_path(self) -> str:
        """返回 Vue 组件文件路径"""
        ...


class ThemePlugin(FuxiPlugin):
    """主题插件基类 - 定制界面风格"""

    @abstractmethod
    def get_theme_config(self) -> Dict[str, Any]:
        """返回主题配置（颜色、字体、布局等）"""
        ...
