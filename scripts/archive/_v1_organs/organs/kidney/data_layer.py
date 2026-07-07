"""
data_layer.py — 肾数据层

职责：数据持久化（加载/保存/查询）
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger("kidney.data")

# 访问计数持久化文件
ACCESS_COUNTS_FILE = os.environ.get(
    "KB_ACCESS_COUNTS_PATH",
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "data", "access_counts.json"),
)


class KidneyDataLayer:
    """肾数据层——数据持久化"""

    def __init__(self):
        self._access_counts: Optional[Dict[str, int]] = None

    # ── 访问计数 ──

    def load_access_counts(self) -> Dict[str, int]:
        """从磁盘加载访问计数"""
        if self._access_counts is not None:
            return self._access_counts

        path = Path(ACCESS_COUNTS_FILE)
        if not path.exists():
            self._access_counts = {}
            return self._access_counts

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._access_counts = data.get("counts", {}) if isinstance(data, dict) else {}
        except Exception as e:
            logger.warning(f"[Kidney] 加载访问计数失败: {e}")
            self._access_counts = {}

        return self._access_counts

    def save_access_counts(self, counts: Dict[str, int]) -> None:
        """持久化访问计数"""
        path = Path(ACCESS_COUNTS_FILE)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump({
                    "counts": counts,
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }, f, ensure_ascii=False, indent=2)
            self._access_counts = counts
        except Exception as e:
            logger.warning(f"[Kidney] 保存访问计数失败: {e}")

    def increment_access_count(self, file_hash: str) -> int:
        """增加访问计数并返回新值"""
        counts = self.load_access_counts()
        counts[file_hash] = counts.get(file_hash, 0) + 1
        self.save_access_counts(counts)
        return counts[file_hash]

    # ── 数据查询 ──

    def load_chunks(self) -> List[Dict]:
        """加载所有数据块"""
        try:
            from src.db.data_store import load_chunks
            return load_chunks()
        except Exception as e:
            logger.error(f"[Kidney] 加载数据块失败: {e}")
            return []

    def save_chunks(self, chunks: List[Dict]) -> bool:
        """保存数据块"""
        try:
            from src.db.data_store import save_chunks
            save_chunks(chunks)
            return True
        except Exception as e:
            logger.error(f"[Kidney] 保存数据块失败: {e}")
            return False

    def query_chunks_by_category(self, category: str) -> List[Dict]:
        """按分类查询数据块"""
        chunks = self.load_chunks()
        return [c for c in chunks if c.get("category") == category]

    def query_stale_chunks(self, stale_days: int) -> List[Dict]:
        """查询过期数据块"""
        import time
        chunks = self.load_chunks()
        now = time.time()
        stale = []

        for chunk in chunks:
            last_access = chunk.get("last_accessed", 0)
            if isinstance(last_access, str):
                try:
                    last_access = time.mktime(time.strptime(last_access, "%Y-%m-%d"))
                except Exception:
                    last_access = 0

            days_stale = (now - float(last_access or 0)) / 86400
            if days_stale > stale_days:
                stale.append(chunk)

        return stale
