"""
tenant.py — 多租户管理模块
===========================
Phase 1: 行级多租户隔离

职责：
  - 租户 CRUD（创建/查询/更新/删除）
  - 租户上下文管理（从 JWT 中提取 tenant_id，注入 request.state）
  - 租户数据隔离（自动为查询添加 tenant_id 过滤）
  - 种子数据：创建默认租户 "default"
"""
import json
import time
import logging
import threading
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

logger = logging.getLogger("auth.tenant")

# ============================================================================
# 数据模型
# ============================================================================

@dataclass
class Tenant:
    """租户数据模型"""
    tenant_id: str
    name: str
    description: str = ""
    is_active: bool = True
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    settings: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "name": self.name,
            "description": self.description,
            "is_active": self.is_active,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "settings": self.settings,
        }


# ============================================================================
# 租户管理器
# ============================================================================

class TenantManager:
    """租户管理器 — 负责租户生命周期管理

    数据持久化：tenants.json 文件（与 users.json 同目录）
    线程安全：使用 threading.Lock 保护共享状态
    """

    # 默认租户 ID
    DEFAULT_TENANT_ID: str = "default"

    def __init__(self, data_dir: Optional[str] = None):
        """初始化租户管理器

        Args:
            data_dir: 持久化数据目录
        """
        self._lock = threading.Lock()

        # 确定持久化路径
        if data_dir:
            self._persist_file = Path(data_dir) / "tenants.json"
        else:
            from src.config import DATA_DIR
            self._persist_file = Path(DATA_DIR) / "tenants.json"

        # 租户缓存: {tenant_id: Tenant}
        self._tenants: Dict[str, Tenant] = {}

        # 加载或初始化
        self._load_from_file()
        self._ensure_default_tenant()

    # ========================================================================
    # CRUD 操作
    # ========================================================================

    def create_tenant(
        self,
        tenant_id: str,
        name: str,
        description: str = "",
        settings: Optional[Dict[str, Any]] = None,
    ) -> Tenant:
        """创建租户

        Args:
            tenant_id:    租户唯一标识
            name:         租户名称
            description:  租户描述
            settings:     租户自定义设置

        Returns:
            创建的 Tenant 对象

        Raises:
            ValueError: tenant_id 已存在或无效
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id 不能为空")

        if not name or not name.strip():
            raise ValueError("租户名称不能为空")

        with self._lock:
            if tenant_id in self._tenants:
                raise ValueError(f"租户 {tenant_id} 已存在")

            tenant = Tenant(
                tenant_id=tenant_id.strip(),
                name=name.strip(),
                description=description,
                settings=settings or {},
            )
            self._tenants[tenant_id] = tenant
            self._save_to_file()

        logger.info("🏢 租户已创建: %s (%s)", tenant.name, tenant.tenant_id)
        return tenant

    def get_tenant(self, tenant_id: str) -> Optional[Tenant]:
        """获取租户信息"""
        with self._lock:
            return self._tenants.get(tenant_id)

    def list_tenants(self, include_inactive: bool = False) -> List[Dict[str, Any]]:
        """列出所有租户

        Args:
            include_inactive: 是否包含已停用的租户

        Returns:
            租户信息列表
        """
        with self._lock:
            tenants = list(self._tenants.values())
        if not include_inactive:
            tenants = [t for t in tenants if t.is_active]
        return [t.to_dict() for t in tenants]

    def update_tenant(
        self,
        tenant_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        is_active: Optional[bool] = None,
        settings: Optional[Dict[str, Any]] = None,
    ) -> Optional[Tenant]:
        """更新租户信息

        Args:
            tenant_id:    租户 ID
            name:         新名称（可选）
            description:  新描述（可选）
            is_active:    是否启用（可选）
            settings:     新设置（可选，合并而非替换）

        Returns:
            更新后的 Tenant 对象，不存在时返回 None
        """
        with self._lock:
            tenant = self._tenants.get(tenant_id)
            if not tenant:
                return None

            if name is not None:
                tenant.name = name.strip()
            if description is not None:
                tenant.description = description
            if is_active is not None:
                tenant.is_active = is_active
            if settings is not None:
                tenant.settings.update(settings)

            tenant.updated_at = time.time()
            self._save_to_file()

        logger.info("🏢 租户已更新: %s", tenant_id)
        return tenant

    def delete_tenant(self, tenant_id: str) -> bool:
        """删除租户（不允许删除默认租户）

        Args:
            tenant_id: 租户 ID

        Returns:
            True 表示成功，False 表示失败
        """
        if tenant_id == self.DEFAULT_TENANT_ID:
            logger.warning("delete_tenant: 不允许删除默认租户 %s", self.DEFAULT_TENANT_ID)
            return False

        with self._lock:
            if tenant_id not in self._tenants:
                return False
            del self._tenants[tenant_id]
            self._save_to_file()

        logger.info("🏢 租户已删除: %s", tenant_id)
        return True

    def tenant_exists(self, tenant_id: str) -> bool:
        """检查租户是否存在"""
        with self._lock:
            return tenant_id in self._tenants

    def is_tenant_active(self, tenant_id: str) -> bool:
        """检查租户是否激活"""
        with self._lock:
            tenant = self._tenants.get(tenant_id)
            return tenant is not None and tenant.is_active

    # ========================================================================
    # 种子数据
    # ========================================================================

    def _ensure_default_tenant(self) -> None:
        """确保默认租户存在"""
        if self.DEFAULT_TENANT_ID not in self._tenants:
            self._tenants[self.DEFAULT_TENANT_ID] = Tenant(
                tenant_id=self.DEFAULT_TENANT_ID,
                name="默认租户",
                description="系统默认租户，所有未分配租户的用户和数据归属此租户",
                is_active=True,
            )
            self._save_to_file()
            logger.info("🏢 已创建默认租户: %s", self.DEFAULT_TENANT_ID)

    # ========================================================================
    # 租户上下文（从 request 中提取）
    # ========================================================================

    @staticmethod
    def get_tenant_from_request(request) -> str:
        """从 request 中提取 tenant_id

        优先级：
          1. request.state.tenant_id（由中间件设置）
          2. JWT payload 中的 tenant_id
          3. 请求头 X-Tenant-Id
          4. 默认租户 "default"

        Args:
            request: FastAPI Request 对象

        Returns:
            tenant_id 字符串
        """
        # 优先从 request.state 获取（中间件已设置）
        tenant_id = getattr(request.state, "tenant_id", None)
        if tenant_id:
            return tenant_id

        # 从 JWT payload 获取
        payload = getattr(request.state, "jwt_payload", None)
        if payload and isinstance(payload, dict):
            tenant_id = payload.get("tenant_id")
            if tenant_id:
                return tenant_id

        # 从请求头获取
        tenant_id = request.headers.get("X-Tenant-Id", "")
        if tenant_id:
            return tenant_id.strip()

        return TenantManager.DEFAULT_TENANT_ID

    # ========================================================================
    # 持久化
    # ========================================================================

    def _save_to_file(self) -> None:
        """持久化到文件"""
        try:
            data = {
                "tenants": {
                    tid: t.to_dict()
                    for tid, t in self._tenants.items()
                },
                "updated_at": time.time(),
            }
            self._persist_file.parent.mkdir(parents=True, exist_ok=True)
            tmp = str(self._persist_file) + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            import os
            os.replace(tmp, str(self._persist_file))
        except Exception as e:
            logger.warning("租户持久化失败: %s", e)

    def _load_from_file(self) -> None:
        """从持久化文件加载"""
        if not self._persist_file.exists():
            return

        try:
            with open(self._persist_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            tenants_data = data.get("tenants", {})
            for tid, tdata in tenants_data.items():
                self._tenants[tid] = Tenant(
                    tenant_id=tdata.get("tenant_id", tid),
                    name=tdata.get("name", tid),
                    description=tdata.get("description", ""),
                    is_active=tdata.get("is_active", True),
                    created_at=tdata.get("created_at", time.time()),
                    updated_at=tdata.get("updated_at", time.time()),
                    settings=tdata.get("settings", {}),
                )

            logger.info("✅ 已从 %s 加载 %d 个租户", self._persist_file, len(self._tenants))
        except Exception as e:
            logger.warning("租户持久化文件加载失败: %s，使用默认状态", e)


# ============================================================================
# 全局单例
# ============================================================================

_global_tenant_manager: Optional[TenantManager] = None


def get_tenant_manager(data_dir: Optional[str] = None) -> TenantManager:
    """获取全局 TenantManager 单例"""
    global _global_tenant_manager
    if _global_tenant_manager is None:
        _global_tenant_manager = TenantManager(data_dir=data_dir)
    return _global_tenant_manager


def reset_tenant_manager() -> None:
    """重置全局 TenantManager（主要用于测试）"""
    global _global_tenant_manager
    _global_tenant_manager = None


__all__ = [
    "Tenant",
    "TenantManager",
    "get_tenant_manager",
    "reset_tenant_manager",
]
