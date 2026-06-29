"""
security.py — Phase 3: 安全模块
Rate Limiting + 审计日志 + Prompt 注入防御
"""
import re, json, time, logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ============ Rate Limiting (3.1) ============

class RateLimiter:
    """简单内存限流器（无需 slowapi 依赖）"""
    
    def __init__(self):
        self._windows = {}  # key -> list of timestamps
    
    def check(self, key: str, max_requests: int, window_seconds: int = 60) -> bool:
        """返回 True 表示允许，False 表示超限"""
        now = time.time()
        if key not in self._windows:
            self._windows[key] = []
        # 清理过期记录
        self._windows[key] = [t for t in self._windows[key] if now - t < window_seconds]
        if len(self._windows[key]) >= max_requests:
            return False
        self._windows[key].append(now)
        return True

# 全局限流器
_limiter = RateLimiter()

def check_rate_limit(ip: str, endpoint: str = "default") -> bool:
    """检查限流"""
    limits = {
        "chat": (10, 60),       # 10/分钟
        "ingest": (3, 60),      # 3/分钟
        "default": (60, 60),    # 60/分钟
    }
    max_req, window = limits.get(endpoint, limits["default"])
    return _limiter.check(f"{ip}:{endpoint}", max_req, window)


# ============ Audit Log (3.3) ============

AUDIT_LOG_PATH = Path.home() / "kb-server/data/audit.jsonl"

def audit_log_entry(ip: str, method: str, path: str, status: int, latency_ms: float, is_sensitive: bool = False):
    """写入审计日志"""
    entry = {
        "time": datetime.now().isoformat(),
        "ip": ip,
        "method": method,
        "path": path,
        "status": status,
        "latency_ms": round(latency_ms, 1),
        "sensitive": is_sensitive,
    }
    try:
        AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(AUDIT_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.warning(f"[Audit] Failed to write: {e}")


# ============ Prompt 注入防御 (3.5) ============

INJECTION_PATTERNS = [
    r'忽略.*(?:之前|上面|以上).*(?:指令|提示|规则|限制)',
    r'ignore.*(?:previous|above).*(?:instructions|prompt|rules)',
    r'输出.*(?:系统|system).*(?:提示|prompt|指令)',
    r'你(?:运行|使用).*(?:什么|哪个).*(?:模型|model|版本)',
    r'(?:forget|disregard).*(?:everything|all).*(?:above|before|previous)',
    r'扮演.*角色.*忽略',
    r'DAN\s|jailbreak|越狱',
]

def sanitize_user_input(query: str) -> Optional[str]:
    """检测并拦截 Prompt 注入，返回 None 表示拦截"""
    for pat in INJECTION_PATTERNS:
        if re.search(pat, query, re.IGNORECASE):
            logger.warning(f"[Security] Prompt injection detected: {query[:100]}")
            return None
    return query.strip()
