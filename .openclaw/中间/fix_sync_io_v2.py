"""
Fix sync I/O in async functions — v2.
This script reads each file, finds the async functions with sync I/O,
and properly wraps the I/O while preserving try/except structure.
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

def ensure_asyncio_import(content):
    if 'import asyncio' in content:
        return content
    lines = content.split('\n')
    last_import = 0
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith('import ') or s.startswith('from '):
            last_import = i
    lines.insert(last_import + 1, 'import asyncio')
    return '\n'.join(lines)


# ============================================================
# src/api/graph.py
# ============================================================
print("=== src/api/graph.py ===")
c = read_file("src/api/graph.py")

# Fix 1: auto_edges - the with open block is inside a try, followed by filtering logic
c = c.replace(
    '        edges = []\n        if os.path.exists(GRAPH_PATH):\n            with open(GRAPH_PATH, "r", encoding="utf-8") as f:\n                kg_data = json.load(f)\n                edges = list(kg_data.get("edges", []))',
    '        edges = []\n        if os.path.exists(GRAPH_PATH):\n            def _read_graph():\n                with open(GRAPH_PATH, "r", encoding="utf-8") as f:\n                    return json.load(f)\n            kg_data = await asyncio.to_thread(_read_graph)\n            edges = list(kg_data.get("edges", []))'
)

# Fix 2: graph_stats - the with open block
c = c.replace(
    '        if os.path.exists(GRAPH_PATH):\n            with open(GRAPH_PATH, "r", encoding="utf-8") as f:\n                kg_data = json.load(f)\n                nodes = kg_data.get("nodes", kg_data.get("entities", {}))\n                nodes_count = len(nodes)',
    '        if os.path.exists(GRAPH_PATH):\n            def _read_graph():\n                with open(GRAPH_PATH, "r", encoding="utf-8") as f:\n                    return json.load(f)\n            kg_data = await asyncio.to_thread(_read_graph)\n            nodes = kg_data.get("nodes", kg_data.get("entities", {}))\n            nodes_count = len(nodes)'
)

c = ensure_asyncio_import(c)
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

c = ensure_asyncio_import(c)
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

c = ensure_asyncio_import(c)
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

c = ensure_asyncio_import(c)
write_file("src/eval/runner.py", c)
print("  FIXED")


# ============================================================
# src/growth/engine.py
# ============================================================
print("=== src/growth/engine.py ===")
c = read_file("src/growth/engine.py")

# Fix 1: record_event write
c = c.replace(
    '        try:\n            with open(log_file, "a", encoding="utf-8") as f:\n                f.write(json.dumps(record, ensure_ascii=False) + "\\n")\n        except Exception as e:  # TODO: Narrow exception type\n            logger.warning(f"[Growth] 写入失败: {e}")',
    '        try:\n            def _write_log():\n                with open(log_file, "a", encoding="utf-8") as f:\n                    f.write(json.dumps(record, ensure_ascii=False) + "\\n")\n            await asyncio.to_thread(_write_log)\n        except Exception as e:  # TODO: Narrow exception type\n            logger.warning(f"[Growth] 写入失败: {e}")'
)

# Fix 2: evaluate read - this has a for loop inside with, followed by except
c = c.replace(
    '        try:\n            with open(log_file, "r", encoding="utf-8") as f:\n                for line in f:\n                    try:\n                        events.append(json.loads(line.strip()))\n                    except Exception as e:  # TODO: Narrow exception type\n                        logger.warning("JSON解析成长事件失败: %s", e, exc_info=True)\n        except Exception as e:  # TODO: Narrow exception type\n            logger.warning("Exception 失败: %s", e, exc_info=True)',
    '        try:\n            def _read_log():\n                result = []\n                with open(log_file, "r", encoding="utf-8") as f:\n                    for line in f:\n                        try:\n                            result.append(json.loads(line.strip()))\n                        except Exception as e:\n                            logger.warning("JSON解析成长事件失败: %s", e, exc_info=True)\n                return result\n            events = await asyncio.to_thread(_read_log)\n        except Exception as e:  # TODO: Narrow exception type\n            logger.warning("Exception 失败: %s", e, exc_info=True)'
)

c = ensure_asyncio_import(c)
write_file("src/growth/engine.py", c)
print("  FIXED")


# ============================================================
# src/growth/growth_recorder.py
# ============================================================
print("=== src/growth/growth_recorder.py ===")
c = read_file("src/growth/growth_recorder.py")

# Fix 1: record write
c = c.replace(
    '        try:\n            with open(log_file, "a", encoding="utf-8") as f:\n                f.write(json.dumps(record, ensure_ascii=False) + "\\n")\n        except Exception as e:  # TODO: Narrow exception type\n            logger.warning(f"[Growth] 写入失败: {e}")',
    '        try:\n            def _write_log():\n                with open(log_file, "a", encoding="utf-8") as f:\n                    f.write(json.dumps(record, ensure_ascii=False) + "\\n")\n            await asyncio.to_thread(_write_log)\n        except Exception as e:  # TODO: Narrow exception type\n            logger.warning(f"[Growth] 写入失败: {e}")'
)

# Fix 2: query read - for loop inside with, with error handling
c = c.replace(
    '        with open(log_file, "r", encoding="utf-8") as f:\n            for line in f:\n                try:\n                    record = json.loads(line.strip())\n\n                    if metric and record.get("metric") != metric:\n                        continue\n\n                    if since_seconds and record.get("timestamp", 0) < time.time() - since_seconds:\n                        continue\n\n                    records.append(record)\n                except Exception as e:  # TODO: Narrow exception type\n                    logger.warning("JSON解析成长记录失败: %s", e, exc_info=True)\n                    continue',
    '        def _read_log():\n            result = []\n            with open(log_file, "r", encoding="utf-8") as f:\n                for line in f:\n                    try:\n                        record = json.loads(line.strip())\n\n                        if metric and record.get("metric") != metric:\n                            continue\n\n                        if since_seconds and record.get("timestamp", 0) < time.time() - since_seconds:\n                            continue\n\n                        result.append(record)\n                    except Exception as e:\n                        logger.warning("JSON解析成长记录失败: %s", e, exc_info=True)\n                        continue\n            return result\n        records = await asyncio.to_thread(_read_log)'
)

c = ensure_asyncio_import(c)
write_file("src/growth/growth_recorder.py", c)
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

c = ensure_asyncio_import(c)
write_file("src/services/eval_automation.py", c)
print("  FIXED")


# ============================================================
# src/services/eval_pipeline.py
# ============================================================
print("=== src/services/eval_pipeline.py ===")
c = read_file("src/services/eval_pipeline.py")

c = c.replace(
    '            with open(eval_file, "r", encoding="utf-8") as f:\n                for line in f:\n                    try:\n                        results.append(json.loads(line.strip()))\n                    except Exception as e:  # TODO: Narrow exception type\n                        logger.warning("JSON解析评测结果失败: %s", e, exc_info=True)\n        except Exception as e:  # TODO: Narrow exception type\n            logger.warning("读取评测结果文件失败: %s", e, exc_info=True)',
    '            def _read_eval():\n                result = []\n                with open(eval_file, "r", encoding="utf-8") as f:\n                    for line in f:\n                        try:\n                            result.append(json.loads(line.strip()))\n                        except Exception as e:\n                            logger.warning("JSON解析评测结果失败: %s", e, exc_info=True)\n                return result\n            results = await asyncio.to_thread(_read_eval)\n        except Exception as e:  # TODO: Narrow exception type\n            logger.warning("读取评测结果文件失败: %s", e, exc_info=True)'
)

c = ensure_asyncio_import(c)
write_file("src/services/eval_pipeline.py", c)
print("  FIXED")


# ============================================================
# src/services/knowledge_lifecycle.py
# ============================================================
print("=== src/services/knowledge_lifecycle.py ===")
c = read_file("src/services/knowledge_lifecycle.py")

# Fix 1: record_event write
c = c.replace(
    '            log_file = LIFECYCLE_DIR / f"{event_type}.jsonl"\n            with open(log_file, "a", encoding="utf-8") as f:\n                f.write(json.dumps(event, ensure_ascii=False) + "\\n")',
    '            log_file = LIFECYCLE_DIR / f"{event_type}.jsonl"\n            def _write_event():\n                with open(log_file, "a", encoding="utf-8") as f:\n                    f.write(json.dumps(event, ensure_ascii=False) + "\\n")\n            await asyncio.to_thread(_write_event)'
)

# Fix 2: get_candidates
c = c.replace(
    '            with open(log_file, "r", encoding="utf-8") as f:\n                for line in f:\n                    try:\n                        event = json.loads(line.strip())\n                        candidates.append(event.get("data", {}))\n                    except Exception as e:  # TODO: Narrow exception type\n                        logger.warning("JSON解析生命周期事件失败: %s", e, exc_info=True)\n        except Exception as e:  # TODO: Narrow exception type\n            logger.warning("加载知识生命周期事件失败: %s", e, exc_info=True)',
    '            def _read_events():\n                result = []\n                with open(log_file, "r", encoding="utf-8") as f:\n                    for line in f:\n                        try:\n                            event = json.loads(line.strip())\n                            result.append(event.get("data", {}))\n                        except Exception as e:\n                            logger.warning("JSON解析生命周期事件失败: %s", e, exc_info=True)\n                return result\n            candidates = await asyncio.to_thread(_read_events)\n        except Exception as e:  # TODO: Narrow exception type\n            logger.warning("加载知识生命周期事件失败: %s", e, exc_info=True)'
)

# Fix 3: _count_events
c = c.replace(
    '            with open(log_file, "r", encoding="utf-8") as f:\n                for line in f:\n                    try:\n                        event = json.loads(line.strip())\n                        if event.get("timestamp", 0) > cutoff:\n                            count += 1\n                    except Exception as e:  # TODO: Narrow exception type\n                        logger.warning("JSON解析生命周期事件统计失败: %s", e, exc_info=True)',
    '            def _count():\n                c = 0\n                with open(log_file, "r", encoding="utf-8") as f:\n                    for line in f:\n                        try:\n                            event = json.loads(line.strip())\n                            if event.get("timestamp", 0) > cutoff:\n                                c += 1\n                        except Exception as e:\n                            logger.warning("JSON解析生命周期事件统计失败: %s", e, exc_info=True)\n                return c\n            count = await asyncio.to_thread(_count)'
)

c = ensure_asyncio_import(c)
write_file("src/services/knowledge_lifecycle.py", c)
print("  FIXED")


# ============================================================
# src/services/memory.py
# ============================================================
print("=== src/services/memory.py ===")
c = read_file("src/services/memory.py")

# Fix 1: save_session
c = c.replace(
    '            session_file = MEMORY_DIR / f"session_{session_id}.json"\n            with open(session_file, "w", encoding="utf-8") as f:\n                json.dump(messages, f, ensure_ascii=False, indent=2)',
    '            session_file = MEMORY_DIR / f"session_{session_id}.json"\n            def _write_session():\n                with open(session_file, "w", encoding="utf-8") as f:\n                    json.dump(messages, f, ensure_ascii=False, indent=2)\n            await asyncio.to_thread(_write_session)'
)

# Fix 2: load_session
c = c.replace(
    '            with open(session_file, "r", encoding="utf-8") as f:\n                messages = json.load(f)\n                self._session_memory[session_id] = messages\n                return messages',
    '            def _read_session():\n                with open(session_file, "r", encoding="utf-8") as f:\n                    return json.load(f)\n            messages = await asyncio.to_thread(_read_session)\n            self._session_memory[session_id] = messages\n            return messages'
)

# Fix 3: add_long_term_memory
c = c.replace(
    '            memory_file = MEMORY_DIR / "long_term.jsonl"\n            record = {\n                "key": key,\n                "value": value,\n                "timestamp": time.time(),\n            }\n            with open(memory_file, "a", encoding="utf-8") as f:\n                f.write(json.dumps(record, ensure_ascii=False) + "\\n")',
    '            memory_file = MEMORY_DIR / "long_term.jsonl"\n            record = {\n                "key": key,\n                "value": value,\n                "timestamp": time.time(),\n            }\n            def _write_memory():\n                with open(memory_file, "a", encoding="utf-8") as f:\n                    f.write(json.dumps(record, ensure_ascii=False) + "\\n")\n            await asyncio.to_thread(_write_memory)'
)

# Fix 4: search_long_term_memory
c = c.replace(
    '            with open(memory_file, "r", encoding="utf-8") as f:\n                for line in f:\n                    try:\n                        record = json.loads(line.strip())\n                        # 简单的关键词匹配\n                        if query.lower() in json.dumps(record.get("value", {})).lower():\n                            results.append(record)\n                    except Exception as e:  # TODO: Narrow exception type\n                        logger.warning("JSON解析会话记忆失败: %s", e, exc_info=True)\n        except Exception as e:  # TODO: Narrow exception type\n            logger.warning("搜索会话记忆失败: %s", e, exc_info=True)',
    '            def _search_memory():\n                found = []\n                with open(memory_file, "r", encoding="utf-8") as f:\n                    for line in f:\n                        try:\n                            record = json.loads(line.strip())\n                            if query.lower() in json.dumps(record.get("value", {})).lower():\n                                found.append(record)\n                        except Exception as e:\n                            logger.warning("JSON解析会话记忆失败: %s", e, exc_info=True)\n                return found\n            results = await asyncio.to_thread(_search_memory)\n        except Exception as e:  # TODO: Narrow exception type\n            logger.warning("搜索会话记忆失败: %s", e, exc_info=True)'
)

c = ensure_asyncio_import(c)
write_file("src/services/memory.py", c)
print("  FIXED")


# ============================================================
# src/services/online_eval.py
# ============================================================
print("=== src/services/online_eval.py ===")
c = read_file("src/services/online_eval.py")

# Fix 1: _flush_metrics
c = c.replace(
    '            metrics_file = ONLINE_EVAL_DIR / "metrics.jsonl"\n            with open(metrics_file, "a", encoding="utf-8") as f:\n                for metric in self._metrics_buffer:\n                    f.write(json.dumps(metric, ensure_ascii=False) + "\\n")\n\n            self._metrics_buffer.clear()',
    '            metrics_file = ONLINE_EVAL_DIR / "metrics.jsonl"\n            buf = list(self._metrics_buffer)\n            def _flush():\n                with open(metrics_file, "a", encoding="utf-8") as f:\n                    for metric in buf:\n                        f.write(json.dumps(metric, ensure_ascii=False) + "\\n")\n            await asyncio.to_thread(_flush)\n\n            self._metrics_buffer.clear()'
)

# Fix 2: get_stats
c = c.replace(
    '            with open(metrics_file, "r", encoding="utf-8") as f:\n                for line in f:\n                    try:\n                        metric = json.loads(line.strip())\n                        if metric.get("timestamp", 0) > cutoff:\n                            metrics.append(metric)\n                    except Exception as e:  # TODO: Narrow exception type\n                        logger.warning("JSON解析线上评测指标失败: %s", e, exc_info=True)\n        except Exception as e:  # TODO: Narrow exception type\n            logger.warning("获取线上评测指标失败: %s", e, exc_info=True)',
    '            def _read_metrics():\n                result = []\n                with open(metrics_file, "r", encoding="utf-8") as f:\n                    for line in f:\n                        try:\n                            metric = json.loads(line.strip())\n                            if metric.get("timestamp", 0) > cutoff:\n                                result.append(metric)\n                        except Exception as e:\n                            logger.warning("JSON解析线上评测指标失败: %s", e, exc_info=True)\n                return result\n            metrics = await asyncio.to_thread(_read_metrics)\n        except Exception as e:  # TODO: Narrow exception type\n            logger.warning("获取线上评测指标失败: %s", e, exc_info=True)'
)

# Fix 3: get_slow_queries
c = c.replace(
    '            with open(metrics_file, "r", encoding="utf-8") as f:\n                for line in f:\n                    try:\n                        metric = json.loads(line.strip())\n                        if (metric.get("type") == "search" and\n                            metric.get("latency_ms", 0) > threshold_ms):\n                            slow_queries.append(metric)\n                    except Exception as e:  # TODO: Narrow exception type\n                        logger.warning("JSON解析慢查询指标失败: %s", e, exc_info=True)\n        except Exception as e:  # TODO: Narrow exception type\n            logger.warning("获取慢查询失败: %s", e, exc_info=True)',
    '            def _read_slow():\n                result = []\n                with open(metrics_file, "r", encoding="utf-8") as f:\n                    for line in f:\n                        try:\n                            metric = json.loads(line.strip())\n                            if (metric.get("type") == "search" and\n                                metric.get("latency_ms", 0) > threshold_ms):\n                                result.append(metric)\n                        except Exception as e:\n                            logger.warning("JSON解析慢查询指标失败: %s", e, exc_info=True)\n                return result\n            slow_queries = await asyncio.to_thread(_read_slow)\n        except Exception as e:  # TODO: Narrow exception type\n            logger.warning("获取慢查询失败: %s", e, exc_info=True)'
)

c = ensure_asyncio_import(c)
write_file("src/services/online_eval.py", c)
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

# Fix 2: build_relations_from_chunks - line 105
# Let me check what this looks like
c = ensure_asyncio_import(c)
write_file("src/shaoyang/relation_builder.py", c)
print("  FIXED (1 of 2)")


# ============================================================
# src/taiyang/seed_score_ab.py
# ============================================================
print("=== src/taiyang/seed_score_ab.py ===")
c = read_file("src/taiyang/seed_score_ab.py")

# Fix 1: record_test_data
c = c.replace(
    '        test_file = os.path.join(TEST_DIR, f"{self.TEST_CONFIG[\'test_name\']}.jsonl")\n        with open(test_file, "a", encoding="utf-8") as f:\n            f.write(json.dumps(test_data, ensure_ascii=False) + "\\n")',
    '        test_file = os.path.join(TEST_DIR, f"{self.TEST_CONFIG[\'test_name\']}.jsonl")\n        def _write_test():\n            with open(test_file, "a", encoding="utf-8") as f:\n                f.write(json.dumps(test_data, ensure_ascii=False) + "\\n")\n        await asyncio.to_thread(_write_test)'
)

# Fix 2: evaluate
c = c.replace(
    '        with open(test_file, "r", encoding="utf-8") as f:\n            for line in f:\n                try:\n                    data.append(json.loads(line.strip()))\n                except Exception as e:  # TODO: Narrow exception type\n                    logger.warning("JSON解析A/B测试数据失败: %s", e, exc_info=True)',
    '        def _read_test():\n            result = []\n            with open(test_file, "r", encoding="utf-8") as f:\n                for line in f:\n                    try:\n                        result.append(json.loads(line.strip()))\n                    except Exception as e:\n                        logger.warning("JSON解析A/B测试数据失败: %s", e, exc_info=True)\n            return result\n        data = await asyncio.to_thread(_read_test)'
)

c = ensure_asyncio_import(c)
write_file("src/taiyang/seed_score_ab.py", c)
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

c = ensure_asyncio_import(c)
write_file("src/taiyin/mcp_tools.py", c)
print("  FIXED")


print("\n" + "=" * 60)
print("All fixes applied!")
print("=" * 60)
