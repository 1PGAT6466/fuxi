"""
runner.py — 评测运行器（P0-E1）
计算 Recall@5、Precision@1、MRR
"""
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

logger = logging.getLogger("eval.runner")

# 评测结果输出目录
_RESULTS_DIR = Path(__file__).parent / "results"


def load_ground_truth() -> List[Dict[str, Any]]:
    """加载 ground_truth.json 评测数据集"""
    gt_path = Path(__file__).parent / "ground_truth.json"
    if not gt_path.exists():
        logger.warning(f"ground_truth.json 不存在: {gt_path}")
        return []
    with open(gt_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("test_cases", [])


def _normalize(text: str) -> str:
    """文本归一化：去空格、小写"""
    if not text:
        return ""
    return " ".join(text.lower().split())


# DEPRECATED: 未使用，v1.50 标记待删除
def _jaccard_similarity(a: set, b: set) -> float:
    """Jaccard 相似度"""
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def compute_recall_at_k(
    retrieved_chunks: List[Dict],
    relevant_keywords: List[str],
    k: int = 5,
) -> float:
    """
    Recall@K：检索返回的 top-K 结果中，包含多少个相关关键词。

    Args:
        retrieved_chunks: 检索结果列表（含 'text' 字段）
        relevant_keywords: ground_truth 中的相关关键词
        k: 取前 K 个结果

    Returns:
        float: Recall@K 值 [0, 1]
    """
    if not retrieved_chunks or not relevant_keywords:
        return 0.0

    top_k = retrieved_chunks[:k]
    kw_lower = set(kw.lower() for kw in relevant_keywords)

    total_hits = 0
    for chunk in top_k:
        text = _normalize(chunk.get("text", ""))
        for kw in kw_lower:
            if kw in text:
                total_hits += 1

    return min(total_hits / max(len(kw_lower), 1), 1.0)


def compute_precision_at_1(
    retrieved_chunks: List[Dict],
    relevant_keywords: List[str],
) -> float:
    """
    Precision@1：第一个结果是否包含相关关键词。

    Returns:
        float: 1.0 如果第一个结果相关，否则 0.0
    """
    if not retrieved_chunks or not relevant_keywords:
        return 0.0

    first = retrieved_chunks[0]
    text = _normalize(first.get("text", ""))
    kw_lower = set(kw.lower() for kw in relevant_keywords)

    hits = sum(1 for kw in kw_lower if kw in text)
    # 至少命中一半关键词视为相关
    threshold = max(1, len(kw_lower) // 2)
    return 1.0 if hits >= threshold else 0.0


def compute_mrr(
    retrieved_chunks: List[Dict],
    relevant_chunk_ids: List[str],
) -> float:
    """
    MRR (Mean Reciprocal Rank):
    第一个相关结果的排名倒数。

    Args:
        retrieved_chunks: 检索结果列表（含 'chunk_id' 或 'file_hash'）
        relevant_chunk_ids: ground_truth 中的相关 chunk ID 列表

    Returns:
        float: MRR 值 [0, 1]
    """
    if not retrieved_chunks or not relevant_chunk_ids:
        return 0.0

    relevant_ids = set(relevant_chunk_ids)
    for rank, chunk in enumerate(retrieved_chunks, start=1):
        cid = chunk.get("chunk_id") or chunk.get("file_hash", "")
        if cid in relevant_ids:
            return 1.0 / rank

    return 0.0
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行


async def run_evaluation(
    retriever_fn=None,
) -> Dict[str, Any]:
    """
    运行完整评测流程。

    Args:
        retriever_fn: 可选的检索函数 async def fn(query: str) -> List[Dict]
                      如果不提供，则使用默认的 hybrid_search。

    Returns:
        Dict: 评测报告，包含 Recall@5、Precision@1、MRR 及各测试用例详情
    """
    test_cases = load_ground_truth()
    if not test_cases:
        return {"error": "没有测试用例", "test_cases_count": 0}

    # 默认检索函数
    if retriever_fn is None:
        try:
            from src.taiyang.retrieval import hybrid_search
            retriever_fn = hybrid_search
        except ImportError:
            return {"error": "检索模块不可用", "test_cases_count": len(test_cases)}

    results = []
    recall_scores = []
    precision_scores = []
    mrr_scores = []

    for tc in test_cases:
        try:
            retrieved = await retriever_fn(tc["query"], top_k=10)
        except Exception as e:
            logger.warning(f"[Eval] 检索失败: tc={tc['id']} error={e}")
            retrieved = []

        recall = compute_recall_at_k(
            retrieved, tc.get("relevant_keywords", []), k=5
        )
        precision = compute_precision_at_1(
            retrieved, tc.get("relevant_keywords", [])
        )
        mrr = compute_mrr(
            retrieved, tc.get("relevant_chunk_ids", [])
        )

        recall_scores.append(recall)
        precision_scores.append(precision)
        mrr_scores.append(mrr)

        results.append({
            "id": tc["id"],
            "query": tc["query"],
            "recall_at_5": round(recall, 4),
            "precision_at_1": round(precision, 4),
            "mrr": round(mrr, 4),
            "result_count": len(retrieved),
            "top_3_scores": [
                r.get("score", 0) for r in retrieved[:3]
            ],
        })

        logger.info(
            f"[Eval] {tc['id']}: R@5={recall:.3f} P@1={precision:.3f} "
            f"MRR={mrr:.3f} n_results={len(retrieved)}"
        )

    n = len(test_cases)
    report = {
        "timestamp": datetime.now().isoformat(),
        "test_cases_count": n,
        "metrics": {
            "recall_at_5": round(sum(recall_scores) / n, 4) if n > 0 else 0,
            "precision_at_1": round(sum(precision_scores) / n, 4) if n > 0 else 0,
            "mrr": round(sum(mrr_scores) / n, 4) if n > 0 else 0,
        },
        "details": results,
    }

    # 写入结果文件
    _RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    result_path = _RESULTS_DIR / f"{date_str}.json"

    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    logger.info(f"[Eval] 评测完成，报告已写入: {result_path}")
    return report
