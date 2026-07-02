"""
trace.py — trace_id 全链路追踪
"""
import uuid
import logging
import time
from typing import Dict, Optional
from pathlib import Path

logger = logging.getLogger("trace")

TRACE_DIR = Path("data/traces")


def generate_trace_id() -> str:
    """生成trace_id"""
    return str(uuid.uuid4())[:8]


class TraceLogger:
    """全链路追踪日志器"""

    def __init__(self, trace_id: str, symbol_id: str):
        self.trace_id = trace_id
        self.symbol_id = symbol_id
        TRACE_DIR.mkdir(parents=True, exist_ok=True)

    def log(self, module: str, message: str, level: str = "INFO"):
        """统一日志格式"""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"[{timestamp}] [{self.trace_id}] [{self.symbol_id}] {module}: {message}"

        log_func = getattr(logger, level.lower(), logger.info)
        log_func(log_line)

        # 写入trace日志文件
        try:
            trace_file = TRACE_DIR / f"{self.trace_id}.log"
            with open(trace_file, "a", encoding="utf-8") as f:
                f.write(log_line + "\n")
        except Exception:
            pass


class TraceContext:
    """trace上下文管理"""

    def __init__(self, trace_id: str = None):
        self.trace_id = trace_id or generate_trace_id()
        self.start_time = time.time()
        self.spans = []

    def start_span(self, symbol_id: str, module: str) -> TraceLogger:
        """开始一个span"""
        logger = TraceLogger(self.trace_id, symbol_id)
        logger.log(module, "开始")
        self.spans.append({
            "symbol": symbol_id,
            "module": module,
            "start": time.time(),
        })
        return logger

    def end_span(self, symbol_id: str, module: str):
        """结束一个span"""
        for span in self.spans:
            if span["symbol"] == symbol_id and span["module"] == module:
                span["end"] = time.time()
                span["duration_ms"] = (span["end"] - span["start"]) * 1000
                break

    def get_summary(self) -> Dict:
        """获取trace摘要"""
        total_duration = (time.time() - self.start_time) * 1000
        return {
            "trace_id": self.trace_id,
            "total_duration_ms": round(total_duration, 2),
            "spans": len(self.spans),
            "details": self.spans,
        }
