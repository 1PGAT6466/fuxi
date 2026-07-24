"""
query_planner.py — 统一5层路由查询规划器（服务层 P2 增强）

为伏羲 RAG 流程提供分层查询规划能力，按复杂度自动选择路由层级：

5 层路由模型：
  L1 缓存层（Cache）  —— <10ms：精确/语义缓存命中，零延迟返回
  L2 向量层（Vector）  —— 50-200ms：向量语义召回 + BM25 关键词
  L3 图谱层（Graph）   —— 50-500ms：实体识别 + 关系图谱遍历 + 多跳查询
  L4 推理层（Reason）  —— 1-5s：多步推理 + LLM 链式分解 + Self-RAG 反思
  L5 生成层（Generate）—— 500ms-3s：LLM 生成最终答案，融合所有层结果

升级判定逻辑：
  L1→L2：缓存未命中 或 上下文变化 或 TTL 过期
  L2→L3：向量召回不足（<3条 或 最大分<0.5）
  L3→L4：问题需要推理（对比/因果/多跳/分析）
  L4→L5：推理完成，需要生成最终答案

能力：
  - 查询复杂度分析：自动判断 simple / medium / complex
  - 多策略路由选择：direct（缓存）/ cascade（逐层升级）/ parallel（并行召回）
  - 结果融合与排序：RRF融合 + 精排 + 置信度评估 + 来源标注
  - 融入现有 retrieval.py 混合检索管线
"""

from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("services.query_planner")

# ============================================================================
# 枚举 & 数据类
# ============================================================================


class RouteLevel(int, Enum):
    """5 层路由层级"""
    L1_CACHE = 1      # 缓存层
    L2_VECTOR = 2     # 向量检索层
    L3_GRAPH = 3      # 图谱检索层
    L4_REASON = 4     # 推理层
    L5_GENERATE = 5   # 生成层


class QueryComplexity(str, Enum):
    """查询复杂度"""
    SIMPLE = "simple"       # 简单：单步检索即可（如 "什么是 VLAN"）
    MEDIUM = "medium"       # 中等：需要多路召回+融合
    COMPLEX = "complex"     # 复杂：多步推理/分析


class RouteStrategy(str, Enum):
    """路由策略"""
    DIRECT = "direct"           # 单层直连（L1 缓存命中时）
    CASCADE = "cascade"         # 逐层升级（层级间接力）
    PARALLEL = "parallel"       # 并行召回（多路同时检索）
    FULL_PIPELINE = "full"      # 全管线（复杂查询走完所有层）


@dataclass
class LayerResult:
    """单层路由结果"""
    level: RouteLevel
    source: str                 # 来源: "cache" / "vector" / "graph" / "reason" / "generate"
    results: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    latency_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PlanStep:
    """查询规划步骤"""
    step_id: int
    level: RouteLevel
    query: str
    action: str                # "cache_lookup" / "vector_retrieve" / "graph_traverse" / "multi_step_reason" / "generate_answer"
    reason: str
    dependencies: List[int] = field(default_factory=list)


@dataclass
class QueryPlan:
    """完整的查询计划"""
    query: str
    complexity: QueryComplexity
    strategy: RouteStrategy
    steps: List[PlanStep]
    fusion_strategy: str = "rrf"   # "rrf" / "weighted" / "none"
    confidence_threshold: float = 0.5
    max_layers: int = 5


# ============================================================================
# 复杂度分析
# ============================================================================

_COMPLEX_PATTERNS = [
    (r"(分析|评估|综合).*(影响|效果|性能|原因|风险)", QueryComplexity.COMPLEX),
    (r"如果.*(那么|会|将|可以|能)|假设.*则|在.*条件下", QueryComplexity.COMPLEX),
    (r"为什么.*(会|这么|那么|导致)|什么原因.*导致|怎么.*优化", QueryComplexity.COMPLEX),
    (r"总结.*对比|全面.*分析|深度.*评估", QueryComplexity.COMPLEX),
    (r"(多跳|推理|归纳|演绎|因果)", QueryComplexity.COMPLEX),
]

_MEDIUM_PATTERNS = [
    (r"(.+)和(.+)的区别|(.+)与(.+)对比|(.+)vs\.?(.+)", QueryComplexity.MEDIUM),
    (r"(.+)有哪些(.+)", QueryComplexity.MEDIUM),
    (r"(怎么|如何)(配置|设置|部署|安装|实现|搭建)", QueryComplexity.MEDIUM),
    (r"(列出|列举|汇总|总结).*(参数|规格|特性|特点)", QueryComplexity.MEDIUM),
]


def analyze_query_complexity(query: str) -> Tuple[QueryComplexity, float]:
    """分析查询复杂度

    Args:
        query: 用户查询文本

    Returns:
        (complexity, confidence)
    """
    q = query.strip()

    for pattern, complexity in _COMPLEX_PATTERNS:
        if re.search(pattern, q):
            return QueryComplexity.COMPLEX, 0.85

    for pattern, complexity in _MEDIUM_PATTERNS:
        if re.search(pattern, q):
            return QueryComplexity.MEDIUM, 0.80

    if len(q) > 30:
        return QueryComplexity.MEDIUM, 0.65

    return QueryComplexity.SIMPLE, 0.90


async def llm_analyze_complexity(query: str) -> Tuple[QueryComplexity, float]:
    """通过 LLM 分析查询复杂度（复杂查询兜底）"""
    try:
        from src.services.llm import call_llm_fast

        prompt = f"""分析以下查询的复杂度，返回 JSON。

## 查询
{query}

## 复杂度定义
- simple: 单步检索即可回答（定义查询、事实查询）
- medium: 需要多路召回或对比分析
- complex: 需要多步推理、因果分析或综合评估

## 输出（仅 JSON）
{{"complexity":"simple|medium|complex","confidence":0.9,"reason":"简因≤20字"}}"""

        result = await call_llm_fast(prompt, max_tokens=100)
        if not result:
            return QueryComplexity.SIMPLE, 0.7

        result = result.strip()
        if result.startswith("```"):
            result = result.split("\n", 1)[1].rsplit("```", 1)[0]

        data = json.loads(result)
        cmap = {"simple": QueryComplexity.SIMPLE, "medium": QueryComplexity.MEDIUM, "complex": QueryComplexity.COMPLEX}
        return cmap.get(data.get("complexity", "simple"), QueryComplexity.SIMPLE), float(data.get("confidence", 0.8))

    except Exception as e:
        logger.debug(f"[QueryPlanner] LLM 复杂度分析失败: {e}")
        return QueryComplexity.SIMPLE, 0.7


# ============================================================================
# 图谱增强辅助函数
# ============================================================================


def _augment_with_graph(
    results: List[Dict[str, Any]],
    categories: List[str],
    relations: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """将图谱分类和关系信息注入检索结果"""
    augmented = list(results)
    for cat in categories[:3]:
        augmented.append({
            "file_hash": f"graph:category:{cat}",
            "text": f"[图谱分类] 相关领域: {cat}",
            "file_name": "[知识图谱]",
            "category": cat,
            "chunk_index": 0,
            "score": 8.0,
            "_source": "graph_category",
        })
    for rel in relations[:5]:
        subj = rel.get("subject", "")
        obj = rel.get("object", "")
        rel_type = rel.get("relation", "关联")
        augmented.append({
            "file_hash": f"graph:rel:{subj}:{obj}",
            "text": f"[图谱关系] {subj} --{rel_type}--> {obj}",
            "file_name": "[知识图谱]",
            "category": "",
            "chunk_index": 0,
            "score": 7.0,
            "_source": "graph_relation",
            "_relation": rel,
        })
    return augmented


# ============================================================================
# QueryPlanner 核心类
# ============================================================================


class QueryPlanner:
    """统一5层路由查询规划器

    使用方式:
        planner = QueryPlanner()
        plan = await planner.plan(query)
        result = await planner.execute(plan)

    路由策略：
      - SIMPLE → direct (L1缓存 → L2向量)
      - MEDIUM → cascade (L2 → L3 → L5)
      - COMPLEX → full_pipeline (L1 → L2 → L3 → L4 → L5)
    """

    def __init__(self, cache_ttl: float = 300.0, enable_llm_analysis: bool = False):
        """
        Args:
            cache_ttl: 缓存生存时间（秒），默认 5 分钟
            enable_llm_analysis: 是否启用 LLM 复杂度分析
        """
        self.cache_ttl = cache_ttl
        self.enable_llm_analysis = enable_llm_analysis
        self._result_cache: Dict[str, Tuple[float, LayerResult]] = {}
        self._stats = {
            "total_queries": 0,
            "layer_hits": {level.name: 0 for level in RouteLevel},
            "cache_hits": 0,
            "cache_misses": 0,
            "avg_latency_ms": 0.0,
            "total_latency_ms": 0.0,
        }

    # ------------------------------------------------------------------
    # 查询规划
    # ------------------------------------------------------------------

    async def plan(
        self,
        query: str,
        force_complexity: Optional[QueryComplexity] = None,
    ) -> QueryPlan:
        """根据查询内容生成执行计划

        Args:
            query: 用户查询文本
            force_complexity: 手动指定复杂度

        Returns:
            完整的 QueryPlan 对象
        """
        query = query.strip()

        # Step 1: 分析复杂度
        if force_complexity:
            complexity = force_complexity
        else:
            complexity, _conf = analyze_query_complexity(query)
            if complexity == QueryComplexity.COMPLEX and self.enable_llm_analysis:
                llm_c, llm_conf = await llm_analyze_complexity(query)
                if llm_conf > 0.8:
                    complexity = llm_c

        # Step 2: 选择策略
        strategy = self._select_strategy(complexity)

        # Step 3: 生成步骤
        steps = self._build_steps(query, complexity, strategy)

        # Step 4: 确定融合策略
        fusion = self._select_fusion(complexity)

        logger.info(
            f"[QueryPlanner] 规划: complexity={complexity.value} "
            f"strategy={strategy.value} steps={len(steps)} fusion={fusion}"
        )

        return QueryPlan(
            query=query,
            complexity=complexity,
            strategy=strategy,
            steps=steps,
            fusion_strategy=fusion,
        )

    def _select_strategy(self, complexity: QueryComplexity) -> RouteStrategy:
        return {
            QueryComplexity.SIMPLE: RouteStrategy.DIRECT,
            QueryComplexity.MEDIUM: RouteStrategy.CASCADE,
            QueryComplexity.COMPLEX: RouteStrategy.FULL_PIPELINE,
        }.get(complexity, RouteStrategy.CASCADE)

    def _build_steps(
        self, query: str, complexity: QueryComplexity, strategy: RouteStrategy
    ) -> List[PlanStep]:
        if strategy == RouteStrategy.DIRECT:
            return [
                PlanStep(1, RouteLevel.L1_CACHE, query, "cache_lookup", "缓存检查"),
                PlanStep(2, RouteLevel.L2_VECTOR, query, "vector_retrieve", "向量+BM25 双路召回"),
            ]
        elif strategy == RouteStrategy.CASCADE:
            return [
                PlanStep(1, RouteLevel.L1_CACHE, query, "cache_lookup", "缓存检查"),
                PlanStep(2, RouteLevel.L2_VECTOR, query, "vector_retrieve", "向量+BM25 召回", [1]),
                PlanStep(3, RouteLevel.L3_GRAPH, query, "graph_traverse", "图谱关系查询", [2]),
                PlanStep(4, RouteLevel.L5_GENERATE, query, "generate_answer", "LLM 生成答案", [2, 3]),
            ]
        elif strategy == RouteStrategy.FULL_PIPELINE:
            return [
                PlanStep(1, RouteLevel.L1_CACHE, query, "cache_lookup", "缓存检查"),
                PlanStep(2, RouteLevel.L2_VECTOR, query, "vector_retrieve", "向量+BM25 多路召回", [1]),
                PlanStep(3, RouteLevel.L3_GRAPH, query, "graph_traverse", "实体识别+图谱遍历", [2]),
                PlanStep(4, RouteLevel.L4_REASON, query, "multi_step_reason", "多步推理+LLM分解", [2, 3]),
                PlanStep(5, RouteLevel.L5_GENERATE, query, "generate_answer", "综合生成最终答案", [4]),
            ]
        # PARALLEL
        return [
            PlanStep(1, RouteLevel.L1_CACHE, query, "cache_lookup", "缓存检查"),
            PlanStep(2, RouteLevel.L2_VECTOR, query, "vector_parallel", "并行向量+BM25"),
            PlanStep(3, RouteLevel.L3_GRAPH, query, "graph_parallel", "并行图谱召回"),
            PlanStep(4, RouteLevel.L5_GENERATE, query, "generate_answer", "LLM 融合生成", [2, 3]),
        ]

    def _select_fusion(self, complexity: QueryComplexity) -> str:
        return {
            QueryComplexity.SIMPLE: "none",
            QueryComplexity.MEDIUM: "rrf",
            QueryComplexity.COMPLEX: "weighted",
        }.get(complexity, "rrf")

    # ------------------------------------------------------------------
    # 执行查询计划
    # ------------------------------------------------------------------

    async def execute(self, plan: QueryPlan) -> Dict[str, Any]:
        """执行查询计划，返回融合后的最终结果

        Args:
            plan: QueryPlan 对象

        Returns:
            {"results": [...], "layer_results": [...], "answer": str, "meta": {...}}
        """
        self._stats["total_queries"] += 1
        start_time = time.time()
        layer_results: List[LayerResult] = []
        context: Dict[str, Any] = {}

        for step in plan.steps:
            should_upgrade = self._should_upgrade(step, layer_results, plan)
            if not should_upgrade and step.level != RouteLevel.L1_CACHE:
                logger.debug(f"[QueryPlanner] 跳过 L{step.level}（无需升级）")
                continue

            t0 = time.time()
            layer_result = await self._execute_layer(step, plan.query, context)
            layer_result.latency_ms = (time.time() - t0) * 1000
            layer_results.append(layer_result)
            self._stats["layer_hits"][step.level.name] += 1

            if layer_result.results:
                context[f"l{step.level.value}_results"] = layer_result.results
                context[f"l{step.level.value}_confidence"] = layer_result.confidence

            logger.info(
                f"[QueryPlanner] L{step.level} '{step.level.name}': "
                f"{len(layer_result.results)} results, "
                f"conf={layer_result.confidence:.2f}, "
                f"{layer_result.latency_ms:.0f}ms"
            )

        fused = await self._fuse_results(layer_results, plan)

        total_ms = (time.time() - start_time) * 1000
        self._stats["total_latency_ms"] += total_ms
        self._stats["avg_latency_ms"] = self._stats["total_latency_ms"] / max(self._stats["total_queries"], 1)

        return {
            "results": fused.get("results", []),
            "answer": fused.get("answer", ""),
            "layer_results": [
                {
                    "level": r.level.value,
                    "source": r.source,
                    "count": len(r.results),
                    "confidence": r.confidence,
                    "latency_ms": round(r.latency_ms, 1),
                }
                for r in layer_results
            ],
            "meta": {
                "query": plan.query,
                "complexity": plan.complexity.value,
                "strategy": plan.strategy.value,
                "total_layers": len(layer_results),
                "total_latency_ms": round(total_ms, 1),
                "fusion": plan.fusion_strategy,
            },
        }

    def _should_upgrade(
        self, step: PlanStep, previous: List[LayerResult], plan: QueryPlan
    ) -> bool:
        """判断是否需要升级到当前层

        升级判定：
          L1→L2：缓存未命中 → 升级
          L2→L3：向量召回不足(<3条 或 最大分<0.5) → 升级
          L3→L4：复杂查询 → 始终升级
          L4→L5：已有前序结果 → 升级生成
        """
        if step.level == RouteLevel.L1_CACHE:
            return True

        prev_level = step.level.value - 1
        prev: Optional[LayerResult] = None
        for r in reversed(previous):
            if r.level.value <= prev_level:
                prev = r
                break

        if prev is None:
            return True

        if step.level == RouteLevel.L2_VECTOR and prev.level == RouteLevel.L1_CACHE:
            if prev.results and prev.confidence >= 0.9:
                return False
            return True

        if prev.confidence >= plan.confidence_threshold and len(prev.results) >= 3:
            if plan.complexity == QueryComplexity.COMPLEX and step.level == RouteLevel.L4_REASON:
                return True
            if step.level == RouteLevel.L5_GENERATE:
                return True
            return False

        return True

    async def _execute_layer(
        self, step: PlanStep, query: str, context: Dict[str, Any]
    ) -> LayerResult:
        handler_map = {
            RouteLevel.L1_CACHE: self._execute_l1_cache,
            RouteLevel.L2_VECTOR: self._execute_l2_vector,
            RouteLevel.L3_GRAPH: self._execute_l3_graph,
            RouteLevel.L4_REASON: self._execute_l4_reason,
            RouteLevel.L5_GENERATE: self._execute_l5_generate,
        }
        handler = handler_map.get(step.level)
        if handler:
            return await handler(query, context, step)
        return LayerResult(level=step.level, source="unknown", confidence=0.0)

    # ------------------------------------------------------------------
    # L1: 缓存层
    # ------------------------------------------------------------------

    async def _execute_l1_cache(
        self, query: str, context: Dict[str, Any], step: PlanStep
    ) -> LayerResult:
        """L1 缓存检查 — 精确+语义缓存"""
        cache_key = hashlib.md5(query.encode("utf-8")).hexdigest()

        if cache_key in self._result_cache:
            timestamp, cached = self._result_cache[cache_key]
            if time.time() - timestamp < self.cache_ttl:
                self._stats["cache_hits"] += 1
                logger.info(f"[QueryPlanner] L1 缓存命中")
                cached.metadata["cache_type"] = "exact"
                return cached

        self._stats["cache_misses"] += 1

        try:
            from src.services.retrieval import _l0_cache_check
            semantic = await _l0_cache_check(query, "", 10, skip_cache=False)
            if semantic:
                result = LayerResult(
                    level=RouteLevel.L1_CACHE,
                    source="semantic_cache",
                    results=semantic,
                    confidence=0.85,
                    metadata={"cache_type": "semantic"},
                )
                self._result_cache[cache_key] = (time.time(), result)
                self._stats["cache_hits"] += 1
                return result
        except Exception as e:
            logger.debug(f"[QueryPlanner] L1 语义缓存: {e}")

        return LayerResult(
            level=RouteLevel.L1_CACHE,
            source="cache",
            results=[],
            confidence=0.0,
            metadata={"cache_type": "miss"},
        )

    # ------------------------------------------------------------------
    # L2: 向量检索层
    # ------------------------------------------------------------------

    async def _execute_l2_vector(
        self, query: str, context: Dict[str, Any], step: PlanStep
    ) -> LayerResult:
        """L2 向量检索 — 向量语义 + BM25 双路召回"""
        try:
            from src.services.retrieval import hybrid_search
            results = await hybrid_search(query, top_k=15, skip_cache=True)

            if not results:
                return LayerResult(
                    level=RouteLevel.L2_VECTOR, source="vector",
                    results=[], confidence=0.0, metadata={"error": "无检索结果"},
                )

            scores = [r.get("score", 0) for r in results]
            max_score = max(scores) if scores else 0
            avg_score = sum(scores) / len(scores) if scores else 0
            confidence = min(max_score / 10.0, 0.95)

            return LayerResult(
                level=RouteLevel.L2_VECTOR, source="vector",
                results=results, confidence=confidence,
                metadata={
                    "count": len(results),
                    "max_score": max_score,
                    "avg_score": round(avg_score, 2),
                    "sources": list(set(r.get("_source", "unknown") for r in results)),
                },
            )
        except Exception as e:
            logger.warning(f"[QueryPlanner] L2 向量检索失败: {e}")
            return LayerResult(level=RouteLevel.L2_VECTOR, source="vector", results=[], confidence=0.0, metadata={"error": str(e)})

    # ------------------------------------------------------------------
    # L3: 图谱检索层
    # ------------------------------------------------------------------

    async def _execute_l3_graph(
        self, query: str, context: Dict[str, Any], step: PlanStep
    ) -> LayerResult:
        """L3 图谱检索 — 实体识别 + 关系图谱遍历"""
        try:
            from src.services.graph_router import route_to_categories
            from src.services.relation_builder import auto_build_relations

            categories = route_to_categories(query)
            if not categories:
                return LayerResult(level=RouteLevel.L3_GRAPH, source="graph", results=[], confidence=0.0, metadata={"categories": []})

            l2_results = context.get("l2_results", [])
            relations = []
            if l2_results:
                try:
                    relations = await auto_build_relations(query=query, chunks=l2_results[:10], categories=categories)
                except Exception:
                    logger.debug("[QueryPlanner] 关系构建跳过")

            graph_augmented = _augment_with_graph(l2_results, categories, relations)
            confidence = min(len(categories) * 0.15 + len(relations) * 0.1, 0.9)

            return LayerResult(
                level=RouteLevel.L3_GRAPH, source="graph",
                results=graph_augmented, confidence=confidence,
                metadata={"categories": categories, "entity_count": len(relations)},
            )
        except Exception as e:
            logger.warning(f"[QueryPlanner] L3 图谱检索失败: {e}")
            return LayerResult(level=RouteLevel.L3_GRAPH, source="graph", results=context.get("l2_results", []), confidence=0.3, metadata={"error": str(e)})

    # ------------------------------------------------------------------
    # L4: 推理层
    # ------------------------------------------------------------------

    async def _execute_l4_reason(
        self, query: str, context: Dict[str, Any], step: PlanStep
    ) -> LayerResult:
        """L4 多步推理 — LLM 链式分解 + Self-RAG 反思"""
        try:
            all_results = []
            for key in ["l2_results", "l3_results"]:
                if key in context:
                    all_results.extend(context[key])

            if not all_results:
                return LayerResult(level=RouteLevel.L4_REASON, source="reason", results=[], confidence=0.0, metadata={"error": "无前序结果"})

            sub_queries = await self._decompose_query(query, len(all_results))
            if not sub_queries:
                return LayerResult(level=RouteLevel.L4_REASON, source="reason", results=all_results, confidence=0.5, metadata={"decomposed": 0})

            try:
                from src.shaoyin.smart_self_rag import SmartSelfRAG
                srag = SmartSelfRAG()
                reflection = await srag.reflect_if_needed(query, all_results[:10])
            except ImportError:
                reflection = None

            return LayerResult(
                level=RouteLevel.L4_REASON, source="reason",
                results=all_results, confidence=0.7,
                metadata={
                    "sub_queries": sub_queries,
                    "self_rag_action": reflection.action if reflection else "skipped",
                    "decomposed_count": len(sub_queries),
                },
            )
        except Exception as e:
            logger.warning(f"[QueryPlanner] L4 推理失败: {e}")
            return LayerResult(level=RouteLevel.L4_REASON, source="reason", results=context.get("l2_results", []), confidence=0.3, metadata={"error": str(e)})

    async def _decompose_query(self, query: str, result_count: int) -> List[str]:
        """将复杂查询分解为子查询"""
        try:
            from src.services.llm import call_llm_fast
            prompt = f"""将以下复杂查询分解为 2-3 个子查询。只输出 JSON 数组。

查询：{query}

示例：["子查询1", "子查询2", "子查询3"]
规则：每个子查询应独立可检索，只输出 JSON。"""
            result = await call_llm_fast(prompt, max_tokens=200)
            if not result:
                return []
            result = result.strip()
            if result.startswith("```"):
                result = result.split("\n", 1)[1].rsplit("```", 1)[0]
            subs = json.loads(result)
            if isinstance(subs, list) and len(subs) > 0:
                return [str(s) for s in subs[:3]]
        except Exception as e:
            logger.debug(f"[QueryPlanner] 分解失败: {e}")
        return []

    # ------------------------------------------------------------------
    # L5: 生成层
    # ------------------------------------------------------------------

    async def _execute_l5_generate(
        self, query: str, context: Dict[str, Any], step: PlanStep
    ) -> LayerResult:
        """L5 生成 — LLM 生成最终答案"""
        try:
            from src.services.llm import call_llm

            all_contexts = []
            for key in ["l2_results", "l3_results", "l4_results"]:
                if key in context:
                    for r in context[key][:5]:
                        text = r.get("text", "") or r.get("chunk_text", "")
                        if text:
                            source = r.get("_source", r.get("file_name", "unknown"))
                            all_contexts.append(f"[来源:{source}] {text[:300]}")

            ctx_text = "\n---\n".join(all_contexts) if all_contexts else "（无参考资料）"

            prompt = f"""基于以下参考资料回答用户问题。如资料不足，据实说明。

## 参考资料
{ctx_text}

## 用户问题
{query}

## 回答要求
- 准确、简洁
- 引用资料中的具体信息
- 如果资料不足，明确指出"""

            answer = await call_llm(prompt)

            return LayerResult(
                level=RouteLevel.L5_GENERATE, source="generate",
                results=[{"answer": answer, "query": query}],
                confidence=0.85,
                metadata={"context_count": len(all_contexts), "answer_length": len(answer) if answer else 0},
            )
        except Exception as e:
            logger.warning(f"[QueryPlanner] L5 生成失败: {e}")
            return LayerResult(
                level=RouteLevel.L5_GENERATE, source="generate",
                results=[{"answer": f"抱歉，生成回答时出错: {e}", "query": query}],
                confidence=0.0, metadata={"error": str(e)},
            )

    # ------------------------------------------------------------------
    # 结果融合
    # ------------------------------------------------------------------

    async def _fuse_results(self, layer_results: List[LayerResult], plan: QueryPlan) -> Dict[str, Any]:
        """多层级结果融合与排序"""
        if not layer_results:
            return {"results": [], "answer": ""}

        if plan.fusion_strategy == "none":
            last = layer_results[-1]
            answer = ""
            if last.results and last.level == RouteLevel.L5_GENERATE:
                answer = last.results[0].get("answer", "")
            return {"results": last.results, "answer": answer}

        if plan.fusion_strategy == "rrf":
            merged = await self._rrf_fuse(layer_results)
            return {"results": merged, "answer": ""}

        if plan.fusion_strategy == "weighted":
            merged = await self._weighted_fuse(layer_results)
            answer = ""
            for lr in layer_results:
                if lr.level == RouteLevel.L5_GENERATE and lr.results:
                    answer = lr.results[0].get("answer", "")
            return {"results": merged, "answer": answer}

        last = layer_results[-1]
        answer = last.results[0].get("answer", "") if last.results else ""
        return {"results": last.results, "answer": answer}

    async def _rrf_fuse(self, layer_results: List[LayerResult]) -> List[Dict[str, Any]]:
        """RRF (Reciprocal Rank Fusion)"""
        try:
            from src.taiyang.fusion import rrf_fusion as _rrf
            all_lists = [lr.results for lr in layer_results if lr.level != RouteLevel.L1_CACHE and lr.results]
            if len(all_lists) == 1:
                return all_lists[0]
            if len(all_lists) >= 2:
                return _rrf(all_lists[0], all_lists[1], k=60)
            return all_lists[0] if all_lists else []
        except ImportError:
            seen: set = set()
            merged = []
            for lr in layer_results:
                for r in lr.results:
                    key = r.get("file_hash", "") + "|" + str(r.get("chunk_index", 0))
                    if key not in seen:
                        seen.add(key)
                        merged.append(r)
            merged.sort(key=lambda x: float(x.get("score", 0)), reverse=True)
            return merged

    async def _weighted_fuse(self, layer_results: List[LayerResult]) -> List[Dict[str, Any]]:
        """加权融合 — 层级越深权重越高"""
        layer_weights = {
            RouteLevel.L1_CACHE: 0.1,
            RouteLevel.L2_VECTOR: 0.3,
            RouteLevel.L3_GRAPH: 0.5,
            RouteLevel.L4_REASON: 0.7,
            RouteLevel.L5_GENERATE: 0.8,
        }

        merged: Dict[str, Dict[str, Any]] = {}
        for lr in layer_results:
            weight = layer_weights.get(lr.level, 0.3)
            for r in lr.results:
                key = r.get("file_hash", "") + "|" + str(r.get("chunk_index", 0))
                if key in merged:
                    old_s = float(merged[key].get("score", 0))
                    new_s = float(r.get("score", 0)) * weight
                    merged[key]["score"] = max(old_s, new_s)
                    existing_sources = merged[key].get("_sources", [])
                    new_source = r.get("_source", r.get("file_name", ""))
                    if new_source not in existing_sources:
                        existing_sources.append(new_source)
                    merged[key]["_sources"] = existing_sources
                else:
                    merged[key] = dict(r)
                    merged[key]["score"] = float(r.get("score", 0)) * weight
                    merged[key]["_sources"] = [r.get("_source", r.get("file_name", ""))]

        result = list(merged.values())
        result.sort(key=lambda x: float(x.get("score", 0)), reverse=True)
        return result

    # ------------------------------------------------------------------
    # 统计信息
    # ------------------------------------------------------------------

    @property
    def stats(self) -> Dict[str, Any]:
        """返回统计信息"""
        return dict(self._stats)

    def clear_cache(self) -> None:
        """清除缓存"""
        self._result_cache.clear()
        self._stats["cache_hits"] = 0
        self._stats["cache_misses"] = 0


# ============================================================================
# 便捷函数（集成到现有 RAG 流程）
# ============================================================================


async def query_with_5layer_routing(
    query: str,
    planner: Optional[QueryPlanner] = None,
    force_complexity: Optional[QueryComplexity] = None,
) -> Dict[str, Any]:
    """通过5层路由查询 — 便捷封装函数

    可直接替换原有的 hybrid_search 调用，享受分层路由优势。

    Args:
        query: 用户查询
        planner: 可选的 QueryPlanner 实例（默认创建新的）
        force_complexity: 强制指定复杂度

    Returns:
        {"results": [...], "answer": str, "layer_results": [...], "meta": {...}}
    """
    if planner is None:
        planner = QueryPlanner()

    plan = await planner.plan(query, force_complexity=force_complexity)
    result = await planner.execute(plan)
    return result
