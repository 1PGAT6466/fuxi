"""
organs/lung.py — 肺 v1.41（自主呼吸+脏标记+变化检测）

肺 = 知识呼吸中枢。
- 吸气：检测文件变化（hash 比对，不是只数数）
- 呼气：触发蒸馏 + 脾 Wiki 同步 + 通知大脑
- 脏标记：无变化时不浪费 CPU
"""

import asyncio
import logging
import time
import hashlib
from typing import Dict, Any

from src.hypothalamus.meridian import Meridian, Signal, SignalPriority
from ..organ_base import OrganBase, OrganMetadata, Element, PrenatalBagua, PostnatalBagua, Stem

logger = logging.getLogger("lung")

class LungAgent(OrganBase):
    """肺智能体——自主呼吸 v1.41
    
    脏标记机制：上一轮的文件指纹 vs 当前 → 有变化才呼气
    """
    
    BREATH_INTERVAL = 25  # 5分钟一次呼吸
    
    def __init__(self, meridian: Meridian):
        super().__init__(meridian, OrganMetadata(
            organ_id="lung", name="肺·呼吸", emoji="🫁", description="LLM生成与知识蒸馏",
            prenatal_gua=PrenatalBagua.XUN, prenatal_direction="西南",
            postnatal_gua=PostnatalBagua.XUN, postnatal_direction="东南",
            element=Element.WOOD, stem=Stem.GENG,
            palace_number=4, ui_position="southeast",
            peak_hour="03:00-05:00", rest_hour="15:00-17:00"))
        self._last_breathe = time.time()
        self._breathe_count = 0
        self._exhale_count = 0  # 真正呼气次数
        self._running = False
        self._task = None
        self._last_fingerprint: str = ""  # v1.41: 文件指纹
        self._dirty = True  # 启动时默认需要首次呼气
        self._stats = {"inhales": 0, "exhales": 0, "skipped": 0}
        self._heartbeat_log: Dict[str, float] = {}  # v1.43: organ heartbeat times
        
        self.meridian.register_organ(
            self.organ_id, "肺", "🫁",
            "自主呼吸：检测变化→触发蒸馏→更新索引"
        )
        
        self.meridian.subscribe(self.organ_id, "new_nutrition", self._handle_new_nutrition)
        self.meridian.subscribe(self.organ_id, "collect_health", self._handle_collect_health)
        self.meridian.subscribe(self.organ_id, "organ_heartbeat", self._handle_organ_heartbeat)
        self.meridian.subscribe(self.organ_id, "breathe", self._handle_breathe)
        self.meridian.subscribe(self.organ_id, "heartbeat", self._handle_heartbeat)
    
    def _handle_heartbeat(self, signal: Signal) -> None:
        self.meridian.heartbeat(self.organ_id)
    
    async def _handle_new_nutrition(self, signal: Signal) -> None:
        """收到胃送来的新营养 → 标记脏数据，触发呼气"""
        chunks = signal.payload.get("chunks", [])
        if chunks:
            logger.info(f"[Lung] New nutrition: {len(chunks)} chunks → marking dirty")
            self._dirty = True
            await self._exhale()
    
    async def _handle_breathe(self, signal: Signal) -> None:
        """手动触发呼吸（无视脏标记）"""
        result = await self._breathe_cycle(force=True)
        self.meridian.reply(signal, {"ok": True, **result})
    
    async def _breathe_cycle(self, force: bool = False) -> Dict:
        """一次完整呼吸周期"""
        self._stats["inhales"] += 1
        
        # 吸气
        changed, fingerprint = await self._inhale()
        self._dirty = self._dirty or (fingerprint != self._last_fingerprint)
        self._last_fingerprint = fingerprint
        
        result = {
            "inhale": {"total_chunks": changed, "fingerprint": fingerprint[:16]},
            "exhale": None,
            "performed": False,
        }
        
        # 呼气：只在脏数据时执行
        if self._dirty or force:
            exhale_result = await self._exhale()
            result["exhale"] = exhale_result
            result["performed"] = True
            self._dirty = False
            self._exhale_count += 1
            self._stats["exhales"] += 1
        else:
            self._stats["skipped"] += 1
        
        self._last_breathe = time.time()
        self._breathe_count += 1
        
        return result
    
    def _inhale(self) -> tuple:
        """吸气：检测文件变化（指纹比对）"""
        try:
            from src.db.data_store import load_chunks
            chunks = load_chunks()
            if not chunks:
                return 0, ""
            
            # 构建指纹：文件名+数量+最后修改时间
            files = set()
            max_mtime = 0
            for c in chunks:
                fn = c.get("file_name", "") or c.get("source_file", "")
                if fn:
                    files.add(fn)
                mtime = c.get("mtime", 0) or 0
                if mtime > max_mtime:
                    max_mtime = mtime
            
            raw = f"{len(chunks)}|{len(files)}|{max_mtime}"
            fingerprint = hashlib.md5(raw.encode()).hexdigest()
            
            return len(chunks), fingerprint
        except Exception as e:
            logger.warning(f"[Lung] Inhale error: {e}")
            return 0, ""
    
    async def _exhale(self) -> Dict:
        """呼气：蒸馏 + Wiki同步 + 通知大脑"""
        try:
            # 蒸馏
            await self._run_distillation()
            
            # 通知脾做 Wiki 向量同步
            self.meridian.send(Signal(
                source=self.organ_id,
                target="spleen",
                signal_type="sync_vectors",
                payload={"timestamp": time.time()},
                priority=SignalPriority.HIGH,
            ))
            
            # 通知大脑：知识已更新
            self.meridian.send(Signal(
                source=self.organ_id,
                target="brain",
                signal_type="knowledge_updated",
                payload={"timestamp": time.time()},
                priority=SignalPriority.LOW,
            ))
            
            return {"ok": True}
        except Exception as e:
            logger.warning(f"[Lung] Exhale error: {e}")
            return {"error": str(e)}
    
    async def _run_distillation(self) -> None:
        """运行蒸馏流程"""
        try:
            from src.services.distiller import distill_batch_async
            from src.db.data_store import load_chunks
            chunks = load_chunks()
            if not chunks:
                logger.info("[Lung] No chunks to distill")
                return
            
            # 只蒸馏最近 24h 内新增/修改的 chunks
            recent = []
            cutoff = time.time() - 86400
            for c in chunks:
                mtime = c.get("mtime", 0) or 0
                if mtime >= cutoff:
                    recent.append(c)
            
            if recent:
                logger.info(f"[Lung] Distilling {len(recent)} recent chunks (of {len(chunks)} total)")
                await distill_batch_async(recent)
            else:
                logger.info(f"[Lung] No recent chunks to distill")
        except Exception as e:
            logger.warning(f"[Lung] Distillation error: {e}")
    
    def start_breathing(self) -> None:
        """启动自主呼吸"""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._breath_loop())
        logger.info("[Lung] 自主呼吸已启动 🫁")
    
    def stop_breathing(self) -> None:
        """停止呼吸"""
        self._running = False
        if self._task:
            self._task.cancel()
    
    async def _breath_loop(self) -> None:
        """呼吸循环"""
        while self._running:
            try:
                await asyncio.sleep(self.BREATH_INTERVAL)
                self.meridian.heartbeat(self.organ_id)
                await self._breathe_cycle()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"[Lung] Breath loop error: {e}")
    
    def _handle_collect_health(self, signal: Signal) -> None:
        """v1.43: 肺朝百脉——汇集所有器官健康指标，形成健康报告"""
        import time as _time
        organ_ids = signal.payload.get("organ_ids", [])
        report = {}
        for oid in organ_ids:
            last_hb = self._heartbeat_log.get(oid, 0)
            alive = (_time.time() - last_hb) < 120 if last_hb else False
            report[oid] = {"alive": alive, "last_heartbeat_ago": _time.time() - last_hb if last_hb else None}

        self.meridian.send(Signal(
            source=self.organ_id, target="brain",
            signal_type="health_report",
            payload={"report": report, "timestamp": _time.time()},
            priority=SignalPriority.LOW,
        ))
        self.meridian.reply(signal, {"ok": True, "organs_checked": len(report)})

    def _handle_organ_heartbeat(self, signal: Signal) -> None:
        """v1.43: 被动跟踪器官心跳"""
        import time as _time
        oid = signal.payload.get("organ_id", "")
        if oid:
            self._heartbeat_log[oid] = _time.time()

    def stats(self) -> Dict:
        return {
            "breathe_count": self._breathe_count,
            "exhale_count": self._exhale_count,
            "last_breathe_ago": round(time.time() - self._last_breathe, 1),
            "dirty": self._dirty,
            "running": self._running,
            "alive": self.meridian.is_alive(self.organ_id),
            **self._stats,
        }
