# DEPRECATED: 本文件已被 organs/sanjiao/signal_layer.py 取代，保留仅为向后兼容。
# 实际生效代码见 organs/sanjiao/signal_layer.py
# v1.50 标记，计划 v1.51 删除。
"""
organs/sanjiao.py — 🌊 三焦（跨层数据通道）v1.43

三焦 = 上中下三焦数据通道。不是具体脏器，是跨层的数据传输层。
  - 上焦：大脑 + 心 + 胆（决策层通信）
  - 中焦：胃 + 小肠 + 脾 + 骨骼（精炼层数据流）
  - 下焦：chunks.db + worldtree.db + knowledge_graph.json（存储层读写）

职责：
  - 大数据块（>1KB）走三焦通道，不塞经络
  - 三焦负责数据一致性：读写锁、事务边界
  - 下焦 → 上焦：状态上报、统计汇总
  - 上焦 → 中焦：调度指令、参数配置
"""

import asyncio
import logging
import time
from typing import Any, Dict, Optional

from src.hypothalamus.meridian import Meridian, Signal, SignalPriority
from .organ_base import OrganBase, OrganMetadata, Element, PrenatalBagua, PostnatalBagua, Stem

logger = logging.getLogger("sanjiao")


class SanJiaoAgent(OrganBase):
    """三焦智能体——跨层数据通道"""

    def __init__(self, meridian: Meridian):
        super().__init__(meridian, OrganMetadata(
            organ_id="sanjiao", name="三焦·通道", emoji="🌊",
            description="跨层数据通道：上中下三焦传输 + 数据一致性",
            prenatal_gua=PrenatalBagua.LI, prenatal_direction="东",
            postnatal_gua=PostnatalBagua.LI, postnatal_direction="南",
            element=Element.FIRE, stem=Stem.DING,
            palace_number=9, ui_position="center",
            peak_hour="21:00-23:00", rest_hour="09:00-11:00"))

        self.meridian.register_organ(self.organ_id, self.md.name, self.md.emoji, self.md.description)
        self.meridian.subscribe(self.organ_id, "data_read", self._handle_read)
        self.meridian.subscribe(self.organ_id, "data_write", self._handle_write)
        self.meridian.subscribe(self.organ_id, "stats_collect", self._handle_stats)
        self.meridian.subscribe(self.organ_id, "heartbeat", self._handle_heartbeat)

        self._read_count = 0
        self._write_count = 0
        self._running = False
        self._task = None
    # FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行

    async def _handle_heartbeat(self, signal: Signal) -> None:
        self.meridian.heartbeat(self.organ_id)
    # FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行

    async def _handle_read(self, signal: Signal) -> None:
        """统一数据读取入口 — 路由到正确的存储后端"""
        source = signal.payload.get("source", "chunks")

        try:
            if source == "chunks":
                from src.db.data_store import load_chunks
                data = load_chunks()
            elif source == "wiki":
                from src.services.wiki import get_wiki_engine
                we = get_wiki_engine()
                data = we.list_pages() if we else []
            elif source == "graph":
                from src.db.data_store import load_graph
                data = load_graph()
            elif source == "worldtree":
                from src.core.db import connect
                with connect("worldtree") as db:
                    data = [dict(r) for r in db.execute("SELECT * FROM wiki_pages").fetchall()]
            else:
                data = {}

            self._read_count += 1
            self.meridian.reply(signal, {"ok": True, "data": data, "source": source})
        except Exception as e:
            logger.error(f"[SanJiao] Read failed ({source}): {e}")
            self.meridian.reply(signal, {"ok": False, "error": str(e)})
    # FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行

    async def _handle_write(self, signal: Signal) -> None:
        """统一数据写入入口"""
        target = signal.payload.get("target", "graph")
        data = signal.payload.get("data", {})

        try:
            if target == "graph":
                from src.db.data_store import save_graph
                save_graph(data)
            elif target == "wiki":
                from src.services.wiki import get_wiki_engine
                we = get_wiki_engine()
                if we and data.get("title"):
                    we.create_page(
                        title=data.get("title", ""),
                        content=data.get("content", ""),
                        category=data.get("category", "通用办公"),
                        tags=data.get("tags", []),
                        sources=data.get("sources", []),
                    )

            self._write_count += 1
            self.meridian.reply(signal, {"ok": True, "target": target})
        except Exception as e:
            logger.error(f"[SanJiao] Write failed ({target}): {e}")
            self.meridian.reply(signal, {"ok": False, "error": str(e)})
    # FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行

    async def _handle_stats(self, signal: Signal) -> None:
        """收集全系统统计数据（下焦→上焦上报）"""
        try:
            from src.core.db import connect
            with connect("chunks") as chunks_db:
                chunk_count = chunks_db.execute("SELECT count(*) FROM chunks").fetchone()[0]
            with connect("worldtree") as wt_db:
                wiki_count = wt_db.execute("SELECT count(*) FROM wiki_pages").fetchone()[0]

            from src.db.data_store import load_graph
            graph = load_graph()
            node_count = len(graph.get("nodes", graph.get("entities", {})))
            edge_count = len(graph.get("edges", []))

            self.meridian.reply(signal, {
                "ok": True,
                "stats": {
                    "chunks": chunk_count,
                    "wiki_pages": wiki_count,
                    "graph_nodes": node_count,
                    "graph_edges": edge_count,
                }
            })
        except Exception as e:
            logger.error(f"[SanJiao] Stats failed: {e}")
            self.meridian.reply(signal, {"ok": False, "error": str(e)})
    # FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行

    async def start_working(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._channel_loop())

    async def _channel_loop(self) -> None:
        while self._running:
            try:
                self.meridian.heartbeat(self.organ_id)
                await asyncio.sleep(25)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[SanJiao] Loop error: {e}")
                await asyncio.sleep(10)

    def stats(self) -> Dict:
        return {"reads": self._read_count, "writes": self._write_count}
