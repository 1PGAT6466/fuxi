"""
organs/nose.py — 👃 鼻（异常嗅探）v1.41

鼻 = 伏羲的异常感知器官。
持续嗅探搜索日志，检测质量下降、异常模式、知识退化。
v1.41: 异常日志修复 + 零结果/延迟检测实现 + 测试修复
"""

import asyncio
import json
import logging
import time
import traceback
from typing import Any, Dict, List

from src.hypothalamus.meridian import Meridian, Signal, SignalPriority
from ..organ_base import OrganBase, OrganMetadata, Element, PrenatalBagua, PostnatalBagua, Stem

logger = logging.getLogger("nose")


class NoseAgent(OrganBase):
    """鼻智能体——异常嗅探

    持续嗅探系统日志，发现异常主动告警。
    """

    SNIFF_INTERVAL = 25

    def __init__(self, meridian: Meridian):
        super().__init__(meridian, OrganMetadata(
            organ_id="nose", name="鼻·嗅探", emoji="👃", description="异常监控与告警",
            prenatal_gua=PrenatalBagua.DUI, prenatal_direction="东南",
            postnatal_gua=PostnatalBagua.DUI, postnatal_direction="西",
            element=Element.METAL, stem=Stem.XIN,
            palace_number=7, ui_position="west",
            peak_hour="13:00-15:00", rest_hour="01:00-03:00"))
        self._sniff_count = 0
        self._alerts: List[Dict] = []
        self._running = False
        self._task = None
        self._baseline = {"avg_score": 0, "avg_latency_ms": 0, "zero_result_rate": 0}

        self.meridian.register_organ(
            self.organ_id, "鼻", "👃",
            "异常嗅探：检测搜索质量趋势→发现异常模式→主动告警",
        )
        self.meridian.subscribe(self.organ_id, "sniff", self._handle_sniff)
        self.meridian.subscribe(self.organ_id, "heartbeat", self._handle_heartbeat)

    def _handle_heartbeat(self, signal: Signal) -> None:
        self.meridian.heartbeat(self.organ_id)

    async def _handle_sniff(self, signal: Signal) -> None:
        result = await self._sniff()
        self.meridian.reply(signal, result)

    async def _sniff(self) -> Dict:
        alerts = []

        try:
            log_alerts = await self._check_search_logs()
            alerts.extend(log_alerts)
        except Exception as e:
            logger.warning(f"[Nose] Search log check failed: {e}")

        try:
            zero_alerts = await self._check_zero_results()
            alerts.extend(zero_alerts)
        except Exception as e:
            logger.warning(f"[nose] Zero result check failed: {e}")

        try:
            latency_alerts = await self._check_latency()
            alerts.extend(latency_alerts)
        except Exception as e:
            logger.warning(f"[nose] Latency check failed: {e}")

        self._sniff_count += 1

        if alerts:
            self._alerts.extend(alerts)
            self.meridian.send(Signal(
                source=self.organ_id, target="brain",
                signal_type="alert",
                payload={"alerts": alerts, "sniff_count": self._sniff_count},
                priority=SignalPriority.HIGH,
            ))

        return {
            "sniff_count": self._sniff_count,
            "alerts": alerts,
            "total_alerts_24h": len([a for a in self._alerts if time.time() - a.get("time", 0) < 86400]),
        }

    def _check_search_logs(self) -> List[Dict]:
        alerts = []
        try:
            from src.db.data_store import search_history
            entries = search_history(days=1)

            if len(entries) < 10:
                return alerts

            zero_count = sum(1 for e in entries if e.get("results", 0) == 0)
            low_score_count = sum(1 for e in entries if e.get("top_score", 10) < 2)

            zero_rate = zero_count / len(entries)
            low_rate = low_score_count / len(entries)

            if zero_rate > 0.3:
                alerts.append({
                    "time": time.time(),
                    "type": "high_zero_result",
                    "message": f"零结果率过高: {zero_rate:.0%}（最近 {len(entries)} 条）",
                    "severity": "warning",
                })

            if low_rate > 0.5:
                alerts.append({
                    "time": time.time(),
                    "type": "low_quality",
                    "message": f"低分结果过多: {low_rate:.0%}（最近 {len(entries)} 条）",
                    "severity": "warning",
                })
        except Exception as e:
            logger.warning(f"[nose] Search log check failed: {e}")
        return alerts

    def _check_zero_results(self) -> List[Dict]:
        """检查持续零结果趋势"""
        alerts = []
        try:
            from src.db.data_store import search_history
            entries = search_history(days=7)
            if len(entries) < 20:
                return alerts

            # 按天统计零结果率
            daily_zero: Dict[str, int] = {}
            daily_total: Dict[str, int] = {}
            for e in entries:
                day = time.strftime("%Y-%m-%d", time.localtime(e.get("timestamp", 0)))
                daily_total[day] = daily_total.get(day, 0) + 1
                if e.get("results", 0) == 0:
                    daily_zero[day] = daily_zero.get(day, 0) + 1

            # 连续 3 天零结果率 > 0.4
            consecutive = 0
            for day in sorted(daily_total.keys()):
                rate = daily_zero.get(day, 0) / max(daily_total[day], 1)
                if rate > 0.4:
                    consecutive += 1
                else:
                    consecutive = 0
                if consecutive >= 3:
                    alerts.append({
                        "time": time.time(),
                        "type": "sustained_zero",
                        "message": f"连续 {consecutive} 天零结果率偏高（>40%）",
                        "severity": "critical",
                    })
                    break
        except Exception as e:
            logger.warning(f"[nose] Zero result trend check failed: {e}")
        return alerts

    def _check_latency(self) -> List[Dict]:
        """检查响应延迟趋势"""
        alerts = []
        try:
            from src.db.data_store import search_history
            entries = search_history(days=1)
            if len(entries) < 10:
                return alerts

            latencies = [e.get("ms", 0) for e in entries if e.get("ms", 0) > 0]
            if not latencies:
                return alerts

            avg_latency = sum(latencies) / len(latencies)
            if avg_latency > 5000:  # 5 秒
                alerts.append({
                    "time": time.time(),
                    "type": "high_latency",
                    "message": f"平均延迟过高: {avg_latency:.0f}ms（最近 {len(latencies)} 条）",
                    "severity": "warning",
                })

            # 是否有最近 10 条中 3 条以上超时
            timeout_count = sum(1 for l in latencies[-10:] if l > 10000)
            if timeout_count >= 3:
                alerts.append({
                    "time": time.time(),
                    "type": "timeout_spike",
                    "message": f"最近 {min(10, len(latencies))} 条中 {timeout_count} 条超时（>10s）",
                    "severity": "critical",
                })
        except Exception as e:
            logger.warning(f"[nose] Latency check failed: {e}")
        return alerts

    def start_sniffing(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._sniff_loop())
        logger.info("[Nose] 异常嗅探已启动 👃")

    def stop_sniffing(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()

    async def _sniff_loop(self) -> None:
        while self._running:
            try:
                await asyncio.sleep(self.SNIFF_INTERVAL)
                self.meridian.heartbeat(self.organ_id)
                await self._sniff()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[Nose] Sniff error: {e}")

    def stats(self) -> Dict:
        return {
            "sniff_count": self._sniff_count,
            "alerts_24h": len([a for a in self._alerts if time.time() - a.get("time", 0) < 86400]),
            "running": self._running,
            "alive": self.meridian.is_alive(self.organ_id),
        }
