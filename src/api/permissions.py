"""
permissions.py — 伏羲 v1.50 Phase E: Company Brain 权限隔离
============================================================

对标 GBrain 的 Company Brain：团队每个成员只看到自己范围的数据。

权限模型：
  - owner:  文档创建者可读写自己的文档
  - team:   同团队成员可读
  - public: 所有人可读（默认）
  - admin:  管理员可读写所有文档

设计原则：
  1. 权限数据暂用内存存储（后续可迁移到 DB/Redis）
  2. 创建默认 "public" 团队，所有现有文档归入 "public"
  3. 向后兼容：visibility 默认 "public"，不影响现有查询
  4. 管理员（role="admin"）自动绕过所有权限检查
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, field

logger = logging.getLogger("api.permissions")

# ============================================================================
# 数据模型
# ============================================================================

@dataclass
class Team:
    """团队数据模型"""
    team_id: str
    name: str
    description: str = ""
    owner_id: str = ""           # 团队创建者
    member_ids: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "team_id": self.team_id,
            "name": self.name,
            "description": self.description,
            "owner_id": self.owner_id,
            "member_ids": self.member_ids,
            "member_count": len(self.member_ids),
            "created_at": self.created_at,
        }

    def has_member(self, user_id: str) -> bool:
        """检查用户是否为团队成员"""
        return user_id in self.member_ids or user_id == self.owner_id


# ============================================================================
# 权限管理器
# ============================================================================

class PermissionManager:
    """团队权限管理器

    权限模型：
      - owner:  文档创建者可读写自己的文档
      - team:   同团队成员可读
      - public: 所有人可读（默认）
      - admin:  管理员可读写所有

    Usage::

        pm = PermissionManager()

        # 创建团队
        pm.create_team(
            team_id="team-eng",
            name="工程部",
            owner_id="admin",
            member_ids=["alice", "bob", "charlie"],
        )

        # 检查读权限
        can_read = pm.check_read(
            user_id="alice",
            team_id="team-eng",
            doc_owner_id="bob",
            doc_team_id="team-eng",
            doc_visibility="team",
        )  # → True（同团队）

        can_read = pm.check_read(
            user_id="david",
            team_id=None,
            doc_owner_id="charlie",
            doc_team_id="team-eng",
            doc_visibility="team",
        )  # → False（不同团队）

        # 检查写权限
        can_write = pm.check_write(
            user_id="alice",
            doc_owner_id="alice",
        )  # → True（文档所有者）
    """

    # 公开团队的固定 ID
    PUBLIC_TEAM_ID: str = "public"

    # 管理员角色名（硬编码，与 auth 模块一致）
    ADMIN_ROLE: str = "admin"

    # 持久化文件路径
    _persist_file: Optional[Path] = None

    def __init__(self, data_dir: Optional[str] = None):
        """初始化权限管理器

        Args:
            data_dir: 持久化数据目录，为 None 时不持久化
        """
        # teams: {team_id: Team}
        self._teams: Dict[str, Team] = {}

        # 持久化目录
        if data_dir:
            self._persist_file = Path(data_dir) / "permissions.json"

        # 初始化默认 public 团队
        self._ensure_public_team()

        # 从持久化文件加载
        if self._persist_file and self._persist_file.exists():
            self._load_from_file()

    # ========================================================================
    # 核心权限检查
    # ========================================================================

    def check_read(
        self,
        user_id: str,
        team_id: Optional[str],
        doc_owner_id: Optional[str],
        doc_team_id: Optional[str],
        doc_visibility: str = "public",
    ) -> bool:
        """检查用户是否对文档有读权限

        权限判定顺序（短路逻辑）：
          1. 文档 visibility=public → 所有人可读
          2. 用户是文档 owner → 可读
          3. 用户拥有 admin 角色 → 可读（admin 可访问所有）
          4. 文档 visibility=team 且用户与文档同团队 → 可读
          5. 文档 visibility=private 且用户是 owner → 可读（已在步骤2覆盖）
          6. 否则拒绝

        Args:
            user_id:       当前用户 ID
            team_id:       当前用户所属团队 ID（可为 None）
            doc_owner_id:  文档创建者用户 ID
            doc_team_id:   文档所属团队 ID
            doc_visibility: 文档可见性: "private" | "team" | "public"

        Returns:
            True 表示允许读取，False 表示拒绝
        """
        if not user_id:
            return False

        # 规则 1: public 文档所有人可读
        if doc_visibility == self.PUBLIC_TEAM_ID:
            return True

        # 规则 2: 文档所有者始终可读
        if doc_owner_id and user_id == doc_owner_id:
            return True

        # 规则 3: 管理员可访问所有
        if self.is_admin(user_id):
            return True

        # 规则 4: team 可见性 → 同团队可读
        if doc_visibility == "team":
            if team_id and doc_team_id and team_id == doc_team_id:
                return True
            # 也检查用户是否在文档所属团队的成员列表中
            if doc_team_id and self._is_team_member(user_id, doc_team_id):
                return True
            return False

        # 规则 5: private 文档只有所有者可读
        if doc_visibility == "private":
            return False  # owner 已在步骤2返回 True

        # 默认拒绝
        return False

    def check_write(
        self,
        user_id: str,
        doc_owner_id: Optional[str],
    ) -> bool:
        """检查用户是否对文档有写权限

        写权限规则：
          1. 用户是文档 owner → 可写
          2. 用户拥有 admin 角色 → 可写
          3. 否则拒绝

        Args:
            user_id:      当前用户 ID
            doc_owner_id: 文档创建者用户 ID

        Returns:
            True 表示允许写入，False 表示拒绝
        """
        if not user_id:
            return False

        # 规则 1: 文档所有者可写
        if doc_owner_id and user_id == doc_owner_id:
            return True

        # 规则 2: 管理员可写所有
        if self.is_admin(user_id):
            return True

        return False

    # ========================================================================
    # 团队管理
    # ========================================================================

    def create_team(
        self,
        team_id: str,
        name: str,
        owner_id: str,
        description: str = "",
        member_ids: Optional[List[str]] = None,
    ) -> Team:
        """创建团队

        Args:
            team_id:     团队唯一标识
            name:        团队名称
            owner_id:    团队创建者
            description: 团队描述
            member_ids:  初始成员列表（不含 owner_id）

        Returns:
            创建的 Team 对象

        Raises:
            ValueError: team_id 已存在或无效
        """
        if not team_id or not team_id.strip():
            raise ValueError("team_id 不能为空")

        if not name or not name.strip():
            raise ValueError("团队名称不能为空")

        if team_id in self._teams:
            raise ValueError(f"团队 {team_id} 已存在")

        members = list(member_ids or [])
        # owner 自动加入团队
        if owner_id and owner_id not in members:
            members.insert(0, owner_id)

        team = Team(
            team_id=team_id.strip(),
            name=name.strip(),
            description=description,
            owner_id=owner_id,
            member_ids=members,
        )
        self._teams[team.team_id] = team

        logger.info("📋 团队已创建: %s (%s), owner=%s, members=%d",
                     team.name, team.team_id, team.owner_id, len(team.member_ids))

        self._save_to_file()
        return team

    def get_team(self, team_id: str) -> Optional[Team]:
        """获取团队信息

        Args:
            team_id: 团队 ID

        Returns:
            Team 对象，不存在时返回 None
        """
        return self._teams.get(team_id)

    def list_teams(self) -> List[Dict[str, Any]]:
        """列出所有团队

        Returns:
            团队信息列表
        """
        return [t.to_dict() for t in self._teams.values()]

    def add_member(self, team_id: str, user_id: str) -> bool:
        """向团队添加成员

        Args:
            team_id: 团队 ID
            user_id: 要添加的用户 ID

        Returns:
            True 表示成功，False 表示失败
        """
        team = self._teams.get(team_id)
        if not team:
            logger.warning("add_member: 团队 %s 不存在", team_id)
            return False

        if user_id in team.member_ids:
            logger.debug("add_member: 用户 %s 已是团队 %s 成员", user_id, team_id)
            return True  # 幂等

        team.member_ids.append(user_id)
        logger.info("👤 用户 %s 已加入团队 %s (%s)", user_id, team_id, team.name)
        self._save_to_file()
        return True

    def remove_member(self, team_id: str, user_id: str) -> bool:
        """从团队移除成员

        Args:
            team_id: 团队 ID
            user_id: 要移除的用户 ID

        Returns:
            True 表示成功，False 表示失败
        """
        team = self._teams.get(team_id)
        if not team:
            logger.warning("remove_member: 团队 %s 不存在", team_id)
            return False

        if user_id == team.owner_id:
            logger.warning("remove_member: 不能移除团队所有者 %s", user_id)
            return False

        if user_id not in team.member_ids:
            logger.debug("remove_member: 用户 %s 不在团队 %s 中", user_id, team_id)
            return True  # 幂等

        team.member_ids.remove(user_id)
        logger.info("👤 用户 %s 已从团队 %s (%s) 移除", user_id, team_id, team.name)
        self._save_to_file()
        return True

    def delete_team(self, team_id: str) -> bool:
        """删除团队（不允许删除 public 团队）

        Args:
            team_id: 团队 ID

        Returns:
            True 表示成功，False 表示失败
        """
        if team_id == self.PUBLIC_TEAM_ID:
            logger.warning("delete_team: 不允许删除 public 默认团队")
            return False

        if team_id not in self._teams:
            return False

        del self._teams[team_id]
        logger.info("📋 团队已删除: %s", team_id)
        self._save_to_file()
        return True

    def get_user_team_id(self, user_id: str) -> Optional[str]:
        """获取用户所属的第一个团队 ID

        遍历所有团队查找成员。
        如果用户在多个团队中，返回第一个。

        Args:
            user_id: 用户 ID

        Returns:
            团队 ID，未找到时返回 None
        """
        for team in self._teams.values():
            if team.has_member(user_id):
                return team.team_id
        return None

    def get_user_teams(self, user_id: str) -> List[Team]:
        """获取用户所属的所有团队

        Args:
            user_id: 用户 ID

        Returns:
            团队列表
        """
        return [t for t in self._teams.values() if t.has_member(user_id)]

    # ========================================================================
    # 管理员检查
    # ========================================================================

    def is_admin(self, user_id: str) -> bool:
        """检查用户是否是管理员

        通过查询 users.json 中的 role 字段判断。
        也预留了 user_id 直接为 "admin" 的兜底判断。

        Args:
            user_id: 用户 ID

        Returns:
            True 如果用户角色为 admin
        """
        if user_id == "admin":
            return True

        try:
            from src.config import DATA_DIR
            users_file = Path(DATA_DIR) / "users.json"
            if users_file.exists():
                users = json.loads(users_file.read_text(encoding="utf-8"))
                user = users.get(user_id, {})
                return user.get("role", "user") == self.ADMIN_ROLE
        except Exception:
            pass

        return False

    # ========================================================================
    # 文档可见性管理
    # ========================================================================

    @staticmethod
    def validate_visibility(visibility: str) -> str:
        """验证并规范化文档可见性

        Args:
            visibility: 原始可见性值

        Returns:
            规范化后的可见性（private / team / public）
        """
        valid = {"private", "team", "public"}
        v = visibility.strip().lower()
        if v not in valid:
            logger.warning("validate_visibility: 无效值 '%s'，使用默认 'public'", visibility)
            return "public"
        return v

    # ========================================================================
    # 初始化与持久化
    # ========================================================================

    def _ensure_public_team(self) -> None:
        """确保默认 public 团队存在"""
        if self.PUBLIC_TEAM_ID not in self._teams:
            self._teams[self.PUBLIC_TEAM_ID] = Team(
                team_id=self.PUBLIC_TEAM_ID,
                name="Public（公开团队）",
                description="默认公开团队，所有未分配团队的文档归入此团队。所有人可见。",
                owner_id="system",
                member_ids=[],
            )
            logger.info("📋 已创建默认 public 团队")

    def _save_to_file(self) -> None:
        """持久化到文件"""
        if not self._persist_file:
            return

        try:
            data = {
                "teams": {
                    tid: {
                        "team_id": t.team_id,
                        "name": t.name,
                        "description": t.description,
                        "owner_id": t.owner_id,
                        "member_ids": t.member_ids,
                        "created_at": t.created_at,
                    }
                    for tid, t in self._teams.items()
                },
                "updated_at": time.time(),
            }
            self._persist_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._persist_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.debug("权限数据已持久化到 %s", self._persist_file)
        except Exception as e:
            logger.warning("权限持久化失败: %s", e)

    def _load_from_file(self) -> None:
        """从持久化文件加载"""
        if not self._persist_file:
            return

        try:
            with open(self._persist_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            teams_data = data.get("teams", {})
            for tid, tdata in teams_data.items():
                if tid == self.PUBLIC_TEAM_ID and tid in self._teams:
                    # 更新已有的 public 团队（保留运行时修改）
                    pub = self._teams[tid]
                    pub.member_ids = tdata.get("member_ids", [])
                else:
                    self._teams[tid] = Team(
                        team_id=tdata.get("team_id", tid),
                        name=tdata.get("name", tid),
                        description=tdata.get("description", ""),
                        owner_id=tdata.get("owner_id", ""),
                        member_ids=tdata.get("member_ids", []),
                        created_at=tdata.get("created_at", time.time()),
                    )

            logger.info("✅ 已从 %s 加载 %d 个团队", self._persist_file, len(self._teams))
        except Exception as e:
            logger.warning("权限持久化文件加载失败: %s，使用默认状态", e)

    def _is_team_member(self, user_id: str, team_id: str) -> bool:
        """检查用户是否为指定团队的直接成员

        Args:
            user_id: 用户 ID
            team_id: 团队 ID

        Returns:
            True 如果是团队成员
        """
        team = self._teams.get(team_id)
        if team:
            return team.has_member(user_id)
        return False

    # ========================================================================
    # 向量检索结果过滤
    # ========================================================================

    def filter_retrieval_results(
        self,
        results: List[Any],
        user_id: str,
        team_id: Optional[str] = None,
    ) -> List[Any]:
        """对检索结果按权限过滤

        遍历检索结果列表，只保留用户有权查看的文档。

        能处理两种结果格式：
          - 带 metadata 属性的对象（如 ChromaDB 返回的文档对象）
          - 包含 metadata 键的字典

        Args:
            results:  检索结果列表
            user_id:  当前用户 ID
            team_id:  当前用户团队 ID（可选）

        Returns:
            过滤后的结果列表
        """
        if not results:
            return []

        filtered = []
        for r in results:
            metadata = self._extract_metadata(r)

            doc_owner_id = metadata.get("owner_id", "")
            doc_team_id = metadata.get("team_id", self.PUBLIC_TEAM_ID)
            doc_visibility = metadata.get("visibility", "public")

            if self.check_read(
                user_id=user_id,
                team_id=team_id,
                doc_owner_id=doc_owner_id,
                doc_team_id=doc_team_id,
                doc_visibility=doc_visibility,
            ):
                filtered.append(r)

        filtered_count = len(results) - len(filtered)
        if filtered_count > 0:
            logger.debug(
                "🔒 权限过滤: %d/%d 条结果已过滤 (user=%s)",
                filtered_count, len(results), user_id,
            )

        return filtered

    @staticmethod
    def _extract_metadata(result: Any) -> Dict[str, Any]:
        """从检索结果对象中提取 metadata

        Args:
            result: 检索结果对象

        Returns:
            metadata 字典
        """
        # ChromaDB 查询结果 (v4 API — 直接是 dict)
        if isinstance(result, dict):
            return result.get("metadata", result)

        # 对象有 metadata 属性
        if hasattr(result, "metadata"):
            meta = getattr(result, "metadata", None)
            if isinstance(meta, dict):
                return meta

        # 兜底：返回空字典（默认允许访问）
        return {}


# ============================================================================
# 全局单例
# ============================================================================

_global_permission_manager: Optional[PermissionManager] = None


def get_permission_manager(data_dir: Optional[str] = None) -> PermissionManager:
    """获取全局 PermissionManager 单例

    Args:
        data_dir: 持久化数据目录

    Returns:
        PermissionManager 实例
    """
    global _global_permission_manager

    if _global_permission_manager is None:
        if data_dir is None:
            from src.config import DATA_DIR
            data_dir = str(DATA_DIR)
        _global_permission_manager = PermissionManager(data_dir=data_dir)

    return _global_permission_manager


def reset_permission_manager() -> None:
    """重置全局 PermissionManager（主要用于测试）"""
    global _global_permission_manager
    _global_permission_manager = None


# ============================================================================
# 文档 metadata 构建辅助函数
# ============================================================================

def build_document_metadata(
    owner_id: str = "",
    team_id: str = "",
    visibility: str = "public",
    base_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """构建包含权限字段的文档 metadata

    用于在写入 ChromaDB / Wiki 时附加权限信息。

    Args:
        owner_id:   文档创建者
        team_id:    所属团队（默认 "public"）
        visibility: 可见性（默认 "public"）
        base_metadata: 基础元数据（chunk_index, file_name 等）

    Returns:
        合并后的 metadata 字典
    """
    meta = dict(base_metadata or {})
    meta["owner_id"] = owner_id
    meta["team_id"] = team_id or PermissionManager.PUBLIC_TEAM_ID
    meta["visibility"] = PermissionManager.validate_visibility(visibility)
    return meta


__all__ = [
    "PermissionManager",
    "Team",
    "get_permission_manager",
    "reset_permission_manager",
    "build_document_metadata",
]
