"""
graph_enhanced.py — 知识图谱增强
==================================
修复内容：
1. 清洗无意义实体（IP 地址、过于泛化的缩写）
2. 图谱查询缓存（避免每次 read_text + json.loads）
3. LLM 辅助实体抽取（可选）
4. 图谱参与检索（1-hop 邻居扩展）
"""

import os
import re
import json
import time
import logging
from typing import List, Dict, Optional
from pathlib import Path

from src.config import DATA_DIR, GRAPH_PATH

logger = logging.getLogger(__name__)

# ============================================================
# 图谱缓存 — 避免每次请求都读文件
# ============================================================

_graph_cache: Optional[dict] = None
_graph_mtime: float = 0


def load_graph_cached() -> dict:
    """带缓存的图谱加载"""
    global _graph_cache, _graph_mtime
    
    if not GRAPH_PATH.exists():
        return {"nodes": {}, "edges": [], "meta": {}}
    
    try:
        mtime = GRAPH_PATH.stat().st_mtime
        if _graph_cache is not None and mtime == _graph_mtime:
            return _graph_cache
        
        _graph_cache = json.loads(GRAPH_PATH.read_text(encoding="utf-8"))
        _graph_mtime = mtime
        return _graph_cache
    except Exception as e:
        logger.warning(f"[Graph] load failed: {e}")
        if _graph_cache:
            return _graph_cache
        return {"nodes": {}, "edges": [], "meta": {}}


def invalidate_graph_cache():
    """手动使缓存失效（写入图谱后调用）"""
    global _graph_cache, _graph_mtime
    _graph_cache = None
    _graph_mtime = 0


# ============================================================
# 实体清洗
# ============================================================

# 需要从图谱中移除的实体模式
CLEAN_PATTERNS = [
    r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$',  # IP 地址
    r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/\d{1,2}$',  # IP 段
    r'^[A-Z]{1,3}$',  # 过短的缩写（如 COM, NET）
]

# 实体黑名单
ENTITY_BLACKLIST = {
    'COM', 'CN', 'NET', 'ORG', 'HTTP', 'HTTPS', 'WWW', 'XML', 'HTML', 'JSON',
    'USB', 'HDMI', 'VGA', 'DVI', 'LED', 'LCD', 'CPU', 'GPU', 'RAM', 'ROM',
    'PVC', 'PE', 'PP', 'PS', 'PET',
    'SET', 'GET', 'PUT', 'DEL', 'PDF', 'DOC', 'XLS', 'TXT',
    'API', 'URL', 'DNS', 'TCP', 'UDP', 'FTP', 'SSH', 'VPN',
    'OK', 'NG', 'YES', 'NO', 'NULL', 'NONE', 'TRUE', 'FALSE',
}


def clean_graph() -> Dict:
    """清洗图谱：移除无意义实体和孤立边"""
    graph = load_graph_cached()
    nodes = graph.get("nodes", {})
    edges = graph.get("edges", [])
    
    initial_nodes = len(nodes)
    initial_edges = len(edges)
    
    # 清洗节点
    cleaned_nodes = {}
    removed_entities = set()
    
    for name, info in nodes.items():
        # 移除 IP 地址
        if any(re.match(pat, name) for pat in CLEAN_PATTERNS):
            removed_entities.add(name)
            continue
        # 移除黑名单
        if name.upper() in ENTITY_BLACKLIST:
            removed_entities.add(name)
            continue
        # 移除出现次数太少的
        if info.get("count", 0) < 2:
            removed_entities.add(name)
            continue
        cleaned_nodes[name] = info
    
    # 清洗边（移除引用已删除实体的边）
    cleaned_edges = []
    for e in edges:
        src = e[0] if isinstance(e, list) else e.get("from", "")
        dst = e[1] if isinstance(e, list) else e.get("to", "")
        if src not in removed_entities and dst not in removed_entities:
            cleaned_edges.append(e)
    
    # 更新图谱
    graph["nodes"] = cleaned_nodes
    graph["edges"] = cleaned_edges
    graph["meta"]["total_entities"] = len(cleaned_nodes)
    graph["meta"]["total_edges"] = len(cleaned_edges)
    
    # 原子写入
    tmp_path = str(GRAPH_PATH) + '.tmp'
    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(graph, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, str(GRAPH_PATH))
    
    invalidate_graph_cache()
    
    result = {
        "removed_entities": initial_nodes - len(cleaned_nodes),
        "removed_edges": initial_edges - len(cleaned_edges),
        "remaining_entities": len(cleaned_nodes),
        "remaining_edges": len(cleaned_edges),
    }
    logger.info(f"[Graph] cleaned: {result}")
    return result


# ============================================================
# 图谱关系增强
# ============================================================

# 关系类型定义
RELATION_TYPES = {
    "connects_to": {"label": "连接", "domain": ["network_device", "plc"], "range": ["network_device", "vlan", "subnet"]},
    "supplied_by": {"label": "供应", "domain": ["standard_part", "material", "sensor"], "range": ["supplier"]},
    "belongs_to": {"label": "归属", "domain": ["ip", "ssid"], "range": ["vlan", "subnet"]},
    "compatible_with": {"label": "兼容", "domain": ["standard_part", "material"], "range": ["standard_part", "material"]},
    "controls": {"label": "控制", "domain": ["plc"], "range": ["sensor", "network_device"]},
    "uses": {"label": "使用", "domain": ["network_device", "plc"], "range": ["material", "standard_part"]},
    "related_to": {"label": "相关", "domain": [], "range": []},  # 通用兜底
}


async def enhance_relations_llm(text: str, entities: List[str]) -> List[tuple]:
    """用 LLM 推理实体关系（可选，需要 DeepSeek API）"""
    if len(entities) < 2:
        return []
    
    entity_str = ", ".join(entities[:20])
    prompt = f"""从以下文本中判断这些实体之间的关系，返回 JSON 三元组列表：

实体：{entity_str}
文本片段：{text[:1500]}

关系类型：connects_to, supplied_by, belongs_to, compatible_with, controls, uses

返回格式：[{{"from": "实体A", "to": "实体B", "relation": "关系类型"}}, ...]
只返回 JSON，不要解释。"""
    
    try:
        from src.services.llm import call_ai_raw
        result = await call_ai_raw(prompt, max_tokens=800)
        parsed = json.loads(result)
        return [(e["from"], e["to"], e["relation"]) for e in parsed if "from" in e and "to" in e]
    except Exception as e:
        logger.debug(f"[Graph] LLM relation inference failed: {e}")
        return []


# ============================================================
# 图谱参与检索
# ============================================================

def get_entity_neighbors(entity: str, max_hops: int = 1) -> List[Dict]:
    """获取实体的 N-hop 邻居"""
    graph = load_graph_cached()
    nodes = graph.get("nodes", {})
    edges = graph.get("edges", [])
    
    if entity not in nodes:
        return []
    
    neighbors = []
    visited = {entity}
    frontier = [entity]
    
    for hop in range(max_hops):
        next_frontier = []
        for current in frontier:
            for e in edges:
                src = e[0] if isinstance(e, list) else e.get("from", "")
                dst = e[1] if isinstance(e, list) else e.get("to", "")
                rel = e[2] if isinstance(e, list) and len(e) > 2 else e.get("relation", "related_to")
                
                neighbor = None
                if src == current and dst not in visited:
                    neighbor = dst
                elif dst == current and src not in visited:
                    neighbor = src
                
                if neighbor:
                    visited.add(neighbor)
                    next_frontier.append(neighbor)
                    neighbors.append({
                        "entity": neighbor,
                        "relation": rel,
                        "hop": hop + 1,
                        "type": nodes.get(neighbor, {}).get("type", "unknown"),
                    })
        frontier = next_frontier
    
    return neighbors


def expand_query_with_graph(query: str, max_entities: int = 3) -> str:
    """用图谱实体扩展查询"""
    graph = load_graph_cached()
    nodes = graph.get("nodes", {})
    
    # 找到查询中命中的实体
    matched_entities = []
    q_upper = query.upper()
    for name in nodes:
        if name.upper() in q_upper and len(name) > 2:
            matched_entities.append(name)
    
    if not matched_entities:
        return query
    
    # 获取邻居
    expansion_terms = set()
    for entity in matched_entities[:max_entities]:
        neighbors = get_entity_neighbors(entity, max_hops=1)
        for n in neighbors[:3]:
            expansion_terms.add(n["entity"])
    
    if expansion_terms:
        return query + " " + " ".join(expansion_terms)
    return query


def get_entity_context_for_query(query: str) -> str:
    """为查询生成图谱上下文（注入到 LLM prompt）"""
    graph = load_graph_cached()
    nodes = graph.get("nodes", {})
    edges = graph.get("edges", [])
    
    # 找到命中的实体
    matched = []
    q_upper = query.upper()
    for name, info in nodes.items():
        if name.upper() in q_upper and len(name) > 2:
            # 找关系
            related = []
            for e in edges:
                src = e[0] if isinstance(e, list) else e.get("from", "")
                dst = e[1] if isinstance(e, list) else e.get("to", "")
                rel = e[2] if isinstance(e, list) and len(e) > 2 else e.get("relation", "related_to")
                if src == name:
                    related.append(f"{name} --{rel}--> {dst}")
                elif dst == name:
                    related.append(f"{src} --{rel}--> {name}")
            matched.append({"entity": name, "type": info.get("type", ""), "related": related[:5]})
    
    if not matched:
        return ""
    
    ctx_parts = ["\n[知识图谱上下文]"]
    for m in matched[:3]:
        ctx_parts.append(f"- 实体: {m['entity']} (类型: {m['type']})")
        for rel in m["related"]:
            ctx_parts.append(f"  {rel}")
    
    return "\n".join(ctx_parts)
