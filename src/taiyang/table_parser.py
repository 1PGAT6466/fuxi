"""
table_parser.py — Phase 8.3: 表格解析与结构化存储
支持 Excel/CSV/PDF表格 → 结构化 JSON，可独立查询
"""
import logging
from typing import List, Dict

logger = logging.getLogger("table_parser")

def parse_table_to_rows(text: str) -> List[Dict]:
    """从Markdown表格文本解析为结构化行"""
    lines = [l.strip() for l in text.split('\n') if l.strip() and '|---' not in l]
    if len(lines) < 2:
        return []
    
    headers = [h.strip() for h in lines[0].split('|') if h.strip()]
    rows = []
    for line in lines[1:]:
        cells = [c.strip() for c in line.split('|') if c.strip()]
        if len(cells) >= len(headers):
            row = dict(zip(headers, cells))
            rows.append(row)
        elif cells:
            # 列对齐修复
            row = {}
            for i, h in enumerate(headers):
                row[h] = cells[i] if i < len(cells) else ""
            rows.append(row)
    return rows

def extract_tables_from_markdown(md_text: str) -> List[Dict]:
    """从 Markdown 文本中提取所有表格"""
    tables = []
    lines = md_text.split('\n')
    in_table = False
    table_lines = []
    
    for line in lines:
        if '|' in line and line.strip().startswith('|'):
            if not in_table:
                in_table = True
                table_lines = []
            table_lines.append(line)
        elif in_table:
            if table_lines:
                rows = parse_table_to_rows('\n'.join(table_lines))
                if rows:
                    tables.append({
                        "headers": list(rows[0].keys()),
                        "rows": rows,
                        "row_count": len(rows)
                    })
            in_table = False
            table_lines = []
    
    if in_table and table_lines:
        rows = parse_table_to_rows('\n'.join(table_lines))
        if rows:
            tables.append({
                "headers": list(rows[0].keys()),
                "rows": rows,
                "row_count": len(rows)
            })
    
    return tables

def search_table(tables: List[Dict], query: str) -> List[Dict]:
    """在结构化表格中搜索"""
    results = []
    for tbl in tables:
        for row in tbl.get("rows", []):
            row_text = ' '.join(str(v) for v in row.values())
            if query.lower() in row_text.lower():
                results.append({
                    "headers": tbl["headers"],
                    "matched_row": row,
                    "table_index": tables.index(tbl)
                })
    return results
