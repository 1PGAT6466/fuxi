"""
chunker_quality.py — Phase 1.5: 分块质量校验 + 补充3 文档版本管理
"""
import re, hashlib, logging

logger = logging.getLogger(__name__)

# ============ 1.5.1 分块质量校验 ============

def quality_check(text: str, min_chars: int = 50, max_junk_ratio: float = 0.5) -> bool:
    """检查单个 chunk 的质量
    
    Returns:
        True = 合格，False = 垃圾
    """
    text = text.strip()
    if len(text) < min_chars:
        return False
    
    # 乱码检测：中文字符 + 字母数字比例
    clean = re.findall(r'[\u4e00-\u9fff\u4e00-\u9fff\w\s]', text)
    ratio = len(clean) / max(len(text), 1)
    if ratio < max_junk_ratio:
        return False
    
    return True


# ============ 1.5.2 文档去重 + 补充3 版本管理 ============

def compute_content_hash(content: str) -> str:
    """计算文档内容哈希"""
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


def check_duplicate(content_hash: str, file_name: str) -> dict:
    """检查文档是否重复入库
    
    补充3：同名文件更新时，先删除旧 chunks 再入库新 chunks
    
    Returns:
        {'action': 'insert'|'update'|'skip', 'reason': '...'}
    """
    from src.db.memory_store import get_store
    store = get_store()
    
    # 检查同名文件是否存在
    existing = store.get_by_file_name(file_name) if hasattr(store, 'get_by_file_name') else []
    
    if existing:
        # 同名文件存在 → 更新（删除旧 + 入库新）
        logger.info(f"[Ingest] Updating existing file: {file_name}")
        try:
            store.invalidate_by_name(file_name)
        except Exception as e:  # TODO: Narrow exception type
            logger.warning(f"[Ingest] Failed to invalidate old chunks: {e}")
        return {'action': 'update', 'reason': f'同名文件更新，已清理 {len(existing)} 个旧 chunks'}
    
    # 检查内容哈希是否已存在
    
    return {'action': 'insert', 'reason': '新文档'}


# ============ 1.5.5 语义清洗 ============

# 版权声明/免责声明正则
NOISE_PATTERNS = [
    r'版权归.*所有',
    r'Copyright\s+©?\s*\d{4}',
    r'All\s+Rights?\s+Reserved',
    r'未经许可.*不得.*(?:复制|转载|传播)',
    r'免责声明.*',
    r'以上内容仅供参考',
    r'本文件.*最终解释权',
    r'如.*侵权.*请联系',
    r'声明：.*不承担.*责任',
    r'温馨提示：.*投资有风险',
]

def clean_text(text: str) -> str:
    """语义清洗：去版权声明、重复段落、格式标准化"""
    
    # 1. 去除版权/声明行
    for pattern in NOISE_PATTERNS:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)
    
    # 2. 去除重复段落
    paragraphs = text.split('\n\n')
    seen = set()
    cleaned = []
    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        # 取前 100 字做去重
        key = p[:100]
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(p)
    text = '\n\n'.join(cleaned)
    
    # 3. 格式标准化
    # 全角字母数字 → 半角
    text = re.sub(r'[Ａ-Ｚ]', lambda m: chr(ord(m.group()) - 0xFEE0), text)
    text = re.sub(r'[ａ-ｚ]', lambda m: chr(ord(m.group()) - 0xFEE0), text)
    text = re.sub(r'[０-９]', lambda m: chr(ord(m.group()) - 0xFEE0), text)
    
    # 多余空白合并
    text = re.sub(r' +', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text.strip()


# ============ 1.5.11 敏感信息检测 ============

SENSITIVE_PATTERNS = [
    (r'1[3-9]\d{9}', '手机号'),
    (r'\d{17}[\dXx]', '身份证号'),
    (r'\d{16,19}', '银行卡号'),
]

def detect_and_mask_sensitive(text: str) -> tuple:
    """检测并脱敏"""
    issues = []
    for pattern, label in SENSITIVE_PATTERNS:
        matches = re.findall(pattern, text)
        if matches:
            issues.append(f'发现 {len(matches)} 个{label}')
            for m in matches:
                text = text.replace(m, m[:3] + '*' * (len(m) - 6) + m[-3:])
    return text, issues
