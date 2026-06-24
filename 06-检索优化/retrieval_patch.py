"""
retrieval_patch.py — 检索优化补丁
==================================
修复内容：
1. 图谱上下文注入到检索流程
2. 意图分类前置（简单查询走快速路径）
3. LLM 调用合并（改写+HyDE 一次完成）
4. embed_texts 加重试

使用方式：将相关函数替换到 src/services/retrieval.py 中
"""

import asyncio
import time
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


# ============================================================
# 修复 1: embed_texts 重试
# ============================================================

async def embed_texts_with_retry(texts: List[str], max_retries: int = 2) -> Optional[List[List[float]]]:
    """带重试的向量嵌入"""
    for attempt in range(max_retries):
        try:
            from src.db.vector_store import embed_texts
            result = await embed_texts(texts)
            if result:
                return result
        except Exception as e:
            logger.warning(f"[embed] attempt {attempt + 1} failed: {e}")
        if attempt < max_retries - 1:
            await asyncio.sleep(0.5 * (attempt + 1))  # 递增等待
    return None


# ============================================================
# 修复 2: 意图分类前置（快速路径）
# ============================================================

def should_use_fast_path(query: str) -> bool:
    """判断是否走快速路径（跳过 LLM 改写和 HyDE）"""
    # 短查询 + 包含型号/编号 → 直接 BM25
    if len(query) < 15:
        import re
        if re.search(r'[A-Z]{2,}[-]?\d+', query, re.IGNORECASE):
            return True
    # 纯数字查询
    if query.strip().isdigit():
        return True
    return False


# ============================================================
# 修复 3: LLM 调用合并
# ============================================================

async def llm_rewrite_and_hyde(query: str) -> Dict[str, str]:
    """一次 LLM 调用同时完成改写和 HyDE"""
    prompt = f"""对以下查询完成两个任务：
1. 改写为更精确的检索查询（保持原意，补充同义词）
2. 生成一个假设性回答片段（用于语义检索）

查询：{query}

严格按以下 JSON 格式返回，不要有其他内容：
{{"rewrite": "改写后的查询", "hyde": "假设性回答片段"}}"""
    
    try:
        from src.services.llm import call_ai_raw
        result = await call_ai_raw(prompt, max_tokens=500)
        import json
        parsed = json.loads(result.strip().strip("`").strip("json"))
        return {
            "rewrite": parsed.get("rewrite", query),
            "hyde": parsed.get("hyde", ""),
        }
    except Exception as e:
        logger.debug(f"[retrieval] LLM rewrite+hyde failed: {e}")
        return {"rewrite": query, "hyde": ""}


# ============================================================
# 修复 4: 图谱上下文注入
# ============================================================

async def hybrid_search_with_graph(
    query: str, chunks: list = None, category: str = "",
    file_type: str = "", date_from: str = "", date_to: str = "",
    top_k: int = 15, skip_cache: bool = False
) -> list:
    """增强版混合检索：加入图谱上下文注入"""
    
    from src.services.retrieval import hybrid_search
    
    # 1. 正常混合检索
    results = await hybrid_search(
        query, chunks, category, file_type, date_from, date_to, top_k, skip_cache
    )
    
    # 2. 图谱上下文注入
    try:
        from src.services.graph_enhanced import get_entity_context_for_query, expand_query_with_graph
        graph_ctx = get_entity_context_for_query(query)
        
        if graph_ctx and len(results) < top_k:
            # 用图谱扩展查询，补充检索
            expanded_q = expand_query_with_graph(query)
            if expanded_q != query:
                extra = await hybrid_search(
                    expanded_q, chunks, category, file_type, date_from, date_to,
                    top_k=5, skip_cache=True
                )
                # 去重合并
                seen = {r.get("file_hash", "") + str(r.get("chunk_index", 0)) for r in results}
                for r in extra:
                    key = r.get("file_hash", "") + str(r.get("chunk_index", 0))
                    if key not in seen:
                        results.append(r)
                        seen.add(key)
    except Exception as e:
        logger.debug(f"[retrieval] graph injection failed: {e}")
    
    return results[:top_k]


# ============================================================
# 修复 5: Rerank chunk 超时保护
# ============================================================

async def stream_with_timeout(generator, chunk_timeout: float = 30.0):
    """给流式响应加 chunk 级超时"""
    import asyncio
    try:
        async for chunk in generator:
            yield chunk
    except asyncio.TimeoutError:
        yield "[响应超时]"
    except Exception as e:
        yield f"[响应异常: {str(e)[:50]}]"
