"""
organs/skeleton.py — 🦴 骨骼（知识图谱）v1.43

骨骼 = 伏羲的身体骨架，撑起整个知识结构。
实体关系推理，支撑大脑的多步推导。
v1.43: query_graph → route_entity_with_neighbors + _save_relations 健壮 + 异常日志修复
"""

import asyncio
import logging
import traceback
from typing import Any, Dict, List

from src.hypothalamus.meridian import Meridian, Signal, SignalPriority

logger = logging.getLogger("skeleton")


class SkeletonAgent:
    """骨骼智能体——知识图谱

    从数据中构建实体关系，支撑关系推理。
    """

    SCAN_INTERVAL = 3600  # 每小时自主扫描一次

    def __init__(self, meridian: Meridian):
        self.meridian = meridian
        self.organ_id = "skeleton"
        self._relation_count = 0
        self._running = False
        self._task = None

        self.meridian.register_organ(
            self.organ_id, "骨骼", "🦴",
            "知识图谱：实体关系构建→路径推理→知识推导",
        )
        self.meridian.subscribe(self.organ_id, "query_relations", self._handle_query)
        self.meridian.subscribe(self.organ_id, "build_relations", self._handle_build)
        self.meridian.subscribe(self.organ_id, "heartbeat", self._handle_heartbeat)

    async def _handle_heartbeat(self, signal: Signal) -> None:
        self.meridian.heartbeat(self.organ_id)

    async def _handle_query(self, signal: Signal) -> None:
        """查询实体关系"""
        entity = signal.payload.get("entity", "")
        result = await self._query(entity)
        self.meridian.reply(signal, result)

    async def _handle_build(self, signal: Signal) -> None:
        """构建关系"""
        chunks = signal.payload.get("chunks", [])
        result = await self._extract_relations(chunks)
        self.meridian.reply(signal, result)

    # ── 查询 ──

    async def _query(self, entity: str) -> Dict:
        """查询知识图谱——使用 graph_router 的邻居路由"""
        try:
            # ✅ P1 修复: query_graph 不存在 → 用 route_entity_with_neighbors
            from src.services.graph_router import route_entity_with_neighbors

            result = route_entity_with_neighbors(entity, max_entities=5)
            entities = result.get("entities", [])
            paths = result.get("paths", [])

            return {
                "entities": entities,
                "paths": paths,
                "count": len(entities),
            }
        except Exception as e:
            logger.error(f"[Skeleton] Graph query failed: {e}")
            return {"entities": [], "paths": [], "error": str(e)}

    # ── 构建 ──

    async def _extract_relations(self, chunks: List[Dict]) -> Dict:
        """从文本中提取实体关系"""
        try:
            from src.services.relation_builder import extract_relations_cooccurrence

            relations = await extract_relations_cooccurrence(chunks)
            if relations:
                saved = self._save_relations(relations)
                if saved:
                    self._relation_count += len(relations)

                # 通知大脑：新关系已构建
                self.meridian.send(Signal(
                    source=self.organ_id, target="brain",
                    signal_type="relations_built",
                    payload={"count": len(relations)},
                    priority=SignalPriority.LOW,
                ))

            return {"relations": len(relations), "ok": True}
        except Exception as e:
            logger.error(f"[Skeleton] Extract relations failed: {e}")
            return {"ok": False, "error": str(e)}

    def _save_relations(self, relations: list) -> bool:
        """保存实体关系到 data_store graph"""
        try:
            from src.db.data_store import load_graph, save_graph

            graph = load_graph()
            entities = graph.get("entities", {})
            edges = list(graph.get("edges", []))

            existing_edges = set()
            for e in edges:
                key = (e.get("source", ""), e.get("target", ""), e.get("relation", ""))
                existing_edges.add(key)

            added = 0
            for r in relations:
                src = r.get("entity_a", "")
                tgt = r.get("entity_b", "")
                rel = r.get("relation", "related_to")
                conf = r.get("confidence", 0.5)

                # 确保实体存在
                if src and src not in entities:
                    entities[src] = {"name": src, "type": "auto", "relations": []}
                if tgt and tgt not in entities:
                    entities[tgt] = {"name": tgt, "type": "auto", "relations": []}

                # 添加边
                edge_key = (src, tgt, rel)
                if edge_key not in existing_edges:
                    edges.append({
                        "source": src,
                        "target": tgt,
                        "relation": rel,
                        "confidence": conf,
                        "source_type": "auto",
                    })
                    existing_edges.add(edge_key)
                    added += 1

            if added > 0:
                graph["entities"] = entities
                graph["edges"] = edges
                save_graph(graph)
                logger.info(f"[Skeleton] Saved {added} new relations")

            return True
        except Exception as e:
            logger.warning(f"[Skeleton] Save relations failed: {e}\n{traceback.format_exc()}")
            return False

    # ── 自主扫描 ──

    async def start_scanning(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._scan_loop())
        logger.info("[Skeleton] 骨骼扫描已启动 🦴")

    async def stop_scanning(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()

    async def _scan_loop(self) -> None:
        loop = asyncio.get_running_loop()
        while self._running:
            try:
                await asyncio.sleep(self.SCAN_INTERVAL)
                from src.db.data_store import load_chunks
                chunks = await loop.run_in_executor(None, load_chunks)
                if chunks:
                    await self._extract_relations(chunks[:500])  # 最多 500
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[Skeleton] Scan error: {e}")

    # ── 统计 ──

    def stats(self) -> Dict:
        entity_count = 0
        edge_count = 0
        try:
            from src.db.data_store import load_graph
            graph = load_graph()
            entity_count = len(graph.get("entities", {}))
            edge_count = len(graph.get("edges", []))
        except Exception as e:
            # ✅ P2 修复: module 未定义 → 用 __name__
            logger.warning(f"[skeleton] Failed to load graph for stats: {e}")

        return {
            "entities": entity_count,
            "edges": edge_count,
            "relations_extracted": self._relation_count,
            "alive": self.meridian.is_alive(self.organ_id),
        }
