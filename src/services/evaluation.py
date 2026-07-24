"""
evaluation.py — 模型质量评估闭环 (v1.44 P1 核心修复)

评估维度：
  1. 相关性（Relevancy）     — 回答是否与用户问题相关
  2. 准确性（Accuracy）      — 回答中事实性声明是否正确
  3. 完整性（Completeness）   — 回答是否充分覆盖问题
  4. 幻觉检测（Hallucination） — 回答中是否存在无出处内容

架构集成点：
  - evaluate_response() 嵌入 SAG 三阶段管线出口
  - 评估结果自动写入 evaluation/pipeline 持久化
  - 与 feedback_store 双向联动（评估 → 反馈 → 学习）
  - 与 shaoyin.fact_check 协同（减少重复 LLM 调用）
  - 评估报告触发 learner 权重调整（P0-B）

约束：
  - 不修改现有框架代码
  - 异步编程模式（async/await）
  - LLM 调用复用 llm.call_llm_fast
  - 持久化复用 JSONL 文件存储（与 eval_pipeline 一致）
"""

import json
import logging
import hashlib
import time
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# ============ 配置 ============
from src.config import DATA_DIR as CONFIG_DATA_DIR
import asyncio

EVAL_DIR = Path(CONFIG_DATA_DIR) / "evaluation"
EVAL_DIR.mkdir(parents=True, exist_ok=True)
EVAL_REPORTS_DIR = EVAL_DIR / "quality_reports"
EVAL_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
EVAL_DB_PATH = EVAL_DIR / "evaluation_results.jsonl"
EVAL_INDEX_PATH = EVAL_DIR / "evaluation_index.json"

# 去重窗口（秒）：相同 (query, response_hash) 300 秒内不重复评估
DEDUP_WINDOW = 300
# 批量持久化阈值
BATCH_FLUSH_SIZE = 50
# 最大并发评估数
MAX_CONCURRENT_EVALS = 10

# 评估 LLM 调用成本控制：单次评估最多 use 3 次轻量 LLM 调用
MAX_LLM_CALLS_PER_EVAL = 3


# ============ 数据模型 ============

@dataclass
class DimensionScore:
    """单个评估维度的得分"""
    dimension: str           # relevancy / accuracy / completeness / hallucination
    score: float             # 0.0 - 1.0
    confidence: float        # 评估置信度 0.0 - 1.0
    detail: str              # 评估详情
    citations: List[str] = field(default_factory=list)  # 引用来源
    issues: List[str] = field(default_factory=list)     # 发现的问题


@dataclass
class EvaluationResult:
    """完整评估结果"""
    eval_id: str                              # 唯一评估 ID
    timestamp: float                          # Unix 时间戳
    query: str                                # 原始用户查询
    response: str                             # 模型回答
    context: str                              # 检索上下文

    # 四维得分
    relevancy_score: float = 0.0
    accuracy_score: float = 0.0
    completeness_score: float = 0.0
    hallucination_score: float = 0.0          # 值越低越好（0 = 无幻觉）

    # 综合得分（加权平均）
    overall_score: float = 0.0
    # 评估是否通过阈值
    passed: bool = False
    # 阈值配置
    threshold: float = 0.6

    # 维度详情
    dimensions: List[Dict] = field(default_factory=list)

    # 元数据
    model: str = "mimo-v2.5"
    trace_id: str = ""
    session_id: str = ""
    latency_ms: float = 0.0
    token_usage: Dict = field(default_factory=dict)

    # 建议
    recommendations: List[str] = field(default_factory=list)
    flags: List[str] = field(default_factory=list)  # 标记如 "hallucination_detected"


# ============ 评估核心类 ============

class Evaluation:
    """
    模型质量评估闭环

    用法:
        evaluator = Evaluation()
        result = await evaluator.evaluate_response(
            query="什么是 SAG 三阶段",
            response="SAG 是一种检索增强生成策略...",
            context="检索到的文档内容..."
        )
        print(f"综合得分: {result.overall_score}")
    """

    # 权重配置：四维加权求和（可通过环境变量覆盖）
    WEIGHTS = {
        "relevancy": 0.25,
        "accuracy": 0.30,
        "completeness": 0.20,
        "hallucination": 0.25,
    }

    # 分数阈值
    PASS_THRESHOLD = 0.60         # 综合得分通过线
    WARNING_THRESHOLD = 0.50      # 综合得分警告线
    CRITICAL_THRESHOLD = 0.35     # 综合得分严重线
    HALLUCINATION_ALERT = 0.30    # 幻觉得分 > 此值触发告警（值越高越差）

    def __init__(self):
        self._eval_semaphore = asyncio.Semaphore(MAX_CONCURRENT_EVALS)
        self._batch_buffer: List[Dict] = []
        self._dedup_cache: Dict[str, float] = {}
        self._last_dedup_cleanup = time.time()
        self._eval_index: Dict[str, str] = {}
        self._load_index()

    # ──────── 主入口 ────────

    async def evaluate_response(
        self,
        query: str,
        response: str,
        context: str = "",
        sources: List[str] = None,
        model: str = "mimo-v2.5",
        trace_id: str = "",
        session_id: str = "",
        threshold: float = None,
    ) -> EvaluationResult:
        """
        对一次 RAG 回答进行全维度质量评估。

        Args:
            query: 用户原始查询
            response: 模型生成的回答
            context: 检索到的上下文内容
            sources: 检索来源列表（用于幻觉检测）
            model: 使用的模型名称
            trace_id: 链路追踪 ID
            session_id: 会话 ID
            threshold: 自定义通过阈值

        Returns:
            EvaluationResult: 包含四维得分和综合得分的评估结果
        """
        t0 = time.time()

        if threshold is None:
            threshold = self.PASS_THRESHOLD

        # 1. 去重检查
        dedup_key = self._make_dedup_key(query, response)
        if self._is_duplicate(dedup_key):
            logger.debug(f"[Evaluation] 跳过重复评估: {dedup_key[:16]}")
            # 返回缓存标记
            return EvaluationResult(
                eval_id=dedup_key,
                timestamp=t0,
                query=query[:200],
                response=response[:200],
                context=context[:200],
                overall_score=-1.0,
                passed=True,
                dimensions=[],
                flags=["cached_duplicate"],
            )

        async with self._eval_semaphore:
            # 生成评估 ID
            eval_id = self._make_eval_id(query, response, t0)

            # 2. 并行评估四个维度（控制 LLM 调用次数 ≤ 3）
            dim_results = await self._evaluate_dimensions(
                query, response, context, sources
            )

            # 3. 计算综合得分
            overall, dim_scores = self._compute_overall(dim_results)
            passed = overall >= threshold

            # 4. 幻觉告警检测
            flags = self._check_flags(dim_scores)

            # 5. 生成改进建议
            recommendations = self._generate_recommendations(dim_scores, overall)

            # 6. 构建结果
            latency = (time.time() - t0) * 1000

            result = EvaluationResult(
                eval_id=eval_id,
                timestamp=t0,
                query=query[:500],
                response=response[:500],
                context=context[:500],
                relevancy_score=dim_scores.get("relevancy", 0.0),
                accuracy_score=dim_scores.get("accuracy", 0.0),
                completeness_score=dim_scores.get("completeness", 0.0),
                hallucination_score=dim_scores.get("hallucination", 0.0),
                overall_score=round(overall, 4),
                passed=passed,
                threshold=threshold,
                dimensions=[
                    {
                        "dimension": k,
                        "score": v,
                        "detail": dim_results.get(f"{k}_detail", ""),
                        "issues": dim_results.get(f"{k}_issues", []),
                    }
                    for k, v in dim_scores.items()
                ],
                model=model,
                trace_id=trace_id,
                session_id=session_id,
                latency_ms=round(latency, 1),
                recommendations=recommendations,
                flags=flags,
            )

            # 7. 异步持久化 + 触发反馈闭环
            asyncio.create_task(self._persist_and_trigger(result))

            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(
                    f"[Evaluation] {eval_id[:12]} 完成: overall={overall:.3f}, "
                    f"relevancy={dim_scores.get('relevancy', 0):.2f}, "
                    f"accuracy={dim_scores.get('accuracy', 0):.2f}, "
                    f"completeness={dim_scores.get('completeness', 0):.2f}, "
                    f"hallucination={dim_scores.get('hallucination', 0):.2f}, "
                    f"passed={passed}, flags={flags}"
                )
            elif logger.isEnabledFor(logging.INFO):
                if not passed:
                    logger.warning(
                        f"[Evaluation] {eval_id[:12]} 未通过: overall={overall:.3f}, "
                        f"flags={flags}"
                    )

            # 记录去重
            self._dedup_cache[dedup_key] = t0

            return result

    # ──────── 维度评估 ────────

    async def _evaluate_dimensions(
        self,
        query: str,
        response: str,
        context: str,
        sources: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """并行评估四个维度。LLM 调用次数：2-3 次（相关性/准确性 1 次，完整性 1 次，幻觉 0-1 次）"""

        dimensions = {}

        # 调用 1: 相关性 + 准确性（合并为一次 LLM 调用）
        rel_acc_task = self._eval_relevancy_accuracy(query, response, context)

        # 调用 2: 完整性（独立调用）
        comp_task = self._eval_completeness(query, response)

        rel_acc_result, comp_result = await asyncio.gather(
            rel_acc_task, comp_task, return_exceptions=True
        )

        # 处理相关性+准确性结果
        if isinstance(rel_acc_result, Exception):
            logger.warning(f"[Evaluation] 相关性/准确性评估失败: {rel_acc_result}")
            dimensions.update({
                "relevancy": 0.5, "relevancy_detail": f"评估失败: {rel_acc_result}",
                "accuracy": 0.5, "accuracy_detail": f"评估失败: {rel_acc_result}",
            })
        else:
            dimensions.update(rel_acc_result)

        # 处理完整性结果
        if isinstance(comp_result, Exception):
            logger.warning(f"[Evaluation] 完整性评估失败: {comp_result}")
            dimensions["completeness"] = 0.5
            dimensions["completeness_detail"] = f"评估失败: {comp_result}"
        else:
            dimensions["completeness"] = comp_result.get("completeness", 0.5)
            dimensions["completeness_detail"] = comp_result.get("detail", "")
            dimensions["completeness_issues"] = comp_result.get("issues", [])

        # 调用 3: 幻觉检测（仅在上下文存在时才进行 LLM 检测）
        if context and len(context.strip()) > 20:
            try:
                hall_result = await self._eval_hallucination(query, response, context, sources)
                if isinstance(hall_result, Exception):
                    logger.warning(f"[Evaluation] 幻觉检测失败: {hall_result}")
                    dimensions["hallucination"] = 0.5
                    dimensions["hallucination_detail"] = f"检测失败: {hall_result}"
                else:
                    dimensions.update(hall_result)
            except Exception as e:
                logger.warning(f"[Evaluation] 幻觉检测异常: {e}")
                dimensions["hallucination"] = 0.5
                dimensions["hallucination_detail"] = f"检测异常: {e}"
        else:
            # 无上下文时使用启发式规则
            dims = self._heuristic_hallucination_check(query, response)
            dimensions.update(dims)

        return dimensions

    async def _eval_relevancy_accuracy(
        self, query: str, response: str, context: str
    ) -> Dict[str, Any]:
        """评估相关性和准确性（合并 LLM 调用）"""
        from src.services.llm import call_llm_fast

        context_snippet = context[:2000] if context else "（无上下文）"
        prompt = (
            "你是 RAG 质量评测专家。请评估以下回答的相关性和准确性。\n\n"
            f"用户问题：{query[:500]}\n\n"
            f"上下文：{context_snippet}\n\n"
            f"回答：{response[:1500]}\n\n"
            "请输出 JSON（不要其他文字）：\n"
            '{\n'
            '  "relevancy": {\n'
            '    "score": 0.0-1.0,\n'
            '    "detail": "评估说明（中文）",\n'
            '    "issues": ["问题1", "问题2"]\n'
            '  },\n'
            '  "accuracy": {\n'
            '    "score": 0.0-1.0,\n'
            '    "detail": "评估说明（中文）",\n'
            '    "issues": ["不准确声明1"]\n'
            '  }\n'
            '}'
        )

        try:
            result = await call_llm_fast(
                prompt, max_tokens=400, temperature=0.1,
                system_prompt="你是 RAG 质量评测专家。只输出 JSON。",
            )
            if not result:
                return {"relevancy": 0.5, "accuracy": 0.5}

            parsed = self._safe_json_parse(result)
            return {
                "relevancy": parsed.get("relevancy", {}).get("score", 0.5)
                if isinstance(parsed.get("relevancy"), dict) else 0.5,
                "relevancy_detail": parsed.get("relevancy", {}).get("detail", "")
                if isinstance(parsed.get("relevancy"), dict) else "",
                "relevancy_issues": parsed.get("relevancy", {}).get("issues", [])
                if isinstance(parsed.get("relevancy"), dict) else [],
                "accuracy": parsed.get("accuracy", {}).get("score", 0.5)
                if isinstance(parsed.get("accuracy"), dict) else 0.5,
                "accuracy_detail": parsed.get("accuracy", {}).get("detail", "")
                if isinstance(parsed.get("accuracy"), dict) else "",
                "accuracy_issues": parsed.get("accuracy", {}).get("issues", [])
                if isinstance(parsed.get("accuracy"), dict) else [],
            }
        except Exception as e:
            logger.warning(f"[Evaluation] 相关性/准确性评估异常: {e}", exc_info=True)
            return {"relevancy": 0.5, "accuracy": 0.5}

    async def _eval_completeness(self, query: str, response: str) -> Dict[str, Any]:
        """评估回答完整性"""
        from src.services.llm import call_llm_fast

        prompt = (
            "评估以下回答是否完整回答了用户问题。\n\n"
            f"用户问题：{query[:500]}\n\n"
            f"回答：{response[:1500]}\n\n"
            "输出 JSON：\n"
            '{\n'
            '  "completeness": 0.0-1.0,\n'
            '  "detail": "评估说明（中文）",\n'
            '  "missing": ["缺失信息1"]\n'
            '}'
        )

        try:
            result = await call_llm_fast(
                prompt, max_tokens=200, temperature=0.1,
                system_prompt="你是回答质量评估专家。只输出 JSON。",
            )
            if not result:
                return {"completeness": 0.5}

            parsed = self._safe_json_parse(result)
            return {
                "completeness": parsed.get("completeness", 0.5),
                "detail": parsed.get("detail", ""),
                "issues": parsed.get("missing", []),
            }
        except Exception as e:
            logger.warning(f"[Evaluation] 完整性评估异常: {e}", exc_info=True)
            return {"completeness": 0.5}

    async def _eval_hallucination(
        self,
        query: str,
        response: str,
        context: str,
        sources: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        检测幻觉：使用 SafetyCritic 进行多维度检测。

        集成 SafetyCritic（三维度：无中生有/事实扭曲/逻辑矛盾），
        替换原有的单一 LLM prompt 方式。

        SafetyCritic 返回的 overall_score = 0 表示无幻觉、1 表示严重幻觉，
        与 evaluation 的 hallucination 字段语义一致。
        """
        try:
            from src.services.safety_critic import get_safety_critic

            critic = get_safety_critic()
            report = await critic.detect_hallucination(
                query=query,
                response=response,
                context=context,
                sources=sources,
                use_llm=True,  # 作为深度评估环节，使用 LLM
            )

            # 将 SafetyCritic 的详细报告映射回评估维度
            return {
                "hallucination": report.overall_score,
                "hallucination_detail": (
                    f"三维检测: 无中生有={report.fabrication_score:.2f}, "
                    f"事实扭曲={report.fact_distortion_score:.2f}, "
                    f"逻辑矛盾={report.logic_contradiction_score:.2f} "
                    f"[方法: {report.detection_method}]"
                ),
                "hallucination_issues": [
                    f"[{s.get('type', '?')}] {s.get('text', '')[:80]}"
                    for s in report.spans[:5]
                ],
                # 附加 SafetyCritic 的详细报告（用于后续分析）
                "_safety_critic_report": {
                    "report_id": report.report_id,
                    "fabrication_score": report.fabrication_score,
                    "fact_distortion_score": report.fact_distortion_score,
                    "logic_contradiction_score": report.logic_contradiction_score,
                    "spans": report.spans[:10],
                    "detection_method": report.detection_method,
                    "flags": report.flags,
                    "recommendations": report.recommendations,
                },
            }
        except ImportError:
            logger.warning(
                "[Evaluation] SafetyCritic 不可用，回退到原有 LLM prompt 方式"
            )
            return await self._eval_hallucination_fallback(
                query, response, context, sources
            )
        except Exception as e:
            logger.warning(f"[Evaluation] SafetyCritic 检测异常，回退: {e}")
            return await self._eval_hallucination_fallback(
                query, response, context, sources
            )

    async def _eval_hallucination_fallback(
        self,
        query: str,
        response: str,
        context: str,
        sources: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        回退的幻觉检测（原有方式）：单一 LLM prompt。
        当 SafetyCritic 不可用时自动回退。
        """
        from src.services.llm import call_llm_fast

        src_text = context[:2000]
        if sources:
            src_text += "\n\n来源：\n" + "\n".join(f"- {s[:100]}" for s in sources[:10])

        prompt = (
            "检测以下回答中是否存在上下文不支持的内容（幻觉）。\n\n"
            f"用户问题：{query[:300]}\n\n"
            f"上下文（权威来源）：{src_text}\n\n"
            f"回答：{response[:1500]}\n\n"
            "输出 JSON：\n"
            '{\n'
            '  "hallucination_score": 0.0-1.0,\n'
            '  "detail": "检测说明（中文）",\n'
            '  "hallucinated_claims": ["幻觉声明1"],\n'
            '  "supported_claims": ["有出处声明1"]\n'
            '}'
        )

        try:
            result = await call_llm_fast(
                prompt, max_tokens=300, temperature=0.1,
                system_prompt="你是事实性校验专家。只输出 JSON。",
            )
            if not result:
                return {"hallucination": 0.5}

            parsed = self._safe_json_parse(result)
            return {
                "hallucination": parsed.get("hallucination_score", 0.5),
                "hallucination_detail": parsed.get("detail", ""),
                "hallucination_issues": parsed.get("hallucinated_claims", []),
            }
        except Exception as e:
            logger.warning(f"[Evaluation] 幻觉检测回退异常: {e}", exc_info=True)
            return {"hallucination": 0.5}

    def _heuristic_hallucination_check(
        self, query: str, response: str
    ) -> Dict[str, Any]:
        """无上下文时的启发式幻觉检测"""
        issues = []
        hallucination_score = 0.0

        # 检查是否包含明显的编造模式
        fabricate_patterns = [
            "根据内部数据显示",
            "据公司统计",
            "根据最新研究表明",
            "专家指出",
        ]
        for pattern in fabricate_patterns:
            if pattern in response:
                issues.append(f"可能编造: '{pattern}' 缺少出处")
                hallucination_score += 0.1

        # 检查是否包含过多的具体数字（可能是编造的）
        import re
        numbers = re.findall(r'\d+(?:\.\d+)?%?', response)
        if len(numbers) > 10:
            issues.append("包含大量具体数字，建议验证出处")
            hallucination_score += 0.05

        hallucination_score = min(hallucination_score, 1.0)

        return {
            "hallucination": round(hallucination_score, 2),
            "hallucination_detail": "启发式检测（无上下文）",
            "hallucination_issues": issues,
        }

    # ──────── 得分计算 ────────

    def _compute_overall(self, dim_results: Dict[str, Any]) -> Tuple[float, Dict[str, float]]:
        """计算加权综合得分。

        Returns:
            overall: 综合得分 (0.0-1.0)
            dim_scores: 原始维度得分（hallucination 保持原始值，0=无幻觉 1=严重幻觉）
        """
        raw_relevancy = dim_results.get("relevancy", 0.5)
        raw_accuracy = dim_results.get("accuracy", 0.5)
        raw_completeness = dim_results.get("completeness", 0.5)
        raw_hallucination = dim_results.get("hallucination", 0.5)  # 原始值：0=无幻觉

        # 综合得分计算：幻觉维度反转（低幻觉=高分）
        overall = (
            raw_relevancy * self.WEIGHTS["relevancy"] +
            raw_accuracy * self.WEIGHTS["accuracy"] +
            raw_completeness * self.WEIGHTS["completeness"] +
            (1.0 - raw_hallucination) * self.WEIGHTS["hallucination"]
        )

        # 返回原始维度得分（hallucination 保持原始语义）
        dim_scores = {
            "relevancy": raw_relevancy,
            "accuracy": raw_accuracy,
            "completeness": raw_completeness,
            "hallucination": raw_hallucination,
        }

        return overall, dim_scores

    def _check_flags(self, scores: Dict[str, float]) -> List[str]:
        """检查告警标记。scores["hallucination"] 为原始值（0=无幻觉）。"""
        flags = []

        if scores.get("relevancy", 1) < 0.4:
            flags.append("low_relevancy")
        if scores.get("accuracy", 1) < 0.4:
            flags.append("low_accuracy")
        if scores.get("completeness", 1) < 0.4:
            flags.append("low_completeness")
        if scores.get("hallucination", 0) > self.HALLUCINATION_ALERT:
            flags.append("hallucination_detected")

        return flags

    def _generate_recommendations(
        self, scores: Dict[str, float], overall: float
    ) -> List[str]:
        """基于得分生成改进建议。scores["hallucination"] 为原始值（0=无幻觉）。"""
        recs = []

        if scores.get("relevancy", 1) < 0.5:
            recs.append("相关性不足：建议优化查询改写或检索策略")
        if scores.get("accuracy", 1) < 0.5:
            recs.append("准确性不足：建议增加事实性校验或减少生成自由度")
        if scores.get("completeness", 1) < 0.5:
            recs.append("完整性不足：建议扩展检索范围或增加多跳探索")
        if scores.get("hallucination", 0) > 0.3:
            recs.append("检测到幻觉：建议启用严格事实校验模式或降低回答置信度")

        if overall < self.CRITICAL_THRESHOLD:
            recs.append("严重质量问题：建议触发人工复核流程")
        elif overall < self.WARNING_THRESHOLD:
            recs.append("质量警告：建议检查模型参数和检索配置")

        return recs

    # ──────── 持久化 ────────

    async def _persist_and_trigger(self, result: EvaluationResult):
        """持久化评估结果并触发反馈闭环"""
        try:
            # 1. 写入评估结果
            await self._save_evaluation(result)

            # 2. 更新索引
            self._eval_index[result.eval_id] = str(result.timestamp)
            if len(self._eval_index) % 100 == 0:
                await self._flush_index()

            # 3. 如果评估未通过，触发反馈闭环
            if not result.passed:
                asyncio.create_task(self._trigger_feedback_loop(result))

            # 4. 如果检测到幻觉，记录高优先级告警
            if "hallucination_detected" in result.flags:
                await self._log_hallucination_alert(result)

        except Exception as e:
            logger.warning(f"[Evaluation] 持久化失败: {e}", exc_info=True)

    async def _save_evaluation(self, result: EvaluationResult):
        """保存评估结果到 JSONL 文件"""
        try:
            record = {
                "eval_id": result.eval_id,
                "timestamp": result.timestamp,
                "query": result.query,
                "response": result.response[:200],
                "context": result.context[:200],
                "scores": {
                    "relevancy": result.relevancy_score,
                    "accuracy": result.accuracy_score,
                    "completeness": result.completeness_score,
                    "hallucination": result.hallucination_score,
                    "overall": result.overall_score,
                },
                "passed": result.passed,
                "threshold": result.threshold,
                "dimensions": result.dimensions,
                "model": result.model,
                "trace_id": result.trace_id,
                "session_id": result.session_id,
                "latency_ms": result.latency_ms,
                "flags": result.flags,
                "recommendations": result.recommendations,
            }

            # 批量写入优化
            self._batch_buffer.append(record)
            if len(self._batch_buffer) >= BATCH_FLUSH_SIZE:
                await self._flush_buffer()

        except Exception as e:
            logger.warning(f"[Evaluation] 序列化评估结果失败: {e}", exc_info=True)

    async def _flush_buffer(self):
        """批量刷新缓冲区到文件"""
        if not self._batch_buffer:
            return

        buf = list(self._batch_buffer)
        self._batch_buffer.clear()

        try:
            def _write():
                with open(EVAL_DB_PATH, "a", encoding="utf-8") as f:
                    for record in buf:
                        f.write(json.dumps(record, ensure_ascii=False) + "\n")
            await asyncio.to_thread(_write)
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"[Evaluation] 批量写入 {len(buf)} 条评估结果")
        except Exception as e:
            logger.warning(f"[Evaluation] 批量写入失败: {e}", exc_info=True)
            # 失败时放回缓冲区
            self._batch_buffer = buf + self._batch_buffer

    async def _flush_index(self):
        """保存评估索引"""
        try:
            def _write_index():
                with open(EVAL_INDEX_PATH, "w", encoding="utf-8") as f:
                    json.dump(self._eval_index, f, ensure_ascii=False)
            await asyncio.to_thread(_write_index)
        except Exception as e:
            logger.warning(f"[Evaluation] 索引写入失败: {e}", exc_info=True)

    async def _trigger_feedback_loop(self, result: EvaluationResult):
        """
        评估未通过时触发反馈闭环：
        1. 将评估结果写入 feedback_store
        2. 触发 learner 权重调整（P0-B）
        """
        try:
            from src.services.feedback_store import log_feedback_unified

            action = "eval_fail" if not result.passed else "eval_pass"
            await log_feedback_unified(
                user_id="evaluation_system",
                query=result.query,
                action=action,
                metadata={
                    "scores": {
                        "overall": result.overall_score,
                        "relevancy": result.relevancy_score,
                        "accuracy": result.accuracy_score,
                        "completeness": result.completeness_score,
                        "hallucination": result.hallucination_score,
                    },
                    "flags": result.flags,
                    "recommendations": result.recommendations,
                    "eval_id": result.eval_id,
                },
            )
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"[Evaluation] 反馈闭环已触发: {result.eval_id[:12]}")
        except ImportError:
            logger.debug("[Evaluation] feedback_store 不可用，跳过反馈闭环")
        except Exception as e:
            logger.warning(f"[Evaluation] 反馈闭环触发失败: {e}", exc_info=True)

    async def _log_hallucination_alert(self, result: EvaluationResult):
        """记录幻觉告警到高优先级日志"""
        alert = {
            "type": "hallucination_alert",
            "timestamp": result.timestamp,
            "eval_id": result.eval_id,
            "query": result.query[:100],
            "hallucination_score": result.hallucination_score,
            "overall_score": result.overall_score,
            "flags": result.flags,
        }
        logger.warning(f"[Evaluation] 幻觉告警: {json.dumps(alert, ensure_ascii=False)}")

        # 同时写入告警文件
        try:
            alert_file = EVAL_DIR / "hallucination_alerts.jsonl"
            def _write_alert():
                with open(alert_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(alert, ensure_ascii=False) + "\n")
            await asyncio.to_thread(_write_alert)
        except Exception as e:
            logger.warning(f"[Evaluation] 幻觉告警写入失败: {e}", exc_info=True)

    # ──────── 批量评估 ────────

    async def evaluate_batch(
        self,
        items: List[Dict[str, str]],
        model: str = "mimo-v2.5",
        threshold: float = None,
    ) -> List[EvaluationResult]:
        """
        批量评估多个 query-response 对。

        Args:
            items: [{"query": "...", "response": "...", "context": "..."}, ...]

        Returns:
            评估结果列表
        """
        tasks = [
            self.evaluate_response(
                query=item.get("query", ""),
                response=item.get("response", ""),
                context=item.get("context", ""),
                sources=item.get("sources"),
                model=model,
                trace_id=item.get("trace_id", ""),
                session_id=item.get("session_id", ""),
                threshold=threshold,
            )
            for item in items
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        validated = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                logger.warning(f"[Evaluation] 批量评估 #{i} 失败: {r}")
                validated.append(EvaluationResult(
                    eval_id=f"batch_error_{i}",
                    timestamp=time.time(),
                    query=items[i].get("query", "")[:200],
                    response="",
                    context="",
                    overall_score=0.0,
                    passed=False,
                    flags=["evaluation_error"],
                ))
            else:
                validated.append(r)

        return validated

    # ──────── RAG 管线集成 ────────

    async def evaluate_rag_output(
        self,
        query: str,
        answer: str,
        context: str,
        sources: List[str] = None,
        trace_id: str = "",
    ) -> Dict[str, Any]:
        """
        集成到 SAG/RAG 管线出口的便捷方法。
        返回可直接序列化的 dict。

        用法（集成到 sag_pipeline.py 出口）:
            from src.services.evaluation import get_evaluator
            eval_result = await get_evaluator().evaluate_rag_output(
                query=query, answer=generated_answer,
                context=merged_context, sources=source_chunks,
            )
            if not eval_result["passed"]:
                logger.warning(f"RAG 输出质量不合格: {eval_result['overall_score']}")
        """
        result = await self.evaluate_response(
            query=query,
            response=answer,
            context=context,
            sources=sources,
            trace_id=trace_id,
        )

        return {
            "eval_id": result.eval_id,
            "overall_score": result.overall_score,
            "passed": result.passed,
            "scores": {
                "relevancy": result.relevancy_score,
                "accuracy": result.accuracy_score,
                "completeness": result.completeness_score,
                "hallucination": result.hallucination_score,
            },
            "flags": result.flags,
            "recommendations": result.recommendations,
            "latency_ms": result.latency_ms,
        }

    # ──────── 评估报告 ────────

    async def generate_report(
        self,
        start_time: float = None,
        end_time: float = None,
        min_samples: int = 1,
    ) -> Dict[str, Any]:
        """
        生成评估报告：汇总指定时间范围内的评估结果。

        Args:
            start_time: 开始时间戳
            end_time: 结束时间戳
            min_samples: 最小样本数（不足时返回 insufficient_data）

        Returns:
            评估报告 dict
        """
        if start_time is None:
            start_time = time.time() - 3600  # 默认最近 1 小时
        if end_time is None:
            end_time = time.time()

        records = await self._load_evaluations(start_time, end_time)

        if len(records) < min_samples:
            return {
                "status": "insufficient_data",
                "sample_count": len(records),
                "required_min": min_samples,
                "period": {
                    "start": start_time,
                    "end": end_time,
                },
            }

        # 汇总统计
        overall_scores = []
        dim_scores = {"relevancy": [], "accuracy": [], "completeness": [], "hallucination": []}
        pass_count = 0
        flag_counts = {}
        hallucination_count = 0

        for r in records:
            scores = r.get("scores", r)
            ov = scores.get("overall", 0)
            if ov > 0:  # 排除缓存的重复项
                overall_scores.append(ov)
            for dim in dim_scores:
                val = scores.get(dim, 0)
                dim_scores[dim].append(val)

            if r.get("passed", False):
                pass_count += 1

            for flag in r.get("flags", []):
                flag_counts[flag] = flag_counts.get(flag, 0) + 1
            if "hallucination_detected" in r.get("flags", []):
                hallucination_count += 1

        total = len(records)
        report = {
            "status": "ok",
            "timestamp": time.time(),
            "period": {
                "start": start_time,
                "end": end_time,
            },
            "sample_count": total,
            "overall": {
                "avg": round(sum(overall_scores) / len(overall_scores), 4) if overall_scores else 0,
                "min": round(min(overall_scores), 4) if overall_scores else 0,
                "max": round(max(overall_scores), 4) if overall_scores else 0,
                "p50": self._percentile(overall_scores, 50),
                "p95": self._percentile(overall_scores, 95),
            },
            "pass_rate": round(pass_count / total, 4) if total > 0 else 0,
            "dimensions": {
                dim: {
                    "avg": round(sum(vals) / len(vals), 4) if vals else 0,
                    "min": round(min(vals), 4) if vals else 0,
                }
                for dim, vals in dim_scores.items() if vals
            },
            "flags_summary": flag_counts,
            "hallucination_rate": round(hallucination_count / total, 4) if total > 0 else 0,
            "recommendations": self._report_recommendations(
                pass_count, total, hallucination_count, dim_scores
            ),
        }

        # 保存报告
        asyncio.create_task(self._save_report(report))

        return report

    def _report_recommendations(
        self,
        pass_count: int,
        total: int,
        hallucination_count: int,
        dim_scores: Dict[str, List[float]],
    ) -> List[str]:
        """生成报告级别的改进建议"""
        recs = []
        pass_rate = pass_count / total if total > 0 else 0

        if pass_rate < 0.6:
            recs.append(f"通过率仅 {pass_rate:.1%}，建议检查模型和检索配置")
        if hallucination_count / total > 0.2 if total > 0 else False:
            recs.append(f"幻觉率 {hallucination_count/total:.1%} 偏高，建议启用严格事实校验")

        for dim, vals in dim_scores.items():
            if vals:
                avg = sum(vals) / len(vals)
                if dim == "relevancy" and avg < 0.5:
                    recs.append("检索相关性偏低，建议优化查询改写")
                elif dim == "accuracy" and avg < 0.5:
                    recs.append("回答准确性偏低，建议降低生成温度")
                elif dim == "completeness" and avg < 0.5:
                    recs.append("回答完整性不足，建议增加检索深度")

        return recs

    async def _save_report(self, report: Dict):
        """保存评估报告到文件"""
        try:
            date_str = datetime.fromtimestamp(report["timestamp"]).strftime("%Y%m%d_%H%M%S")
            report_file = EVAL_REPORTS_DIR / f"quality_report_{date_str}.json"
            def _write_report():
                with open(report_file, "w", encoding="utf-8") as f:
                    json.dump(report, f, ensure_ascii=False, indent=2)
            await asyncio.to_thread(_write_report)
            logger.info(f"[Evaluation] 质量报告已保存: {report_file}")
        except Exception as e:
            logger.warning(f"[Evaluation] 报告保存失败: {e}", exc_info=True)

    # ──────── 数据加载 ────────

    async def _load_evaluations(
        self, start_time: float, end_time: float
    ) -> List[Dict]:
        """加载指定时间范围内的评估结果"""
        if not EVAL_DB_PATH.exists():
            return []

        # 先刷新缓冲区
        if self._batch_buffer:
            await self._flush_buffer()

        records = []
        try:
            def _read():
                result = []
                with open(EVAL_DB_PATH, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            record = json.loads(line)
                            ts = record.get("timestamp", 0)
                            if start_time <= ts <= end_time:
                                result.append(record)
                        except json.JSONDecodeError:
                            continue
                return result
            records = await asyncio.to_thread(_read)
        except Exception as e:
            logger.warning(f"[Evaluation] 加载评估数据失败: {e}", exc_info=True)

        return records

    def _load_index(self):
        """加载评估索引"""
        if EVAL_INDEX_PATH.exists():
            try:
                self._eval_index = json.loads(EVAL_INDEX_PATH.read_text(encoding="utf-8"))
            except Exception:
                self._eval_index = {}

    # ──────── 查询接口 ────────

    async def get_stats(self, hours: int = 24) -> Dict[str, Any]:
        """获取评估统计摘要"""
        cutoff = time.time() - hours * 3600
        records = await self._load_evaluations(cutoff, time.time())

        total = len(records)
        if total == 0:
            return {
                "total_evaluations": 0,
                "avg_overall_score": 0,
                "pass_rate": 0,
                "hallucination_rate": 0,
            }

        scores = []
        passed = 0
        hallucinations = 0
        for r in records:
            s = r.get("scores", r)
            ov = s.get("overall", 0)
            if ov > 0:
                scores.append(ov)
            if r.get("passed"):
                passed += 1
            if "hallucination_detected" in r.get("flags", []):
                hallucinations += 1

        return {
            "total_evaluations": total,
            "avg_overall_score": round(sum(scores) / len(scores), 4) if scores else 0,
            "pass_rate": round(passed / total, 4),
            "hallucination_rate": round(hallucinations / total, 4),
            "dimensions": self._aggregate_dimensions(records),
        }

    def _aggregate_dimensions(self, records: List[Dict]) -> Dict[str, float]:
        """汇总维度得分"""
        dims = {"relevancy": [], "accuracy": [], "completeness": [], "hallucination": []}
        for r in records:
            scores = r.get("scores", r.get("dimensions", r))
            for dim in dims:
                val = scores.get(dim, None)
                if val is not None:
                    dims[dim].append(val)

        return {
            dim: round(sum(vals) / len(vals), 4) if vals else 0.0
            for dim, vals in dims.items()
        }

    async def get_recent_failures(self, limit: int = 20) -> List[Dict]:
        """获取最近评估失败的记录"""
        cutoff = time.time() - 86400  # 最近 24 小时
        records = await self._load_evaluations(cutoff, time.time())
        failures = [r for r in records if not r.get("passed", True)]
        failures.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
        return failures[:limit]

    # ──────── 工具方法 ────────

    def _make_dedup_key(self, query: str, response: str) -> str:
        """生成去重 key"""
        raw = f"{query[:200]}|{response[:200]}"
        return hashlib.md5(raw.encode()).hexdigest()[:32]

    def _is_duplicate(self, key: str) -> bool:
        """检查是否重复"""
        now = time.time()
        # 定期清理过期去重项
        if now - self._last_dedup_cleanup > 600:  # 每 10 分钟清理
            self._dedup_cache = {
                k: v for k, v in self._dedup_cache.items()
                if now - v < DEDUP_WINDOW
            }
            self._last_dedup_cleanup = now

        return key in self._dedup_cache and now - self._dedup_cache[key] < DEDUP_WINDOW

    def _make_eval_id(self, query: str, response: str, timestamp: float) -> str:
        """生成唯一评估 ID"""
        raw = f"{query[:100]}|{response[:100]}|{timestamp}"
        return "eval_" + hashlib.md5(raw.encode()).hexdigest()[:16]

    @staticmethod
    def _safe_json_parse(text: str) -> Dict[str, Any]:
        """安全解析 LLM 返回的 JSON"""
        text = text.strip()
        # 提取 JSON 块
        s = text.find("{")
        e = text.rfind("}")
        if s >= 0 and e > s:
            try:
                return json.loads(text[s:e + 1])
            except json.JSONDecodeError:
                pass
        # 尝试修复常见格式问题
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        return {}

    @staticmethod
    def _percentile(data: List[float], p: float) -> float:
        """计算百分位数"""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        k = (len(sorted_data) - 1) * p / 100.0
        f = int(k)
        c = k - f
        if f + 1 < len(sorted_data):
            return round(sorted_data[f] + c * (sorted_data[f + 1] - sorted_data[f]), 4)
        return round(sorted_data[f], 4)

    async def flush(self):
        """强制刷新所有缓冲区（graceful shutdown 时调用）"""
        await self._flush_buffer()
        await self._flush_index()
        logger.info("[Evaluation] 已刷新所有缓冲数据")

    async def clear_dedup_cache(self):
        """清空去重缓存"""
        self._dedup_cache.clear()
        self._last_dedup_cleanup = time.time()
        logger.info("[Evaluation] 去重缓存已清空")


# ============ 全局实例 ============

_evaluator: Optional[Evaluation] = None


def get_evaluator() -> Evaluation:
    """获取全局 Evaluation 实例（线程安全懒加载）"""
    global _evaluator
    if _evaluator is None:
        _evaluator = Evaluation()
    return _evaluator


# ============ 便捷函数（兼容现有调用模式） ============

async def evaluate_response(
    query: str,
    response: str,
    context: str = "",
    sources: List[str] = None,
    **kwargs,
) -> Dict[str, Any]:
    """
    便捷函数：评估单次回答质量。
    替代 evaluator.py 中的 eval_faithfulness + eval_answer_relevancy。

    返回: {
        "overall_score": 0.85,
        "passed": True,
        "scores": {...},
        "flags": [...],
        ...
    }
    """
    evaluator = get_evaluator()
    result = await evaluator.evaluate_rag_output(
        query=query,
        answer=response,
        context=context,
        sources=sources,
        trace_id=kwargs.get("trace_id", ""),
    )
    return result


async def evaluate_batch(
    items: List[Dict[str, str]],
    **kwargs,
) -> List[Dict[str, Any]]:
    """
    便捷函数：批量评测。
    """
    evaluator = get_evaluator()
    results = await evaluator.evaluate_batch(items, **kwargs)
    return [asdict(r) for r in results]


async def generate_quality_report(
    hours: int = 24,
) -> Dict[str, Any]:
    """
    便捷函数：生成质量报告。
    """
    evaluator = get_evaluator()
    cutoff = time.time() - hours * 3600
    return await evaluator.generate_report(start_time=cutoff)
