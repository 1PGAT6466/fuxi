"""
knowledge_evolver.py — 知识图谱自动进化 (v13.0)
基于 Ontology 骨架 → 填充实体（血肉）→ 关系推理

本体（Ontology）定义规则，知识图谱（KG）记录事实。
"""
import json, re
from datetime import datetime

from src.config import DATA_DIR
import logging; logger = logging.getLogger(__name__)

GRAPH_FILE = DATA_DIR / "knowledge_graph.json"

# 实体发现模式（从 ontology.py 精简内联，避免循环引用）
ENTITY_PATTERNS = {
    "network_device":  r'\b(LSW\d+[\-]?\w*|RG-\w+[\-]?\w*)\b',
    "standard_part":   r'\b(GP-\d{2,4}[\-]?\w*|EP-\d{2,4}[\-]?\w*|RP-\d{2,4}[\-]?\w*|SB-\d{2,4}[\-]?\w*)\b',
    "material":        r'\b(SUJ2|SKD61|SKH51|S136|SKD11|DC53|NAK80|718H|P20|H13|LCP|PA66|PBT|POM|PPS|PA6|PA12|ABS|PC|PP|PE|PEEK)\b',
    "supplier":        r'(米思米|盘起|东莞天田|深圳恒钢|翁开尔|住友|蔡司|西门子|欧姆龙|三菱|基恩士|SMC|FESTO)',
    "standard":        r'\b(GB/T\s*\d+[\.\-]?\d*|ISO\s*\d+|JIS\s*\w+\d+|DIN\s*\d+)',
    "vlan":            r'\bVLAN\s*\d+\b',
    "subnet":          r'\b(172\.25\.\d{1,3}\.\d{1,3}(?:/\d{1,2})?)\b',
    "ip":              r'\b(172\.25\.\d{1,3}\.\d{1,3})\b',
    "sensor":          r'\b(E3Z[\-]?\w+|E2E[\-]?\w+|EE-SX\d+|TL-\w+|D4[\-]\w+|FX-\w+)\b',
    "plc":             r'\b(S7[- ]?1200|S7[- ]?1500|FX5U|CP1H|KV-\w+|TM2\w+)\b',
    "model":           r'\b(CM2[\-]?\d{2,4}|CJ2[\-]?\d{2,4}|MY\d[\-]?\w*|E3Z[\-]?\w+|D4[\-]\w+)\b',
    "document_ref":    r'\b(SOP-\w+|WI-\w+|QR-\w+|FM-\w+)\b',
}

# 实体类型中文标签
TYPE_LABELS = {
    "network_device": "网络设备", "standard_part": "标准件",
    "material": "材料", "supplier": "供应商", "standard": "标准规范",
    "vlan": "VLAN", "subnet": "子网", "ip": "IP地址",
    "sensor": "传感器", "plc": "PLC", "model": "型号",
    "document_ref": "文档编号",
}


# 实体黑名单：常见误匹配词汇（不构成有意义的实体）
ENTITY_BLACKLIST = {
    'COM', 'CN', 'NET', 'ORG', 'HTTP', 'HTTPS', 'WWW', 'XML', 'HTML', 'JSON',
    'USB', 'HDMI', 'VGA', 'DVI', 'LED', 'LCD', 'CPU', 'GPU', 'RAM', 'ROM',
    'PVC', 'PE', 'PP', 'PS', 'PET',    # 常见塑料缩写（这些太泛，靠 material 模式匹配 LI>
    'SET', 'GET', 'PUT', 'DEL', 'PDF', 'DOC', 'XLS', 'TXT',
    'API', 'URL', 'DNS', 'TCP', 'UDP', 'FTP', 'SSH', 'VPN',
    'OK', 'NG', 'YES', 'NO', 'NULL', 'NONE', 'TRUE', 'FALSE',
}

def discover_entities(text: str) -> dict:
    """从文本中发现实体（基于 regex 模式匹配 + 黑名单过滤）"""
    discovered = {}
    for etype, pattern in ENTITY_PATTERNS.items():
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            # 去重+去空+大小写归一化 + 黑名单过滤
            cleaned = list(set(
                m.upper() for m in matches
                if len(m) > 1
                and not m.startswith('172.25')
                and m.upper() not in ENTITY_BLACKLIST
            ))
            if cleaned:
                discovered[etype] = cleaned[:30]
    return discovered


def infer_relations(nodes: dict, edges: list, text: str, file_name: str) -> list:
    """
    基于 Ontology 关系规则 + 文本共现推断实体关系（三元组）
    """
    new_edges = []
    node_names = list(nodes.keys())
    
    for etype, pattern in ENTITY_PATTERNS.items():
        matches = re.findall(pattern, text, re.IGNORECASE)
        unique_matches = list(dict.fromkeys(m for m in matches if m in node_names))
        
        if len(unique_matches) >= 2:
            # 同一类型实体间关系
            for i in range(len(unique_matches)):
                for j in range(i + 1, len(unique_matches)):
                    edge = (
                        unique_matches[i], unique_matches[j],
                        _resolve_relation(etype, etype),
                    )
                    if edge not in new_edges:
                        new_edges.append(edge)
    
    # 跨类型关系：supplier → standard_part
    for node_name, node_info in nodes.items():
        ntype = node_info.get("type", "unknown")
        if ntype == "supplier":
            # 如果 supplier 出现在文本中，且附近有标准件
            for other_name, other_info in nodes.items():
                if other_info.get("type") == "standard_part":
                    # 简单就近判断：两个实体名都在文本中
                    if node_name in text and other_name in text:
                        edge = (other_name, node_name, "supplied_by")
                        if edge not in new_edges:
                            new_edges.append(edge)
    
    return new_edges


def _resolve_relation(type_a: str, type_b: str) -> str:
    """根据两实体类型推断关系"""
    if type_a == type_b:
        if type_a in ("network_device", "server", "plc"):
            return "connects_to"
        if type_a in ("standard_part", "material", "sensor"):
            return "compatible_with"
        return "related_to"
    
    # supplier关系
    if "supplier" in (type_a, type_b):
        return "supplied_by"
    # 归属关系
    if type_a in ("ip", "pc_client", "server") or type_b in ("vlan", "subnet"):
        return "belongs_to"
    # 控制关系
    if ("plc" in (type_a, type_b) and "sensor" in (type_a, type_b) or "actuator" in (type_a, type_b)):
        return "controlled_by"
    
    return "related_to"


def evolve_graph(new_entities: dict, file_name: str = ""):
    """增量更新知识图谱：本体为骨架，实体为血肉"""
    graph = {"nodes": {}, "edges": [], "meta": {"total_entities": 0, "total_edges": 0, "last_updated": "", "source_files": []}}
    
    if GRAPH_FILE.exists():
        try:
            graph = json.loads(GRAPH_FILE.read_text(encoding='utf-8'))
        except (json.JSONDecodeError, Exception) as e:
            logger.warning("(json.JSONDecodeError, Exception) 失败: %s", e, exc_info=True)
    
    graph.setdefault("nodes", {})
    graph.setdefault("edges", [])
    graph.setdefault("meta", {"total_entities": 0, "total_edges": 0, "last_updated": "", "source_files": []})
    
    now = datetime.now().isoformat()
    added = 0
    
    # 填充实体（血肉）
    for etype, names in new_entities.items():
        for name in names:
            if name not in graph["nodes"]:
                graph["nodes"][name] = {
                    "type": etype,
                    "label": TYPE_LABELS.get(etype, etype),
                    "first_seen": now,
                    "files": [file_name] if file_name else [],
                    "count": 1,
                }
                added += 1
            else:
                node = graph["nodes"][name]
                node["count"] = node.get("count", 0) + 1
                node["last_seen"] = now
                if file_name and file_name not in node.get("files", []):
                    node.setdefault("files", []).append(file_name)
    
    # 推断关系（边）
    # 尝试从 graph 中提取全量文本做关系推理
    all_text = " ".join(
        name for name in graph["nodes"].keys() if graph["nodes"][name].get("count", 0) > 0
    )
    new_edges = infer_relations(graph["nodes"], graph["edges"], all_text, file_name)
    
    edge_added = 0
    existing_edges = set(
        (e[0], e[1], e[2]) if isinstance(e, list) and len(e) >= 3 else tuple(e)
        for e in graph["edges"]
    )
    for edge in new_edges:
        if edge not in existing_edges:
            graph["edges"].append(list(edge))
            existing_edges.add(edge)
            edge_added += 1
    
    # 更新 meta
    graph["meta"]["total_entities"] = len(graph["nodes"])
    graph["meta"]["total_edges"] = len(graph["edges"])
    graph["meta"]["last_updated"] = now
    if file_name and file_name not in graph["meta"]["source_files"]:
        graph["meta"]["source_files"].append(file_name)
    
    # 持久化（原子写入防损坏）
    import os as _os
    GRAPH_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = str(GRAPH_FILE) + '.tmp'
    with open(tmp_path, 'w', encoding='utf-8') as _f:
        json.dump(graph, _f, ensure_ascii=False, indent=2)
    _os.replace(tmp_path, str(GRAPH_FILE))
    
    return {"entities_added": added, "edges_added": edge_added}


def get_graph_stats() -> dict:
    """获取图谱统计信息"""
    if not GRAPH_FILE.exists():
        return {"total_entities": 0, "total_edges": 0}
    try:
        graph = json.loads(GRAPH_FILE.read_text(encoding='utf-8'))
    except Exception as e:  # TODO: Narrow exception type
        logger.warning("get_graph_stats 读取图谱失败: %s", e, exc_info=True)
        return {"total_entities": 0, "total_edges": 0}
    
    type_counts = {}
    for n, v in graph.get("nodes", {}).items():
        t = v.get("type", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1
    
    return {
        "total_entities": len(graph.get("nodes", {})),
        "total_edges": len(graph.get("edges", [])),
        "entity_types": type_counts,
        "last_updated": graph.get("meta", {}).get("last_updated", ""),
    }


# 兼容旧接口
def get_graph_nodes() -> dict:
    if not GRAPH_FILE.exists():
        return {"nodes": [], "edges": []}
    try:
        graph = json.loads(GRAPH_FILE.read_text(encoding='utf-8'))
    except Exception as e:  # TODO: Narrow exception type
        logger.warning("get_graph_nodes 读取图谱失败: %s", e, exc_info=True)
        return {"nodes": [], "edges": []}
    
    nodes_list = []
    for name, info in graph.get("nodes", {}).items():
        nodes_list.append({
            "id": name,
            "type": info.get("type", "unknown"),
            "label": info.get("label", ""),
            "mentions": info.get("count", 0),
            "files": info.get("files", []),
        })
    
    edges_list = []
    for e in graph.get("edges", []):
        if isinstance(e, list) and len(e) >= 3:
            edges_list.append({"from": e[0], "to": e[1], "relation": e[2]})
    
    return {"nodes": nodes_list, "edges": edges_list}
