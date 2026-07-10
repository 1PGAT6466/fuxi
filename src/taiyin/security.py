"""
security.py - Phase 3: 安全模块
Rate Limiting + 审计日志 + Prompt 注入防御
"""
import os, re, json, time, logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ============ Rate Limiting (3.1) ============

class RateLimiter:
    """简单内存限流器(无需 slowapi 依赖)"""

    def __init__(self):
        self._windows = {}  # key -> list of timestamps

    def check(self, key: str, max_requests: int, window_seconds: int = 60) -> bool:
        """返回 True 表示允许,False 表示超限"""
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

# 审计日志路径 — 优先使用环境变量，回退到默认路径
AUDIT_LOG_PATH = Path(os.getenv("FUXI_AUDIT_LOG_PATH", str(Path.home() / "kb-server/data/audit.jsonl")))

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
    except Exception as e:  # TODO: Narrow exception type
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

# ============ XSS 防御 (v1.44 R2) ============
# 事件处理器拦截
_EVENT_HANDLER_PATTERN = re.compile(
    r'\b(?:on(?:error|click|load|mouseover|mouseout|mousedown|mouseup|keydown|keyup|keypress|focus|blur|change|submit|reset|select|abort|beforeunload|error|hashchange|message|offline|online|pagehide|pageshow|popstate|resize|scroll|storage|unload|animationend|animationiteration|animationstart|transitionend|contextmenu|drag|dragend|dragenter|dragleave|dragover|dragstart|drop|input|invalid|search|touchcancel|touchend|touchmove|touchstart|wheel|copy|cut|paste)\b)\s*=',
    re.IGNORECASE
)
# javascript: 协议拦截
_JS_PROTOCOL_PATTERN = re.compile(
    r'(?:javascript|vbscript|livescript|data)\s*:',
    re.IGNORECASE
)
# HTML 标签拦截(script, iframe, object, embed, form 等危险标签)
_DANGEROUS_TAG_PATTERN = re.compile(
    r'<\s*(?:script|iframe|object|embed|applet|form|input|textarea|button|select|link|meta|base|style|svg|math|marquee|details|dialog|template|slot|portal|fencedframe)\b[^>]*>',
    re.IGNORECASE
)
# data: URI 中的 HTML/JS 内容
_DATA_URI_PATTERN = re.compile(
    r'data\s*:\s*(?:text/html|application/javascript|text/javascript|image/svg\+xml)\s*[;,]',
    re.IGNORECASE
)


def sanitize_xss(input_str: str) -> str:
    """v1.44 R2: XSS 防御 - 净化输入中的 XSS 攻击向量

    检测并移除:
      - 事件处理器 (onerror, onclick, onload 等)
      - javascript: / vbscript: / data: 协议
      - 危险 HTML 标签 (script, iframe, object 等)
      - data: URI 中的 HTML/JS 内容

    Args:
        input_str: 用户输入

    Returns:
        净化后的字符串
    """
    if not input_str:
        return input_str

    result = input_str

    # 拦截事件处理器
    if _EVENT_HANDLER_PATTERN.search(result):
        logger.warning(f"[Security] XSS: 事件处理器拦截, input_len={len(result)}")
        result = _EVENT_HANDLER_PATTERN.sub('', result)

    # 拦截 javascript: 等协议
    if _JS_PROTOCOL_PATTERN.search(result):
        logger.warning(f"[Security] XSS: 危险协议拦截, input_len={len(result)}")
        result = _JS_PROTOCOL_PATTERN.sub('', result)

    # 拦截危险 HTML 标签
    if _DANGEROUS_TAG_PATTERN.search(result):
        logger.warning(f"[Security] XSS: 危险标签拦截, input_len={len(result)}")
        result = _DANGEROUS_TAG_PATTERN.sub('', result)

    # 拦截 data: URI 中的 HTML/JS
    if _DATA_URI_PATTERN.search(result):
        logger.warning(f"[Security] XSS: data: URI 危险内容拦截, input_len={len(result)}")
        result = _DATA_URI_PATTERN.sub('', result)

    return result


def sanitize_user_input(query: str) -> Optional[str]:
    """检测并拦截 Prompt 注入 + XSS 攻击，返回 None 表示拦截

    v1.44 R2: 增加 XSS 防御层
    v1.44 R3: 集中化注入检测 — 使用 prompt_guard 模块
    """
    # 1. Prompt 注入检测 — 优先使用集中的 prompt_guard 模块
    try:
        from src.services.prompt_guard import detect_injection
        is_injection, pattern_desc = detect_injection(query)
        if is_injection:
            logger.warning(f"[Security] Prompt injection detected: pattern={pattern_desc[:40]}, query_len={len(query)}")
            return None
    except ImportError:
        # 降级：使用本地模式
        for pat in INJECTION_PATTERNS:
            if re.search(pat, query, re.IGNORECASE):
                pat_name = pat[:40].replace('\n', ' ')
                logger.warning(f"[Security] Prompt injection detected: pattern={pat_name}, query_len={len(query)}")
                return None
    
    # 2. XSS 净化
    sanitized = sanitize_xss(query)
    
    return sanitized.strip()
