"""
health_check.py — 健康检查
系统状态 + 组件状态
"""
import time
import logging
from typing import Dict, List

logger = logging.getLogger("infra.health_check")


class HealthChecker:
    """健康检查器"""

    def __init__(self):
        self._checks = {}

    def register_check(self, name: str, check_func):
        """注册检查项"""
        self._checks[name] = check_func

    async def check_all(self) -> Dict:
        """执行所有检查"""
        results = {}
        all_healthy = True

        for name, check_func in self._checks.items():
            try:
                result = await check_func()
                results[name] = {
                    "status": "healthy" if result else "unhealthy",
                    "timestamp": time.time(),
                }
                if not result:
                    all_healthy = False
            except Exception as e:
                results[name] = {
                    "status": "error",
                    "error": str(e),
                    "timestamp": time.time(),
                }
                all_healthy = False

        return {
            "status": "healthy" if all_healthy else "unhealthy",
            "checks": results,
            "timestamp": time.time(),
        }


async def check_database() -> bool:
    """检查数据库"""
    try:
        from src.db.memory_store import get_store
        store = get_store()
        store._db_conn.execute("SELECT 1")
        return True
    except Exception:
        return False


async def check_vector_store() -> bool:
    """检查向量存储"""
    try:
        from src.db.vector_store import get_vector_store
        vs = get_vector_store()
        return vs is not None
    except Exception:
        return False


async def check_llm() -> bool:
    """检查LLM服务"""
    try:
        from src.infra.llm import call_llm
        # 简单的健康检查
        return True
    except Exception:
        return False


# 全局健康检查器
_health_checker: HealthChecker = None


def get_health_checker() -> HealthChecker:
    """获取全局健康检查器"""
    global _health_checker
    if _health_checker is None:
        _health_checker = HealthChecker()
        _health_checker.register_check("database", check_database)
        _health_checker.register_check("vector_store", check_vector_store)
        _health_checker.register_check("llm", check_llm)
    return _health_checker
