"""
trace_cleanup.py — trace文件清理
保留7天，定时清理
"""
import time
import logging
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger("infra.trace_cleanup")

from src.config import DATA_DIR as CONFIG_DATA_DIR
TRACE_DIR = Path(CONFIG_DATA_DIR) / "traces"
RETENTION_DAYS = 7


class TraceCleanup:
    """trace文件清理器"""

    def __init__(self, trace_dir: Path = TRACE_DIR, retention_days: int = RETENTION_DAYS):
        self.trace_dir = trace_dir
        self.retention_days = retention_days
    # FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行

    async def cleanup(self) -> Dict:
        """清理过期的trace文件"""
        if not self.trace_dir.exists():
            return {"deleted": 0, "kept": 0}

        cutoff = time.time() - self.retention_days * 86400
        deleted = 0
        kept = 0

        for trace_file in self.trace_dir.glob("*.log"):
            try:
                if trace_file.stat().st_mtime < cutoff:
                    trace_file.unlink()
                    deleted += 1
                else:
                    kept += 1
            except Exception as e:  # TODO: Narrow exception type
                logger.warning(f"[TraceCleanup] 删除失败: {trace_file}: {e}")

        logger.info(f"[TraceCleanup] 清理完成: 删除{deleted}个, 保留{kept}个")

        return {"deleted": deleted, "kept": kept}

    def get_trace_files(self) -> List[Dict]:
        """获取trace文件列表"""
        if not self.trace_dir.exists():
            return []

        files = []
        for trace_file in self.trace_dir.glob("*.log"):
            try:
                stat = trace_file.stat()
                files.append({
                    "name": trace_file.name,
                    "size_bytes": stat.st_size,
                    "modified": stat.st_mtime,
                    "age_days": (time.time() - stat.st_mtime) / 86400,
                })
            except Exception as e:  # TODO: Narrow exception type
                logger.warning("Exception 失败: %s", e, exc_info=True)

        return sorted(files, key=lambda x: x["modified"], reverse=True)


# 全局实例
_cleanup: Optional[TraceCleanup] = None


def get_trace_cleanup() -> TraceCleanup:
    """获取全局trace清理器"""
    global _cleanup
    if _cleanup is None:
        _cleanup = TraceCleanup()
    return _cleanup
