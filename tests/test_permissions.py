"""
test_permissions.py — 伏羲 v1.50 Phase E 权限隔离单元测试
==========================================================

测试覆盖:
  1. PermissionManager 基础权限检查 (check_read / check_write)
  2. 团队管理 (CRUD)
  3. 文档可见性验证
  4. 检索结果过滤
  5. 管理员绕过权限
  6. 向后兼容 (visibility=public)
"""

import sys
import os
from pathlib import Path

# 确保项目路径在 sys.path 中
_proj_root = Path(__file__).parent.parent
sys.path.insert(0, str(_proj_root))
sys.path.insert(0, str(_proj_root / "src"))

from src.api.permissions import (
    PermissionManager,
    get_permission_manager,
    reset_permission_manager,
    build_document_metadata,
    Team,
)

# ============================================================================
# 测试 1: PermissionManager 基础权限检查
# ============================================================================

def test_check_read_public():
    """公开文档：所有人可读"""
    pm = PermissionManager()
    # public 文档，任何人可读
    assert pm.check_read("alice", None, "bob", "team-x", "public") is True
    assert pm.check_read("stranger", None, "bob", "team-x", "public") is True
    assert pm.check_read("", None, "bob", "team-x", "public") is False  # 空 user_id
    print("✓ test_check_read_public PASSED")


def test_check_read_owner():
    """文档所有者始终可读（无论 visibility）"""
    pm = PermissionManager()
    assert pm.check_read("alice", None, "alice", "team-x", "private") is True
    assert pm.check_read("alice", None, "alice", "team-x", "team") is True
    assert pm.check_read("alice", None, "alice", "team-x", "public") is True
    print("✓ test_check_read_owner PASSED")


def test_check_read_team():
    """同团队成员可读 team 可见性文档"""
    pm = PermissionManager()
    pm.create_team("team-1", "团队1", "admin", member_ids=["alice", "bob"])

    # alice 和 bob 同属 team-1，且文档 team_id=team-1
    assert pm.check_read("alice", "team-1", "bob", "team-1", "team") is True
    assert pm.check_read("bob", "team-1", "alice", "team-1", "team") is True

    # charlie 不在 team-1
    assert pm.check_read("charlie", None, "bob", "team-1", "team") is False
    print("✓ test_check_read_team PASSED")


def test_check_read_private():
    """private 文档仅所有者可读"""
    pm = PermissionManager()
    assert pm.check_read("alice", None, "alice", "team-x", "private") is True
    assert pm.check_read("bob", None, "alice", "team-x", "private") is False
    print("✓ test_check_read_private PASSED")


def test_check_write():
    """只有文档所有者和管理员可写"""
    pm = PermissionManager()
    assert pm.check_write("alice", "alice") is True
    assert pm.check_write("bob", "alice") is False  # 非所有者
    
    # admin 可绕过（通过 users.json 或直接 user_id="admin"）
    assert pm.check_write("admin", "alice") is True
    print("✓ test_check_write PASSED")


# ============================================================================
# 测试 2: 团队管理
# ============================================================================

def test_team_crud():
    """团队创建、查询、删除"""
    pm = PermissionManager()

    # 创建团队
    team = pm.create_team("team-eng", "工程部", "admin", description="工程部门", member_ids=["alice", "bob"])
    assert team.team_id == "team-eng"
    assert team.owner_id == "admin"
    assert "alice" in team.member_ids
    assert "admin" in team.member_ids  # owner 自动加入

    # 获取团队
    t = pm.get_team("team-eng")
    assert t is not None
    assert t.name == "工程部"

    # 列出团队（包括默认 public）
    teams = pm.list_teams()
    assert len(teams) >= 2  # public + team-eng

    # 添加成员
    assert pm.add_member("team-eng", "charlie") is True
    t = pm.get_team("team-eng")
    assert "charlie" in t.member_ids

    # 移除成员
    assert pm.remove_member("team-eng", "bob") is True
    t = pm.get_team("team-eng")
    assert "bob" not in t.member_ids

    # 不能移除 owner
    assert pm.remove_member("team-eng", "admin") is False

    # 删除团队
    assert pm.delete_team("team-eng") is True
    assert pm.get_team("team-eng") is None

    # 不能删除 public
    assert pm.delete_team("public") is False
    print("✓ test_team_crud PASSED")


def test_user_teams():
    """用户所属团队查询"""
    pm = PermissionManager()
    pm.create_team("team-a", "团队A", "admin", member_ids=["alice"])
    pm.create_team("team-b", "团队B", "admin", member_ids=["alice", "bob"])

    teams = pm.get_user_teams("alice")
    assert len(teams) == 2
    assert {t.team_id for t in teams} == {"team-a", "team-b"}

    team_id = pm.get_user_team_id("bob")
    assert team_id == "team-b"

    assert pm.get_user_team_id("nobody") is None
    print("✓ test_user_teams PASSED")


# ============================================================================
# 测试 3: 文档可见性验证
# ============================================================================

def test_validate_visibility():
    """可见性值验证"""
    pm = PermissionManager()
    assert pm.validate_visibility("private") == "private"
    assert pm.validate_visibility("team") == "team"
    assert pm.validate_visibility("public") == "public"
    assert pm.validate_visibility("PUBLIC") == "public"
    assert pm.validate_visibility(" Team ") == "team"
    assert pm.validate_visibility("invalid") == "public"  # 默认回退到 public
    print("✓ test_validate_visibility PASSED")


# ============================================================================
# 测试 4: 检索结果过滤
# ============================================================================

def test_filter_retrieval_results():
    """权限过滤：不同用户返回不同结果"""
    pm = PermissionManager()
    pm.create_team("team-eng", "工程部", "admin", member_ids=["alice"])

    # 模拟检索结果
    results = [
        {"metadata": {"owner_id": "alice", "team_id": "team-eng", "visibility": "team"}, "content": "doc1"},
        {"metadata": {"owner_id": "bob", "team_id": "team-eng", "visibility": "team"}, "content": "doc2"},
        {"metadata": {"owner_id": "charlie", "team_id": "other", "visibility": "public"}, "content": "doc3"},
        {"metadata": {"owner_id": "david", "team_id": "other", "visibility": "private"}, "content": "doc4"},
    ]

    # alice 在 team-eng 中：能看到 doc1(owner), doc2(同团队team), doc3(public)
    # 看不到 doc4(private 且不是owner)
    alice_results = pm.filter_retrieval_results(results, user_id="alice", team_id="team-eng")
    alice_docs = [r["content"] for r in alice_results]
    assert "doc1" in alice_docs  # owner
    assert "doc2" in alice_docs  # team
    assert "doc3" in alice_docs  # public
    assert "doc4" not in alice_docs  # private, 非owner

    # charlie 不在 team-eng：只能看到 public (doc3)
    charlie_results = pm.filter_retrieval_results(results, user_id="charlie", team_id=None)
    charlie_docs = [r["content"] for r in charlie_results]
    assert charlie_docs == ["doc3"]

    print("✓ test_filter_retrieval_results PASSED")


# ============================================================================
# 测试 5: 管理员绕过
# ============================================================================

def test_admin_bypass():
    """管理员可绕过所有权限限制"""
    pm = PermissionManager()

    # admin 可读所有
    assert pm.check_read("admin", None, "alice", "team-x", "private") is True
    assert pm.check_read("admin", None, "bob", "team-x", "team") is True

    # admin 可写所有
    assert pm.check_write("admin", "alice") is True
    assert pm.check_write("admin", "bob") is True

    # 检索结果过滤中 admin 看到全部
    results = [
        {"metadata": {"owner_id": "alice", "team_id": "team-x", "visibility": "private"}, "content": "secret"},
        {"metadata": {"owner_id": "bob", "team_id": "team-y", "visibility": "team"}, "content": "internal"},
    ]
    admin_results = pm.filter_retrieval_results(results, user_id="admin", team_id=None)
    assert len(admin_results) == 2

    print("✓ test_admin_bypass PASSED")


# ============================================================================
# 测试 6: 向后兼容
# ============================================================================

def test_backward_compatibility():
    """visibility 默认 public，不影响现有查询"""
    pm = PermissionManager()

    # 无 metadata 的文档视为 public
    results = [{"content": "legacy doc"}]
    filtered = pm.filter_retrieval_results(results, user_id="alice", team_id=None)
    assert len(filtered) == 1

    # visibility 缺省值 = public
    assert pm.check_read("alice", None, "owner", "team-x", "public") is True

    # 空字符串文档 owner/team 也不影响（默认 public）
    assert pm.check_read("alice", None, "", "", "public") is True

    print("✓ test_backward_compatibility PASSED")


# ============================================================================
# 测试 7: metadata 构建辅助函数
# ============================================================================

def test_build_document_metadata():
    """构建包含权限字段的文档 metadata"""
    base = {"chunk_index": "0", "file_name": "test.pdf"}
    meta = build_document_metadata(
        owner_id="alice",
        team_id="team-eng",
        visibility="team",
        base_metadata=base,
    )
    assert meta["owner_id"] == "alice"
    assert meta["team_id"] == "team-eng"
    assert meta["visibility"] == "team"
    assert meta["chunk_index"] == "0"
    assert meta["file_name"] == "test.pdf"
    print("✓ test_build_document_metadata PASSED")


# ============================================================================
# 运行所有测试
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("伏羲 v1.50 Phase E: Company Brain 权限隔离 — 单元测试")
    print("=" * 60)

    tests = [
        test_check_read_public,
        test_check_read_owner,
        test_check_read_team,
        test_check_read_private,
        test_check_write,
        test_team_crud,
        test_user_teams,
        test_validate_visibility,
        test_filter_retrieval_results,
        test_admin_bypass,
        test_backward_compatibility,
        test_build_document_metadata,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            reset_permission_manager()
            test()
            passed += 1
        except AssertionError as e:
            print(f"✗ {test.__name__} FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {test.__name__} ERROR: {e}")
            failed += 1

    print()
    print(f"结果: {passed} 通过, {failed} 失败, 共 {len(tests)} 项")
    if failed > 0:
        print("❌ 存在失败的测试")
        sys.exit(1)
    else:
        print("✅ 所有测试通过！")
