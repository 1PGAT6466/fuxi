"""
services/rerank.py — Rerank 精排服务（v11.0 DeepSeek + 本地降级）
优先级: DeepSeek 相关性打分 > embedder_server > 本地 TF-IDF
"""
import os, re, json, aiohttp, logging

logger = logging.getLogger(__name__)

# ============ DeepSeek Rerank ============
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
RERANK_VIA_PROXY = os.getenv("KB_RERANK_PROXY", "http://127.0.0.1:8091")
from src.config import EMBEDDER_URL, DEEPSEEK_BASE_URL as _DEEPSEEK_BASE_URL, SILICONFLOW_BASE_URL as _SF_BASE_URL


async def rerank_with_deepseek(query: str, candidates: list, top_k: int = 30) -> list:
    """使用 DeepSeek Chat 做相关性打分（批处理，5个一组）"""
    if not candidates or not DEEPSEEK_API_KEY:
        return []

    try:
        documents = [(r.get("text", "") or "")[:800] for r in candidates]
        if not any(d.strip() for d in documents):
            return []

        # 构建打分 prompt（批量处理所有候选，一次请求）
        doc_list = "\n".join([f"[{i}] {d[:400]}" for i, d in enumerate(documents[:30])])
        prompt = (
            f"对以下文档片段与查询的相关性打分（0-10分，10=完全相关）：\n"
            f"查询：{query[:200]}\n\n"
            f"文档：\n{doc_list}\n\n"
            f"返回 JSON 数组：{{\"scores\": [分数1, 分数2, ...]}}，只输出 JSON。"
        )

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{_DEEPSEEK_BASE_URL}/v1/chat/completions",
                json={
                    "model": "deepseek-chat",
                    "messages": [
                        {"role": "system", "content": "只输出纯 JSON。你是相关性打分引擎。"},
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 500,
                    "temperature": 0,
                },
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                },
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    raw = data["choices"][0]["message"]["content"]
                    raw = re.sub(r"```(?:json)?\s*|```", "", raw).strip()
                    scores_data = json.loads(raw)
                    scores = scores_data.get("scores", [])

                    scored = []
                    for i, r in enumerate(candidates[:len(scores)]):
                        r["_rerank_score"] = round(float(scores[i]) if i < len(scores) else 0, 4)
                        scored.append((scores[i] if i < len(scores) else 0, r))
                    scored.sort(key=lambda x: x[0], reverse=True)
                    return [r for _, r in scored[:top_k]]
    except Exception as e:  # TODO: Narrow exception type
        logger.debug(f"DeepSeek rerank failed: {e}")

    return []


async def rerank_with_embedder(query: str, candidates: list, top_k: int = 30) -> list:
    """embedder_server /rerank 端点做 Bi-Encoder 精排"""
    if not candidates:
        return []

    try:
        documents = [(r.get("text", "") or "")[:2000] for r in candidates]
        if not any(d.strip() for d in documents):
            return []

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{EMBEDDER_URL}/rerank",
                json={"query": query, "documents": documents, "top_k": min(top_k, len(documents))},
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    indices = data.get("indices", [])
                    scores = data.get("scores", [])
                    scored = []
                    for rank, idx in enumerate(indices):
                        if idx < len(candidates):
                            r = dict(candidates[idx])
                            r["_rerank_score"] = round(float(scores[rank]) if rank < len(scores) else 0, 4)
                            r["_rerank_rank"] = rank + 1
                            scored.append(r)
                    return scored[:top_k]
    except Exception:  # TODO: Narrow exception type
        logger.warning(f"[rerank] suppressed exception", exc_info=True)
        pass
    return []


def rerank_local(query: str, candidates: list, top_k: int = 30) -> list:
    """本地 TF-IDF 精排（兜底方案）"""
    if not candidates:
        return candidates

    tokens = []
    try:
        import jieba
        tokens = [t.strip() for t in jieba.cut_for_search(query.strip()) if len(t.strip()) >= 1]
    except ImportError:
        tokens = query.lower().split()

    if not tokens:
        return candidates[:top_k]

    scored = []
    for r in candidates:
        text = (r.get("text", "") or "").lower()
        if not text:
            scored.append((r.get("score", 0), r))
            continue

        score = 0.0
        text_len = max(len(text), 1)
        for t in tokens:
            count = text.count(t.lower())
            score += count / text_len * 1000
            if t.lower() in text:
                score += 5

        original = float(r.get("score", 0))
        r = dict(r)
        r["_rerank_score"] = round(score, 4)
        r["score"] = round(original * 0.5 + score * 0.5, 2)
        scored.append((r["score"], r))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in scored[:top_k]]




async def rerank_with_siliconflow(query: str, candidates: list, top_k: int = 30) -> list:
    """L1: SiliconFlow BGE-Reranker (专用排序模型)"""
    sf_key = os.getenv("SILICONFLOW_API_KEY", "")
    if not sf_key or not candidates:
        return []
    documents = [(r.get("text", "") or "")[:1024] for r in candidates]
    if not any(d.strip() for d in documents):
        return []
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{_SF_BASE_URL}/rerank",
                json={
                    "model": "BAAI/bge-reranker-v2-m3",
                    "query": query[:512],
                    "documents": documents,
                    "top_n": min(top_k, len(documents)),
                },
                headers={
                    "Authorization": f"Bearer {sf_key}",
                    "Content-Type": "application/json",
                },
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = []
                    for item in data.get("results", []):
                        idx = item["index"]
                        score = item["relevance_score"]
                        r = dict(candidates[idx])
                        r["_rerank_score"] = round(float(score), 4)
                        results.append(r)
                    logger.info(f"[Rerank SiliconFlow] {len(results)} results, top_score={results[0]['_rerank_score'] if results else 0}")
                    return results[:top_k]
                else:
                    err = await resp.text()
                    logger.warning(f"[Rerank SiliconFlow] {resp.status}: {err[:200]}")
    except Exception as e:  # TODO: Narrow exception type
        logger.warning(f"[Rerank SiliconFlow] failed: {e}")
    return []

async def rerank(query: str, candidates: list, top_k: int = 30) -> list:
    """统一的 Rerank 入口
    优先级: SiliconFlow > DeepSeek > embedder_server > 本地 TF-IDF
    """
    if not candidates:
        return candidates

    # L1: SiliconFlow 专用 Rerank（快、准、便宜）
    results = await rerank_with_siliconflow(query, candidates, top_k)
    if results:
        return results

    # L2: DeepSeek LLM 打分（云端兜底）
    results = await rerank_with_deepseek(query, candidates, top_k)
    if results:
        return results

    # L3: 本地 embedder_server Bi-Encoder（网络断了还能用）
    results = await rerank_with_embedder(query, candidates, top_k)
    if results:
        return results

    # L4: 本地 TF-IDF 终极兜底（零依赖，纯 CPU）
    return rerank_local(query, candidates, top_k)
