"""
trace_logger.py — 全链路追踪日志器
trace_id 贯穿 taiyin→shaoyin→taiyang→降级链→growth
"""
import os
import logging
import asyncio
from datetime import datetime
from typing import Optional

logger = logging.getLogger("infra.trace")

# trace 文件目录
TRACE_DIR = "data/traces"


class TraceLogger:
    """全链路追踪日志器"""

    def __init__(self, trace_id: str = "unknown", symbol_id: str = "unknown"):
        self.trace_id = trace_id
        self.symbol_id = symbol_id
        # 确保 trace 目录存在
        os.makedirs(TRACE_DIR, exist_ok=True)

    def log(self, module: str, message: str, level: str = "INFO"):
        """记录日志"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        log_line = f"[{timestamp}] [{self.trace_id}] [{self.symbol_id}] {module}: {message}"

        # 写入标准日志
        getattr(logger, level.lower(), logger.info)(log_line)

        # 异步写入 trace 文件
        try:
            asyncio.get_event_loop().run_in_executor(None, self._write_to_trace_file, log_line)
        except RuntimeError:
            # 没有事件循环时直接写入
            self._write_to_trace_file(log_line)

    def _write_to_trace_file(self, log_line: str):
        """写入 trace 日志文件"""
        try:
            trace_file = os.path.join(TRACE_DIR, f"{self.trace_id}.log")
            with open(trace_file, "a", encoding="utf-8") as f:
                f.write(log_line + "\n")
        except Exception as e:
            logger.error(f"写入 trace 文件失败: {e}")

    def log_exception(self, module: str, exception: Exception):
        """记录异常"""
        self.log(module, f"异常: {exception}", level="ERROR")

    def log_timing(self, module: str, operation: str, duration_ms: float):
        """记录耗时"""
        self.log(module, f"{operation} 完成, 耗时={duration_ms:.0f}ms")


def get_trace_logger(trace_id: str, symbol_id: str) -> TraceLogger:
    """获取 TraceLogger 实例"""
    return TraceLogger(trace_id, symbol_id)
