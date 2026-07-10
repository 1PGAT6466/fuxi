"""
Fix sync I/O in async functions — v3.
Properly handles asyncio import placement and preserves try/except structure.
"""
import os
import re

REPO = r"E:\easyclaw\伏羲-v1.44\repo"

def read_file(relpath):
    with open(os.path.join(REPO, relpath), 'r', encoding='utf-8') as f:
        return f.read()

def write_file(relpath, content):
    with open(os.path.join(REPO, relpath), 'w', encoding='utf-8') as f:
        f.write(content)

def add_asyncio_import_top(content):
    """Add 'import asyncio' after the first block of imports at the top of the file."""
    if 'import asyncio' in content:
        return content
    lines = content.split('\n')
    # Find the last top-level import line (not inside try/except/if blocks)
    last_import = -1
    for i, line in enumerate(lines):
        s = line.strip()
        # Skip empty lines, comments, docstrings
        if not s or s.startswith('#') or s.startswith('"""') or s.startswith("'''"):
            continue
        # If we hit a non-import, non-from, non-empty line at top level, stop
        if s.startswith('import ') or s.startswith('from '):
            last_import = i
        elif s.startswith('logger') or s.startswith('router') or s.startswith('_'):
            # These are module-level assignments that come after imports
            break
        elif s.startswith('class ') or s.startswith('def ') or s.startswith('async def '):
            break
        elif s.startswith('@'):
            break
        elif not s.startswith('import ') and not s.startswith('from '):
            # Could be a continuation or other module-level code
            if last_import >= 0:
                break
    
    if last_import >= 0:
        lines.insert(last_import + 1, 'import asyncio')
    else:
        # Fallback: add at the very beginning
        lines.insert(0, 'import asyncio')
    return '\n'.join(lines)


# ============================================================
# src/api/graph.py
# ============================================================
print("=== src/api/graph.py ===")
c = read_file("src/api/graph.py")

# Fix 1: auto_edges - the with open block
c = c.replace(
    '        edges = []\n        if os.path.exists(GRAPH_PATH):\n            with open(GRAPH_PATH, "r", encoding="utf-8") as f:\n                kg_data = json.load(f)\n                edges = list(kg_data.get("edges", []))',
    '        edges = []\n        if os.path.exists(GRAPH_PATH):\n            def _read_graph():\n                with open(GRAPH_PATH, "r", encoding="utf-8") as f:\n                    return json.load(f)\n            kg_data = await asyncio.to_thread(_read_graph)\n            edges = list(kg_data.get("edges", []))'
)

# Fix 2: graph_stats - the with open block, followed by indented code
# The original has: with open(...) as f: kg_data = json.load(f) nodes = ...
# After replacement, the nodes/edges code stays at the same indent level
c = c.replace(
    '        if os.path.exists(GRAPH_PATH):\n            with open(GRAPH_PATH, "r", encoding="utf-8") as f:\n                kg_data = json.load(f)\n                nodes = kg_data.get("nodes", kg_data.get("entities", {}))\n                nodes_count = len(nodes)',
    '        if os.path.exists(GRAPH_PATH):\n            def _read_graph():\n                with open(GRAPH_PATH, "r", encoding="utf-8") as f:\n                    return json.load(f)\n            kg_data = await asyncio.to_thread(_read_graph)\n            nodes = kg_data.get("nodes", kg_data.get("entities", {}))\n            nodes_count = len(nodes)'
)

c = add_asyncio_import_top(c)
write_file("src/api/graph.py", c)
print("  FIXED")


# ============================================================
# src/api/synthesis.py
# ============================================================
print("=== src/api/synthesis.py ===")
c = read_file("src/api/synthesis.py")

c = c.replace(
    '                    if os.path.exists(kg_path):\n                        with open(kg_path, "r", encoding="utf-8") as f:\n                            kg_data = json.load(f)\n                        graph_entities = kg_data.get("entities", [])',
    '                    if os.path.exists(kg_path):\n                        def _read_kg():\n                            with open(kg_path, "r", encoding="utf-8") as f:\n                                return json.load(f)\n                        kg_data = await asyncio.to_thread(_read_kg)\n                        graph_entities = kg_data.get("entities", [])'
)

c = add_asyncio_import_top(c)
write_file("src/api/synthesis.py", c)
print("  FIXED")


# ============================================================
# src/api/worldtree.py
# ============================================================
print("=== src/api/worldtree.py ===")
c = read_file("src/api/worldtree.py")

# Fix 1: worldtree_entities
c = c.replace(
    '                if os.path.exists(kg_path):\n                    with open(kg_path, "r", encoding="utf-8") as f:\n                        kg_data = json.load(f)\n                    entities = [',
    '                if os.path.exists(kg_path):\n                    def _read_kg():\n                        with open(kg_path, "r", encoding="utf-8") as f:\n                            return json.load(f)\n                    kg_data = await asyncio.to_thread(_read_kg)\n                    entities = ['
)

# Fix 2: worldtree_relations
c = c.replace(
    '                if os.path.exists(kg_path):\n                    with open(kg_path, "r", encoding="utf-8") as f:\n                        kg_data = json.load(f)\n                    relations = kg_data.get("edges", [])',
    '                if os.path.exists(kg_path):\n                    def _read_kg():\n                        with open(kg_path, "r", encoding="utf-8") as f:\n                            return json.load(f)\n                    kg_data = await asyncio.to_thread(_read_kg)\n                    relations = kg_data.get("edges", [])'
)

c = add_asyncio_import_top(c)
write_file("src/api/worldtree.py", c)
print("  FIXED")


# ============================================================
# src/eval/runner.py
# ============================================================
print("=== src/eval/runner.py ===")
c = read_file("src/eval/runner.py")

c = c.replace(
    '    with open(result_path, "w", encoding="utf-8") as f:\n        json.dump(report, f, ensure_ascii=False, indent=2)',
    '    def _write_result():\n        with open(result_path, "w", encoding="utf-8") as f:\n            json.dump(report, f, ensure_ascii=False, indent=2)\n    await asyncio.to_thread(_write_result)'
)

c = add_asyncio_import_top(c)
write_file("src/eval/runner.py", c)
print("  FIXED")


# ============================================================
# src/services/eval_automation.py
# ============================================================
print("=== src/services/eval_automation.py ===")
c = read_file("src/services/eval_automation.py")

# Fix 1: get_eval_history
c = c.replace(
    '            with open(history_file, "r", encoding="utf-8") as f:\n                for line in f:\n                    try:\n                        record = json.loads(line.strip())\n                        # 简单的日期比较\n                        records.append(record)\n                    except Exception as e:  # TODO: Narrow exception type\n                        logger.warning("JSON解析评测历史记录失败: %s", e, exc_info=True)\n        except Exception as e:  # TODO: Narrow exception type\n            logger.warning("读取评测历史记录失败: %s", e, exc_info=True)',
    '            def _read_history():\n                result = []\n                with open(history_file, "r", encoding="utf-8") as f:\n                    for line in f:\n                        try:\n                            record = json.loads(line.strip())\n                            result.append(record)\n                        except Exception as e:\n                            logger.warning("JSON解析评测历史记录失败: %s", e, exc_info=True)\n                return result\n            records = await asyncio.to_thread(_read_history)\n        except Exception as e:  # TODO: Narrow exception type\n            logger.warning("读取评测历史记录失败: %s", e, exc_info=True)'
)

# Fix 2: get_latest_report
c = c.replace(
    '            with open(report_file, "r", encoding="utf-8") as f:\n                return json.load(f)',
    '            def _read_report():\n                with open(report_file, "r", encoding="utf-8") as f:\n                    return json.load(f)\n            return await asyncio.to_thread(_read_report)'
)

c = add_asyncio_import_top(c)
write_file("src/services/eval_automation.py", c)
print("  FIXED")


# ============================================================
# src/shaoyang/relation_builder.py
# ============================================================
print("=== src/shaoyang/relation_builder.py ===")
c = read_file("src/shaoyang/relation_builder.py")

# Fix 1: extract_relations_cooccurrence
c = c.replace(
    '        db = sqlite3.connect(str(WORLDTREE_DB_PATH), timeout=10)\n        db.execute("PRAGMA journal_mode=WAL")\n        db.execute("PRAGMA busy_timeout=5000")\n        entities = db.execute("SELECT id, name, type FROM entities").fetchall()\n        entity_names = {r[1]: (r[0], r[2]) for r in entities}\n        db.close()',
    '        def _load_entities():\n            db = sqlite3.connect(str(WORLDTREE_DB_PATH), timeout=10)\n            db.execute("PRAGMA journal_mode=WAL")\n            db.execute("PRAGMA busy_timeout=5000")\n            entities = db.execute("SELECT id, name, type FROM entities").fetchall()\n            entity_names = {r[1]: (r[0], r[2]) for r in entities}\n            db.close()\n            return entity_names\n        entity_names = await asyncio.to_thread(_load_entities)'
)

c = add_asyncio_import_top(c)
write_file("src/shaoyang/relation_builder.py", c)
print("  FIXED")


# ============================================================
# src/taiyin/mcp_tools.py
# ============================================================
print("=== src/taiyin/mcp_tools.py ===")
c = read_file("src/taiyin/mcp_tools.py")

# Fix 1: graph_query
c = c.replace(
    '        if _os.path.exists(GRAPH_PATH):\n            with open(GRAPH_PATH, "r", encoding="utf-8") as f:\n                kg_data = json.load(f)\n                edges = list(kg_data.get("edges", []))',
    '        if _os.path.exists(GRAPH_PATH):\n            def _read_graph():\n                with open(GRAPH_PATH, "r", encoding="utf-8") as f:\n                    return json.load(f)\n            kg_data = await asyncio.to_thread(_read_graph)\n            edges = list(kg_data.get("edges", []))'
)

# Fix 2: graph_stats
c = c.replace(
    '        if _os.path.exists(GRAPH_PATH):\n            with open(GRAPH_PATH, "r", encoding="utf-8") as f:\n                kg_data = json.load(f)\n                nodes = kg_data.get("nodes", kg_data.get("entities", {}))',
    '        if _os.path.exists(GRAPH_PATH):\n            def _read_graph():\n                with open(GRAPH_PATH, "r", encoding="utf-8") as f:\n                    return json.load(f)\n            kg_data = await asyncio.to_thread(_read_graph)\n            nodes = kg_data.get("nodes", kg_data.get("entities", {}))'
)

# Fix 3: cross_entity_synthesize
c = c.replace(
    '        with open(GRAPH_PATH, "r", encoding="utf-8") as f:\n            kg_data = json.load(f)',
    '        def _read_graph():\n            with open(GRAPH_PATH, "r", encoding="utf-8") as f:\n                return json.load(f)\n        kg_data = await asyncio.to_thread(_read_graph)'
)

c = add_asyncio_import_top(c)
write_file("src/taiyin/mcp_tools.py", c)
print("  FIXED")


print("\n" + "=" * 60)
print("All fixes applied!")
print("=" * 60)
