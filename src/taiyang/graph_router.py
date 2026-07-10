"""
services/graph_router.py — 图谱驱动检索路由（v10.0）
负责：实体识别 → 分类定位 → 对应 Collection 检索 → 关系扩展
"""
import json
from typing import List, Dict

import sqlite3
from src.config import GRAPH_PATH
import logging; logger = logging.getLogger(__name__)


# ============ 17 类 → Category 映射 ============

CATEGORY_ALIAS = {
    "模具设计": "模具设计",
    "连接器设计": "连接器设计",
    "机械设计": "机械设计",
    "标准件库": "标准件库",
    "电气自动化": "电气自动化",
    "自动化产线": "自动化产线",
    "网络建设": "网络建设",
    "工程技术规范": "工程技术规范",
    "品质管理": "品质管理",
    "供应商管理": "供应商管理",
    "财务文档": "财务文档",
    "合同文件": "合同文件",
    "办公文档": "办公文档",
    "技术文档": "技术文档",
    "公司制度": "公司制度",
    "行政人事": "行政人事",
    "项目管理": "项目管理",
}


# Query 意图 → 分类映射（关键词触发）
INTENT_KEYWORDS = {
    "模具设计": ["模具", "模腔", "模芯", "注塑", "浇口", "顶出", "滑块", "斜顶", "热流道", "冷流道", "脱模", "排气槽"],
    "机械设计": ["机械", "公差", "配合", "轴承", "齿轮", "弹簧", "键槽", "花键", "螺纹", "联轴器", "热处理", "硬度", "表面粗糙度"],
    "电气自动化": ["传感器", "PLC", "继电器", "接触器", "变频器", "伺服", "步进", "HMI", "触摸屏", "电气柜", "接线", "断路器", "熔断器", "光电开关", "接近开关"],
    "自动化产线": ["产线", "机械手", "机器人", "传送带", "振动盘", "自动组装", "CCD", "视觉检测", "气动", "气缸", "电磁阀"],
    "标准件库": ["标准件", "GB/T", "螺栓", "螺母", "垫圈", "销", "键", "挡圈", "O型圈", "密封圈", "卡簧"],
    "网络建设": ["VLAN", "交换机", "路由器", "子网", "DHCP", "ACL", "防火墙", "IP", "端口", "Trunk", "AP", "WiFi"],
    "连接器设计": ["连接器", "Fakra", "端子", "防水", "板端", "线端"],
    "工程技术规范": ["规范", "工艺", "标准", "作业指导", "SOP", "验收", "检查"],
    "品质管理": ["品质", "质量", "检验", "测量", "CPK", "SPC", "不良", "8D", "纠正"],
    "项目管理": ["项目", "进度", "里程碑", "甘特", "APQP", "PPAP", "DFMEA", "PFMEA"],
    "公司制度": ["泛微", "OA", "ecology", "使用手册", "操作指南", "流程引擎", "建模引擎", "门户引擎", "组织权限", "系统参数", "公文", "人事", "资产", "会议", "日程", "协作"],
    "公司制度": ["泛微", "OA", "ecology", "使用手册", "操作指南", "流程引擎", "建模引擎", "门户引擎", "组织权限", "系统参数"],
}

# Entity type → 默认分类

def validate_graph_relation(entity_a, entity_b, rel_type="related_to"):
    """P3: Validate relation against ontology type constraints"""
    try:
        import sys, os as _os
        _os.environ.setdefault("KB_ROOT", _os.path.dirname(_os.path.dirname(__file__)))
        sys.path.insert(0, _os.path.dirname(_os.path.dirname(__file__)))
        from src.db.ontology import get_entity_type, RELATION_TYPES
        type_a = get_entity_type(entity_a, "")
        type_b = get_entity_type(entity_b, "")
        rule = RELATION_TYPES.get(rel_type, {})
        domain = rule.get("domain", [])
        range_types = rule.get("range", [])
        if domain and type_a not in domain and type_a != "unknown":
            return False, f"{entity_a}({type_a}) not in domain {domain}"
        if range_types and type_b not in range_types and type_b != "unknown":
            return False, f"{entity_b}({type_b}) not in range {range_types}"
        return True, "ok"
    except Exception:  # TODO: Narrow exception type
        return True, "validation_skipped"


ENTITY_TYPE_TO_CATEGORY = {
    "device": "网络建设",
    "vlan": "网络建设",
    "subnet": "网络建设",
    "ssid": "网络建设",
    "protocol": "网络建设",
    "standard_part": "标准件库",
    "material": "模具设计",
    "plastic": "工程技术规范",
    "sensor_or_actuator": "电气自动化",
    "supplier": "供应商管理",
    "operation_manual": "公司制度",
    "operation_manual": "公司制度",
}

# 同义实体链接（规则匹配）
# 中英文同义词 + 简写映射（统一归入 category_registry 之前先用这里兜底）
# ENTITY_SYNONYMS 已统一到 category_registry.SYNONYM_MAP
from src.category_registry import SYNONYM_MAP as ENTITY_SYNONYMS


def normalize_entity(name: str) -> str:
    """实体名称归一化"""
    return ENTITY_SYNONYMS.get(name.lower(), name.upper())


def load_graph() -> dict:
    try:
        return json.loads(GRAPH_PATH.read_text(encoding="utf-8"))
    except Exception as e:  # TODO: Narrow exception type
        logger.warning("Exception 失败: %s", e, exc_info=True)
        return {}


def _match_entities_in_query(query: str) -> List[Dict]:
    """从查询中识别图谱实体"""
    graph = load_graph()
    nodes = graph.get("nodes", {})
    edges = graph.get("edges", [])
    
    matched = []
    q_upper = query.upper()
    
    for name, info in nodes.items():
        if name.upper() in q_upper:
            # 找到实体的关系
            related_to = []
            for e in edges:
                if isinstance(e, dict):
                    src, dst, rel = e.get("source",""), e.get("target",""), e.get("relation","related_to")
                else:
                    src, dst, rel = e[0], e[1], e[2] if len(e) > 2 else "related_to"
                if src == name:
                    related_to.append({"entity": dst, "relation": rel, "weight": 1})
                elif dst == name:
                    related_to.append({"entity": src, "relation": rel, "weight": 1})
            related_to.sort(key=lambda x: x.get("weight", 0), reverse=True)
            
            matched.append({
                "entity": name,
                "type": info.get("type", "unknown"),
                "mentions": info.get("mentions", 0),
                "category": ENTITY_TYPE_TO_CATEGORY.get(info.get("type", ""), ""),
                "related": related_to[:5],
            })
    
    # 按 mentions 降序排序
    matched.sort(key=lambda x: x.get("mentions", 0), reverse=True)
    return matched


def route_to_categories(query: str) -> List[str]:
    """
    图谱路由：识别查询中的实体 → 映射到分类 → 返回应检索的分类列表
    
    Returns:
        分类列表（按优先级排序）
    """
    entities = _match_entities_in_query(query)
    
    if not entities:
        # 无实体匹配 → 全类检索
        return []
    
    # 收集实体涉及的分类
    cats = {}
    for e in entities:
        cat = e.get("category", "")
        if cat:
            cats[cat] = cats.get(cat, 0) + e.get("mentions", 1)
    
    # 实体相关分类 → 关系扩展分类
    for e in entities:
        for rel in e.get("related", []):
            rel_entity = rel["entity"]
            # 查关联实体的类型
            graph = load_graph()
            rel_node = graph.get("nodes", {}).get(rel_entity, {})
            rel_cat = ENTITY_TYPE_TO_CATEGORY.get(rel_node.get("type", ""), "")
            if rel_cat and rel_cat not in cats:
                cats[rel_cat] = 1  # 低权重
    
    # 按权重排序
    sorted_cats = sorted(cats.items(), key=lambda x: x[1], reverse=True)
    return [c for c, _ in sorted_cats]




def fuzzy_match_entity(query: str, node_name: str) -> float:
    # 简并模糊匹配：精确子串 → 100%，包含任意词 → 40%
    q = query.upper()
    n = node_name.upper()
    if n in q:
        return 1.0
    # 词匹配
    q_words = set(q.split())
    n_words = set(n.split())
    if not q_words or not n_words:
        return 0.0
    overlap = q_words & n_words
    return len(overlap) / max(len(q_words), 1) * 0.4




def detect_query_intent(query: str) -> dict:
    # 按关键词数匹配意图
    scores = {}
    for cat, keywords in INTENT_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in query)
        if score > 0:
            scores[cat] = score
    if not scores:
        return {}
    sorted_cats = sorted(scores.items(), key=lambda x: -x[1])
    return {
        "primary_category": sorted_cats[0][0],
        "sub_categories": [c for c, _ in sorted_cats[:4]],
        "all_scores": dict(sorted_cats),
    }

def route_entity_with_neighbors(query: str, max_entities: int = 5) -> dict:
    graph = load_graph()
    nodes = graph.get("nodes", {})
    edges = graph.get("edges", [])
    
    matched = {}
    for name, info in nodes.items():
        score = fuzzy_match_entity(query, name)
        if score > 0.3:
            matched[name] = {
                "entity": name,
                "type": info.get("type", "unknown"),
                "mentions": info.get("mentions", 0),
                "match_score": score,
                "category": ENTITY_TYPE_TO_CATEGORY.get(info.get("type", ""), ""),
            }
    
    sorted_matches = sorted(matched.values(), key=lambda x: (x["match_score"], x.get("mentions", 0)), reverse=True)
    top = sorted_matches[:max_entities]
    
    # 1-hop 邻域遍历
    all_categories = {}
    all_neighbors = {}
    expanded_terms = set()
    
    for e in top:
        cat = e.get("category", "")
        if cat:
            all_categories[cat] = all_categories.get(cat, 0) + 1
        # 遍历边
        for edge in edges:
            # 兼容多种边格式: list/tuple 或 dict
            if isinstance(edge, (list, tuple)):
                src = edge[0] if len(edge) > 0 else ""
                dst = edge[1] if len(edge) > 1 else ""
                rel = edge[2] if len(edge) > 2 else "related_to"
            elif isinstance(edge, dict):
                src = edge.get("from", edge.get("source", ""))
                dst = edge.get("to", edge.get("target", ""))
                rel = edge.get("relation", edge.get("rel", "related_to"))
            else:
                continue
            if src == e["entity"]:
                target = dst
            elif dst == e["entity"]:
                target = src
            else:
                continue
            rel_node = nodes.get(target, {})
            rel_cat = ENTITY_TYPE_TO_CATEGORY.get(rel_node.get("type", ""), "")
            if rel_cat:
                all_categories[rel_cat] = all_categories.get(rel_cat, 0) + 0.5
            all_neighbors[target] = {"entity": target, "relation": rel, "weight": 1}
            expanded_terms.add(target)
    
    # 排序分类
    sorted_cats = sorted(all_categories.items(), key=lambda x: x[1], reverse=True)
    primary_category = sorted_cats[0][0] if sorted_cats else ""
    
    # Phase 2: Auto-link matched entities to wiki pages
    try:
        from src.config import WORLDTREE_DB_PATH
        wiki_db = str(WORLDTREE_DB_PATH)
        if WORLDTREE_DB_PATH.exists():
            import sqlite3 as _sqlite
            conn = _sqlite.connect(wiki_db)
            # Batch: 用单条 SQL 替代 N+1 循环查询
            entity_names = [e["entity"] for e in top]
            if entity_names:
                conditions = []
                params = []
                for name in entity_names:
                    conditions.append("(title LIKE ? OR content LIKE ?)")
                    params.extend([f"%{name}%", f"%{name}%"])
                sql = f"SELECT id, title FROM wiki_pages WHERE {' OR '.join(conditions)} LIMIT {len(entity_names) * 3}"
                cur = conn.execute(sql, params)
                # 建立 title -> entity_name 映射
                title_to_entity = {}
                for row in cur.fetchall():
                    row_title = (row[1] or "").lower()
                    for name in entity_names:
                        if name.lower() in row_title:
                            wiki_links.append({
                                "entity": name,
                                "wiki_id": row[0],
                                "wiki_title": row[1],
                                "auto_linked": True
                            })
                            break
            conn.close()
    except Exception as e:  # TODO: Narrow exception type
        import logging; logging.getLogger(__name__).warning(f"[Graph wiki-link] {e}")
    sub_categories = [c for c, _ in sorted_cats[:5]]
    
    # 构建扩展查询
    expanded_query = query
    if expanded_terms:
        expanded_query += " " + " ".join(sorted(expanded_terms)[:8])
    
    # 意图检测优先
    intent = detect_query_intent(query)
    if intent and intent.get("primary_category"):
        if not primary_category:
            primary_category = intent["primary_category"]
        # 合并 intent 的 sub_categories
        for c in intent.get("sub_categories", []):
            if c not in sub_categories:
                sub_categories.append(c)
            all_categories[c] = all_categories.get(c, 0) + 2
        # 将意图关键词注入 expanded_query
        intent_kws = []
        for cat in intent.get("sub_categories", []):
            intent_kws.extend(INTENT_KEYWORDS.get(cat, [])[:3])
        expanded_query += " " + " ".join(intent_kws)[:200]
    
    # Wiki 链接查询：匹配实体名到 Wiki 页面
    wiki_links = []
    try:
        import sqlite3
        from src.config import WORLDTREE_DB_PATH
        conn = sqlite3.connect(str(WORLDTREE_DB_PATH), timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        # Batch: 用单条 SQL 替代 N+1 循环查询
        entity_names = [e["entity"] for e in top]
        if entity_names:
            conditions = []
            params = []
            for name in entity_names:
                conditions.append("(title LIKE ? OR content LIKE ?)")
                params.extend([f"%{name}%", f"%{name}%"])
            sql = f"SELECT id, title FROM wiki_pages WHERE {' OR '.join(conditions)} LIMIT {len(entity_names) * 3}"
            cur = conn.execute(sql, params)
            for row in cur.fetchall():
                row_title = (row[1] or "").lower()
                for name in entity_names:
                    if name.lower() in row_title:
                        wiki_links.append({"entity": name, "wiki_id": row[0], "wiki_title": row[1]})
                        break
        conn.close()
    except Exception as e:  # TODO: Narrow exception type
        import logging; logging.getLogger(__name__).warning(f"[Graph wiki-link] {e}")

    return {
        "entities": top,
        "neighbors": all_neighbors,
        "primary_category": primary_category,
        "sub_categories": sub_categories,
        "expanded_query": expanded_query,
        "entity_count": len(top),
        "neighbor_count": len(all_neighbors),
        "intent": intent,
        "wiki_links": wiki_links,
    }

def get_entity_context(query: str) -> str:
    """
    构建图谱上下文，注入 LLM Prompt
    """
    entities = _match_entities_in_query(query)
    if not entities:
        return ""
    
    parts = ["\n[知识图谱上下文]"]
    for e in entities[:5]:
        parts.append(f"- {e['entity']} ({e['type']}) → 分类: {e.get('category', '未知')}")
        if e.get("related"):
            rels = ", ".join(r["entity"] for r in e["related"][:3])
            parts.append(f"  关联: {rels}")
    return "\n".join(parts)


def expand_query_with_synonyms(query: str) -> str:
    """同义词扩展 + 图谱 1-hop 邻居扩展（v10.1）"""
    for short, full in ENTITY_SYNONYMS.items():
        if short in query:
            query = query.replace(short, f"{short}({full})")
    
    # 图谱 1-hop 扩展：在查询中检测到实体 → 扩展关联实体到查询
    entities = _match_entities_in_query(query)
    if entities:
        neighbors = set()
        for e in entities[:3]:  # 最多 3 个实体
            for rel in e.get('related', [])[:3]:  # 每个实体取 3 个关联
                neighbor_name = rel.get('entity', '')
                if neighbor_name and neighbor_name not in query:
                    neighbors.add(neighbor_name)
        if neighbors:
            query = query + ' ' + ' '.join(sorted(neighbors)[:5])
    return query

def multi_hop_search(query: str, max_hops: int = 3) -> dict:
    """多跳图搜索（GraphRAG 入口）"""
    try:
        from src.services.graph_traversal import multi_hop_traverse
        # 先匹配实体
        matched = fuzzy_match_entity(query, "")  # 直接找最匹配的
        if not matched:
            # 尝试 normalize
            normalized = normalize_entity(query)
            result = multi_hop_traverse(normalized, max_hops=max_hops)
        else:
            result = multi_hop_traverse(query, max_hops=max_hops)
        return result
    except ImportError:
        return {"paths": [], "entities": [], "error": "graph_traversal not available"}
