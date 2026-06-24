"""
clean_graph.py — 图谱清洗脚本
===============================
运行方式：
    cd /home/feng-shaoxuan/kb-server
    python scripts/clean_graph.py [--dry-run]
"""

import os
import sys
import re
import json
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import GRAPH_PATH


def clean(dry_run=False):
    if not GRAPH_PATH.exists():
        print("knowledge_graph.json not found!")
        return
    
    graph = json.loads(GRAPH_PATH.read_text(encoding="utf-8"))
    nodes = graph.get("nodes", {})
    edges = graph.get("edges", [])
    
    initial_nodes = len(nodes)
    initial_edges = len(edges)
    
    # 需要移除的实体
    remove_patterns = [
        r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}',  # IP 地址/段
    ]
    blacklist = {
        'COM', 'CN', 'NET', 'ORG', 'HTTP', 'HTTPS', 'WWW',
        'USB', 'HDMI', 'VGA', 'LED', 'LCD', 'CPU', 'GPU',
        'PVC', 'PE', 'PP', 'PS', 'PET',
        'SET', 'GET', 'PUT', 'DEL', 'PDF', 'DOC', 'XLS', 'TXT',
        'API', 'URL', 'DNS', 'TCP', 'UDP', 'FTP', 'SSH', 'VPN',
        'OK', 'NG', 'NULL', 'NONE', 'TRUE', 'FALSE',
    }
    
    removed = []
    cleaned_nodes = {}
    
    for name, info in nodes.items():
        # IP 地址
        if any(re.match(pat, name) for pat in remove_patterns):
            removed.append((name, "ip_address"))
            continue
        # 黑名单
        if name.upper() in blacklist:
            removed.append((name, "blacklist"))
            continue
        # 出现次数太少
        if info.get("count", 0) < 2:
            removed.append((name, "low_count"))
            continue
        cleaned_nodes[name] = info
    
    removed_names = {r[0] for r in removed}
    
    # 清洗边
    cleaned_edges = []
    for e in edges:
        src = e[0] if isinstance(e, list) else e.get("from", "")
        dst = e[1] if isinstance(e, list) else e.get("to", "")
        if src not in removed_names and dst not in removed_names:
            cleaned_edges.append(e)
    
    # 统计
    print(f"\n{'='*50}")
    print(f"图谱清洗报告")
    print(f"{'='*50}")
    print(f"清洗前: {initial_nodes} 实体, {initial_edges} 边")
    print(f"清洗后: {len(cleaned_nodes)} 实体, {len(cleaned_edges)} 边")
    print(f"移除实体: {initial_nodes - len(cleaned_nodes)}")
    print(f"移除边: {initial_edges - len(cleaned_edges)}")
    
    # 按原因分组
    by_reason = {}
    for name, reason in removed:
        by_reason.setdefault(reason, []).append(name)
    for reason, names in by_reason.items():
        print(f"\n  [{reason}] ({len(names)} 个):")
        for n in names[:10]:
            print(f"    - {n}")
        if len(names) > 10:
            print(f"    ... 还有 {len(names) - 10} 个")
    
    # 类型分布
    type_counts = {}
    for name, info in cleaned_nodes.items():
        t = info.get("type", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1
    print(f"\n实体类型分布:")
    for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"  {t}: {c}")
    
    if dry_run:
        print(f"\n[DRY RUN] 未实际修改文件")
        return
    
    # 写入
    graph["nodes"] = cleaned_nodes
    graph["edges"] = cleaned_edges
    graph["meta"]["total_entities"] = len(cleaned_nodes)
    graph["meta"]["total_edges"] = len(cleaned_edges)
    
    tmp_path = str(GRAPH_PATH) + '.tmp'
    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(graph, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, str(GRAPH_PATH))
    
    print(f"\n✅ 图谱已清洗并保存")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="只分析不修改")
    args = parser.parse_args()
    clean(dry_run=args.dry_run)
