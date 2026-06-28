'''services/context_compressor.py - v1.42

RAG Context Compression: 在检索结果送入 LLM 之前，提炼冗余内容。
不暴力截断，用轻量 LLM 调用提取关键信息。
'''
import logging
logger = logging.getLogger(__name__)

COMPRESS_PROMPT = '''Extract only the key facts from the following text that are relevant to answering user questions. Keep numbers, names, and technical details. Remove redundant explanations, filler words, and repeated information.

Text:
{text}

Key facts (concise, no more than 200 words):'''


async def compress_text(text, query, call_llm_fn=None, max_output_chars=500):
    if not text or len(text) < 300:
        return text
    
    prompt = COMPRESS_PROMPT.format(text=text[:2000])
    
    try:
        if call_llm_fn:
            result = await call_llm_fn(prompt, max_tokens=200, temperature=0.0)
        else:
            from src.services.llm import call_deepseek
            result = await call_deepseek(prompt, max_tokens=200, temperature=0.0)
        
        if result and len(result) > 20:
            compressed = result.strip()[:max_output_chars]
            ratio = len(compressed) / max(len(text), 1)
            logger.debug(f"[Compress] {len(text)} -> {len(compressed)} chars ({ratio:.0%})")
            return compressed
    except Exception as e:
        logger.warning(f"[Compress] failed: {e}")
    
    return text[:max_output_chars]


async def compress_context(ctx_parts, query, call_llm_fn=None, total_budget=4000):
    if not ctx_parts:
        return ctx_parts
    
    total_len = sum(len(p) for p in ctx_parts)
    if total_len <= total_budget:
        return ctx_parts
    
    compressed = []
    remaining = total_budget
    per_part_budget = max(200, remaining // len(ctx_parts))
    
    for part in ctx_parts:
        if len(part) <= per_part_budget:
            compressed.append(part)
            remaining -= len(part)
        else:
            result = await compress_text(part, query, call_llm_fn, per_part_budget)
            compressed.append(result)
            remaining -= len(result)
    
    ratio = sum(len(p) for p in compressed) / max(total_len, 1)
    logger.info(f"[Compress] Context: {total_len} -> {sum(len(p) for p in compressed)} chars ({ratio:.0%})")
    return compressed
