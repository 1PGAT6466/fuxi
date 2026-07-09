"""
graph.py — 太阳·图谱路由
route_to_categories + get_entity_context
"""
import logging
from typing import Dict, List

logger = logging.getLogger("taiyang.graph")


class GraphRouter:
    """图谱路由器"""

    def route_to_categories(self, query: str) -> List[str]:
        """路由到分类"""
        try:
            from src.db.memory_store import get_store
            store = get_store()
            rows = store._db_conn.execute(
                "SELECT DISTINCT category FROM chunks WHERE category IS NOT NULL LIMIT 10"
            ).fetchall()
            return [r[0] for r in rows if r[0]]
        except Exception as e:  # TODO: Narrow exception type
            logger.warning("Exception 失败: %s", e, exc_info=True)
            return []

    def get_entity_context(self, entity_name: str) -> Dict:
        """获取实体上下文"""
        try:
            from src.db.memory_store import get_store
            store = get_store()
            rows = store._db_conn.execute(
                "SELECT * FROM entities WHERE name LIKE ? LIMIT 5",
                (f"%{entity_name}%",)
            ).fetchall()
            if rows:
                return {"entity": entity_name, "found": True, "count": len(rows)}
        except Exception as e:  # TODO: Narrow exception type
            logger.warning("Exception 失败: %s", e, exc_info=True)
        return {"entity": entity_name, "found": False, "count": 0}
