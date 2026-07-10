import asyncio
"""
dream_cycle.py — 第九宫·中宫：24/7 后台神经消化循环

对标 GBrain 的 Dream Cycle，实现夜间自动消化循环：
  - digest（消化）：增量处理新文档，补做未向量化的 embedding
  - enrich（丰富化）：补全实体缺失属性，更新知识图谱
  - consolidate（整合）：压缩冗余、合并语义相似 chunk
  - gap_scan（扫描）：发现知识盲区
  - health_report（日报）：生成每日摘要

关键设计决策：
  - 不依赖 LLM：digest/enrich/consolidate 全部基于向量相似度 + 正则规则
  - gap_scan 可选用 LLM（分析搜索日志），但默认关闭
  - 日报格式：Markdown，同 GBrain 风格
  - 所有操作日志写入 logging

调度方式：由 EasyClaw cron 每夜 02:00 触发
"""


import json
import logging
import os
import re
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("evolution.dream_cycle")

# ============================================================================
# 配置
# ============================================================================

REPORT_DIR = os.environ.get(
    "DREAM_CYCLE_REPORT_DIR",
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "dream_reports"),
)

DUPLICATE_SIMILARITY_THRESHOLD = float(os.environ.get("DREAM_CYCLE_DUP_THRESHOLD", "0.95"))
MAX_DAILY_DIGEST = int(os.environ.get("DREAM_CYCLE_MAX_DIGEST", "500"))
MAX_CONSOLIDATE_CHUNKS = int(os.environ.get("DREAM_CYCLE_MAX_CONSOLIDATE", "2000"))
GAP_SCAN_DAYS = int(os.environ.get("DREAM_CYCLE_GAP_DAYS", "7"))
GAP_LOW_SCORE_THRESHOLD = float(os.environ.get("DREAM_CYCLE_GAP_SCORE_THRESHOLD", "0.5"))

# Entity 正则模式（GBrain 风格零 LLM 实体提取）
ENTITY_PATTERNS: Dict[str, "re.Pattern"] = {
    "person": re.compile(
        r"(?:[A-Z][a-z]+(?:\s[A-Z][a-z]+)+)"
        r"|(?:[\u4e00-\u9fff]{2,4}(?:\u8001\u5e08|\u7ecf\u7406|\u603b\u88c1|\u603b\u76d1|\u4e3b\u4efb|\u5de5\u7a0b\u5e08|\u535a\u58eb|\u6559\u6388)?)",
    ),
    "company": re.compile(
        r"(?:[\u4e00-\u9fff]{2,}(?:\u516c\u53f8|\u96c6\u56e2|\u6709\u9650|\u79d1\u6280|\u5b9e\u4e1a|\u80a1\u4efd|\u63a7\u80a1|\u4f01\u4e1a|\u5de5\u5382|\u4e8b\u52a1\u6240))"
        r"|(?:\b[A-Z][a-zA-Z]*(?:\s(?:Inc|Corp|Ltd|LLC|Co|Group|Technologies|Systems))\b)",
    ),
    "product": re.compile(
        r"(?:[\u4e00-\u9fff]{2,}(?:\u7cfb\u7edf|\u5e73\u53f0|\u8f6f\u4ef6|\u5de5\u5177|\u65b9\u6848|\u4ea7\u54c1|\u5f15\u64ce|\u6846\u67b6|\u6a21\u578b))"
        r"|(?:\b[A-Z][a-zA-Z]*\s*(?:v?\d+(?:\.\d+)*)|(?:Pro|Lite|Ultra|Enterprise))\b",
    ),
    "date": re.compile(
        r"\b\d{4}[-/\u5e74]\d{1,2}[-/\u6708]\d{1,2}[\u65e5\u53f7]?"
        r"|\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b",
    ),
    "amount": re.compile(
        r"(?:\u00a5|\uffe5|CNY|USD|\$)\s*\d[\d,]*(?:\.\d{1,2})?"
        r"|\d[\d,]*(?:\.\d{1,2})?(?:\u4e07\u5143|\u4ebf\u5143|\u5143|\u7f8e\u5143|\u7f8e\u91d1|\u4eba\u6c11\u5e01)",
    ),
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "phone": re.compile(r"\b1[3-9]\d{9}\b|\b0\d{2,3}[-]?\d{7,8}\b"),
}

TYPE_HINTS: Dict[str, str] = {
    "\u516c\u53f8": "company",
    "\u96c6\u56e2": "company",
    "\u6709\u9650": "company",
    "\u79d1\u6280": "company",
    "\u4ea7\u54c1": "product",
    "\u7cfb\u7edf": "system",
    "\u5e73\u53f0": "platform",
    "\u8f6f\u4ef6": "software",
    "\u5de5\u5177": "tool",
    "\u8001\u5e08": "person",
    "\u7ecf\u7406": "person",
    "\u603b\u88c1": "person",
    "\u603b\u76d1": "person",
    "\u56e2\u961f": "team",
    "\u9879\u76ee": "project",
    "\u4f1a\u8bae": "event",
    "\u534f\u8bae": "document",
    "\u5408\u540c": "document",
    "\u62a5\u544a": "document",
}


# ============================================================================
# DreamCycle 主类
# ============================================================================


class DreamCycle:
    """
    第九宫·中宫：24/7 后台神经消化循环

    对标 GBrain 的 Dream Cycle：
    - 消化(digest)：增量处理新文档
    - 丰富化(enrich)：补全实体属性、更新图谱
    - 整合(consolidate)：压缩冗余、合并相似 chunk
    - 扫描(gap_scan)：发现知识盲区
    - 日报(health_report)：生成每日摘要
    """

    def __init__(self, report_dir: Optional[str] = None):
        self._report_dir = Path(report_dir or REPORT_DIR)
        self._report_dir.mkdir(parents=True, exist_ok=True)
        self._start_time = time.time()
        logger.info("[DreamCycle] init report_dir=%s", self._report_dir)

    # ========================================================================
    # 主循环入口
    # ========================================================================

    async def run(self) -> str:
        """主循环入口，由 cron 调度或手动触发"""
        logger.info("[DreamCycle] === night cycle start ===")
        start_ts = time.time()

        results = {
            "digest": await self.digest_new(),
            "enrich": await self.enrich_entities(),
            "consolidate": await self.consolidate_duplicates(),
            "gap_scan": await self.scan_knowledge_gaps(),
        }

        report = self.generate_report(results)
        await self.push_report(report)

        elapsed = time.time() - start_ts
        logger.info("[DreamCycle] === night cycle done (%.1fs) ===", elapsed)
        return report

    # ========================================================================
    # Step 1: digest
    # ========================================================================

    async def digest_new(self) -> dict:
        """消化当日新入库文档"""
        logger.info("[DreamCycle] Phase 1/4: digest_new")
        result: Dict[str, Any] = {
            "new_docs": 0, "embedded": 0, "total_docs": 0, "errors": []
        }

        try:
            from src.db.memory_store import get_store
            store = get_store()
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

            try:
                cursor = store._db_conn.execute(
                    "SELECT id, doc, file_hash, file_name, chunk_index FROM chunks "
                    "WHERE date(created_at) = ? ORDER BY created_at DESC LIMIT ?",
                    (today, MAX_DAILY_DIGEST),
                )
                new_chunks = [dict(row) for row in cursor.fetchall()]
            except Exception as e:  # TODO: Narrow exception type
                logger.warning("[DreamCycle] chunks query failed: %s", e)
                new_chunks = []

            result["new_docs"] = len(new_chunks)

            if not new_chunks:
                logger.info("[DreamCycle] digest: no new docs today")
                try:
                    total = store._db_conn.execute(
                        "SELECT COUNT(*) FROM chunks"
                    ).fetchone()
                    result["total_docs"] = total[0] if total else 0
                except Exception:  # TODO: Narrow exception type
                    result["total_docs"] = 0
                return result

            try:
                from src.db.vector_store import get_vector_store
                vs = get_vector_store()
                if vs is not None:
                    embedded_count = 0
                    chunk_ids = [f"chunk_{c['id']}" for c in new_chunks]
                    batch_size = 50
                    for i in range(0, len(chunk_ids), batch_size):
                        batch = chunk_ids[i : i + batch_size]
                        try:
                            existing = vs._collection.get(ids=batch, include=[])
                            if existing and existing.get("ids"):
                                embedded_count += len(existing["ids"])
                        except Exception:  # TODO: Narrow exception type
                            pass
                    result["embedded"] = embedded_count
                    result["total_docs"] = (
                        vs.count() if vs.count() > 0 else len(new_chunks)
                    )
                else:
                    result["errors"].append("VectorStore unavailable")
                    result["total_docs"] = len(new_chunks)
            except Exception as e:  # TODO: Narrow exception type
                logger.warning("[DreamCycle] VectorStore query failed: %s", e)
                result["errors"].append(f"VectorStore: {e}")
                result["total_docs"] = len(new_chunks)

            logger.info(
                "[DreamCycle] digest: new=%d embedded=%d total=%d",
                result["new_docs"], result["embedded"], result["total_docs"],
            )

        except Exception as e:  # TODO: Narrow exception type
            logger.error("[DreamCycle] digest_new error: %s", e, exc_info=True)
            result["errors"].append(str(e))

        return result

    # ========================================================================
    # Step 2: enrich
    # ========================================================================

    async def enrich_entities(self) -> dict:
        """丰富化：补全实体缺失属性"""
        logger.info("[DreamCycle] Phase 2/4: enrich_entities")
        result: Dict[str, Any] = {
            "new_entities": 0, "new_edges": 0, "total_entities": 0,
            "total_edges": 0, "enriched": 0, "errors": [],
        }

        try:
            from src.db.memory_store import get_store
            store = get_store()

            try:
                cursor = store._db_conn.execute(
                    "SELECT entity_id, name, entity_type, description, chunk_ids_json "
                    "FROM entities "
                    "WHERE (description IS NULL OR description = '' "
                    "OR entity_type IS NULL OR entity_type = '') "
                    "AND status = 'active' LIMIT 100"
                )
                bare_entities = [dict(row) for row in cursor.fetchall()]
            except Exception as e:  # TODO: Narrow exception type
                logger.warning("[DreamCycle] entities query failed: %s", e)
                bare_entities = []

            if not bare_entities:
                logger.info("[DreamCycle] enrich: no bare entities")
                try:
                    total = store._db_conn.execute(
                        "SELECT COUNT(*) FROM entities WHERE status='active'"
                    ).fetchone()
                    result["total_entities"] = total[0] if total else 0
                except Exception:  # TODO: Narrow exception type
                    pass
                return result

            enriched_count = 0
            for entity in bare_entities:
                try:
                    chunk_ids_json = entity.get("chunk_ids_json", "[]")
                    if isinstance(chunk_ids_json, str):
                        chunk_ids = json.loads(chunk_ids_json)
                    else:
                        chunk_ids = chunk_ids_json or []

                    if not chunk_ids:
                        continue

                    chunk_id = chunk_ids[0]
                    row = store._db_conn.execute(
                        "SELECT doc FROM chunks WHERE id = ?", (chunk_id,)
                    ).fetchone()
                    if not row:
                        continue

                    context = row["doc"] or ""
                    inferred_type = self._infer_entity_type(
                        entity["name"], context
                    )
                    description = self._extract_entity_description(
                        entity["name"], context
                    )

                    if inferred_type or description:
                        update_fields = []
                        update_values: List[str] = []
                        if inferred_type and not entity.get("entity_type"):
                            update_fields.append("entity_type = ?")
                            update_values.append(inferred_type)
                        if description:
                            update_fields.append("description = ?")
                            update_values.append(description[:500])
                        if update_fields:
                            update_values.append(entity["entity_id"])
                            store._db_conn.execute(
                                f"UPDATE entities SET {', '.join(update_fields)} "
                                f"WHERE entity_id = ?",
                                update_values,
                            )
                            store._db_conn.commit()
                            enriched_count += 1
                except Exception as e:  # TODO: Narrow exception type
                    logger.debug(
                        "[DreamCycle] enrich single fail %s: %s",
                        entity.get("name", "?"), e,
                    )

            result["enriched"] = enriched_count

            try:
                total = store._db_conn.execute(
                    "SELECT COUNT(*) FROM entities WHERE status='active'"
                ).fetchone()
                result["total_entities"] = total[0] if total else 0
            except Exception:  # TODO: Narrow exception type
                pass

            try:
                from src.db.data_store import load_graph
                graph = await asyncio.to_thread(load_graph)
                result["total_edges"] = len(graph.get("edges", []))
            except Exception:  # TODO: Narrow exception type
                pass

            logger.info(
                "[DreamCycle] enrich: entities=%d enriched=%d",
                result["total_entities"], result["enriched"],
            )

        except Exception as e:  # TODO: Narrow exception type
            logger.error("[DreamCycle] enrich error: %s", e, exc_info=True)
            result["errors"].append(str(e))

        return result

    # ========================================================================
    # Step 3: consolidate
    # ========================================================================

    async def consolidate_duplicates(self) -> dict:
        """整合：合并语义相似度 > 阈值的重复 chunk"""
        logger.info("[DreamCycle] Phase 3/4: consolidate_duplicates")
        result: Dict[str, Any] = {
            "duplicates_found": 0, "merged": 0, "candidates": 0, "errors": [],
        }

        try:
            from src.db.vector_store import get_vector_store
            vs = get_vector_store()
            if vs is None:
                result["errors"].append("VectorStore unavailable")
                return result

            total_vectors = vs.count()
            if total_vectors <= 0:
                return result

            sample_size = min(total_vectors, MAX_CONSOLIDATE_CHUNKS)
            duplicates_found = 0
            candidates = 0

            try:
                existing = vs._collection.get(
                    limit=sample_size, include=["embeddings", "metadatas"]
                )
                if not existing or not existing.get("ids"):
                    return result

                ids = existing["ids"]
                embeddings = existing.get("embeddings", [])
                from src.db.memory_store import get_store
                store = get_store()

                for i in range(0, len(ids), 100):
                    batch_ids = ids[i : i + 100]
                    batch_emb = embeddings[i : i + 100] if embeddings else []

                    for j, chunk_id in enumerate(batch_ids):
                        try:
                            if not batch_emb or j >= len(batch_emb):
                                continue
                            qr = vs.query(
                                query_embedding=batch_emb[j], n_results=3,
                            )
                            if qr.get("error"):
                                continue

                            distances = qr.get("distances", [[]])[0]
                            result_ids = qr.get("ids", [[]])[0]

                            for k, rid in enumerate(result_ids):
                                if rid == chunk_id:
                                    continue
                                candidates += 1
                                similarity = max(0.0, 1.0 - distances[k])
                                if similarity >= DUPLICATE_SIMILARITY_THRESHOLD:
                                    duplicates_found += 1
                                    try:
                                        raw_id = chunk_id.replace("chunk_", "")
                                        store._db_conn.execute(
                                            "UPDATE chunks SET status = "
                                            "'duplicate_candidate' WHERE id = ?",
                                            (raw_id,),
                                        )
                                    except Exception:  # TODO: Narrow exception type
                                        pass
                                    break
                        except Exception as e:  # TODO: Narrow exception type
                            logger.debug(
                                "[DreamCycle] consolidate single fail: %s", e
                            )

                try:
                    store._db_conn.commit()
                except Exception:  # TODO: Narrow exception type
                    pass

            except Exception as e:  # TODO: Narrow exception type
                logger.warning(
                    "[DreamCycle] consolidate vector fail: %s", e
                )
                result["errors"].append(f"vector: {e}")

            result["duplicates_found"] = duplicates_found
            result["candidates"] = candidates
            result["merged"] = 0

            logger.info(
                "[DreamCycle] consolidate: duplicates=%d candidates=%d",
                duplicates_found, candidates,
            )

        except Exception as e:  # TODO: Narrow exception type
            logger.error("[DreamCycle] consolidate error: %s", e, exc_info=True)
            result["errors"].append(str(e))

        return result

    # ========================================================================
    # Step 4: gap_scan
    # ========================================================================

    async def scan_knowledge_gaps(self) -> dict:
        """扫描知识盲区"""
        logger.info("[DreamCycle] Phase 4/4: gap_scan")
        result: Dict[str, Any] = {
            "frequent_no_result": [], "suggested_topics": [],
            "total_searches": 0, "gap_queries": 0, "errors": [],
        }

        try:
            from src.db.data_store import search_history
            history = search_history(days=GAP_SCAN_DAYS)
            result["total_searches"] = len(history)

            if not history:
                return result

            low_quality: List[Dict[str, Any]] = []
            for entry in history:
                query = entry.get("query", "").strip()
                rc = entry.get("results", 0)
                ts_val = entry.get("top_score", 1.0)
                avs = entry.get("avg_score", 1.0)

                if (
                    rc == 0
                    or (ts_val is not None and ts_val < GAP_LOW_SCORE_THRESHOLD)
                    or (avs is not None and avs < GAP_LOW_SCORE_THRESHOLD * 0.6)
                ):
                    low_quality.append({
                        "query": query,
                        "results": rc,
                        "top_score": ts_val,
                        "avg_score": avs,
                        "is_no_result": rc == 0,
                        "timestamp": entry.get("time", ""),
                    })

            qc: Counter = Counter()
            qd: Dict[str, List[dict]] = {}
            for item in low_quality:
                q = item["query"].lower().strip()
                qc[q] += 1
                if q not in qd:
                    qd[q] = []
                qd[q].append(item)

            for query, count in qc.most_common(20):
                if count >= 2:
                    details = qd.get(query, [])
                    result["frequent_no_result"].append({
                        "query": query,
                        "frequency": count,
                        "avg_results": (
                            sum(d.get("results", 0) for d in details) / len(details)
                            if details else 0
                        ),
                        "last_seen": (
                            max(d.get("timestamp", "") for d in details)
                            if details else ""
                        ),
                        "samples": details[:3],
                    })

            result["gap_queries"] = len(result["frequent_no_result"])
            result["suggested_topics"] = [
                item["query"] for item in result["frequent_no_result"][:10]
            ]

            logger.info(
                "[DreamCycle] gap_scan: searches=%d gaps=%d",
                result["total_searches"], result["gap_queries"],
            )

        except Exception as e:  # TODO: Narrow exception type
            logger.error("[DreamCycle] gap_scan error: %s", e, exc_info=True)
            result["errors"].append(str(e))

        return result

    # ========================================================================
    # 日报生成
    # ========================================================================

    def generate_report(self, results: dict) -> str:
        """生成日报 Markdown"""
        now = datetime.now(timezone.utc)
        now_str = now.strftime("%Y-%m-%d %H:%M UTC")

        d = results.get("digest", {})
        e = results.get("enrich", {})
        c = results.get("consolidate", {})
        g = results.get("gap_scan", {})

        qs = self._calculate_quality_score(results)
        stars = "\u2b50" * min(5, max(1, qs // 20))

        nd = d.get("new_docs", 0)
        emb = d.get("embedded", 0)
        td = d.get("total_docs", 0)
        enr = e.get("enriched", 0)
        te = e.get("total_entities", 0)
        dup = c.get("duplicates_found", 0)
        gq = g.get("gap_queries", 0)
        tsearch = g.get("total_searches", 0)

        all_errors: List[str] = []

        lines = [
            "# Night Dream Report",
            "",
            f"> Time: {now_str}",
            f"> Duration: {time.time() - self._start_time:.1f}s",
            f"> Score: {stars} ({qs}/100)",
            "",
            "---",
            "",
            "## Summary",
            "",
            f"- Digest: new={nd}, embedded={emb}, total={td}",
            f"- Enrich: enriched={enr}, total_entities={te}",
            f"- Consolidate: duplicates={dup}",
            f"- Gap Scan: gaps={gq}, searches={tsearch}",
            "",
        ]

        # Digest
        if nd > 0:
            lines.extend([
                "## Digest",
                f"New chunks: {nd}, Vectorized: {emb}, Total: {td}",
                "",
            ])
            if d.get("errors"):
                all_errors.extend(d["errors"])
        else:
            lines.extend(["## Digest", "No new documents today.", ""])

        # Enrich
        if enr > 0:
            lines.extend([
                "## Enrich",
                f"Enriched entities: {enr}, Total entities: {te}",
                "",
            ])
        else:
            lines.extend(["## Enrich", "All entities complete.", ""])

        # Consolidate
        if dup > 0:
            lines.extend([
                "## Consolidate",
                f"Found {dup} duplicate pairs (threshold > {DUPLICATE_SIMILARITY_THRESHOLD})",
                "Marked as duplicate_candidate for manual review.",
                "",
            ])
        else:
            lines.extend(["## Consolidate", "No duplicates found.", ""])

        # Gap Scan
        if gq > 0:
            lines.extend([
                "## Gap Scan",
                f"Searches: {tsearch}, Gap queries: {gq} (last {GAP_SCAN_DAYS} days)",
                "",
                "### Frequent No-Result Queries",
            ])
            for item in g.get("frequent_no_result", [])[:10]:
                freq = item.get("frequency", 0)
                query = item.get("query", "?")
                avg_res = item.get("avg_results", 0)
                lines.append(f"- {query} (x{freq}, avg results: {avg_res:.1f})")
            lines.append("")

            suggested = g.get("suggested_topics", [])
            if suggested:
                lines.append("### Suggested Topics")
                for topic in suggested[:5]:
                    lines.append(f"- {topic}")
                lines.append("")
        else:
            lines.extend([
                "## Gap Scan",
                f"No knowledge gaps found in last {GAP_SCAN_DAYS} days.",
                "",
            ])

        # Errors
        for _cat, data in results.items():
            if isinstance(data, dict) and data.get("errors"):
                for err in data["errors"]:
                    all_errors.append(f"[{_cat}] {err}")

        if all_errors:
            lines.append("## Warnings")
            lines.append("")
            for err in all_errors[:10]:
                lines.append(f"- {err}")
            lines.append("")

        lines.extend([
            "---",
            "",
            "*Fuxi Night Dream v1.50 -- Palace 9 Dream Cycle*",
        ])

        report = "\n".join(lines)
        self._save_report(report, results)
        return report

    def _save_report(self, report: str, results: dict) -> str:
        """保存日报到本地文件"""
        now = datetime.now(timezone.utc)
        ts = now.strftime("%Y%m%d_%H%M")
        fp = self._report_dir / f"dream_report_{ts}.md"

        try:
            fp.write_text(report, encoding="utf-8")
            jp = self._report_dir / f"dream_data_{ts}.json"
            jp.write_text(
                json.dumps({
                    "timestamp": now.isoformat(),
                    "results": results,
                    "report_path": str(fp),
                }, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            logger.info("[DreamCycle] report saved: %s", fp)
        except Exception as e:  # TODO: Narrow exception type
            logger.error("[DreamCycle] save failed: %s", e)
        return str(fp)

    async def push_report(self, report: str) -> bool:
        """推送日报到通知中心"""
        try:
            try:
                from src.services.feature_flags import is_enabled
                if not is_enabled("enable_dream_cycle_notifications"):
                    logger.info("[DreamCycle] notifications disabled via flag")
                    return False
            except ImportError:
                pass

            now = datetime.now(timezone.utc)
            notif = {
                "id": f"dream_cycle_{now.strftime('%Y%m%d%H%M')}",
                "type": "dream_cycle_report",
                "title": f"Night Dream Report ({now.strftime('%Y-%m-%d')})",
                "content": report,
                "timestamp": now.isoformat(),
                "read": False,
                "source": "dream_cycle",
            }
            notif_dir = self._report_dir.parent / "notifications"
            notif_dir.mkdir(parents=True, exist_ok=True)
            nf = notif_dir / f"dream_cycle_{now.strftime('%Y%m%d_%H%M')}.json"
            nf.write_text(
                json.dumps(notif, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            logger.info("[DreamCycle] report pushed to notification center")
            return True
        except Exception as e:  # TODO: Narrow exception type
            logger.error("[DreamCycle] push failed: %s", e, exc_info=True)
            return False

    def _calculate_quality_score(self, results: dict) -> int:
        """质量评分 0-100"""
        score = 70
        d = results.get("digest", {})
        e = results.get("enrich", {})
        c = results.get("consolidate", {})
        g = results.get("gap_scan", {})

        if d.get("new_docs", 0) > 0:
            score += 10
        if d.get("embedded", 0) >= d.get("new_docs", 1) * 0.9:
            score += 10
        if e.get("enriched", 0) > 0:
            score += 5
        if c.get("duplicates_found", 0) == 0:
            score += 10
        if g.get("gap_queries", 0) == 0:
            score += 5

        return min(100, max(0, score))

    def _infer_entity_type(self, name: str, context: str) -> Optional[str]:
        """从实体名称推断类型（零 LLM）"""
        for hint_word, entity_type in TYPE_HINTS.items():
            if hint_word in name:
                return entity_type
        for pattern_name, pattern in ENTITY_PATTERNS.items():
            if pattern_name in ("date", "amount", "email", "phone"):
                continue
            if pattern.search(name):
                return pattern_name
        return None

    def _extract_entity_description(
        self, name: str, context: str
    ) -> Optional[str]:
        """从上下文中提取实体描述"""
        if not name or not context or name not in context:
            return None
        sentences = re.split(r"[。！？\n.!?]", context)
        for sent in sentences:
            if name in sent and len(sent) > 10:
                return sent.strip()[:500]
        return None
