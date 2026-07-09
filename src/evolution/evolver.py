"""
evolver.py — 知识进化封装层（第九宫 · 中宫）

封装 src/services/evolver.py 的实体发现、关系推理、图谱增量更新功能，
在第九宫（EvolutionGua）框架内统一调用。

不复制代码，全部 import 自 services/evolver。
"""

import logging
from typing import Dict, List, Any

# ---- 从 services 导入原有实现 ----
from src.services.evolver import (
    discover_entities,
    infer_relations,
    evolve_graph,
    get_graph_stats,
    get_graph_nodes,
)

logger = logging.getLogger("evolution.evolver")


class EvolutionEvolver:
    """知识进化器 — 第九宫的知识图谱进化组件

    封装 services/evolver 的底层实现，提供一致的演化层接口。

    主要功能：
      - discover():     从文本中发现实体（基于 RegEx 模式匹配）
      - infer():        推断实体间关系（三元组）
      - evolve():       增量更新知识图谱（新实体 + 新关系入库）
      - stats():        获取图谱统计信息
      - get_nodes():    获取图谱节点列表
    """

    def __init__(self):
        self._initialized = True
        logger.info("[EvolutionEvolver] 初始化完成")

    def discover(self, text: str) -> Dict[str, List[str]]:
        """从文本中发现实体

        基于 RegEx 模式匹配（如网络设备 LSW、标准件 GP-/EP-/SB-、
        材料 SUJ2/SKD61、供应商 米思米/盘起 等）发现结构化实体。

        Args:
            text: 待分析的文本

        Returns:
            {entity_type: [entity_name, ...], ...}
        """
        return discover_entities(text)

    def infer(
        self,
        nodes: Dict[str, Any],
        edges: List,
        text: str,
        file_name: str = "",
    ) -> List:
        """推断实体间关系

        基于 Ontology 关系规则 + 文本共现推断实体关系三元组。

        Args:
            nodes:    节点字典 {name: {type, label, ...}}
            edges:    已有边列表
            text:     分析文本
            file_name: 来源文件名

        Returns:
            新边列表 [(from, to, relation), ...]
        """
        return infer_relations(nodes, edges, text, file_name)

    def evolve(
        self,
        new_entities: Dict[str, List[str]],
        file_name: str = "",
    ) -> Dict[str, int]:
        """增量更新知识图谱

        将新发现的实体和推断出的关系持久化到 knowledge_graph.json。
        使用原子写入防止数据损坏。

        Args:
            new_entities: 新发现的实体 {type: [names]}
            file_name:    来源文件名

        Returns:
            {"entities_added": int, "edges_added": int}
        """
        return evolve_graph(new_entities, file_name=file_name)

    def stats(self) -> Dict:
        """获取知识图谱统计信息

        Returns:
            {
                "total_entities": int,
                "total_edges": int,
                "entity_types": {type: count, ...},
                "last_updated": str,
            }
        """
        return get_graph_stats()

    def get_nodes(self) -> Dict:
        """获取知识图谱节点与边列表

        Returns:
            {
                "nodes": [{"id": ..., "type": ..., "label": ..., "mentions": ..., "files": [...]}, ...],
                "edges": [{"from": ..., "to": ..., "relation": ...}, ...],
            }
        """
        return get_graph_nodes()


# ---- 便捷函数 ----

def evolve_knowledge_graph(
    new_entities: Dict[str, List[str]],
    file_name: str = "",
) -> Dict[str, int]:
    """便捷函数：增量更新知识图谱

    Args:
        new_entities: 新发现的实体
        file_name:    来源文件名

    Returns:
        {"entities_added": int, "edges_added": int}
    """
    evolver = EvolutionEvolver()
    return evolver.evolve(new_entities, file_name=file_name)


def discover_entities_from_text(text: str) -> Dict[str, List[str]]:
    """便捷函数：从文本中发现实体"""
    evolver = EvolutionEvolver()
    return evolver.discover(text)


def get_knowledge_graph_stats() -> Dict:
    """便捷函数：获取图谱统计"""
    evolver = EvolutionEvolver()
    return evolver.stats()


def get_knowledge_graph_nodes() -> Dict:
    """便捷函数：获取图谱节点列表"""
    evolver = EvolutionEvolver()
    return evolver.get_nodes()
