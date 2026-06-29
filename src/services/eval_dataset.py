"""
eval_dataset.py — Phase 1.3.1: 评测数据集管理
"""
import sqlite3, json, os, logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

DB_PATH = os.path.expanduser("~/kb-server/data/eval.db")


def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS eval_dataset (
            id TEXT PRIMARY KEY,
            query TEXT NOT NULL,
            expected_answer TEXT,
            expected_chunks TEXT,
            expected_entities TEXT,
            category TEXT DEFAULT 'general',
            difficulty TEXT DEFAULT 'medium',
            source TEXT DEFAULT 'manual',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    return conn


def add_case(case: Dict) -> bool:
    """添加评测用例"""
    conn = _get_conn()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO eval_dataset (id, query, expected_answer, expected_chunks, expected_entities, category, difficulty, source) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                case["id"],
                case["query"],
                case.get("expected_answer"),
                json.dumps(case.get("expected_chunks", []), ensure_ascii=False),
                json.dumps(case.get("expected_entities", []), ensure_ascii=False),
                case.get("category", "general"),
                case.get("difficulty", "medium"),
                case.get("source", "manual"),
            )
        )
        conn.commit()
        return True
    except Exception as e:
        logger.warning(f"add_case failed: {e}")
        return False
    finally:
        conn.close()


def get_cases(category: str = None, limit: int = 100) -> List[Dict]:
    """获取评测用例"""
    conn = _get_conn()
    try:
        if category:
            rows = conn.execute("SELECT * FROM eval_dataset WHERE category=? LIMIT ?", (category, limit)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM eval_dataset LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def count() -> int:
    conn = _get_conn()
    try:
        return conn.execute("SELECT COUNT(*) FROM eval_dataset").fetchone()[0]
    finally:
        conn.close()


# 30 条种子评测用例
SEED_CASES = [
    {"id": "f001", "query": "权限管理功能在哪里", "category": "fact", "difficulty": "easy", "source": "manual"},
    {"id": "f002", "query": "如何创建部门", "category": "fact", "difficulty": "easy", "source": "manual"},
    {"id": "f003", "query": "流程引擎有什么功能", "category": "fact", "difficulty": "easy", "source": "manual"},
    {"id": "f004", "query": "证照管理怎么操作", "category": "fact", "difficulty": "easy", "source": "manual"},
    {"id": "f005", "query": "移动引擎是什么", "category": "fact", "difficulty": "easy", "source": "manual"},
    {"id": "f006", "query": "门户引擎配置方法", "category": "fact", "difficulty": "medium", "source": "manual"},
    {"id": "f007", "query": "SAP集成怎么设置", "category": "fact", "difficulty": "medium", "source": "manual"},
    {"id": "f008", "query": "资产管理模块功能", "category": "fact", "difficulty": "easy", "source": "manual"},
    {"id": "f009", "query": "项目管理如何使用", "category": "fact", "difficulty": "easy", "source": "manual"},
    {"id": "f010", "query": "预算管理在哪里", "category": "fact", "difficulty": "easy", "source": "manual"},
    {"id": "f011", "query": "公文管理流程", "category": "fact", "difficulty": "medium", "source": "manual"},
    {"id": "f012", "query": "报表怎么导出", "category": "fact", "difficulty": "medium", "source": "manual"},
    {"id": "f013", "query": "系统参数在哪里设置", "category": "fact", "difficulty": "easy", "source": "manual"},
    {"id": "f014", "query": "日程管理功能", "category": "fact", "difficulty": "easy", "source": "manual"},
    {"id": "f015", "query": "组织架构怎么管理", "category": "fact", "difficulty": "medium", "source": "manual"},
    {"id": "c001", "query": "权限管理和证照管理有什么区别", "category": "comparison", "difficulty": "hard", "source": "manual"},
    {"id": "c002", "query": "门户引擎和移动引擎的区别", "category": "comparison", "difficulty": "hard", "source": "manual"},
    {"id": "c003", "query": "项目管理和预算管理的关系", "category": "comparison", "difficulty": "hard", "source": "manual"},
    {"id": "t001", "query": "如何创建审批流程", "category": "procedural", "difficulty": "medium", "source": "manual"},
    {"id": "t002", "query": "怎么配置表单字段", "category": "procedural", "difficulty": "medium", "source": "manual"},
    {"id": "t003", "query": "如何添加用户权限", "category": "procedural", "difficulty": "medium", "source": "manual"},
    {"id": "t004", "query": "怎么设置流程路径", "category": "procedural", "difficulty": "hard", "source": "manual"},
    {"id": "t005", "query": "如何导出报表数据", "category": "procedural", "difficulty": "medium", "source": "manual"},
    {"id": "x001", "query": "为什么流程审批失败", "category": "causal", "difficulty": "hard", "source": "manual"},
    {"id": "x002", "query": "权限不足的原因", "category": "causal", "difficulty": "medium", "source": "manual"},
    {"id": "x003", "query": "为什么无法登录系统", "category": "causal", "difficulty": "medium", "source": "manual"},
    {"id": "x004", "query": "流程卡住的原因", "category": "causal", "difficulty": "hard", "source": "manual"},
    {"id": "x005", "query": "为什么报表数据不对", "category": "causal", "difficulty": "hard", "source": "manual"},
    {"id": "g001", "query": "系统有哪些模块", "category": "aggregation", "difficulty": "easy", "source": "manual"},
    {"id": "g002", "query": "支持哪些文件格式上传", "category": "aggregation", "difficulty": "medium", "source": "manual"},
]


def seed_dataset():
    """初始化种子评测集"""
    existing = count()
    if existing >= 30:
        logger.info(f"评测集已有 {existing} 条，跳过 seed")
        return
    for case in SEED_CASES:
        add_case(case)
    logger.info(f"已初始化 {len(SEED_CASES)} 条种子评测用例")
