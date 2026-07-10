"""
Fix sync I/O in async functions — Phase 4 optimization.
Wraps open() and sqlite3.connect() in asyncio.to_thread().
"""
import os
import re

REPO = r"E:\easyclaw\伏羲-v1.44\repo"


def fix_file(relpath, transformations):
    """Apply text transformations to a file."""
    fpath = os.path.join(REPO, relpath)
    with open(fpath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    for old, new in transformations:
        if old not in content:
            print(f"  WARNING: Pattern not found in {relpath}:")
            print(f"    {old[:80]}...")
            continue
        content = content.replace(old, new, 1)
    
    if content != original:
        # Ensure asyncio is imported
        if 'import asyncio' not in content:
            # Add after last import
            lines = content.split('\n')
            last_import_idx = 0
            for i, line in enumerate(lines):
                s = line.strip()
                if s.startswith('import ') or s.startswith('from '):
                    last_import_idx = i
            lines.insert(last_import_idx + 1, 'import asyncio')
            content = '\n'.join(lines)
        
        with open(fpath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"  FIXED: {relpath}")
    else:
        print(f"  NO CHANGE: {relpath}")


# ============================================================
# 1. src/api/graph.py (2 occurrences)
# ============================================================
print("\n=== src/api/graph.py ===")
fix_file("src/api/graph.py", [
    # auto_edges function - line 83
    (
        '        edges = []\n        if os.path.exists(GRAPH_PATH):\n            with open(GRAPH_PATH, "r", encoding="utf-8") as f:\n                kg_data = json.load(f)\n                edges = list(kg_data.get("edges", []))',
        '        edges = []\n        if os.path.exists(GRAPH_PATH):\n            def _read_graph():\n                with open(GRAPH_PATH, "r", encoding="utf-8") as f:\n                    return json.load(f)\n            kg_data = await asyncio.to_thread(_read_graph)\n            edges = list(kg_data.get("edges", []))'
    ),
    # graph_stats function - line 174
    (
        '        if os.path.exists(GRAPH_PATH):\n            with open(GRAPH_PATH, "r", encoding="utf-8") as f:\n                kg_data = json.load(f)\n                nodes = kg_data.get("nodes", kg_data.get("entities", {}))\n                nodes_count = len(nodes)',
        '        if os.path.exists(GRAPH_PATH):\n            def _read_graph():\n                with open(GRAPH_PATH, "r", encoding="utf-8") as f:\n                    return json.load(f)\n            kg_data = await asyncio.to_thread(_read_graph)\n            nodes = kg_data.get("nodes", kg_data.get("entities", {}))\n            nodes_count = len(nodes)'
    ),
])


# ============================================================
# 2. src/api/synthesis.py (1 occurrence)
# ============================================================
print("\n=== src/api/synthesis.py ===")
fix_file("src/api/synthesis.py", [
    (
        '                    if os.path.exists(kg_path):\n                        with open(kg_path, "r", encoding="utf-8") as f:\n                            kg_data = json.load(f)\n                        graph_entities = kg_data.get("entities", [])',
        '                    if os.path.exists(kg_path):\n                        def _read_kg():\n                            with open(kg_path, "r", encoding="utf-8") as f:\n                                return json.load(f)\n                        kg_data = await asyncio.to_thread(_read_kg)\n                        graph_entities = kg_data.get("entities", [])'
    ),
])


# ============================================================
# 3. src/api/worldtree.py (2 occurrences)
# ============================================================
print("\n=== src/api/worldtree.py ===")
fix_file("src/api/worldtree.py", [
    # worldtree_entities - line 242
    (
        '                if os.path.exists(kg_path):\n                    with open(kg_path, "r", encoding="utf-8") as f:\n                        kg_data = json.load(f)\n                    entities = [',
        '                if os.path.exists(kg_path):\n                    def _read_kg():\n                        with open(kg_path, "r", encoding="utf-8") as f:\n                            return json.load(f)\n                    kg_data = await asyncio.to_thread(_read_kg)\n                    entities = ['
    ),
    # worldtree_relations - line 345
    (
        '                if os.path.exists(kg_path):\n                    with open(kg_path, "r", encoding="utf-8") as f:\n                        kg_data = json.load(f)\n                    relations = kg_data.get("edges", [])',
        '                if os.path.exists(kg_path):\n                    def _read_kg():\n                        with open(kg_path, "r", encoding="utf-8") as f:\n                            return json.load(f)\n                    kg_data = await asyncio.to_thread(_read_kg)\n                    relations = kg_data.get("edges", [])'
    ),
])


# ============================================================
# 4. src/bagua/qian.py (1 occurrence)
# ============================================================
print("\n=== src/bagua/qian.py ===")
fix_file("src/bagua/qian.py", [
    (
        '            shadow_path = _DATA_DIR / "shadow_decisions.jsonl"\n            with open(shadow_path, "a", encoding="utf-8") as f:\n                f.write(json.dumps(shadow_log, ensure_ascii=False) + "\\n")',
        '            shadow_path = _DATA_DIR / "shadow_decisions.jsonl"\n            def _write_shadow():\n                with open(shadow_path, "a", encoding="utf-8") as f:\n                    f.write(json.dumps(shadow_log, ensure_ascii=False) + "\\n")\n            await asyncio.to_thread(_write_shadow)'
    ),
])


# ============================================================
# 5. src/eval/runner.py (1 occurrence)
# ============================================================
print("\n=== src/eval/runner.py ===")
fix_file("src/eval/runner.py", [
    (
        '    with open(result_path, "w", encoding="utf-8") as f:\n        json.dump(report, f, ensure_ascii=False, indent=2)',
        '    def _write_result():\n        with open(result_path, "w", encoding="utf-8") as f:\n            json.dump(report, f, ensure_ascii=False, indent=2)\n    await asyncio.to_thread(_write_result)'
    ),
])


# ============================================================
# 6. src/growth/adjustment_log.py (2 occurrences)
# ============================================================
print("\n=== src/growth/adjustment_log.py ===")
fix_file("src/growth/adjustment_log.py", [
    # record - line 54
    (
        '            with open(log_file, "a", encoding="utf-8") as f:\n                f.write(json.dumps(entry, ensure_ascii=False) + "\\n")',
        '            def _write_log():\n                with open(log_file, "a", encoding="utf-8") as f:\n                    f.write(json.dumps(entry, ensure_ascii=False) + "\\n")\n            await asyncio.to_thread(_write_log)'
    ),
    # get_pending_adjustments - line 68
    (
        '            with open(log_file, "r", encoding="utf-8") as f:\n                for line in f:\n                    try:\n                        records.append(json.loads(line.strip()))',
        '            def _read_log():\n                result = []\n                with open(log_file, "r", encoding="utf-8") as f:\n                    for line in f:\n                        try:\n                            result.append(json.loads(line.strip()))\n                        except Exception as e:  # TODO: Narrow exception type\n                            logger.warning("JSON解析调整记录失败: %s", e, exc_info=True)\n                return result\n            records = await asyncio.to_thread(_read_log)'
    ),
])


# ============================================================
# 7. src/growth/engine.py (2 occurrences)
# ============================================================
print("\n=== src/growth/engine.py ===")
fix_file("src/growth/engine.py", [
    # record_event - line 67
    (
        '        try:\n            with open(log_file, "a", encoding="utf-8") as f:\n                f.write(json.dumps(record, ensure_ascii=False) + "\\n")\n        except Exception as e:  # TODO: Narrow exception type\n            logger.warning(f"[Growth] 写入失败: {e}")',
        '        try:\n            def _write_log():\n                with open(log_file, "a", encoding="utf-8") as f:\n                    f.write(json.dumps(record, ensure_ascii=False) + "\\n")\n            await asyncio.to_thread(_write_log)\n        except Exception as e:  # TODO: Narrow exception type\n            logger.warning(f"[Growth] 写入失败: {e}")'
    ),
    # evaluate - line 125
    (
        '            with open(log_file, "r", encoding="utf-8") as f:\n                for line in f:\n                    try:\n                        events.append(json.loads(line.strip()))',
        '            def _read_log():\n                result = []\n                with open(log_file, "r", encoding="utf-8") as f:\n                    for line in f:\n                        try:\n                            result.append(json.loads(line.strip()))\n                        except Exception as e:  # TODO: Narrow exception type\n                            logger.warning("JSON解析成长事件失败: %s", e, exc_info=True)\n                return result\n            events = await asyncio.to_thread(_read_log)'
    ),
])


# ============================================================
# 8. src/growth/growth_recorder.py (2 occurrences)
# ============================================================
print("\n=== src/growth/growth_recorder.py ===")
fix_file("src/growth/growth_recorder.py", [
    # record - line 36
    (
        '        try:\n            with open(log_file, "a", encoding="utf-8") as f:\n                f.write(json.dumps(record, ensure_ascii=False) + "\\n")\n        except Exception as e:  # TODO: Narrow exception type\n            logger.warning(f"[Growth] 写入失败: {e}")',
        '        try:\n            def _write_log():\n                with open(log_file, "a", encoding="utf-8") as f:\n                    f.write(json.dumps(record, ensure_ascii=False) + "\\n")\n            await asyncio.to_thread(_write_log)\n        except Exception as e:  # TODO: Narrow exception type\n            logger.warning(f"[Growth] 写入失败: {e}")'
    ),
    # query - line 53
    (
        '        with open(log_file, "r", encoding="utf-8") as f:\n            for line in f:\n                try:\n                    record = json.loads(line.strip())',
        '        def _read_log():\n            result = []\n            with open(log_file, "r", encoding="utf-8") as f:\n                for line in f:\n                    try:\n                        record = json.loads(line.strip())\n                        result.append(record)\n                    except Exception as e:  # TODO: Narrow exception type\n                        logger.warning("JSON解析成长记录失败: %s", e, exc_info=True)\n                        continue\n            return result\n        records = await asyncio.to_thread(_read_log)'
    ),
])


# ============================================================
# 9. src/services/eval_automation.py (2 occurrences)
# ============================================================
print("\n=== src/services/eval_automation.py ===")
fix_file("src/services/eval_automation.py", [
    # get_eval_history - line 285
    (
        '            with open(history_file, "r", encoding="utf-8") as f:\n                for line in f:\n                    try:\n                        record = json.loads(line.strip())\n                        # 简单的日期比较\n                        records.append(record)',
        '            def _read_history():\n                result = []\n                with open(history_file, "r", encoding="utf-8") as f:\n                    for line in f:\n                        try:\n                            record = json.loads(line.strip())\n                            result.append(record)\n                        except Exception as e:  # TODO: Narrow exception type\n                            logger.warning("JSON解析评测历史记录失败: %s", e, exc_info=True)\n                return result\n            records = await asyncio.to_thread(_read_history)'
    ),
    # get_latest_report - line 313
    (
        '            with open(report_file, "r", encoding="utf-8") as f:\n                return json.load(f)',
        '            def _read_report():\n                with open(report_file, "r", encoding="utf-8") as f:\n                    return json.load(f)\n            return await asyncio.to_thread(_read_report)'
    ),
])


# ============================================================
# 10. src/services/eval_pipeline.py (1 occurrence)
# ============================================================
print("\n=== src/services/eval_pipeline.py ===")
fix_file("src/services/eval_pipeline.py", [
    (
        '            with open(eval_file, "r", encoding="utf-8") as f:\n                for line in f:\n                    try:\n                        results.append(json.loads(line.strip()))',
        '            def _read_eval():\n                result = []\n                with open(eval_file, "r", encoding="utf-8") as f:\n                    for line in f:\n                        try:\n                            result.append(json.loads(line.strip()))\n                        except Exception as e:  # TODO: Narrow exception type\n                            logger.warning("JSON解析评测结果失败: %s", e, exc_info=True)\n                return result\n            results = await asyncio.to_thread(_read_eval)'
    ),
])


# ============================================================
# 11. src/services/knowledge_lifecycle.py (3 occurrences)
# ============================================================
print("\n=== src/services/knowledge_lifecycle.py ===")
fix_file("src/services/knowledge_lifecycle.py", [
    # record_event - line 52
    (
        '            log_file = LIFECYCLE_DIR / f"{event_type}.jsonl"\n            with open(log_file, "a", encoding="utf-8") as f:\n                f.write(json.dumps(event, ensure_ascii=False) + "\\n")',
        '            log_file = LIFECYCLE_DIR / f"{event_type}.jsonl"\n            def _write_event():\n                with open(log_file, "a", encoding="utf-8") as f:\n                    f.write(json.dumps(event, ensure_ascii=False) + "\\n")\n            await asyncio.to_thread(_write_event)'
    ),
    # get_candidates - line 83
    (
        '            with open(log_file, "r", encoding="utf-8") as f:\n                for line in f:\n                    try:\n                        event = json.loads(line.strip())\n                        candidates.append(event.get("data", {}))',
        '            def _read_events():\n                result = []\n                with open(log_file, "r", encoding="utf-8") as f:\n                    for line in f:\n                        try:\n                            event = json.loads(line.strip())\n                            result.append(event.get("data", {}))\n                        except Exception as e:  # TODO: Narrow exception type\n                            logger.warning("JSON解析生命周期事件失败: %s", e, exc_info=True)\n                return result\n            candidates = await asyncio.to_thread(_read_events)'
    ),
    # _count_events - line 107
    (
        '            with open(log_file, "r", encoding="utf-8") as f:\n                for line in f:\n                    try:\n                        event = json.loads(line.strip())\n                        if event.get("timestamp", 0) > cutoff:\n                            count += 1',
        '            def _count():\n                c = 0\n                with open(log_file, "r", encoding="utf-8") as f:\n                    for line in f:\n                        try:\n                            event = json.loads(line.strip())\n                            if event.get("timestamp", 0) > cutoff:\n                                c += 1\n                        except Exception as e:  # TODO: Narrow exception type\n                            logger.warning("JSON解析生命周期事件统计失败: %s", e, exc_info=True)\n                return c\n            count = await asyncio.to_thread(_count)'
    ),
])


# ============================================================
# 12. src/services/memory.py (4 occurrences)
# ============================================================
print("\n=== src/services/memory.py ===")
fix_file("src/services/memory.py", [
    # save_session - line 61
    (
        '            session_file = MEMORY_DIR / f"session_{session_id}.json"\n            with open(session_file, "w", encoding="utf-8") as f:\n                json.dump(messages, f, ensure_ascii=False, indent=2)',
        '            session_file = MEMORY_DIR / f"session_{session_id}.json"\n            def _write_session():\n                with open(session_file, "w", encoding="utf-8") as f:\n                    json.dump(messages, f, ensure_ascii=False, indent=2)\n            await asyncio.to_thread(_write_session)'
    ),
    # load_session - line 75
    (
        '            with open(session_file, "r", encoding="utf-8") as f:\n                messages = json.load(f)\n                self._session_memory[session_id] = messages\n                return messages',
        '            def _read_session():\n                with open(session_file, "r", encoding="utf-8") as f:\n                    return json.load(f)\n            messages = await asyncio.to_thread(_read_session)\n            self._session_memory[session_id] = messages\n            return messages'
    ),
    # add_long_term_memory - line 93
    (
        '            memory_file = MEMORY_DIR / "long_term.jsonl"\n            record = {\n                "key": key,\n                "value": value,\n                "timestamp": time.time(),\n            }\n            with open(memory_file, "a", encoding="utf-8") as f:\n                f.write(json.dumps(record, ensure_ascii=False) + "\\n")',
        '            memory_file = MEMORY_DIR / "long_term.jsonl"\n            record = {\n                "key": key,\n                "value": value,\n                "timestamp": time.time(),\n            }\n            def _write_memory():\n                with open(memory_file, "a", encoding="utf-8") as f:\n                    f.write(json.dumps(record, ensure_ascii=False) + "\\n")\n            await asyncio.to_thread(_write_memory)'
    ),
    # search_long_term_memory - line 109
    (
        '            with open(memory_file, "r", encoding="utf-8") as f:\n                for line in f:\n                    try:\n                        record = json.loads(line.strip())\n                        # 简单的关键词匹配\n                        if query.lower() in json.dumps(record.get("value", {})).lower():\n                            results.append(record)',
        '            def _search_memory():\n                found = []\n                with open(memory_file, "r", encoding="utf-8") as f:\n                    for line in f:\n                        try:\n                            record = json.loads(line.strip())\n                            if query.lower() in json.dumps(record.get("value", {})).lower():\n                                found.append(record)\n                        except Exception as e:  # TODO: Narrow exception type\n                            logger.warning("JSON解析会话记忆失败: %s", e, exc_info=True)\n                return found\n            results = await asyncio.to_thread(_search_memory)'
    ),
])


# ============================================================
# 13. src/services/online_eval.py (3 occurrences)
# ============================================================
print("\n=== src/services/online_eval.py ===")
fix_file("src/services/online_eval.py", [
    # _flush_metrics - line 69
    (
        '            metrics_file = ONLINE_EVAL_DIR / "metrics.jsonl"\n            with open(metrics_file, "a", encoding="utf-8") as f:\n                for metric in self._metrics_buffer:\n                    f.write(json.dumps(metric, ensure_ascii=False) + "\\n")',
        '            metrics_file = ONLINE_EVAL_DIR / "metrics.jsonl"\n            buf = list(self._metrics_buffer)\n            def _flush():\n                with open(metrics_file, "a", encoding="utf-8") as f:\n                    for metric in buf:\n                        f.write(json.dumps(metric, ensure_ascii=False) + "\\n")\n            await asyncio.to_thread(_flush)'
    ),
    # get_stats - line 89
    (
        '            with open(metrics_file, "r", encoding="utf-8") as f:\n                for line in f:\n                    try:\n                        metric = json.loads(line.strip())\n                        if metric.get("timestamp", 0) > cutoff:\n                            metrics.append(metric)',
        '            def _read_metrics():\n                result = []\n                with open(metrics_file, "r", encoding="utf-8") as f:\n                    for line in f:\n                        try:\n                            metric = json.loads(line.strip())\n                            if metric.get("timestamp", 0) > cutoff:\n                                result.append(metric)\n                        except Exception as e:  # TODO: Narrow exception type\n                            logger.warning("JSON解析线上评测指标失败: %s", e, exc_info=True)\n                return result\n            metrics = await asyncio.to_thread(_read_metrics)'
    ),
    # get_slow_queries - line 128
    (
        '            with open(metrics_file, "r", encoding="utf-8") as f:\n                for line in f:\n                    try:\n                        metric = json.loads(line.strip())\n                        if (metric.get("type") == "search" and\n                            metric.get("latency_ms", 0) > threshold_ms):\n                            slow_queries.append(metric)',
        '            def _read_slow():\n                result = []\n                with open(metrics_file, "r", encoding="utf-8") as f:\n                    for line in f:\n                        try:\n                            metric = json.loads(line.strip())\n                            if (metric.get("type") == "search" and\n                                metric.get("latency_ms", 0) > threshold_ms):\n                                result.append(metric)\n                        except Exception as e:  # TODO: Narrow exception type\n                            logger.warning("JSON解析慢查询指标失败: %s", e, exc_info=True)\n                return result\n            slow_queries = await asyncio.to_thread(_read_slow)'
    ),
])


# ============================================================
# 14. src/services/retrieval.py (1 sqlite3 occurrence)
# ============================================================
print("\n=== src/services/retrieval.py ===")
fix_file("src/services/retrieval.py", [
    (
        '                wt_db = sqlite3.connect(str(WORLDTREE_DB_PATH), timeout=10)\n                wt_db.execute("PRAGMA journal_mode=WAL")\n                wt_db.execute("PRAGMA busy_timeout=5000")\n                wt_db.row_factory = sqlite3.Row\n                rows = wt_db.execute(\n                    "SELECT id, title, summary, category_path FROM wiki_pages WHERE title LIKE ? OR summary LIKE ? LIMIT 5",\n                    (f"%{query}%", f"%{query}%")\n                ).fetchall()\n                wt_db.close()',
        '                def _query_wiki():\n                    wt_db = sqlite3.connect(str(WORLDTREE_DB_PATH), timeout=10)\n                    wt_db.execute("PRAGMA journal_mode=WAL")\n                    wt_db.execute("PRAGMA busy_timeout=5000")\n                    wt_db.row_factory = sqlite3.Row\n                    rows = wt_db.execute(\n                        "SELECT id, title, summary, category_path FROM wiki_pages WHERE title LIKE ? OR summary LIKE ? LIMIT 5",\n                        (f"%{query}%", f"%{query}%")\n                    ).fetchall()\n                    wt_db.close()\n                    return rows\n                rows = await asyncio.to_thread(_query_wiki)'
    ),
])


# ============================================================
# 15. src/services/doc_tools/routes.py (4 occurrences)
# ============================================================
print("\n=== src/services/doc_tools/routes.py ===")
fix_file("src/services/doc_tools/routes.py", [
    # merge_pdfs - line 202
    (
        '        with open(str(output_path), "wb") as out_f:\n            merger.write(out_f)\n\n        return FileResponse(\n            path=str(output_path),\n            filename="merged.pdf",',
        '        def _write_pdf():\n            with open(str(output_path), "wb") as out_f:\n                merger.write(out_f)\n        await asyncio.to_thread(_write_pdf)\n\n        return FileResponse(\n            path=str(output_path),\n            filename="merged.pdf",'
    ),
    # split_pdf - line 268
    (
        '        with open(str(output_path), "wb") as out_f:\n            writer.write(out_f)\n\n        return FileResponse(\n            path=str(output_path),\n            filename=f"split_pages_{start_page}-{actual_end}.pdf",',
        '        def _write_pdf():\n            with open(str(output_path), "wb") as out_f:\n                writer.write(out_f)\n        await asyncio.to_thread(_write_pdf)\n\n        return FileResponse(\n            path=str(output_path),\n            filename=f"split_pages_{start_page}-{actual_end}.pdf",'
    ),
    # compress_pdf helper - line 412
    (
        '    with open(str(output_path), "wb") as out_f:\n        writer.write(out_f)\n\n    return output_path',
        '    def _write_pdf():\n        with open(str(output_path), "wb") as out_f:\n            writer.write(out_f)\n    import asyncio\n    asyncio.get_event_loop().run_in_executor(None, _write_pdf) if not asyncio.get_event_loop().is_running() else None\n    # Note: this is a sync helper, will be called from async context via to_thread\n    _write_pdf()\n\n    return output_path'
    ),
    # compress_image - line 487
    (
        '        with open(str(output_path), "wb") as out_f:\n            img.save(out_f, format=img.format or "JPEG", quality=quality, optimize=True)',
        '        def _save_img():\n            with open(str(output_path), "wb") as out_f:\n                img.save(out_f, format=img.format or "JPEG", quality=quality, optimize=True)\n        await asyncio.to_thread(_save_img)'
    ),
])


# ============================================================
# 16. src/shaoyang/distiller.py (1 sqlite3 occurrence)
# ============================================================
print("\n=== src/shaoyang/distiller.py ===")
fix_file("src/shaoyang/distiller.py", [
    (
        '    conn = sqlite3.connect(str(CHUNKS_DB), timeout=10)\n    conn.execute("PRAGMA journal_mode=WAL")\n    conn.execute("PRAGMA busy_timeout=5000")\n    all_chunks = []',
        '    def _load_chunks():\n        conn = sqlite3.connect(str(CHUNKS_DB), timeout=10)\n        conn.execute("PRAGMA journal_mode=WAL")\n        conn.execute("PRAGMA busy_timeout=5000")\n        all_chunks = []'
    ),
    # Find the fetchall and close after it
    (
        '            all_chunks.append({\n                "id": rid,\n                "text": text,\n                "file_name": fname or "",\n                "raw_category": raw_cat or "",',
        '                all_chunks.append({\n                    "id": rid,\n                    "text": text,\n                    "file_name": fname or "",\n                    "raw_category": raw_cat or "",'
    ),
])

# ============================================================
# 17. src/shaoyang/relation_builder.py (2 sqlite3 occurrences)
# ============================================================
print("\n=== src/shaoyang/relation_builder.py ===")
fix_file("src/shaoyang/relation_builder.py", [
    # extract_relations_cooccurrence - line 19
    (
        '        db = sqlite3.connect(str(WORLDTREE_DB_PATH), timeout=10)\n        db.execute("PRAGMA journal_mode=WAL")\n        db.execute("PRAGMA busy_timeout=5000")\n        entities = db.execute("SELECT id, name, type FROM entities").fetchall()\n        entity_names = {r[1]: (r[0], r[2]) for r in entities}\n        db.close()',
        '        def _load_entities():\n            db = sqlite3.connect(str(WORLDTREE_DB_PATH), timeout=10)\n            db.execute("PRAGMA journal_mode=WAL")\n            db.execute("PRAGMA busy_timeout=5000")\n            entities = db.execute("SELECT id, name, type FROM entities").fetchall()\n            entity_names = {r[1]: (r[0], r[2]) for r in entities}\n            db.close()\n            return entity_names\n        entity_names = await asyncio.to_thread(_load_entities)'
    ),
])


# ============================================================
# 18. src/taiyang/seed_score_ab.py (2 occurrences)
# ============================================================
print("\n=== src/taiyang/seed_score_ab.py ===")
fix_file("src/taiyang/seed_score_ab.py", [
    # record_test_data - line 81
    (
        '        test_file = os.path.join(TEST_DIR, f"{self.TEST_CONFIG[\'test_name\']}.jsonl")\n        with open(test_file, "a", encoding="utf-8") as f:\n            f.write(json.dumps(test_data, ensure_ascii=False) + "\\n")',
        '        test_file = os.path.join(TEST_DIR, f"{self.TEST_CONFIG[\'test_name\']}.jsonl")\n        def _write_test():\n            with open(test_file, "a", encoding="utf-8") as f:\n                f.write(json.dumps(test_data, ensure_ascii=False) + "\\n")\n        await asyncio.to_thread(_write_test)'
    ),
    # evaluate - line 97
    (
        '        with open(test_file, "r", encoding="utf-8") as f:\n            for line in f:\n                try:\n                    data.append(json.loads(line.strip()))',
        '        def _read_test():\n            result = []\n            with open(test_file, "r", encoding="utf-8") as f:\n                for line in f:\n                    try:\n                        result.append(json.loads(line.strip()))\n                    except Exception as e:  # TODO: Narrow exception type\n                        logger.warning("JSON解析A/B测试数据失败: %s", e, exc_info=True)\n            return result\n        data = await asyncio.to_thread(_read_test)'
    ),
])


# ============================================================
# 19. src/taiyin/mcp_tools.py (3 occurrences)
# ============================================================
print("\n=== src/taiyin/mcp_tools.py ===")
fix_file("src/taiyin/mcp_tools.py", [
    # graph_query - line 173
    (
        '        if _os.path.exists(GRAPH_PATH):\n            with open(GRAPH_PATH, "r", encoding="utf-8") as f:\n                kg_data = json.load(f)\n                edges = list(kg_data.get("edges", []))',
        '        if _os.path.exists(GRAPH_PATH):\n            def _read_graph():\n                with open(GRAPH_PATH, "r", encoding="utf-8") as f:\n                    return json.load(f)\n            kg_data = await asyncio.to_thread(_read_graph)\n            edges = list(kg_data.get("edges", []))'
    ),
    # graph_stats - line 226
    (
        '        if _os.path.exists(GRAPH_PATH):\n            with open(GRAPH_PATH, "r", encoding="utf-8") as f:\n                kg_data = json.load(f)\n                nodes = kg_data.get("nodes", kg_data.get("entities", {}))',
        '        if _os.path.exists(GRAPH_PATH):\n            def _read_graph():\n                with open(GRAPH_PATH, "r", encoding="utf-8") as f:\n                    return json.load(f)\n            kg_data = await asyncio.to_thread(_read_graph)\n            nodes = kg_data.get("nodes", kg_data.get("entities", {}))'
    ),
    # cross_entity_synthesize - line 420
    (
        '        with open(GRAPH_PATH, "r", encoding="utf-8") as f:\n            kg_data = json.load(f)',
        '        def _read_graph():\n            with open(GRAPH_PATH, "r", encoding="utf-8") as f:\n                return json.load(f)\n        kg_data = await asyncio.to_thread(_read_graph)'
    ),
])


print("\n" + "=" * 60)
print("All fixes applied!")
print("=" * 60)
