"""
semantic_chunker.py — Phase 4.2: 语义边界切分
基于话题转换检测的自适应切分（替代固定窗口）
"""
import re, logging
from typing import List

logger = logging.getLogger(__name__)

# 中英文句子切分正则
SENT_SPLITTER = re.compile(r'[。！？!?\n]')


def split_sentences(text: str) -> List[str]:
    """句子切分"""
    parts = SENT_SPLITTER.split(text)
    return [s.strip() + '。' for s in parts if s.strip()]


def _keyword_overlap(s1: str, s2: str) -> float:
    """计算两个文本段的关键词重叠率"""
    words1 = set(re.findall(r'[\u4e00-\u9fff]{2,}|\w{3,}', s1.lower()))
    words2 = set(re.findall(r'[\u4e00-\u9fff]{2,}|\w{3,}', s2.lower()))
    if not words1 or not words2:
        return 0.0
    overlap = len(words1 & words2)
    return overlap / max(len(words1), len(words2))


def is_topic_shift(text_a: str, text_b: str, threshold: float = 0.15) -> bool:
    """判断两个文本段是否发生了话题转换"""
    return _keyword_overlap(text_a, text_b) < threshold


def split_by_semantic_boundary(
    text: str,
    max_chars: int = 800,
    min_chars: int = 100,
    overlap_threshold: float = 0.15
) -> List[str]:
    """
    基于话题转换检测的自适应切分
    
    Args:
        text: 原始文本
        max_chars: 最大 chunk 字符数
        min_chars: 最小 chunk 字符数
        overlap_threshold: 话题转换阈值（越低越敏感）
    
    Returns:
        chunk 文本列表
    """
    sentences = split_sentences(text)
    if not sentences:
        return [text]
    
    chunks = []
    current_chunk = []
    current_len = 0
    
    for sent in sentences:
        sent_len = len(sent)
        
        # 如果当前 chunk 加上这句会超 max_chars
        if current_len + sent_len > max_chars and current_len >= min_chars:
            # 检查是否话题转换
            last_text = ' '.join(current_chunk[-2:]) if len(current_chunk) >= 2 else current_chunk[-1] if current_chunk else ''
            if last_text and is_topic_shift(last_text, sent, overlap_threshold):
                # 话题转换 → 结束当前 chunk
                chunks.append(''.join(current_chunk))
                current_chunk = [sent]
                current_len = sent_len
            else:
                # 未转换 → 继续累积
                current_chunk.append(sent)
                current_len += sent_len
        else:
            current_chunk.append(sent)
            current_len += sent_len
    
    # 最后一个 chunk
    if current_chunk:
        chunks.append(''.join(current_chunk))
    
    # 合并过短的 chunk
    merged = []
    for chunk in chunks:
        if merged and len(chunk) < min_chars:
            merged[-1] += chunk
        else:
            merged.append(chunk)
    
    return merged if merged else [text]


def chunk_text(text: str, max_chars: int = 800) -> List[str]:
    """统一分块入口"""
    try:
        return split_by_semantic_boundary(text, max_chars)
    except Exception as e:
        logger.warning(f"[Chunker] Semantic chunking failed: {e}, using fixed-size fallback")
        # 固定大小 fallback
        return [text[i:i+max_chars] for i in range(0, len(text), max_chars - 50)]
