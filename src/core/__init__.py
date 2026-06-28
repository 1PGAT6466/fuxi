"""
lib/utils.py — 世界树统一工具库
集中所有跨模块复用的通用函数，禁止在各 service 中重复定义。
"""
import os, re, json, hashlib, logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("worldtree.utils")

# ========== API Key ==========
def get_deepseek_key() -> str:
    """统一获取 DeepSeek API Key"""
    return os.environ.get("DEEPSEEK_API_KEY", "")

def get_siliconflow_key() -> str:
    """获取 SiliconFlow Key (仅为向后兼容，请使用 get_deepseek_key)"""
    return os.environ.get("SILICONFLOW_API_KEY", "")

# ========== ID 生成 ==========
def make_id(prefix: str, seed: str) -> str:
    """生成统一 ID: {prefix}_{md5[:10]}"""
    return f"{prefix}_{hashlib.md5(seed.encode()).hexdigest()[:10]}"

# ========== 时间 ==========
def now_iso() -> str:
    """当前时间 YYYY-MM-DD HH:MM:SS"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def now_ts() -> str:
    """当前时间戳用于文件名"""
    return datetime.now().strftime("%Y%m%d_%H%M%S")

# ========== JSON 解析 ==========
def parse_json(raw: str) -> dict | list | None:
    """鲁棒 JSON 解析，自动去除 Markdown 代码块"""
    if not raw:
        return None
    raw = re.sub(r"```(?:json)?\s*|```", "", raw).strip()
    raw = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", " ", raw)
    for _ in range(5):
        try:
            return json.loads(raw, strict=False)
        except json.JSONDecodeError:
            pass
        # 尝试提取 [...] 或 {...}
        for bracket, end_b in [('[', ']'), ('{', '}')]:
            s = raw.find(bracket)
            if s >= 0:
                e = raw.rfind(end_b) + 1
                if e > s:
                    raw = raw[s:e]
                    break
    return None

# ========== 文本清洗 ==========
def clean_text(text: str) -> str:
    """去除控制字符"""
    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', ' ', text).strip()

# ========== 数据库连接 ==========
def get_db(path: str):
    """获取 sqlite3 连接 (调用方负责 close)"""
    import sqlite3
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn

# ========== 结果包装 ==========
def ok(data=None, **kwargs) -> dict:
    """统一成功响应"""
    resp = {"ok": True}
    if data is not None:
        resp["data"] = data
    resp.update(kwargs)
    return resp

def fail(msg: str, detail: str = "") -> dict:
    """统一失败响应"""
    return {"ok": False, "error": msg, "detail": detail}

# ========== 文本截断 ==========
def truncate(text: str, max_chars: int = 300, ellipsis: str = "…") -> str:
    return text[:max_chars] + (ellipsis if len(text) > max_chars else "")

# ========== 安全文件名 ==========
def safe_filename(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', '_', name).strip()[:200]

if __name__ == "__main__":
    print(f"世界树工具库已加载")
    print(f"  DeepSeek Key: {'已配置' if get_deepseek_key() else '未配置'}")
    print(f"  ID示例: {make_id('wiki', '测试标题')}")
    print(f"  JSON解析: {parse_json(chr(123)+chr(34)+chr(97)+chr(34)+chr(58)+chr(49)+chr(125))}")
