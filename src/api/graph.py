"""
routers/graph.py — 知识图谱路由（v10.0）
负责：/api/graph, /api/graph/path, /api/graph/build, /api/graph/nodes
"""
import os, re, json
from collections import deque

from fastapi import APIRouter, Query, HTTPException, Request

from src.db.data_store import load_graph, save_graph, load_chunks
from src.config import ADMIN_TOKEN

router = APIRouter(tags=["知识图谱"])


def _check_admin_token(request: Request):
    token = request.headers.get("x-admin-token", "")
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="需要管理令牌")


def _bfs_path(nodes: dict, edges: list, start: str, end: str) -> list:
    """BFS 最短路径搜索"""
    if start not in nodes or end not in nodes:
        return []
    adj = {}
    for e in edges:
        adj.setdefault(e["from"], []).append(e["to"])
        adj.setdefault(e["to"], []).append(e["from"])
    queue = deque([[start]])
    visited = {start}
    while queue:
        path = queue.popleft()
        node = path[-1]
        if node == end:
            return path
        for nb in adj.get(node, []):
            if nb not in visited:
                visited.add(nb)
                queue.append(path + [nb])
    return []


def _describe_path(path: list, edges: list) -> list:
    """路径描述"""
    desc = []
    for i in range(len(path) - 1):
        a, b = path[i], path[i + 1]
        rel = "connects_to"
        for e in edges:
            if (e["from"] == a and e["to"] == b) or (e["from"] == b and e["to"] == a):
                rel = e.get("relation", "connects_to")
                break
        desc.append({"from": a, "to": b, "relation": rel})
    return desc


# ============ 实体抽取（规则匹配）============

def _extract_entities(text: str) -> dict:
    """从文档文本抽取实体和关系"""
    entities = {}
    # 设备名
    for m in re.finditer(r'\b(LSW\d+|AR\d+|AP[\-]?\d*|AC\d*|FW\d*)\b', text):
        name = m.group()
        if name not in entities:
            entities[name] = {"type": "device", "mentions": 0, "relations": []}
        entities[name]["mentions"] += 1
    # VLAN
    for m in re.finditer(r'VLAN\s*(\d+)', text, re.I):
        vid = f"VLAN {m.group(1)}"
        if vid not in entities:
            entities[vid] = {"type": "vlan", "mentions": 0, "relations": []}
        entities[vid]["mentions"] += 1
    # IP 段
    for m in re.finditer(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/\d{1,2})', text):
        ip = m.group()
        if ip not in entities:
            entities[ip] = {"type": "subnet", "mentions": 0, "relations": []}
        entities[ip]["mentions"] += 1
    # SSID
    for m in re.finditer(r'(SSID|WiFi|Wi-Fi)[::\s]*([\w\-]+)', text, re.I):
        ssid = m.group(2)
        key = f"SSID:{ssid}"
        if key not in entities:
            entities[key] = {"type": "ssid", "mentions": 0, "relations": []}
        entities[key]["mentions"] += 1
    # 协议
    for m in re.finditer(r'\b(OSPF|BGP|STP|RSTP|MSTP|HSRP|VRRP|DHCP|DNS|NTP|SNMP|SSH|Telnet|HTTP|HTTPS|802\.1X|WPA2|WPA3|AES|TKIP)\b', text):
        proto = m.group()
        if proto not in entities:
            entities[proto] = {"type": "protocol", "mentions": 0, "relations": []}
        entities[proto]["mentions"] += 1
    # 标准件
    for m in re.finditer(r'(GP-?\d+|EP-?\d+|RP-?\d+|SB-[NL]-\d+|AP-\d+-\d+|GB-?\d+)', text):
        name = m.group()
        if name not in entities:
            entities[name] = {"type": "standard_part", "mentions": 0, "relations": []}
        entities[name]["mentions"] += 1
    # 材料
    for m in re.finditer(r'(SUJ2|SKD61|SKH51|S136|SKD11|50#)', text):
        name = m.group()
        if name not in entities:
            entities[name] = {"type": "material", "mentions": 0, "relations": []}
        entities[name]["mentions"] += 1
    # 塑料
    for m in re.finditer(r'(LCP|PA66|PBT|POM|PPS|PA6)', text):
        name = m.group()
        if name not in entities:
            entities[name] = {"type": "plastic", "mentions": 0, "relations": []}
        entities[name]["mentions"] += 1
    # 传感器
    for m in re.finditer(r'(E3Z-?\w+-\w+|E2E-?\w+-\w+|D-?\w+|FU-?\d+\w*|HG-?K\w+|CM2-?\w+|SY\d+|FR-?D\w+|G3NA-?\w+|E5CC)', text):
        name = m.group()
        if name not in entities:
            entities[name] = {"type": "sensor_or_actuator", "mentions": 0, "relations": []}
        entities[name]["mentions"] += 1
    # 供应商
    for m in re.finditer(r'(米思米|盘起|东莞天田|深圳恒钢|翁开尔|住友重机|蔡司\s*ZEISS|西门子|欧姆龙|三菱)', text):
        name = m.group()
        if name not in entities:
            entities[name] = {"type": "supplier", "mentions": 0, "relations": []}
        entities[name]["mentions"] += 1
    return entities


def _build_relations(entities: dict, text: str) -> dict:
    """构建实体关系（共现+权重）"""
    edges = []
    keys = list(entities.keys())
    edge_counts = {}
    for para in text.split("\n\n"):
        in_para = [k for k in keys if k in para]
        for i, e1 in enumerate(in_para):
            for e2 in in_para[i + 1:]:
                key1 = (e1, e2)
                key2 = (e2, e1)
                edge_counts[key1] = edge_counts.get(key1, 0) + 1
                edge_counts[key2] = edge_counts.get(key2, 0) + 1
                rel = f"{e2}:co_occurs"
                if rel not in entities[e1]["relations"]:
                    entities[e1]["relations"].append(rel)
                rel2 = f"{e1}:co_occurs"
                if rel2 not in entities[e2]["relations"]:
                    entities[e2]["relations"].append(rel2)
    for (e1, e2), count in edge_counts.items():
        if count >= 2:
            edges.append({"from": e1, "to": e2, "weight": count, "relation": "co_occurs"})
    return entities


# ============ API 端点 ============

@router.get("/api/graph")
async def graph_query(q: str = Query("")):
    """图谱实体查询 + BFS 路径搜索"""
    graph = load_graph()
    nodes = graph.get("nodes", {})
    edges = graph.get("edges", [])
    path_keywords = ["→", "->", "到", "至", "to", "连接", "经过"]
    is_path = any(kw in q for kw in path_keywords) if q else False
    if is_path and q:
        import re as _re
        tokens = _re.split(r"[→\->到至]|连接|经过|to", q, flags=_re.I)
        tokens = [t.strip() for t in tokens if t.strip()]
        if len(tokens) >= 2:
            start, end = tokens[0].upper(), tokens[1].upper()
            path = _bfs_path(nodes, edges, start, end)
            if path:
                return {"query": q, "type": "path", "path": path, "length": len(path) - 1,
                        "description": _describe_path(path, edges)}
            else:
                return {"query": q, "type": "path", "path": [], "message": f"未找到 {start} → {end} 的路径"}
    results = []
    q_lower = q.lower() if q else ""
    for entity, info in nodes.items():
        if not q or q_lower in entity.lower() or entity.lower() in q_lower:
            related = []
            for e in edges:
                if e["from"] == entity:
                    related.append({"to": e["to"], "relation": e["relation"]})
                elif e["to"] == entity:
                    related.append({"from": e["from"], "relation": e["relation"]})
            results.append({"entity": entity, **info, "related": related[:10]})
    # 兼容前端：同时返回 entities(list) 和 nodes(dict)
    nodes_out = {}
    for r in results[:20]:
        name = r.pop("entity", "?")
        nodes_out[name] = r
    return {
        "query": q, "type": "entity", "matches": len(results), "entities": results[:20],
        "nodes": nodes_out, "edges": edges[:100],
        "total_nodes": len(nodes), "total_edges": len(edges)
    }


@router.get("/api/graph/path")
async def graph_path(source: str, target: str):
    """BFS 最短路径查询"""
    graph = load_graph()
    nodes = graph.get("nodes", {})
    edges = graph.get("edges", [])
    
    # Smart node matching: try exact, then partial match
    def _find_node(name, nodes):
        if name in nodes:
            return name
        upper = name.upper()
        if upper in nodes:
            return upper
        # Partial match
        for n in nodes:
            if name in n or upper in n:
                return n
        return name
    
    src_key = _find_node(source, nodes)
    tgt_key = _find_node(target, nodes)
    path = _bfs_path(nodes, edges, src_key, tgt_key)
    if path:
        return {
            "source": source, "target": target, "path": path,
            "length": len(path) - 1, "description": _describe_path(path, edges)
        }
    return {"source": source, "target": target, "path": [], "message": "无路径"}


@router.get("/api/graph/nodes")
async def graph_nodes():
    """知识图谱节点列表"""
    try:
        graph = load_graph()
        nodes = []
        for entity, info in graph.get("nodes", {}).items():
            nodes.append({
                "id": entity,
                "type": info.get("type", "unknown"),
                "mentions": info.get("count", info.get("mentions", 0)),
                "files": info.get("files", [])[:5],
                "relations": info.get("relations", [])[:10]
            })
        edges = graph.get("edges", [])
        return {"nodes": nodes, "edges": edges, "total": len(nodes)}
    except Exception as e:
        return {"error": str(e)}


@router.post("/api/graph/build")
async def build_graph(request: Request):
    """从全部文档重建关系图谱"""
    _check_admin_token(request)
    chunks = load_chunks()
    files = {}
    for c in chunks:
        fh = c.get("file_hash", "")
        if fh not in files:
            files[fh] = {"name": c.get("file_name", ""), "text": "", "size": 0}
        files[fh]["text"] += c.get("text", "")[:2000] + "\n"
        files[fh]["size"] += 1
    sorted_files = sorted(files.values(), key=lambda x: x["size"], reverse=True)[:50]
    
    # 使用 knowledge_evolver 的实体发现（12 种类型 regex 覆盖）
    from src.services.evolver import discover_entities, evolve_graph
    for info in sorted_files:
        entities = discover_entities(info["text"])
        if entities:
            evolve_graph(entities, info["name"])
    
    # 读取更新后的图谱
    from src.db.data_store import load_graph
    all_graph = load_graph()
    nodes = all_graph.get("nodes", {})
    return {
        "status": "ok",
        "entities": len(nodes),
        "edges": len(all_graph.get("edges", [])),
        "top_entities": sorted(
            [{"id": k, **v} for k, v in nodes.items()],
            key=lambda x: x.get("count", x.get("mentions", 0)),
            reverse=True
        )[:10]
    }
