"""
services/query_resolver.py — 指代消解 + 上下文压缩
Phase 1: 多轮对话核心模块
"""
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

# 指代消解 prompt
RESOLVE_PROMPT = """你是一个查询改写助手。根据对话历史，将用户的最新问题改写成一个独立、完整的搜索查询。

规则：
1. 替换所有代词（"它"、"这个"、"那个"、"他们"）为具体指代对象
2. 补充缺失的上下文（如"多少钱"→"PLC型号X的价格是多少"）
3. 保持原意不变，不要添加额外信息
4. 如果查询已经是独立的（无需改写），直接返回原查询
5. 只输出改写后的查询，不要解释

对话历史：
{history}

用户最新问题：{query}

改写后的独立查询："""

# 上下文压缩 prompt
COMPRESS_PROMPT = """将以下对话历史压缩成简短摘要（保留关键信息，不超过200字）：

{history}

摘要："""

async def resolve_query(query: str, history: List[dict], llm_fn=None) -> str:
    """指代消解：将多轮对话中的指代性查询改写为独立查询"""
    if not history or len(history) == 0:
        return query

    # 快速检查：如果查询没有指代词，直接返回
    pronouns = ['它', '这个', '那个', '他们', '她们', '这些', '那些',
                '上述', '前面', '刚才', '之前', '上面', '其', '此',
                'that', 'this', 'it', 'they', 'them', 'these', 'those']
    has_pronoun = any(p in query for p in pronouns)
    
    # 也检查是否是短追问（< 15字且没有主语）
    is_short_followup = len(query) < 15 and not any(kw in query for kw in ['什么是', '如何', '怎么', '为什么', '哪些', '请问'])
    
    if not has_pronoun and not is_short_followup:
        return query

    if llm_fn is None:
        try:
            from src.services.llm import call_llm
            llm_fn = call_llm
        except ImportError:
            return query

    # 构建历史摘要（最近 5 轮）
    recent = history[-10:]  # 最近 10 条消息（5 轮对话）
    history_text = ""
    for msg in recent:
        role = "用户" if msg.get("role") == "user" else "AI"
        content = msg.get("content", "")[:200]
        history_text += f"{role}: {content}\n"

    prompt = RESOLVE_PROMPT.format(history=history_text, query=query)

    try:
        resolved = await llm_fn(
            [{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.1,
        )
        resolved = resolved.strip().strip('"').strip("'")
        
        if resolved and resolved != query:
            logger.info(f"[QueryResolver] '{query[:30]}' → '{resolved[:50]}'")
        return resolved if resolved else query
    except Exception as e:
        logger.warning(f"[QueryResolver] failed: {e}")
        return query


async def compress_history(history: List[dict], llm_fn=None, max_turns: int = 5) -> List[dict]:
    """上下文压缩：将早期对话压缩成摘要，保留最近 max_turns 轮"""
    if not history or len(history) <= max_turns * 2:
        return history

    if llm_fn is None:
        try:
            from src.services.llm import call_llm
            llm_fn = call_llm
        except ImportError:
            return history[-(max_turns * 2):]

    # 分离早期对话和近期对话
    recent = history[-(max_turns * 2):]
    early = history[:-(max_turns * 2)]

    # 压缩早期对话
    early_text = ""
    for msg in early:
        role = "用户" if msg.get("role") == "user" else "AI"
        content = msg.get("content", "")[:300]
        early_text += f"{role}: {content}\n"

    try:
        summary = await llm_fn(
            [{"role": "user", "content": COMPRESS_PROMPT.format(history=early_text)}],
            max_tokens=200,
            temperature=0.3,
        )
        summary = summary.strip()
        if summary:
            # 将摘要作为系统消息放在最前面
            compressed = [{"role": "system", "content": f"之前的对话摘要：{summary}"}]
            compressed.extend(recent)
            logger.info(f"[HistoryCompress] {len(history)} msgs → {len(compressed)} msgs")
            return compressed
    except Exception as e:
        logger.warning(f"[HistoryCompress] failed: {e}")

    return recent
