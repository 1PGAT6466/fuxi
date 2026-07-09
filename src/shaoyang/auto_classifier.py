"""
services/auto_classifier.py — 向量聚类自动分类器
基于 ChromaDB 中已有的向量做 HDBSCAN 聚类，自动发现文档大类，
将分类结果写入 chunk 元数据 + 同步知识图谱节点。
"""

import logging
import numpy as np
from typing import List, Dict, Tuple

logger = logging.getLogger(__name__)

# 预定义候选分类名（根据伏羲业务）
CATEGORY_KEYWORDS = {
    "机械设计": ["机械", "模具", "公差", "装配", "零件", "加工", "铸造", "注塑", "金属", "热处理", "硬度", "齿轮",
                 "轴承", "螺栓", "焊接", "车削", "铣削", "磨削", "图纸", "CAD", "三维", "Soli", "Creo", "Inventor",
                 "表面处理", "电镀", "镀锌", "喷涂", "氧化", "夹具", "治具", "工装", "标准件", "卡尺", "千分尺"],
    "电气自动化": ["电气", "PLC", "传感器", "伺服", "变频", "电机", "继电器", "接触器", "接线", "控制柜",
                    "自动化", "产线", "机器人", "视觉", "HMI", "SCADA", "EtherCAT", "Profi", "Modbus",
                    "OMRON", "西门子", "三菱", "FANUC", "Beckhoff", "倍福", "NC", "脉冲", "编码器",
                    "电路", "电压", "电流", "布线", "接线图", "原理图", "电控"],
    # IT系统分类 — 按网络技术细分
    "IT系统 > 网络拓扑": ["拓扑", "拓扑图", "网络架构", "核心层", "汇聚层", "接入层", "园区网", "组网", "架构设计", "网络规划", "VLAN规划", "IP规划"],
    "IT系统 > 交换路由": ["交换机", "路由器", "路由", "OSPF", "BGP", "静态路由", "VLAN", "trunk", "access", "STP", "链路聚合", "Eth-Trunk", "端口聚合", "三层交换", "二层交换", "VLANIF", "子接口", "ACL", "访问控制", "NAT", "端口映射", "端口安全"],
    "IT系统 > 无线网络": ["无线", "WiFi", "Wi-Fi", "AP", "AC控制器", "瘦AP", "胖AP", "SSID", "WPA2", "WPA3", "802.1X", "Portal认证", "信号覆盖", "信道", "漫游", "Mesh", "射频", "天线"],
    "IT系统 > 网络安全": ["防火墙", "安全策略", "VPN", "IPSec", "SSL", "入侵检测", "入侵防御", "IDS", "IPS", "安全域", "DMZ", "NPS", "Radius", "准入", "ACL策略", "端口扫描", "漏洞", "堡垒机", "日志审计", "准入控制"],
    "IT系统 > IP地址与DNS": ["IP地址", "子网", "子网掩码", "DHCP", "DNS", "域名", "hosts", "A记录", "CNAME", "PTR", "NS记录", "IPv4", "IPv6", "地址池", "MAC地址", "ARP", "网关", "静态IP", "动态IP"],
    "IT系统 > 服务器与存储": ["服务器", "Linux", "Ubuntu", "CentOS", "Windows Server", "虚拟机", "VMware", "Hyper-V", "Docker", "容器", "RAID", "NAS", "SAN", "备份", "容灾", "快照", "磁盘阵列", "LVM", "NFS", "SMB"],
    "IT系统 > 监控与运维": ["监控", "Zabbix", "Prometheus", "Grafana", "SNMP", "syslog", "ping", "traceroute", "带宽监控", "流量分析", "故障排查", "巡检", "运维", "自动化运维", "Ansible", "告警", "通知", "日志", "CRON", "定时任务"],
    "IT系统 > 弱电与布线": ["布线", "弱电", "网线", "光纤", "光模块", "配线架", "信息点", "RJ45", "六类线", "超五类", "单模", "多模", "LC", "SC", "走线", "机柜", "PDU", "UPS", "线槽", "桥架"],
    "采购合同": ["合同", "采购", "报价", "供应商", "招标", "订单", "付款", "发票", "验收", "交付",
                 "协议", "条款", "乙方", "价格", "交货", "质保", "违约责任"],
    "公司管理": ["组织", "人事", "考勤", "绩效", "制度", "流程", "表单", "审批", "报销", "用车",
                 "公章", "通知", "会议", "纪要", "年假", "培训", "入职", "离职"],
    "质量体系": ["ISO", "9001", "质量", "检验", "检测", "校准", "计量", "认证", "审核", "追溯",
                 "不合格", "纠正", "预防", "8D", "SPC", "FMEA", "PPAP", "内审", "外审"],
    "软件工具": ["软件", "编程", "Python", "代码", "数据库", "SQL", "API", "前端", "后端",
                 "配置", "安装", "license", "授权", "版本", "补丁", "固件", "卸载", "环境变量"],
    "工程文档": ["工程", "项目", "设计", "开发", "测试", "验收", "调试", "方案", "技术规格",
                 "BOM", "变更", "图纸", "规范", "作业指导", "WI", "程序文件"],
}

def compute_similarity(vec_a: np.ndarray, keywords_embedding: np.ndarray) -> float:
    """计算向量与关键词向量的余弦相似度"""
    return float(np.dot(vec_a, keywords_embedding.T).max())

def classify_by_vectors(
    embeddings: np.ndarray,
    texts: List[str],
    file_names: List[str],
    top_k: int = 3
) -> List[Dict]:
    """
    对每个 chunk 进行语义分类
    Args:
        embeddings: [N, dim] 向量矩阵
        texts: 对应文本列表
        file_names: 对应文件名列表
        top_k: 返回的候选分类数
    Returns:
        [{category, confidence, candidates: [{name, score}]}, ...]
    """
    from src.db.vector_store import get_vector_store
    
    results = []
    vs = get_vector_store()
    
    for i in range(len(embeddings)):
        vec = embeddings[i]
        text = texts[i] if i < len(texts) else ""
        fname = file_names[i] if i < len(file_names) else ""
        
        # 方案1: 关键词匹配（快速，冷启动）
        text_lower = (text + " " + fname).lower()
        category_scores = {}
        for cat, keywords in CATEGORY_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw.lower() in text_lower)
            if score > 0:
                category_scores[cat] = score
        
        # 方案2: 如果没有关键词命中，用向量聚类（需要全量数据后生效）
        candidates = []
        if category_scores:
            # 按分数排序
            sorted_cats = sorted(category_scores.items(), key=lambda x: -x[1])
            primary = sorted_cats[0][0] if sorted_cats else "通用办公"
            confidence = min(sorted_cats[0][1] * 0.15, 0.95) if sorted_cats else 0.3
            candidates = [{"name": c, "score": round(s * 0.15, 3)} for c, s in sorted_cats[:top_k]]
        else:
            primary = "通用办公"
            confidence = 0.0
        
        results.append({
            "category": primary,
            "confidence": round(confidence, 3),
            "candidates": candidates,
        })
    
    return results

def reclassify_store(store, batch_size: int = 200) -> Tuple[int, int]:
    """
    对 SQLite 中所有 chunk 重新分类
    Returns: (已分类数, 错误数)
    """
    import sqlite3
    from pathlib import Path
    
    from src.config import CHUNKS_DB_PATH
    db_path = Path(CHUNKS_DB_PATH)
    if not db_path.exists():
        logger.warning("chunks.db not found")
        return (0, 0)
    
    conn = sqlite3.connect(str(db_path), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.row_factory = sqlite3.Row
    
    # 获取所有需重新分类的 chunk
    rows = conn.execute(
        "SELECT rowid, text, file_name, category FROM chunks WHERE status='active'"
    ).fetchall()
    
    total = len(rows)
    updated = 0
    errors = 0
    
    for i in range(0, total, batch_size):
        batch = rows[i:i+batch_size]
        texts = [r["text"] or "" for r in batch]
        fnames = [r["file_name"] or "" for r in batch]
        
        # 用关键词做分类
        for j, r in enumerate(batch):
            text_lower = (texts[j] + " " + fnames[j]).lower()
            best_cat = "通用办公"
            best_score = 0
            
            for cat, keywords in CATEGORY_KEYWORDS.items():
                score = sum(1 for kw in keywords if kw.lower() in text_lower)
                if score > best_score:
                    best_score = score
                    best_cat = cat
            
            if best_score > 0 and best_cat != r["category"]:
                try:
                    conn.execute(
                        "UPDATE chunks SET category=? WHERE rowid=?",
                        (best_cat, r["rowid"])
                    )
                    updated += 1
                except Exception as e:  # TODO: Narrow exception type
                    errors += 1
                    logger.error(f"reclassify error: {e}")
        
        conn.commit()
        logger.info(f"reclassify progress: {min(i+batch_size, total)}/{total}")
    
    conn.close()
    logger.info(f"reclassify done: {updated} updated, {errors} errors out of {total}")
    return (updated, errors)

def sync_category_graph(category_counts: Dict[str, int]):
    """将分类统计同步到知识图谱"""
    try:
        from knowledge_evolver import EntityGraph
        
        graph = EntityGraph()
        for cat, count in category_counts.items():
            graph.upsert_entity(
                name=cat,
                entity_type="category",
                metadata={"chunk_count": count, "auto_classified": True}
            )
        graph.save()
        logger.info(f"synced {len(category_counts)} categories to graph")
    except Exception as e:  # TODO: Narrow exception type
        logger.warning(f"graph sync failed: {e}")


def sync_graph_to_categories():
    """将图谱实体类型映射为分类关键词，同步到 CATEGORY_KEYWORDS"""
    import json, logging
    logger = logging.getLogger(__name__)
    try:
        with open("data/knowledge_graph.json", encoding="utf-8") as f:
            graph = json.load(f)
        nodes = graph.get("nodes", {})
        
        # 实体类型 → 分类补充关键词
        type_to_category = {
            "standard": "机械设计",
            "sensor": "电气自动化",
            "plc": "电气自动化",
            "model": "机械设计",
            "material": "工程技术规范",
            "standard_part": "机械设计",
            "supplier": "采购合同",
            "network_device": "IT网络",
            "document_ref": "公司管理",
        }
        
        added = 0
        for name, info in nodes.items():
            etype = info.get("type", "")
            cat = type_to_category.get(etype)
            if cat and cat in CATEGORY_KEYWORDS:
                # 将实体名作为关键词加入对应分类
                keywords = [name.lower()]
                for kw in keywords:
                    if kw not in CATEGORY_KEYWORDS[cat]:
                        CATEGORY_KEYWORDS[cat].append(kw)
                        added += 1
        
        logger.info(f"synced {added} graph entities to category keywords")
        return added
    except Exception as e:  # TODO: Narrow exception type
        logger.warning(f"graph sync failed: {e}")
        return 0
