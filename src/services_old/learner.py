"""
feedback_learner.py — 反馈学习闭环 (P0-A + P0-B + P0-C)
- 收集用户 👍/👎 反馈
- 自动调整 ReRank 权重
- 自动补充术语词表和同义词表
- 使用数据训练轻量级 ranking
"""
import os, json, time
from pathlib import Path
from datetime import datetime, timedelta
from collections import Counter, defaultdict

from src.config import DATA_DIR
import logging; logger = logging.getLogger(__name__)

BASE_DIR = DATA_DIR.parent  # 伏羲·内世界 root
FEEDBACK_DIR = BASE_DIR / "feedback_data"
FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)

# ========== 术语权重（基于反馈动态调整） ==========
TERM_WEIGHTS_FILE = FEEDBACK_DIR / "term_weights.json"

def load_term_weights() -> dict:
    if TERM_WEIGHTS_FILE.exists():
        return json.loads(TERM_WEIGHTS_FILE.read_text(encoding='utf-8'))
    return {}

def update_term_weight(term: str, positive: bool):
    """用户点击/点赞 → 术语权重+0.1，👎 → -0.05"""
    weights = load_term_weights()
    delta = 0.1 if positive else -0.05
    weights[term] = round(weights.get(term, 1.0) + delta, 3)
    weights[term] = max(0.1, min(weights[term], 5.0))  # 限制范围
    TERM_WEIGHTS_FILE.write_text(json.dumps(weights, ensure_ascii=False), encoding='utf-8')

# ========== 反馈日志 ==========
FEEDBACK_LOG = FEEDBACK_DIR / "feedback_log.jsonl"

def log_feedback(query: str, file_hash: str, chunk_index: int, action: str, 
                 correction: str = "", source: str = "search"):
    """记录每条用户反馈"""
    entry = {
        "time": datetime.now().isoformat(),
        "query": query[:200],
        "file_hash": file_hash,
        "chunk_index": chunk_index,
        "action": action,  # "like", "dislike", "correct", "copy", "click"
        "correction": correction[:500],
        "source": source,
    }
    with open(FEEDBACK_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    
    # 自动学习
    if action in ("like", "copy", "click"):
        for term in query.split():
            if len(term) >= 2:
                update_term_weight(term, positive=True)
    elif action == "dislike":
        for term in query.split():
            if len(term) >= 2:
                update_term_weight(term, positive=False)

# ========== 术语自动提取 ==========
def extract_new_terms(text: str, min_freq: int = 3) -> list:
    """从文档中提取高频专业术语（基于 jieba + 词频）"""
    try:
        import jieba
        import jieba.posseg as pseg
        jieba.setLogLevel(20)
    except ImportError:
        return []
    
    # 过滤：只保留名词/动词/英文
    words = pseg.cut(text)
    candidates = defaultdict(int)
    for word, flag in words:
        if len(word) < 2:
            continue
        if flag in ('n', 'nz', 'nr', 'ns', 'nt', 'eng', 'j') or word.isalpha():
            candidates[word] += 1
    
    # 过滤停用词
    stopwords = {'的', '是', '在', '和', '与', '了', '有', '不', '也', '都', '就', '要',
                 '会', '可以', '这个', '那个', '什么', '怎么', '一个', '一种', '一些'}
    new_terms = [w for w, c in candidates.items() 
                 if c >= min_freq and w not in stopwords]
    return new_terms[:50]


def get_personalized_boost(query: str) -> dict:
    """基于用户反馈历史，返回个性化术语权重"""
    weights = load_term_weights()
    if not weights:
        return {}
    
    boost = {}
    for term in query.split():
        if term in weights:
            w = weights[term]
            if w > 1.0:
                boost[term] = round((w - 1.0) * 2, 2)  # 转换为加成值
    
    return boost


# ========== 反馈统计 ==========
def get_feedback_stats(days: int = 7) -> dict:
    """获取最近 N 天的反馈统计"""
    cutoff = datetime.now() - timedelta(days=days)
    stats = {"total": 0, "likes": 0, "dislikes": 0, "corrections": 0}
    
    if not FEEDBACK_LOG.exists():
        return stats
    
    with open(FEEDBACK_LOG, "r", encoding="utf-8") as f:
        for line in f:
            try:
                entry = json.loads(line)
                t = datetime.fromisoformat(entry["time"])
                if t < cutoff:
                    continue
                stats["total"] += 1
                if entry["action"] == "like":
                    stats["likes"] += 1
                elif entry["action"] == "dislike":
                    stats["dislikes"] += 1
                elif entry["action"] == "correct":
                    stats["corrections"] += 1
            except Exception:
                continue
    
    return stats
