"""
core/rag_engine.py — RAG 引擎核心 (v1.50, 🚫 DEPRECATED v2.2)

⚠️ 弃用通知 (2026-08-05):
  本模块已被 src.shaoyin.brain.ShaoyinBrain 取代为 RAG 权威入口。
  ShaoyinBrain 提供更完整的管线：意图识别→策略选择→检索→
  Self-RAG→CRAG→答案合成→L5 CRAG→校验→重试。

  过渡期兼容性：
    - 现有代码可继续使用，但新功能请使用 ShaoyinBrain
    - 计划在下个主版本（v3.0）移除 RAGEngine

  迁移指南:
    # 旧方式
    from src.core.rag_engine import RAGEngine, rag_query
    result = await rag_query("你的问题")

    # 新方式
    from src.shaoyin.brain import ShaoyinBrain
    brain = ShaoyinBrain(meridian)
    result = await brain.think("你的问题")

  功能对比:
    RAGEngine              ShaoyinBrain
    ──────────             ────────────
    retrieve() ✓           _retrieve() ✓ (via hybrid_search)
    rerank()   ✓           内建于 hybrid_search L4-L5
    generate_answer() ✓    _compose() ✓ (LLM 合成)
    prompt_guard ✓         内建 (shaoyin 安全模块)
    意图识别   ✗            _classify_intent() ✓
    Self-RAG   ✗            SmartSelfRAG ✓
    CRAG       ✗            CRAGCorrector ✓
    L5 CRAG    ✗            L5CRAGExecutor ✓
    成长记录   ✗            GrowthRecordPoints ✓

伏羲系统统一的 RAG（检索增强生成）引擎，整合检索、重排序和 LLM 生成，
为整个系统提供统一的 RAG 能力入口。

设计原则:
  - 三层架构: 检索(Retrieve) → 重排序(Rerank) → 生成(Generate)
  - 降级策略: LLM 不可用或检索失败 → 仅返回检索结果
  - 上下文窗口管理: 自动截断过长上下文，确保在 LLM token 限制内
  - 安全: 集成 prompt_guard 防止注入攻击

核心流程:
    用户查询 → process_query()
      ├── retrieve()     — 混合检索 (BM25 + 向量 + Wiki + 表格)
      ├── rerank()       — Cross-encoder 精排 (可选)
      └── generate_answer() — LLM 生成回答

Usage::

    from src.core.rag_engine import RAGEngine

    engine = RAGEngine()

    # 完整 RAG 流程
    result = await engine.process_query(
        query="什么是 VLAN 101？",
        context={"user_id": "u123", "category": "network"},
    )

    # 仅检索
    docs = await engine.retrieve("VLAN 配置", top_k=10)

    # 仅生成
    answer = await engine.generate_answer(
        "总结以下文档", context={"documents": ["..."], "role": "assistant"}
    )
"""

import warnings

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Union

# ─── v2.2 DEPRECATION: 发出弃用警告 ───
warnings.warn(
    "core.rag_engine.RAGEngine 已弃用 (v2.2)。"
    "请迁移到 src.shaoyin.brain.ShaoyinBrain（更完整的 RAG 管线）。"
    "详见模块文档中的迁移指南。",
    DeprecationWarning,
    stacklevel=2,
)

logger = logging.getLogger(__name__)

# ============================================================================
# 配置常量
# ============================================================================

# 默认返回结果数
DEFAULT_TOP_K: int = 15

# LLM 生成最大 token 数
MAX_GENERATION_TOKENS: int = 1024

# 上下文最大字符数（约对应 4K tokens）
MAX_CONTEXT_CHARS: int = 12000

# 检索超时时间（秒）
RETRIEVAL_TIMEOUT: float = 30.0

# LLM 生成超时时间（秒）
GENERATION_TIMEOUT: float = 60.0

# 默认系统提示词
DEFAULT_SYSTEM_PROMPT: str = (
    "你是一个专业的知识助手，基于提供的参考资料回答用户问题。\n"
    "请遵循以下原则：\n"
    "1. 只根据提供的参考资料回答，不要编造信息\n"
    "2. 如果参考资料不足以回答问题，请明确说明\n"
    "3. 引用具体的参考来源（文件名、页码等）\n"
    "4. 回答应简洁、准确、结构化\n"
    "5. 使用中文回答"
)

# RAG 上下文模板
RAG_CONTEXT_TEMPLATE: str = "参考资料：\n" "{context}\n\n" "用户问题：{query}\n\n" "请根据以上参考资料回答问题。"


# ============================================================================
# RAGEngine 类
# ============================================================================


class RAGEngine:
    """伏羲 RAG 引擎 — 统一检索增强生成入口

    整合完整的 RAG 管线:
      - retrieve():   混合检索，返回相关文档
      - rerank():     Cross-encoder 精排
      - generate_answer(): 基于检索结果生成回答

    特性:
      - 异步设计（retrieve/generate 均为 async）
      - 三级降级: LLM → 检索结果拼接 → 空回答
      - 安全: 集成 prompt_guard 防止 prompt injection
      - 可观测: 全流程 trace 日志

    Attributes:
        default_top_k:    默认检索返回结果数
        max_context_chars: LLM 上下文最大字符数
        system_prompt:     系统提示词
        enable_rerank:     是否启用重排序
        enable_cache:      是否启用语义缓存
    """

    def __init__(
        self,
        default_top_k: int = DEFAULT_TOP_K,
        max_context_chars: int = MAX_CONTEXT_CHARS,
        system_prompt: Optional[str] = None,
        enable_rerank: bool = True,
        enable_cache: bool = True,
    ) -> None:
        """
        Args:
            default_top_k:     默认检索结果数
            max_context_chars: 上下文最大字符数
            system_prompt:     自定义系统提示词（None 使用默认）
            enable_rerank:     是否启用 Cross-encoder 重排序
            enable_cache:      是否启用语义缓存
        """
        self.default_top_k = default_top_k
        self.max_context_chars = max_context_chars
        self.system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT
        self.enable_rerank = enable_rerank
        self.enable_cache = enable_cache

        # 统计
        self._query_count: int = 0
        self._total_retrieval_time: float = 0.0
        self._total_generation_time: float = 0.0

        # 组件延迟初始化，避免循环导入
        self._rerank_fn = None
        self._llm_available: Optional[bool] = None

        logger.info(
            "[RAGEngine] 初始化完成 top_k=%d context_chars=%d rerank=%s cache=%s",
            self.default_top_k,
            self.max_context_chars,
            self.enable_rerank,
            self.enable_cache,
        )

    # ========================================================================
    # 主入口：process_query（重构 v1.50）
    # ========================================================================

    def _extract_context_params(self, context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """提取并规范化上下文参数"""
        ctx = context or {}
        return {
            "top_k": ctx.get("top_k", self.default_top_k),
            "category": ctx.get("category", ""),
            "file_type": ctx.get("file_type", ""),
            "date_from": ctx.get("date_from", ""),
            "date_to": ctx.get("date_to", ""),
            "user_id": ctx.get("user_id", ""),
            "skip_rerank": ctx.get("skip_rerank", not self.enable_rerank),
            "skip_cache": ctx.get("skip_cache", not self.enable_cache),
            "enable_generation": ctx.get("enable_generation", True),
            "direct_context": ctx.get("rag_context", ""),
            "custom_system_prompt": ctx.get("system_prompt", self.system_prompt),
        }

    def _build_result_template(self, query: str, trace_id: str) -> Dict[str, Any]:
        """构建结果模板"""
        return {
            "ok": True,
            "query": query,
            "answer": "",
            "retrieved_docs": [],
            "retrieval_count": 0,
            "retrieval_time_ms": 0.0,
            "generation_time_ms": 0.0,
            "sources": [],
            "pipeline": "full_rag",
            "error": "",
            "trace_id": trace_id,
        }

    async def _execute_retrieval(
        self,
        query: str,
        params: Dict[str, Any],
        result: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """执行检索步骤，返回检索文档列表"""
        direct_context = params["direct_context"]

        # 直接上下文模式
        if direct_context:
            result["retrieved_docs"] = [
                {
                    "text": direct_context,
                    "file_name": "[Direct Context]",
                    "score": 10.0,
                    "_source": "direct_context",
                }
            ]
            result["retrieval_count"] = 1
            result["pipeline"] = "direct_context"
            return result["retrieved_docs"]

        # 混合检索模式
        try:
            retrieval_start = time.time()
            retrieved_docs = await self.retrieve(
                query=query,
                top_k=params["top_k"],
                category=params["category"],
                file_type=params["file_type"],
                date_from=params["date_from"],
                date_to=params["date_to"],
                skip_cache=params["skip_cache"],
            )
            retrieval_time = (time.time() - retrieval_start) * 1000
            result["retrieval_time_ms"] = round(retrieval_time, 1)
            result["retrieved_docs"] = retrieved_docs
            result["retrieval_count"] = len(retrieved_docs)
            self._total_retrieval_time += retrieval_time

            # 提取来源
            sources = list(set(doc.get("file_name", "") for doc in retrieved_docs[:5] if doc.get("file_name")))
            result["sources"] = sources
            return retrieved_docs

        except asyncio.TimeoutError:
            logger.error("[RAGEngine] 检索超时: %s", query[:50])
            result["error"] = "检索超时"
            result["ok"] = False
            return []
        except (ConnectionError, TimeoutError, OSError, ValueError) as exc:
            logger.error("[RAGEngine] 检索异常: %s — %s", query[:50], exc, exc_info=True)
            result["error"] = f"检索失败: {exc}"
            result["ok"] = False
            return []

    async def _execute_rerank(
        self,
        query: str,
        docs: List[Dict[str, Any]],
        top_k: int,
        skip_rerank: bool,
        is_direct_context: bool,
    ) -> List[Dict[str, Any]]:
        """执行重排序步骤"""
        if skip_rerank or not docs or is_direct_context:
            return docs
        try:
            return await self.rerank(query, docs, top_k)
        except (ConnectionError, TimeoutError, OSError, ValueError) as exc:
            logger.warning("[RAGEngine] 重排序失败，使用原始排序: %s", exc)
            return docs

    async def _execute_generation(
        self,
        query: str,
        docs: List[Dict[str, Any]],
        params: Dict[str, Any],
        result: Dict[str, Any],
    ) -> None:
        """执行 LLM 生成步骤"""
        if not params["enable_generation"]:
            return

        try:
            gen_start = time.time()
            answer = await self.generate_answer(
                query=query,
                context={
                    "retrieved_docs": docs,
                    "system_prompt": params["custom_system_prompt"],
                    "user_id": params["user_id"],
                },
            )
            gen_time = (time.time() - gen_start) * 1000
            result["answer"] = answer
            result["generation_time_ms"] = round(gen_time, 1)
            self._total_generation_time += gen_time
        except asyncio.TimeoutError:
            logger.warning("[RAGEngine] LLM 生成超时，降级为检索结果")
            result["answer"] = self._build_fallback_answer(query, docs)
            result["pipeline"] = "retrieve_only"
        except (ConnectionError, TimeoutError, OSError, ValueError) as exc:
            logger.warning("[RAGEngine] LLM 生成失败: %s，降级为检索结果", exc)
            result["answer"] = self._build_fallback_answer(query, docs)
            result["pipeline"] = "retrieve_only"

    async def process_query(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """完整的 RAG 处理流程（重构 v1.50）

        执行完整的检索 → 重排序 → 生成管线，返回结构化结果。
        """
        trace_id = self._generate_trace_id(query)
        params = self._extract_context_params(context)
        result = self._build_result_template(query, trace_id)
        self._query_count += 1

        # 安全: 限制 top_k 上限
        top_k = params["top_k"]
        try:
            from src.services.prompt_guard import clamp_top_k

            top_k = clamp_top_k(top_k)
        except ImportError:
            if top_k > 100:
                top_k = 100
        params["top_k"] = top_k

        # 步骤 1: 检索
        retrieved_docs = await self._execute_retrieval(query, params, result)
        if not result["ok"]:
            return result

        # 步骤 2: 重排序
        retrieved_docs = await self._execute_rerank(
            query,
            retrieved_docs,
            top_k,
            params["skip_rerank"],
            bool(params["direct_context"]),
        )
        result["retrieved_docs"] = retrieved_docs

        # 步骤 3: LLM 生成
        await self._execute_generation(query, retrieved_docs, params, result)

        return result

    # ========================================================================
    # 检索：retrieve
    # ========================================================================

    async def retrieve(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        category: str = "",
        file_type: str = "",
        date_from: str = "",
        date_to: str = "",
        skip_cache: bool = False,
    ) -> List[Dict[str, Any]]:
        """RAG 检索入口 — 混合检索

        使用伏羲的混合检索管线（hybrid_search），包含：
          - L-1: QA 对匹配
          - L0:  语义缓存 + 图谱路由
          - L1:  Query 扩展 + BM25 关键词检索
          - L1.5: HyDE 向量语义检索
          - L1.75: Wiki 召回
          - L2:   表格视图
          - L3:   RRF 融合
          - L4:   精排（exact_match + category_weight + personalized_boost）
          - L5:   Rerank
          - L6:   上下文扩展 + Parent-Child 展开

        Args:
            query:      查询字符串
            top_k:      返回结果数
            category:   分类过滤
            file_type:  文件类型过滤
            date_from:  起始日期
            date_to:    截止日期
            skip_cache: 是否跳过缓存

        Returns:
            检索结果列表，每个结果包含:
                - text:        文本内容
                - file_name:   文件名
                - file_hash:   文件哈希
                - category:    分类
                - chunk_index: 块索引
                - score:       分数
                - _source:     来源标记 (bm25/vector/wiki/table_view/qa_pair)
                - context:     上下文片段
                - meta:        元数据
        """
        try:
            from src.services.retrieval import hybrid_search

            docs = await asyncio.wait_for(
                hybrid_search(
                    query=query,
                    top_k=top_k,
                    category=category,
                    file_type=file_type,
                    date_from=date_from,
                    date_to=date_to,
                    skip_cache=skip_cache,
                ),
                timeout=RETRIEVAL_TIMEOUT,
            )

            if not docs:
                logger.info("[RAGEngine] 检索无结果: %s", query[:80])
                return []

            logger.info(
                "[RAGEngine] 检索完成: query='%s...' docs=%d",
                query[:40],
                len(docs),
            )
            return docs

        except ImportError as exc:
            logger.warning("[RAGEngine] hybrid_search 不可用: %s，尝试降级检索", exc)
            return await self._fallback_retrieve(query, top_k, category)

    async def _fallback_retrieve(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        category: str = "",
    ) -> List[Dict[str, Any]]:
        """降级检索：直接使用 vector_store + memory_store

        当完整的 hybrid_search 不可用时使用。
        """
        results: List[Dict[str, Any]] = []

        # 尝试向量检索
        try:
            from src.services.retrieval import vector_recall

            vec_results = await vector_recall(query, n_results=top_k, category=category)
            if vec_results:
                results.extend(vec_results)
        except ImportError:
            pass
        except Exception as exc:  # TODO: Narrow exception type
            logger.warning("[RAGEngine] 降级向量检索失败: %s", exc)

        # 尝试 BM25 检索
        try:
            from src.db.memory_store import get_store

            store = get_store()
            bm25_results = store.keyword_search(query, top_k)
            if bm25_results:
                for r in bm25_results:
                    r["_source"] = "bm25"
                    if "score" not in r:
                        r["score"] = 5.0
                # 去重合并
                seen = set()
                for r in results:
                    key = r.get("file_hash", "") + "|" + str(r.get("chunk_index", 0))
                    seen.add(key)
                for r in bm25_results:
                    key = r.get("file_hash", "") + "|" + str(r.get("chunk_index", 0))
                    if key not in seen:
                        seen.add(key)
                        results.append(r)
        except ImportError:
            pass
        except Exception as exc:  # TODO: Narrow exception type
            logger.warning("[RAGEngine] 降级 BM25 检索失败: %s", exc)

        # 按分数排序
        results.sort(key=lambda x: float(x.get("score", 0)), reverse=True)
        return results[:top_k]

    # ========================================================================
    # 重排序：rerank
    # ========================================================================

    async def rerank(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_k: int = DEFAULT_TOP_K,
    ) -> List[Dict[str, Any]]:
        """对检索结果进行 Cross-encoder 精排

        三级降级链:
          1. 专用 Reranker 模型（SiliconFlow 或本地）
          2. TF-IDF 基于 jieba 的本地重排序
          3. 返回原始排序

        Args:
            query:     查询字符串
            documents: 待重排文档列表
            top_k:     返回结果数

        Returns:
            重排序后的文档列表
        """
        if not documents:
            return documents

        try:
            from src.services.retrieval import _rerank_layer

            ranked = await asyncio.wait_for(
                _rerank_layer(query, documents, top_k),
                timeout=20.0,
            )
            if ranked:
                logger.info(
                    "[RAGEngine] 重排序完成: %d → %d results",
                    len(documents),
                    len(ranked),
                )
                return ranked
        except ImportError:
            pass
        except asyncio.TimeoutError:
            logger.warning("[RAGEngine] 重排序超时")
        except Exception as exc:  # TODO: Narrow exception type
            logger.warning("[RAGEngine] 重排序失败: %s", exc)

        # 按分数排序兜底
        documents.sort(key=lambda x: float(x.get("score", 0)), reverse=True)
        return documents[:top_k]

    # ========================================================================
    # 生成回答：generate_answer
    # ========================================================================

    async def generate_answer(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """基于检索结果和上下文，通过 LLM 生成回答

        Args:
            query:   用户查询
            context: 生成上下文，支持:
                - retrieved_docs: List[dict] — 检索到的文档
                - system_prompt: str       — 系统提示词
                - user_id: str             — 用户 ID
                - model: str               — 指定模型名
                - max_tokens: int          — 最大 token 数

        Returns:
            生成的回答文本
        """
        ctx = context or {}

        retrieved_docs = ctx.get("retrieved_docs", [])
        system_prompt = ctx.get("system_prompt", self.system_prompt)
        user_id = ctx.get("user_id", "")
        model = ctx.get("model", None)
        max_tokens = ctx.get("max_tokens", MAX_GENERATION_TOKENS)

        # ----------------------------------------------------------------
        # 构建 LLM 上下文
        # ----------------------------------------------------------------
        context_text = self._build_context_text(query, retrieved_docs)

        # 安全: 净化上下文防止 prompt injection
        try:
            from src.services.prompt_guard import sanitize_prompt

            context_text = sanitize_prompt(context_text)
            query = sanitize_prompt(query)
        except ImportError:
            pass

        # ----------------------------------------------------------------
        # 调用 LLM
        # ----------------------------------------------------------------
        try:
            from src.services.llm import get_llm_client

            llm = get_llm_client()

            # 构建消息
            messages = [
                {"role": "system", "content": system_prompt},
            ]

            if context_text:
                messages.append(
                    {
                        "role": "user",
                        "content": RAG_CONTEXT_TEMPLATE.format(
                            context=context_text,
                            query=query,
                        ),
                    }
                )
            else:
                # 无上下文时的兜底提示
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            f"用户问题：{query}\n\n"
                            f"注意：没有找到相关参考资料，请基于你的知识回答，"
                            f"但要明确声明信息来自通用知识而非系统文档。"
                        ),
                    }
                )

            response = await asyncio.wait_for(
                llm.chat(
                    messages=messages,
                    model=model,
                    max_tokens=max_tokens,
                    temperature=0.3,
                ),
                timeout=GENERATION_TIMEOUT,
            )

            answer = response.get("content", "") if isinstance(response, dict) else str(response)

            # 安全: 净化输出
            try:
                from src.services.prompt_guard import sanitize_prompt

                answer = sanitize_prompt(answer)
            except ImportError:
                pass

            logger.info(
                "[RAGEngine] LLM 生成完成: query='%s...' answer_len=%d",
                query[:40],
                len(answer),
            )
            return answer

        except ImportError as exc:
            logger.warning("[RAGEngine] LLM 客户端不可用: %s", exc)
            return self._build_fallback_answer(query, retrieved_docs)
        except asyncio.TimeoutError:
            raise  # 向上传播，由 process_query 处理
        except Exception as exc:  # TODO: Narrow exception type
            raise  # 向上传播，由 process_query 处理

    # ========================================================================
    # 辅助方法
    # ========================================================================

    def _build_context_text(
        self,
        query: str,
        documents: List[Dict[str, Any]],
    ) -> str:
        """从检索文档构建 LLM 上下文文本

        自动截断以保持在 max_context_chars 限制内。

        Args:
            query:     查询字符串（用于判断相关性）
            documents: 检索到的文档列表

        Returns:
            拼接后的上下文文本
        """
        if not documents:
            return ""

        parts: List[str] = []
        total_chars = 0

        for i, doc in enumerate(documents[:30]):  # 最多 30 个文档
            # 提取文本
            text = doc.get("text", "") or doc.get("chunk_text", "") or doc.get("content", "")
            file_name = doc.get("file_name", "未知来源")
            score = doc.get("score", 0)

            if not text.strip():
                continue

            # 格式: [来源 N] 文件名 (相关性: X.X) | 内容
            entry = f"[来源 {i + 1}] {file_name} (相关性: {float(score):.1f})\n" f"{text}\n"

            # 截断控制
            if total_chars + len(entry) > self.max_context_chars:
                remaining = self.max_context_chars - total_chars
                if remaining > 100:
                    entry = entry[:remaining] + "\n...(已截断)"
                    parts.append(entry)
                break

            parts.append(entry)
            total_chars += len(entry)

        return "\n".join(parts)

    def _build_fallback_answer(
        self,
        query: str,
        documents: List[Dict[str, Any]],
    ) -> str:
        """LLM 不可用时的降级回答

        将检索结果直接拼接为回答。

        Args:
            query:     用户查询
            documents: 检索到的文档

        Returns:
            拼接后的降级回答
        """
        if not documents:
            return "抱歉，没有找到与您问题相关的信息。"

        parts: List[str] = []
        parts.append(f"以下是关于「{query}」的检索结果：\n")

        for i, doc in enumerate(documents[:5]):
            text = doc.get("text", "") or doc.get("content", "")
            file_name = doc.get("file_name", "")
            if text:
                snippet = text[:300].strip()
                source_info = f"（来源: {file_name}）" if file_name else ""
                parts.append(f"{i + 1}. {snippet}...{source_info}")

        return "\n\n".join(parts)

    def _generate_trace_id(self, query: str) -> str:
        """生成追踪 ID"""
        import hashlib
        import uuid

        ts = str(int(time.time() * 1000))
        short_uuid = str(uuid.uuid4())[:8]
        return f"rag_{ts}_{short_uuid}"

    # ========================================================================
    # 统计
    # ========================================================================

    def stats(self) -> Dict[str, Any]:
        """获取 RAG 引擎统计信息

        Returns:
            统计摘要字典
        """
        avg_retrieval = round(self._total_retrieval_time / self._query_count, 1) if self._query_count > 0 else 0.0
        avg_generation = round(self._total_generation_time / self._query_count, 1) if self._query_count > 0 else 0.0

        return {
            "total_queries": self._query_count,
            "avg_retrieval_time_ms": avg_retrieval,
            "avg_generation_time_ms": avg_generation,
            "config": {
                "default_top_k": self.default_top_k,
                "max_context_chars": self.max_context_chars,
                "enable_rerank": self.enable_rerank,
                "enable_cache": self.enable_cache,
            },
        }

    def reset_stats(self) -> None:
        """重置统计计数器"""
        self._query_count = 0
        self._total_retrieval_time = 0.0
        self._total_generation_time = 0.0
        logger.info("[RAGEngine] 统计已重置")


# ============================================================================
# 全局单例
# ============================================================================

_rag_engine_instance: Optional[RAGEngine] = None


def get_rag_engine(
    default_top_k: int = DEFAULT_TOP_K,
    max_context_chars: int = MAX_CONTEXT_CHARS,
    enable_rerank: bool = True,
) -> RAGEngine:
    """获取全局 RAGEngine 单例

    Args:
        default_top_k:     默认检索结果数
        max_context_chars: 上下文最大字符数
        enable_rerank:     是否启用重排序

    Returns:
        RAGEngine 单例
    """
    global _rag_engine_instance
    if _rag_engine_instance is None:
        _rag_engine_instance = RAGEngine(
            default_top_k=default_top_k,
            max_context_chars=max_context_chars,
            enable_rerank=enable_rerank,
        )
    return _rag_engine_instance


# ============================================================================
# 便捷函数
# ============================================================================


async def rag_query(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    enable_generation: bool = True,
    **kwargs: Any,
) -> Dict[str, Any]:
    """便捷函数：执行完整的 RAG 查询

    Args:
        query:            用户查询
        top_k:            检索结果数
        enable_generation: 是否启用 LLM 生成
        **kwargs:         其他 process_query 参数

    Returns:
        process_query 返回的结构化结果
    """
    engine = get_rag_engine()
    context: Dict[str, Any] = {
        "top_k": top_k,
        "enable_generation": enable_generation,
        **kwargs,
    }
    return await engine.process_query(query, context)


async def rag_retrieve(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    **kwargs: Any,
) -> List[Dict[str, Any]]:
    """便捷函数：仅执行检索（不生成回答）

    Args:
        query:   查询字符串
        top_k:   返回结果数
        **kwargs: 其他检索参数

    Returns:
        检索文档列表
    """
    engine = get_rag_engine()
    return await engine.retrieve(query, top_k=top_k, **kwargs)
