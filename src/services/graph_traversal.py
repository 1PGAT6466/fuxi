"""
graph_traversal.py — Phase 8.1: 图遍历推理引擎
支持多跳实体遍历，替代 BFS 最短路径
"""
import json, os, logging
from typing import List, Dict, Set, Optional
from collections import deque

logger = logging.getLogger("graph_traversal")
GRAPH_FILE = os.path.join(os.path.dirname(__file__), "../../data/knowledge_graph.json")

def load_graph() -> dict:
    if os.path.exists(GRAPH_FILE):
        with open(GRAPH_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"nodes": [], "edges": []}

def multi_hop_traverse(
    start_entity: str,
    target_type: Optional[str] = None,
    max_hops: int = 3,
    relation_filter: Optional[str] = None
) -> Dict:
    """
    多跳图遍历引擎
    
    Args:
        start_entity: 起始实体名称
        target_type: 目标实体类型（可选，找到即停止）
        max_hops: 最大跳数（默认 3）
        relation_filter: 关系过滤（可选）
    
    Returns:
        {paths: [[entities]], entities: [distinct_entities]}
    """
    graph = load_graph()
    nodes = {n["id"]: n for n in graph.get("nodes", [])}
    edges = graph.get("edges", [])
    
    # 构建邻接表
    adj = {}
    for e in edges:
        s, t = e.get("source", ""), e.get("target", "")
        rel = e.get("relation", "related_to")
        if relation_filter and rel != relation_filter:
            continue
        adj.setdefault(s, []).append((t, rel))
        adj.setdefault(t, []).append((s, rel))
    
    if start_entity not in nodes:
        return {"paths": [], "entities": [], "error": f"Entity not found: {start_entity}"}
    
    # BFS 多跳遍历
    visited = {start_entity}
    paths = [[start_entity]]
    queue = deque([(start_entity, [start_entity], 0)])
    found_paths = []
    found_entities = set()
    
    while queue:
        current, path, depth = queue.popleft()
        if depth >= max_hops:
            continue
        
        for neighbor, rel in adj.get(current, []):
            if neighbor in visited and neighbor not in path:
                continue
            new_path = path + [neighbor]
            visited.add(neighbor)
            
            node = nodes.get(neighbor, {})
            ntype = node.get("type", "")
            
            if target_type and ntype == target_type:
                found_paths.append({
                    "path": new_path,
                    "hops": depth + 1,
                    "target_type": ntype
                })
                found_entities.add(neighbor)
            
            queue.append((neighbor, new_path, depth + 1))
    
    return {
        "paths": found_paths,
        "entities": list(found_entities),
        "start": start_entity,
        "hops_traversed": min(max_hops, depth if 'depth' in dir() else 0)
    }

def get_reachable_entities(entity: str, max_hops: int = 2) -> List[str]:
    """获取可达实体（用于 GraphRAG 上下文扩展）"""
    result = multi_hop_traverse(entity, max_hops=max_hops)
    return result.get("entities", [])
