"""
knowledge_evolver — 知识图谱进化模块 (v1.50)
=============================================
为 auto_classifier 提供 EntityGraph 接口，
内部委托到 src/services/evolver.py 的图谱函数。
"""
import json
import logging
from datetime import datetime

from src.services.evolver import (
    GRAPH_FILE,
    discover_entities,
    infer_relations,
    evolve_graph,
    get_graph_stats,
    get_graph_nodes,
)

logger = logging.getLogger(__name__)

__all__ = ["EntityGraph", "discover_entities", "infer_relations", "evolve_graph",
           "get_graph_stats", "get_graph_nodes"]


class EntityGraph:
    """
    知识图谱读写封装，提供实体增删改查 + 持久化。
    """

    def __init__(self):
        self._graph = {"nodes": {}, "edges": [], "meta": {
            "total_entities": 0, "total_edges": 0, "last_updated": "", "source_files": []
        }}
        if GRAPH_FILE.exists():
            try:
                self._graph = json.loads(GRAPH_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass
        self._graph.setdefault("nodes", {})
        self._graph.setdefault("edges", [])
        self._graph.setdefault("meta", {"total_entities": 0, "total_edges": 0, "last_updated": "", "source_files": []})

    def upsert_entity(self, name: str, entity_type: str, metadata: dict = None):
        """插入或更新实体"""
        now = datetime.now().isoformat()
        if name not in self._graph["nodes"]:
            self._graph["nodes"][name] = {
                "type": entity_type,
                "label": entity_type,
                "first_seen": now,
                "count": 1,
            }
        else:
            self._graph["nodes"][name]["count"] = self._graph["nodes"][name].get("count", 0) + 1
            self._graph["nodes"][name]["last_seen"] = now

        if metadata:
            self._graph["nodes"][name].update(metadata)

    def get_entity(self, name: str) -> dict:
        return self._graph["nodes"].get(name, {})

    def remove_entity(self, name: str):
        self._graph["nodes"].pop(name, None)

    def add_edge(self, src: str, dst: str, relation: str):
        edge = [src, dst, relation]
        if edge not in self._graph["edges"]:
            self._graph["edges"].append(edge)

    def save(self):
        """持久化图谱（原子写入）"""
        self._graph["meta"]["total_entities"] = len(self._graph["nodes"])
        self._graph["meta"]["total_edges"] = len(self._graph["edges"])
        self._graph["meta"]["last_updated"] = datetime.now().isoformat()

        import os as _os
        GRAPH_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = str(GRAPH_FILE) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._graph, f, ensure_ascii=False, indent=2)
        _os.replace(tmp, str(GRAPH_FILE))

    @property
    def stats(self) -> dict:
        return {
            "total_entities": len(self._graph["nodes"]),
            "total_edges": len(self._graph["edges"]),
        }
