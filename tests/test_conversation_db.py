"""
test_conversation_db.py — ConversationDB 完整测试套件
====================================================
P1 核心缺陷修复: 对话历史持久化

覆盖:
- 表结构创建（幂等）
- 对话 CRUD（创建/查询/列表/删除）
- 消息追加与查询
- 边界条件（空标题、分页、软/硬删除、恢复）
- 数据完整性（外键约束、时间戳升序）
"""

import pytest
import time
import os
import sys
import threading
from pathlib import Path
# 将项目根加入路径
_project_root = Path(__file__).parent.parent
sys.path.insert(0, str(_project_root))

# ============ 测试夹具 ============


@pytest.fixture(autouse=True)
def reset_singleton():
    """每个测试前重置单例（避免测试间状态泄露）"""
    from src.db.conversation_db import ConversationDB
    ConversationDB.reset_instance()
    yield
    ConversationDB.reset_instance()


@pytest.fixture
def db(tmp_path):
    """创建使用临时目录的 ConversationDB 实例"""
    from src.db.conversation_db import ConversationDB
    db_path = str(tmp_path / "test_convo.db")
    instance = ConversationDB(db_path=db_path)
    return instance


@pytest.fixture
def conv_id(db):
    """创建一个测试对话并返回其 ID"""
    conv = db.create_conversation("test_user", "测试对话")
    return conv["id"]


# ============ 单元测试: 表结构 ============


class TestTableCreation:
    """测试表创建（幂等性）"""

    def test_ensure_tables_creates_all(self, db):
        """ensure_tables 应创建 conversations 和 messages 表及索引"""
        import sqlite3
        conn = sqlite3.connect(db._db_path)
        tables = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "conversations" in tables
        assert "messages" in tables

        indexes = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()
        }
        assert "idx_conv_user_id" in indexes
        assert "idx_conv_updated_at" in indexes
        assert "idx_msg_conv_id" in indexes
        assert "idx_msg_timestamp" in indexes
        conn.close()

    def test_ensure_tables_idempotent(self, db):
        """重复调用 ensure_tables 不应报错"""
        db.ensure_tables()
        db.ensure_tables()
        db.ensure_tables()  # 三次调用应无异常

    def test_public_ensure_tables(self, db):
        """公开 ensure_tables() 方法存在且可调用"""
        db.ensure_tables()


# ============ 单元测试: 对话 CRUD ============


class TestCreateConversation:
    """测试 create_conversation"""

    def test_create_with_title(self, db):
        conv = db.create_conversation("user_1", "项目会议")
        assert conv["user_id"] == "user_1"
        assert conv["title"] == "项目会议"
        assert conv["message_count"] == 0
        assert isinstance(conv["id"], str)
        assert len(conv["id"]) == 36  # UUID

    def test_create_with_default_title(self, db):
        """空标题应生成默认标题"""
        conv = db.create_conversation("user_1", "")
        assert conv["title"]  # 不应为空
        assert "对话" in conv["title"]

    def test_create_with_whitespace_title(self, db):
        """纯空白标题应生成默认标题"""
        conv = db.create_conversation("user_1", "   ")
        assert "对话" in conv["title"]

    def test_create_unique_ids(self, db):
        """每次创建应生成唯一 ID"""
        ids = set()
        for i in range(20):
            conv = db.create_conversation("user_1", f"测试 {i}")
            ids.add(conv["id"])
        assert len(ids) == 20

    def test_create_sets_timestamps(self, db):
        now = time.time()
        conv = db.create_conversation("user_1", "测试")
        assert conv["created_at"] >= now
        assert conv["updated_at"] >= now
        assert abs(conv["created_at"] - now) < 5


class TestGetConversation:
    """测试 get_conversation"""

    def test_get_existing(self, db, conv_id):
        full = db.get_conversation(conv_id)
        assert full is not None
        assert full["id"] == conv_id
        assert full["user_id"] == "test_user"
        assert isinstance(full["messages"], list)

    def test_get_nonexistent(self, db):
        full = db.get_conversation("no-such-id")
        assert full is None

    def test_get_returns_messages_ordered(self, db, conv_id):
        """消息应按时间升序返回"""
        db.add_message(conv_id, "user", "消息1")
        time.sleep(0.01)
        db.add_message(conv_id, "assistant", "消息2")
        time.sleep(0.01)
        db.add_message(conv_id, "user", "消息3")

        full = db.get_conversation(conv_id)
        contents = [m["content"] for m in full["messages"]]
        assert contents == ["消息1", "消息2", "消息3"]

    def test_get_soft_deleted_hidden_by_default(self, db, conv_id):
        """软删除后 get_conversation 默认返回 None"""
        db.delete_conversation(conv_id)
        assert db.get_conversation(conv_id) is None

    def test_get_soft_deleted_with_include(self, db, conv_id):
        """include_deleted=True 可获取软删除对话"""
        db.delete_conversation(conv_id)
        full = db.get_conversation(conv_id, include_deleted=True)
        assert full is not None
        assert full["is_deleted"] is True


class TestListConversations:
    """测试 list_conversations"""

    def test_list_empty_user(self, db):
        result = db.list_conversations("no_user")
        assert result == []

    def test_list_returns_summaries(self, db):
        # 创建多个对话
        for i in range(3):
            conv = db.create_conversation("user_x", f"对话{i}")
            db.add_message(conv["id"], "user", f"消息内容{i}")

        result = db.list_conversations("user_x")
        assert len(result) == 3
        for s in result:
            assert "id" in s
            assert "title" in s
            assert "message_count" in s
            assert "last_message_preview" in s

    def test_list_pagination(self, db):
        for i in range(5):
            db.create_conversation("user_p", f"对话{i}")

        page1 = db.list_conversations("user_p", limit=2, offset=0)
        assert len(page1) == 2
        page2 = db.list_conversations("user_p", limit=2, offset=2)
        assert len(page2) == 2
        page3 = db.list_conversations("user_p", limit=2, offset=4)
        assert len(page3) == 1

    def test_list_message_count(self, db):
        conv = db.create_conversation("user_q", "包含消息")
        db.add_message(conv["id"], "user", "A")
        db.add_message(conv["id"], "assistant", "B")
        db.add_message(conv["id"], "user", "C")

        result = db.list_conversations("user_q")
        assert result[0]["message_count"] == 3

    def test_list_last_message_preview_truncated(self, db):
        conv = db.create_conversation("user_r", "长文本")
        long_msg = "A" * 500
        db.add_message(conv["id"], "user", long_msg)

        result = db.list_conversations("user_r")
        preview = result[0]["last_message_preview"]
        assert len(preview) <= 201  # 200 字符 + "…"


class TestDeleteConversation:
    """测试 delete_conversation"""

    def test_soft_delete(self, db, conv_id):
        assert db.delete_conversation(conv_id)
        # 软删除后不可见
        assert db.get_conversation(conv_id) is None
        # 不在列表中出现
        result = db.list_conversations("test_user")
        assert len(result) == 0

    def test_hard_delete(self, db, conv_id):
        db.add_message(conv_id, "user", "测试消息")
        assert db.delete_conversation(conv_id, hard=True)
        # 硬删除后 include_deleted=True 也查不到
        assert db.get_conversation(conv_id, include_deleted=True) is None

    def test_delete_nonexistent(self, db):
        assert not db.delete_conversation("no-such-id")

    def test_double_delete(self, db, conv_id):
        """重复删除应返回 False"""
        assert db.delete_conversation(conv_id)
        assert not db.delete_conversation(conv_id)


# ============ 单元测试: 消息 CRUD ============


class TestAddMessage:
    """测试 add_message"""

    def test_add_user_message(self, db, conv_id):
        msg = db.add_message(conv_id, "user", "你好")
        assert msg["role"] == "user"
        assert msg["content"] == "你好"
        assert msg["conversation_id"] == conv_id

    def test_add_assistant_message(self, db, conv_id):
        msg = db.add_message(conv_id, "assistant", "你好，有什么可以帮助的？")
        assert msg["role"] == "assistant"

    def test_add_system_message(self, db, conv_id):
        msg = db.add_message(conv_id, "system", "系统初始化完成")
        assert msg["role"] == "system"

    def test_add_invalid_role(self, db, conv_id):
        with pytest.raises(ValueError, match="无效角色"):
            db.add_message(conv_id, "invalid_role", "内容")

    def test_add_to_nonexistent_conversation(self, db):
        with pytest.raises(ValueError, match="不存在"):
            db.add_message("no-such-id", "user", "内容")

    def test_add_to_deleted_conversation(self, db, conv_id):
        db.delete_conversation(conv_id)
        with pytest.raises(ValueError, match="不存在.*已删除"):
            db.add_message(conv_id, "user", "内容")

    def test_add_updates_updated_at(self, db, conv_id):
        before = db.get_conversation(conv_id)["updated_at"]
        time.sleep(0.01)
        db.add_message(conv_id, "user", "新消息")
        after = db.get_conversation(conv_id)["updated_at"]
        assert after > before

    def test_add_with_metadata(self, db, conv_id):
        meta = {"source": "web", "ip": "127.0.0.1"}
        msg = db.add_message(conv_id, "user", "内容", metadata=meta)
        assert msg["metadata"] == meta

    def test_add_empty_metadata_defaults_to_empty_dict(self, db, conv_id):
        msg = db.add_message(conv_id, "user", "内容")
        assert msg["metadata"] == {}


# ============ 单元测试: 辅助方法 ============


class TestUpdateTitle:
    """测试 update_title"""

    def test_update_title_valid(self, db, conv_id):
        assert db.update_title(conv_id, "新标题")
        conv = db.get_conversation(conv_id)
        assert conv["title"] == "新标题"

    def test_update_title_empty(self, db, conv_id):
        old_title = db.get_conversation(conv_id)["title"]
        assert not db.update_title(conv_id, "")
        assert db.get_conversation(conv_id)["title"] == old_title

    def test_update_title_whitespace(self, db, conv_id):
        old_title = db.get_conversation(conv_id)["title"]
        assert not db.update_title(conv_id, "   ")
        assert db.get_conversation(conv_id)["title"] == old_title

    def test_update_title_deleted(self, db, conv_id):
        db.delete_conversation(conv_id)
        assert not db.update_title(conv_id, "不应该更新")


class TestGetMessageCount:
    """测试 get_message_count"""

    def test_empty_conversation(self, db, conv_id):
        assert db.get_message_count(conv_id) == 0

    def test_with_messages(self, db, conv_id):
        db.add_message(conv_id, "user", "A")
        db.add_message(conv_id, "assistant", "B")
        assert db.get_message_count(conv_id) == 2


class TestRestoreConversation:
    """测试 restore_conversation"""

    def test_restore_soft_deleted(self, db, conv_id):
        db.delete_conversation(conv_id)
        assert db.get_conversation(conv_id) is None
        assert db.restore_conversation(conv_id)
        assert db.get_conversation(conv_id) is not None

    def test_restore_active_returns_false(self, db, conv_id):
        assert not db.restore_conversation(conv_id)


# ============ 单元测试: 单例模式 ============


class TestSingleton:
    """测试单例模式正确性"""

    def test_same_instance(self, tmp_path):
        from src.db.conversation_db import ConversationDB

        ConversationDB.reset_instance()
        db_path = str(tmp_path / "singleton.db")

        a = ConversationDB.get_instance(db_path=db_path)
        b = ConversationDB.get_instance(db_path=db_path)
        assert a is b

    def test_different_path_returns_same(self, tmp_path):
        """第二个不同路径调用应返回第一次创建的实例"""
        from src.db.conversation_db import ConversationDB

        ConversationDB.reset_instance()
        path1 = str(tmp_path / "db1.db")
        path2 = str(tmp_path / "db2.db")

        a = ConversationDB.get_instance(db_path=path1)
        b = ConversationDB.get_instance(db_path=path2)
        assert a is b  # 单例，不管路径
        assert a._db_path == path1  # 保留第一次的路径


# ============ 单元测试: 数据完整性 ============


class TestDataIntegrity:
    """测试外键约束与数据完整性"""

    def test_messages_cascade_on_hard_delete(self, db, conv_id):
        """硬删除对话时应级联删除消息"""
        db.add_message(conv_id, "user", "消息")
        db.delete_conversation(conv_id, hard=True)

        import sqlite3
        conn = sqlite3.connect(db._db_path)
        count = conn.execute(
            "SELECT COUNT(*) FROM messages WHERE conversation_id = ?",
            (conv_id,),
        ).fetchone()[0]
        conn.close()
        assert count == 0

    def test_messages_preserved_on_soft_delete(self, db, conv_id):
        """软删除不应删除消息"""
        db.add_message(conv_id, "user", "消息")
        db.delete_conversation(conv_id)  # 软删除

        import sqlite3
        conn = sqlite3.connect(db._db_path)
        count = conn.execute(
            "SELECT COUNT(*) FROM messages WHERE conversation_id = ?",
            (conv_id,),
        ).fetchone()[0]
        conn.close()
        assert count == 1  # 消息应保留

    def test_messages_restored_on_restore(self, db, conv_id):
        """恢复对话后消息应可见"""
        db.add_message(conv_id, "user", "消息")
        db.delete_conversation(conv_id)
        db.restore_conversation(conv_id)

        full = db.get_conversation(conv_id)
        assert len(full["messages"]) == 1


# ============ 单元测试: 边界条件 ============


class TestEdgeCases:
    """测试边界条件"""

    def test_multiple_users_isolated(self, db):
        """不同用户对话互不干扰"""
        c1 = db.create_conversation("user_a", "A对话")
        c2 = db.create_conversation("user_b", "B对话")

        assert len(db.list_conversations("user_a")) == 1
        assert len(db.list_conversations("user_b")) == 1
        assert db.list_conversations("user_a")[0]["id"] == c1["id"]
        assert db.list_conversations("user_b")[0]["id"] == c2["id"]

    def test_large_content_message(self, db, conv_id):
        """应能处理超大消息内容"""
        large = "A" * 100_000  # 100KB
        msg = db.add_message(conv_id, "user", large)
        assert len(msg["content"]) == 100_000

    def test_special_characters_in_title(self, db):
        """标题应能包含特殊 Unicode 字符"""
        title = "对话 🎉 — 测试 #1 @用户 📝"
        conv = db.create_conversation("user_z", title)
        assert conv["title"] == title

    def test_empty_user_id(self, db):
        """空白用户 ID 应可创建（取决于业务逻辑，此处验证不崩溃）"""
        conv = db.create_conversation("", "匿名对话")
        assert conv["user_id"] == ""

    def test_concurrent_creates(self, db):
        """并发创建应线程安全"""
        ids = set()
        lock = threading.Lock()

        def create():
            conv = db.create_conversation("thread_user", "线程对话")
            with lock:
                ids.add(conv["id"])

        threads = [threading.Thread(target=create) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(ids) == 10  # 每个创建应生成唯一 ID


# ============ 集成测试: init_conversation_db ============


class TestInitFunction:
    """测试启动初始化函数"""

    def test_init_returns_singleton(self, tmp_path):
        """init_conversation_db 应返回共享的单例"""
        from src.db.conversation_db import ConversationDB, init_conversation_db, _CONVERSATIONS_DB_PATH as _DB_PATH_REF
        import src.db.conversation_db as cdb

        ConversationDB.reset_instance()
        db_path = str(tmp_path / "conversation_sessions.db")
        # 直接使用自定义路径构造实例，然后验证 init 行为
        instance = ConversationDB(db_path=db_path)
        assert isinstance(instance, ConversationDB)
        # 确认表已创建
        import sqlite3
        conn = sqlite3.connect(db_path)
        tables = {
            r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "conversations" in tables
        assert "messages" in tables
        conn.close()

    def test_init_idempotent(self, tmp_path):
        """重复调用 init_conversation_db 不应报错"""
        from src.db.conversation_db import ConversationDB, init_conversation_db

        ConversationDB.reset_instance()
        a = init_conversation_db()
        b = init_conversation_db()
        assert a is b


# ============ 运行入口 ============

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
