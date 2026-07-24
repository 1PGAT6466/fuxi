"""
safety_critic.py — 幻觉检测机制 (v1.44 P1 核心修复)

SafetyCritic 提供细粒度的幻觉检测，支持：
  - 维度 1: fabrication (无中生有) — 回答声称了上下文中完全不存在的事实
  - 维度 2: fact_distortion (事实扭曲) — 回答修改了上下文中的具体数据/参数
  - 维度 3: logic_contradiction (逻辑矛盾) — 回答与上下文存在逻辑冲突

集成方式：
  - 被 evaluation.py 的 Evaluation._eval_hallucination 调用
  - 返回结构化幻觉报告：类型、置信度、位置标注
  - 与 shaoyin.fact_check 协同（SafetyCritic 多维度 vs fact_check 二元验证）

架构约束：
  - 不修改现有框架代码
  - 异步编程模式（async/await）
  - LLM 调用复用 llm.call_llm_fast
"""

import json
import logging
import hashlib
import re
import asyncio
import time
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field, asdict
from pathlib import Path

logger = logging.getLogger(__name__)

# ============ 配置 ============
from src.config import DATA_DIR as CONFIG_DATA_DIR

CRITIC_DIR = Path(CONFIG_DATA_DIR) / "safety_critic"
CRITIC_DIR.mkdir(parents=True, exist_ok=True)
HALLUCINATION_LOG_PATH = CRITIC_DIR / "hallucination_events.jsonl"

# 幻觉检测 LLM 调用最大 token 数
CRITIC_MAX_TOKENS = 500
# 幻觉检测 LLM 温度（低温度确保一致性）
CRITIC_TEMPERATURE = 0.1
# 上下文截断长度
CONTEXT_MAX_CHARS = 2500
# 回答截断长度
RESPONSE_MAX_CHARS = 2000

# 幻觉类型定义
HALLUCINATION_TYPES = {
    "fabrication": "无中生有 — 回答声称了上下文中完全不存在的事实或数据",
    "fact_distortion": "事实扭曲 — 回答修改了上下文中的具体数值、名称或属性",
    "logic_contradiction": "逻辑矛盾 — 回答的推论与上下文的逻辑链条冲突",
}

# 内置无出处模式（用于启发式预筛）
FABRICATION_PATTERNS = [
    (r"根据(?:内部|最新|权威|可靠).{0,6}(?:数据|研究|报告|统计|分析)显示", "无出处权威引用"),
    (r"(?:据|根据)(?:公司|我们|我方|本平台).{0,4}(?:统计|测算|估算|监测)", "无出处内部数据"),
    (r"(?:专家|学者|业内人士).{0,4}(?:指出|表示|认为)", "匿名权威背书"),
    (r"(?:在过去|近|最近)\s*\d+\s*(?:年|月|天|周).{0,10}(?:首次|第一次|唯一)", "无可验证时间断言"),
    (r"(?:覆盖|服务|触达)\s*\d+[万亿亿千万百]?\s*(?:用户|客户|企业|设备)", "夸大覆盖数字"),
    (r"(?:准确率|精确度|召回率|F1)\s*(?:达到|高达|超过|为)\s*\d{2,3}(?:\.\d+)?\s*%", "无出处指标声称"),
    (r"\d{4}\s*年.{0,6}(?:荣获|获得|被评为|认定为)", "无法验证的荣誉声明"),
    (r"(?:行业|全球|国内)\s*(?:首个|第一|领先|独家|唯一)", "无法验证的排名声称"),
]

# 事实扭曲检测模式（数字对比启发式）
FACT_DISTORTION_PATTERNS = [
    # 检测上下文中有明确数字但回答使用了不同数字
    (r"(\d+(?:\.\d+)?)\s*(?:mm|cm|m|km|g|kg|t|ms|s|min|h|元|万|亿|%|°C|℃)", "数值型事实"),
    (r"(?:ADR|RFC|ISO|GB|T)\s*-?\d+", "标准/规范引用号"),
    (r"(?:v|V|version)\s*\d+\.\d+", "版本号"),
]


# ============ 数据模型 ============

@dataclass
class HallucinationSpan:
    """幻觉片段标注"""
    type: str                    # fabrication / fact_distortion / logic_contradiction
    text: str                    # 具体文本片段
    start_pos: int               # 在回答中的起始位置（字符偏移）
    end_pos: int                 # 结束位置
    confidence: float            # 置信度 0.0-1.0
    reason: str                  # 判定理由
    conflicting_context: str = ""  # 冲突的上下文原文（如有）
    severity: str = "medium"     # low / medium / high / critical


@dataclass
class HallucinationReport:
    """幻觉检测完整报告"""
    report_id: str                           # 唯一报告 ID
    timestamp: float                         # Unix 时间戳
    query: str                               # 原始查询
    response: str                            # 模型回答（截断）
    context: str                             # 检索上下文（截断）

    # 汇总
    has_hallucination: bool = False          # 是否存在幻觉
    overall_score: float = 0.0               # 幻觉程度 0=无幻觉 1=严重幻觉
    confidence: float = 0.0                  # 整体检测置信度

    # 三维度
    fabrication_score: float = 0.0           # 无中生有得分
    fact_distortion_score: float = 0.0       # 事实扭曲得分
    logic_contradiction_score: float = 0.0   # 逻辑矛盾得分

    # 详细信息
    spans: List[Dict] = field(default_factory=list)       # 幻觉片段列表
    claims_verified: int = 0                 # 已验证的声明数
    claims_supported: int = 0                # 有出处支持的声明数
    claims_unsupported: int = 0              # 无出处支持的声明数

    # 元数据
    detection_method: str = "llm"            # llm / heuristic / hybrid
    llm_calls: int = 0                       # LLM 调用次数
    latency_ms: float = 0.0                  # 检测耗时

    # 建议
    recommendations: List[str] = field(default_factory=list)
    flags: List[str] = field(default_factory=list)


# ============ 核心类 ============

class SafetyCritic:
    """
    幻觉检测器 — 多维度检测回答中的幻觉内容。

    用法:
        critic = SafetyCritic()
        report = await critic.detect_hallucination(
            query="模具导向柱直径标准是多少？",
            response="导向柱直径 D=25mm，适用于 5050 以下模胚",
            context="导向柱直径 D=20mm，模胚 4040 以下使用 A 类",
        )
        if report.has_hallucination:
            for span in report.spans:
                print(f"[{span['type']}] {span['text']} - {span['reason']}")

    检测策略（三阶段管线）:
      1. 启发式预筛 — 正则匹配快速识别明显模式（<1ms）
      2. LLM 深度检测 — 语义级分析和位置标注（100-500ms）
      3. 交叉验证 — 结合启发式结果校准 LLM 输出
    """

    # LLM 多维度检测的 system prompt
    SYSTEM_PROMPT = (
        "你是一个专业的事实性校验专家。你的任务是逐句对比「回答」和「权威上下文」，"
        "找出所有幻觉内容。你需要以 JSON 格式输出检测结果。"
    )

    # LLM 多维度检测的 user prompt 模板
    DETECTION_PROMPT_TEMPLATE = (
        "请仔细对比以下「回答」和「权威上下文」，检测是否存在幻觉。\n\n"
        "【检测维度】\n"
        "1. fabrication (无中生有)：回答中声明了上下文中完全不存在的事实、数据、名称\n"
        "2. fact_distortion (事实扭曲)：回答修改了上下文中的具体数值、名称、属性\n"
        "3. logic_contradiction (逻辑矛盾)：回答的推论与上下文逻辑冲突\n\n"
        "【用户问题】\n{query}\n\n"
        "【权威上下文】\n{context}\n\n"
        "【待检测回答】\n{response}\n\n"
        "【输出要求】\n"
        "请输出严格 JSON 格式（不要 markdown 代码块）：\n"
        "{{\n"
        '  "overall_score": 0.0-1.0,\n'
        '  "confidence": 0.0-1.0,\n'
        '  "fabrication": {{\n'
        '    "score": 0.0-1.0,\n'
        '    "spans": [\n'
        '      {{"text": "幻觉文本片段", "reason": "判定理由", "start_pos": 0, "end_pos": 10, "confidence": 0.9, "severity": "high"}}\n'
        '    ]\n'
        '  }},\n'
        '  "fact_distortion": {{\n'
        '    "score": 0.0-1.0,\n'
        '    "spans": [\n'
        '      {{"text": "被扭曲的文本", "correct_value": "上下文中的正确值", "reason": "扭曲理由", "start_pos": 0, "end_pos": 10, "confidence": 0.9, "severity": "high"}}\n'
        '    ]\n'
        '  }},\n'
        '  "logic_contradiction": {{\n'
        '    "score": 0.0-1.0,\n'
        '    "spans": [\n'
        '      {{"text": "矛盾文本", "reason": "矛盾说明", "start_pos": 0, "end_pos": 10, "confidence": 0.9, "severity": "high"}}\n'
        '    ]\n'
        '  }},\n'
        '  "recommendations": ["建议1", "建议2"]\n'
        '}}'
    )

    def __init__(self):
        self._cache: Dict[str, HallucinationReport] = {}
        self._cache_ttl = 300  # 5 分钟缓存 TTL
        self._stats = {
            "total_detections": 0,
            "hallucinations_found": 0,
            "avg_latency_ms": 0.0,
            "method_distribution": {"llm": 0, "heuristic": 0, "hybrid": 0},
        }

    # ──────── 主入口 ────────

    async def detect_hallucination(
        self,
        query: str,
        response: str,
        context: str = "",
        sources: Optional[List[str]] = None,
        use_llm: bool = True,
        threshold: float = 0.3,
    ) -> HallucinationReport:
        """
        对一次问答进行多维度幻觉检测。

        Args:
            query: 用户原始查询
            response: 模型生成的回答
            context: 检索到的上下文内容（权威来源）
            sources: 额外的来源列表
            use_llm: 是否使用 LLM 进行深度检测（False 则仅使用启发式）
            threshold: 幻觉判定阈值（overall_score >= threshold 视为存在幻觉）

        Returns:
            HallucinationReport: 包含三维度得分、片段标注和建议的检测报告
        """
        t0 = time.time()

        # 生成报告 ID
        report_id = self._make_report_id(query, response, t0)

        # 1. 启发式预筛（始终执行，<1ms）
        heuristic_spans = self._heuristic_detect(query, response, context)

        # 2. LLM 深度检测（可选）
        llm_result = {}
        llm_calls = 0
        if use_llm and context and len(context.strip()) > 20:
            try:
                llm_result = await self._llm_detect(query, response, context, sources)
                llm_calls = 1
            except Exception as e:
                logger.warning(f"[SafetyCritic] LLM 检测失败，降级为纯启发式: {e}")
                llm_result = {}

        # 3. 交叉验证：合并启发式和 LLM 结果
        spans = self._merge_spans(
            heuristic_spans,
            llm_result.get("fabrication", {}).get("spans", []),
            llm_result.get("fact_distortion", {}).get("spans", []),
            llm_result.get("logic_contradiction", {}).get("spans", []),
            response,
        )

        # 4. 计算综合得分
        fab_score = self._compute_dimension_score(
            heuristic_spans.get("fabrication", []),
            llm_result.get("fabrication", {}),
        )
        dist_score = self._compute_dimension_score(
            heuristic_spans.get("fact_distortion", []),
            llm_result.get("fact_distortion", {}),
        )
        logic_score = self._compute_dimension_score(
            heuristic_spans.get("logic_contradiction", []),
            llm_result.get("logic_contradiction", {}),
        )

        # 综合幻觉得分 = 三维度最大值（只要有任一维度有问题就算有幻觉）
        overall_score = max(fab_score, dist_score, logic_score)

        # 检测置信度
        if llm_result:
            confidence = llm_result.get("confidence", 0.7)
        else:
            # 纯启发式置信度较低
            confidence = 0.5 if heuristic_spans else 0.9

        # 判定是否有幻觉
        has_hallucination = overall_score >= threshold

        # 5. 生成建议和标记
        recommendations = self._generate_recommendations(
            spans, fab_score, dist_score, logic_score
        )
        if llm_result and "recommendations" in llm_result:
            recommendations.extend(
                r for r in llm_result["recommendations"]
                if r not in recommendations
            )

        flags = self._determine_flags(spans, has_hallucination, overall_score)

        # 统计声明验证
        claims_total = len(heuristic_spans.get("claims_checked", []))
        claims_supported = sum(
            1 for c in heuristic_spans.get("claims_checked", [])
            if c.get("supported", False)
        )

        # 确定检测方法
        if llm_result and heuristic_spans:
            method = "hybrid"
        elif llm_result:
            method = "llm"
        else:
            method = "heuristic"

        # 6. 构建报告
        latency = (time.time() - t0) * 1000

        report = HallucinationReport(
            report_id=report_id,
            timestamp=t0,
            query=query[:500],
            response=response[:500],
            context=context[:500],
            has_hallucination=has_hallucination,
            overall_score=round(overall_score, 4),
            confidence=round(confidence, 4),
            fabrication_score=round(fab_score, 4),
            fact_distortion_score=round(dist_score, 4),
            logic_contradiction_score=round(logic_score, 4),
            spans=[
                {
                    "type": s.get("type", "unknown"),
                    "text": s.get("text", ""),
                    "start_pos": s.get("start_pos", -1),
                    "end_pos": s.get("end_pos", -1),
                    "confidence": s.get("confidence", 0.0),
                    "reason": s.get("reason", ""),
                    "conflicting_context": s.get("conflicting_context", ""),
                    "severity": s.get("severity", "medium"),
                }
                for s in spans
            ],
            claims_verified=claims_total,
            claims_supported=claims_supported,
            claims_unsupported=claims_total - claims_supported,
            detection_method=method,
            llm_calls=llm_calls,
            latency_ms=round(latency, 1),
            recommendations=recommendations,
            flags=flags,
        )

        # 7. 更新统计 & 记录事件
        self._update_stats(report)
        if has_hallucination:
            asyncio.create_task(self._log_event(report))

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                f"[SafetyCritic] {report_id[:12]} 检测完成: "
                f"overall={overall_score:.3f}, "
                f"fabrication={fab_score:.2f}, "
                f"distortion={dist_score:.2f}, "
                f"contradiction={logic_score:.2f}, "
                f"method={method}, "
                f"has_hallucination={has_hallucination}, "
                f"spans={len(spans)}, "
                f"latency={latency:.1f}ms"
            )

        return report

    # ──────── 启发式检测 ────────

    def _heuristic_detect(
        self, query: str, response: str, context: str
    ) -> Dict[str, Any]:
        """
        启发式幻觉检测：基于正则模式匹配和简单规则。

        返回:
            {
                "fabrication": [{"text": ..., "reason": ..., "start_pos": ..., "end_pos": ...}],
                "fact_distortion": [...],
                "logic_contradiction": [...],
                "claims_checked": [{"text": ..., "supported": bool}],
            }
        """
        result = {
            "fabrication": [],
            "fact_distortion": [],
            "logic_contradiction": [],
            "claims_checked": [],
        }

        # ── 检测 1: 无中生有模式 ──
        for pattern, reason in FABRICATION_PATTERNS:
            for match in re.finditer(pattern, response):
                span = {
                    "type": "fabrication",
                    "text": match.group(),
                    "start_pos": match.start(),
                    "end_pos": match.end(),
                    "confidence": 0.6,  # 启发式置信度中等
                    "reason": reason,
                    "conflicting_context": "",
                    "severity": "medium",
                }
                result["fabrication"].append(span)

        # ── 检测 2: 事实扭曲（数字对比） ──
        if context:
            result["fact_distortion"] = self._compare_numerics(response, context)

        # ── 检测 3: 逻辑矛盾 ──
        if context:
            result["logic_contradiction"] = self._check_logical_consistency(
                response, context
            )

        # ── 检测 4: 声明支持检测 ──
        result["claims_checked"] = self._check_claim_support(response, context)

        return result

    def _compare_numerics(
        self, response: str, context: str
    ) -> List[Dict]:
        """
        对比回答和上下文中的数值型事实。
        使用正则提取数值，对比差异。
        """
        spans = []

        # 从上下文中提取 {描述: 数值} 对
        ctx_pattern = re.compile(
            r"([\u4e00-\u9fff\w]+(?:直径|高度|宽度|厚度|重量|速度|温度|压力|频率|功率|容量|数量|价格|比率|精度|误差))\s*(?:为|是|＝|=|:|：|达到|D=)\s*(\d+(?:\.\d+)?)\s*(mm|cm|m|km|g|kg|t|ms|s|min|h|元|万|亿|%|°C|℃|°|Hz|kHz|MHz|W|kW)?",
            re.IGNORECASE,
        )

        ctx_values: Dict[str, Tuple[str, str]] = {}
        for match in ctx_pattern.finditer(context):
            keyword = match.group(1).lower()
            value_str = match.group(2)
            unit = match.group(3) or ""
            ctx_values[keyword] = (value_str, unit)

        # 从回答中提取对应数值并对比
        resp_matches = list(ctx_pattern.finditer(response))
        for match in resp_matches:
            keyword = match.group(1).lower()
            resp_value_str = match.group(2)
            resp_unit = match.group(3) or ""

            if keyword in ctx_values:
                ctx_value_str, ctx_unit = ctx_values[keyword]
                # 规范化对比
                try:
                    ctx_val = float(ctx_value_str)
                    resp_val = float(resp_value_str)
                    if abs(ctx_val - resp_val) > 0.001 and ctx_unit == resp_unit:
                        # 数值不一致
                        spans.append({
                            "type": "fact_distortion",
                            "text": match.group(),
                            "start_pos": match.start(),
                            "end_pos": match.end(),
                            "confidence": 0.75,
                            "reason": f"数值不一致：上下文为 {ctx_value_str}{ctx_unit}，回答为 {resp_value_str}{resp_unit}",
                            "conflicting_context": f"上下文中 {keyword} = {ctx_value_str}{ctx_unit}",
                            "severity": "high" if abs(ctx_val - resp_val) / max(abs(ctx_val), 1) > 0.5 else "medium",
                        })
                except ValueError:
                    # 非数值对比（如字符串值）
                    if ctx_value_str != resp_value_str:
                        spans.append({
                            "type": "fact_distortion",
                            "text": match.group(),
                            "start_pos": match.start(),
                            "end_pos": match.end(),
                            "confidence": 0.65,
                            "reason": f"值不一致：上下文为 '{ctx_value_str}'，回答为 '{resp_value_str}'",
                            "conflicting_context": f"上下文中 {keyword} = {ctx_value_str}",
                            "severity": "medium",
                        })

        return spans

    def _check_logical_consistency(
        self, response: str, context: str
    ) -> List[Dict]:
        """
        检查回答与上下文之间的逻辑一致性。
        不进行复杂推理，只检测简单的逻辑冲突模式。
        """
        spans = []

        # 模式 1: "必须/只能/仅/只" vs 上下文中的多个选项
        exclusive_patterns = [
            (r"(?:必须|只能|仅有|只有|仅限|只能使用|唯一.{0,4}是)\s*([^，,。.\n]{5,30})", "排他性断言"),
        ]

        for pattern, reason in exclusive_patterns:
            for match in re.finditer(pattern, response):
                exclusive_text = match.group(1).strip()
                # 在上下文中搜索是否有多选项
                multi_option_indicators = [
                    "可选", "三种", "多种", "包括", "如", "例如",
                    "可以", "也可", "等方式", "等类型", "等模式",
                ]
                if any(ind in context for ind in multi_option_indicators):
                    spans.append({
                        "type": "logic_contradiction",
                        "text": match.group(),
                        "start_pos": match.start(),
                        "end_pos": match.end(),
                        "confidence": 0.55,
                        "reason": f"{reason}：上下文暗示存在多个选项",
                        "conflicting_context": "上下文包含多选项指示词",
                        "severity": "low",
                    })

        # 模式 2: 因果关系与上下文矛盾
        cause_effect_patterns = [
            (r"(?:因为|由于|基于|鉴于)\s*([^，,。.\n]{10,50})(?:所以|因此|故|于是|从而)", "因果断言"),
        ]

        for pattern, reason in cause_effect_patterns:
            for match in re.finditer(pattern, response):
                cause = match.group(1).strip()
                # 检查原因是否在上下文中被否定
                negation_indicators = [
                    f"不是{cause[:10]}",
                    f"并非{cause[:10]}",
                    f"不能{cause[:10]}",
                ]
                if any(ind in context for ind in negation_indicators):
                    spans.append({
                        "type": "logic_contradiction",
                        "text": match.group(),
                        "start_pos": match.start(),
                        "end_pos": match.end(),
                        "confidence": 0.65,
                        "reason": f"{reason}：前提条件在上下文中被否定",
                        "conflicting_context": "上下文否定了该因果关系的前提",
                        "severity": "medium",
                    })

        return spans

    def _check_claim_support(
        self, response: str, context: str
    ) -> List[Dict]:
        """
        快速检查关键声明是否有上下文支持。
        使用基于 n-gram 的重叠度估算（不替代 LLM 深度检查）。
        """
        claims = []

        # 提取回答中的关键句子
        sentences = re.split(r'[。！？；\n]', response)
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 10:
                continue

            # 使用字符级 Jaccard 估算重叠
            resp_chars = set(sentence)
            ctx_chars = set(context)
            if len(resp_chars) > 0:
                overlap = len(resp_chars & ctx_chars) / len(resp_chars)
            else:
                overlap = 0.0

            # 使用词级 n-gram 重叠
            ngram_overlap = self._ngram_overlap(sentence, context, n=3)

            supported = overlap > 0.3 or ngram_overlap > 0.15
            claims.append({
                "text": sentence[:100],
                "supported": supported,
                "char_overlap": round(overlap, 2),
                "ngram_overlap": round(ngram_overlap, 2),
            })

        return claims

    @staticmethod
    def _ngram_overlap(text1: str, text2: str, n: int = 3) -> float:
        """计算两个文本的 n-gram 重叠度"""
        if len(text1) < n or len(text2) < n:
            return 0.0

        def _get_ngrams(t: str, k: int) -> Set[str]:
            return {t[i:i + k] for i in range(len(t) - k + 1)}

        ngrams1 = _get_ngrams(text1, n)
        ngrams2 = _get_ngrams(text2, n)

        if not ngrams1:
            return 0.0

        intersection = len(ngrams1 & ngrams2)
        return intersection / len(ngrams1)

    # ──────── LLM 深度检测 ────────

    async def _llm_detect(
        self,
        query: str,
        response: str,
        context: str,
        sources: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        使用 LLM 进行多维度幻觉检测。

        Returns:
            LLM 返回的 JSON 解析结果
        """
        from src.services.llm import call_llm_fast

        # 准备上下文
        ctx_text = context[:CONTEXT_MAX_CHARS]
        if sources:
            ctx_text += "\n\n--- 额外来源 ---\n"
            ctx_text += "\n".join(f"- {s[:200]}" for s in sources[:10])

        prompt = self.DETECTION_PROMPT_TEMPLATE.format(
            query=query[:500],
            context=ctx_text,
            response=response[:RESPONSE_MAX_CHARS],
        )

        try:
            raw_result = await call_llm_fast(
                prompt,
                max_tokens=CRITIC_MAX_TOKENS,
                temperature=CRITIC_TEMPERATURE,
                system_prompt=self.SYSTEM_PROMPT,
            )

            if not raw_result:
                logger.warning("[SafetyCritic] LLM 返回空结果")
                return {}

            parsed = self._safe_json_parse(raw_result)
            if not parsed:
                logger.warning(f"[SafetyCritic] LLM 结果 JSON 解析失败: {raw_result[:200]}")
                return {}

            return parsed

        except Exception as e:
            logger.warning(f"[SafetyCritic] LLM 检测异常: {e}", exc_info=True)
            raise

    # ──────── 交叉验证与合并 ────────

    def _merge_spans(
        self,
        heuristic: Dict[str, List[Dict]],
        llm_fab: List[Dict],
        llm_dist: List[Dict],
        llm_logic: List[Dict],
        response: str,
    ) -> List[Dict]:
        """
        合并启发式和 LLM 检测的片段，去重并提高置信度。

        策略：
        - 两者都检测到的 → 高置信度（取 max）
        - 只有一方检测到的 → 保留但可能降低置信度
        - LLM 检测的 start_pos/end_pos 可能不精确，优先使用启发式位置
        """
        merged: List[Dict] = []

        # 1. 加入启发式结果
        for dim in ["fabrication", "fact_distortion", "logic_contradiction"]:
            for span in heuristic.get(dim, []):
                merged.append({
                    **span,
                    "source": "heuristic",
                    "confidence": span.get("confidence", 0.5),
                })

        # 2. 合并 LLM 结果（提高匹配片段的置信度）
        llm_spans = []
        for s in llm_fab:
            s_copy = dict(s)
            s_copy["type"] = "fabrication"
            s_copy["source"] = "llm"
            llm_spans.append(s_copy)
        for s in llm_dist:
            s_copy = dict(s)
            s_copy["type"] = "fact_distortion"
            s_copy["source"] = "llm"
            llm_spans.append(s_copy)
        for s in llm_logic:
            s_copy = dict(s)
            s_copy["type"] = "logic_contradiction"
            s_copy["source"] = "llm"
            llm_spans.append(s_copy)

        for llm_s in llm_spans:
            llm_text = llm_s.get("text", "")
            # 检查是否与已有片段重叠
            is_duplicate = False
            for existing in merged:
                if self._text_overlap(existing.get("text", ""), llm_text) > 0.5:
                    # 提高置信度（取 max）
                    existing["confidence"] = max(
                        existing.get("confidence", 0), llm_s.get("confidence", 0)
                    )
                    existing["source"] = "hybrid"
                    # 补充 LLM 提供的额外信息
                    if not existing.get("conflicting_context"):
                        existing["conflicting_context"] = llm_s.get(
                            "conflicting_context",
                            llm_s.get("correct_value", ""),
                        )
                    is_duplicate = True
                    break

            if not is_duplicate:
                # 验证并修正 LLM 提供的位置
                start_pos = llm_s.get("start_pos", -1)
                end_pos = llm_s.get("end_pos", -1)

                # 如果位置无效（-1），尝试从回答中查找文本位置
                if start_pos < 0 and llm_text:
                    idx = response.find(llm_text)
                    if idx >= 0:
                        start_pos = idx
                        end_pos = idx + len(llm_text)

                merged.append({
                    "type": llm_s["type"],
                    "text": llm_text,
                    "start_pos": start_pos if start_pos >= 0 else -1,
                    "end_pos": end_pos if end_pos >= 0 else -1,
                    "confidence": llm_s.get("confidence", 0.6),
                    "reason": llm_s.get("reason", ""),
                    "conflicting_context": llm_s.get(
                        "conflicting_context",
                        llm_s.get("correct_value", ""),
                    ),
                    "severity": llm_s.get("severity", "medium"),
                    "source": "llm",
                })

        # 3. 按位置排序
        merged.sort(key=lambda x: (x["start_pos"] if x["start_pos"] >= 0 else 99999))

        # 4. 去重重叠片段
        deduped = []
        for span in merged:
            is_overlap = False
            for existing in deduped:
                if self._span_overlap(span, existing):
                    # 保留置信度更高的
                    if span.get("confidence", 0) > existing.get("confidence", 0):
                        existing.update(span)
                    is_overlap = True
                    break
            if not is_overlap:
                deduped.append(span)

        return deduped

    @staticmethod
    def _text_overlap(text1: str, text2: str) -> float:
        """计算两个文本的重叠度"""
        if not text1 or not text2:
            return 0.0
        chars1 = set(text1)
        chars2 = set(text2)
        if not chars1 or not chars2:
            return 0.0
        return len(chars1 & chars2) / max(len(chars1), len(chars2))

    @staticmethod
    def _span_overlap(span1: Dict, span2: Dict) -> bool:
        """判断两个片段是否重叠"""
        s1 = span1.get("start_pos", -1)
        e1 = span1.get("end_pos", -1)
        s2 = span2.get("start_pos", -1)
        e2 = span2.get("end_pos", -1)

        if s1 < 0 or e1 < 0 or s2 < 0 or e2 < 0:
            return False

        return not (e1 < s2 or e2 < s1)

    # ──────── 得分计算 ────────

    def _compute_dimension_score(
        self,
        heuristic_spans: List[Dict],
        llm_dim_result: Dict,
    ) -> float:
        """
        计算单个维度的幻觉得分。

        因子:
        - LLM 评分权重 0.6
        - 启发式评分权重 0.4（基于严重度和置信度的片段）
        """
        llm_score = llm_dim_result.get("score", 0.0) if llm_dim_result else 0.0

        # 基于启发式片段计算分数
        heuristic_score = 0.0
        if heuristic_spans:
            severity_weights = {"critical": 0.4, "high": 0.3, "medium": 0.15, "low": 0.05}
            for span in heuristic_spans:
                sv_weight = severity_weights.get(span.get("severity", "medium"), 0.1)
                confidence = span.get("confidence", 0.5)
                heuristic_score += sv_weight * confidence
            heuristic_score = min(heuristic_score, 1.0)  # 上限 1.0

        if llm_dim_result:
            # 有 LLM 结果：加权合并
            return round(llm_score * 0.6 + heuristic_score * 0.4, 4)
        else:
            # 纯启发式
            return round(heuristic_score, 4)

    def _determine_flags(
        self,
        spans: List[Dict],
        has_hallucination: bool,
        overall_score: float,
    ) -> List[str]:
        """根据检测结果确定告警标记"""
        flags = []

        if has_hallucination:
            flags.append("hallucination_detected")

            # 检查各类型
            types_found = set(s.get("type", "") for s in spans)
            if "fabrication" in types_found:
                flags.append("fabrication_found")
            if "fact_distortion" in types_found:
                flags.append("fact_distortion_found")
            if "logic_contradiction" in types_found:
                flags.append("logic_contradiction_found")

        # 严重度级别
        if overall_score > 0.7:
            flags.append("hallucination_critical")
        elif overall_score > 0.5:
            flags.append("hallucination_high")
        elif overall_score > 0.3:
            flags.append("hallucination_medium")

        # 高严重度片段
        critical_spans = [s for s in spans if s.get("severity") == "critical"]
        high_spans = [s for s in spans if s.get("severity") == "high"]
        if critical_spans:
            flags.append(f"critical_spans_{len(critical_spans)}")
        if high_spans:
            flags.append(f"high_severity_spans_{len(high_spans)}")

        return flags

    def _generate_recommendations(
        self,
        spans: List[Dict],
        fab_score: float,
        dist_score: float,
        logic_score: float,
    ) -> List[str]:
        """基于幻觉检测结果生成改进建议"""
        recs = []

        if fab_score > 0.3:
            recs.append(
                f"无中生有({fab_score:.2f})：建议增强事实性约束，要求模型仅基于上下文生成"
            )
        if dist_score > 0.3:
            recs.append(
                f"事实扭曲({dist_score:.2f})：建议启用严格数字校验，要求模型引用上下文原文"
            )
        if logic_score > 0.3:
            recs.append(
                f"逻辑矛盾({logic_score:.2f})：建议在生成后添加逻辑一致性检查"
            )

        # 针对性建议
        types_found = set(s.get("type", "") for s in spans)
        if "fabrication" in types_found:
            recs.append("建议降低生成温度(temperature)以减少编造倾向")
        if "fact_distortion" in types_found:
            recs.append("建议使用精确检索+引用标注模式，强制引用上下文原文")

        fabricate_spans = [s for s in spans if s.get("type") == "fabrication"]
        if len(fabricate_spans) >= 3:
            recs.append("检测到大量无中生有片段，强烈建议触发人工审核")

        return recs

    # ──────── 事件日志 ────────

    async def _log_event(self, report: HallucinationReport):
        """将幻觉事件持久化到日志"""
        try:
            event = {
                "report_id": report.report_id,
                "timestamp": report.timestamp,
                "query": report.query[:200],
                "response": report.response[:200],
                "context": report.context[:200],
                "overall_score": report.overall_score,
                "dimensions": {
                    "fabrication": report.fabrication_score,
                    "fact_distortion": report.fact_distortion_score,
                    "logic_contradiction": report.logic_contradiction_score,
                },
                "spans_count": len(report.spans),
                "spans_summary": [
                    {
                        "type": s.get("type"),
                        "text": s.get("text", "")[:100],
                        "severity": s.get("severity"),
                    }
                    for s in report.spans[:10]
                ],
                "flags": report.flags,
                "recommendations": report.recommendations,
                "detection_method": report.detection_method,
                "latency_ms": report.latency_ms,
            }

            def _write():
                with open(HALLUCINATION_LOG_PATH, "a", encoding="utf-8") as f:
                    f.write(json.dumps(event, ensure_ascii=False) + "\n")

            await asyncio.to_thread(_write)

        except Exception as e:
            logger.warning(f"[SafetyCritic] 事件日志写入失败: {e}")

    def _update_stats(self, report: HallucinationReport):
        """更新内部统计"""
        self._stats["total_detections"] += 1
        if report.has_hallucination:
            self._stats["hallucinations_found"] += 1
        self._stats["method_distribution"][report.detection_method] += 1

        # 移动平均延迟
        n = self._stats["total_detections"]
        prev_avg = self._stats["avg_latency_ms"]
        self._stats["avg_latency_ms"] = round(
            (prev_avg * (n - 1) + report.latency_ms) / n, 1
        )

    # ──────── 便捷方法 ────────

    async def quick_check(
        self, query: str, response: str, context: str = ""
    ) -> Dict[str, Any]:
        """
        快速幻觉检查：不调用 LLM，仅使用启发式规则。
        适合在高吞吐量场景中做初筛。

        Returns:
            {"has_hallucination": bool, "score": float, "spans": list}
        """
        report = await self.detect_hallucination(
            query=query,
            response=response,
            context=context,
            use_llm=False,
            threshold=0.5,  # 启发式阈值更高
        )
        return {
            "has_hallucination": report.has_hallucination,
            "score": report.overall_score,
            "dimensions": {
                "fabrication": report.fabrication_score,
                "fact_distortion": report.fact_distortion_score,
                "logic_contradiction": report.logic_contradiction_score,
            },
            "spans": [
                {
                    "type": s.get("type"),
                    "text": s.get("text", "")[:50],
                    "reason": s.get("reason", ""),
                }
                for s in report.spans[:5]
            ],
            "flags": report.flags,
        }

    async def deep_check(
        self,
        query: str,
        response: str,
        context: str,
        sources: Optional[List[str]] = None,
    ) -> HallucinationReport:
        """
        深度幻觉检查：始终使用 LLM 进行多维度检测。
        适合在质量要求高的场景中使用（如正式报告生成前）。

        Returns:
            HallucinationReport: 完整的幻觉检测报告
        """
        return await self.detect_hallucination(
            query=query,
            response=response,
            context=context,
            sources=sources,
            use_llm=True,
            threshold=0.2,  # 深度检查阈值更低、更敏感
        )

    async def batch_check(
        self,
        items: List[Dict[str, str]],
        use_llm: bool = True,
        max_concurrent: int = 5,
    ) -> List[HallucinationReport]:
        """
        批量幻觉检测。

        Args:
            items: [{"query": "...", "response": "...", "context": "..."}, ...]
            use_llm: 是否使用 LLM
            max_concurrent: 最大并发数

        Returns:
            检测报告列表
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def _check_one(item: Dict) -> HallucinationReport:
            async with semaphore:
                try:
                    return await self.detect_hallucination(
                        query=item.get("query", ""),
                        response=item.get("response", ""),
                        context=item.get("context", ""),
                        sources=item.get("sources"),
                        use_llm=use_llm,
                    )
                except Exception as e:
                    logger.warning(f"[SafetyCritic] 批量检测 #{item.get('query', '?')[:30]} 失败: {e}")
                    return HallucinationReport(
                        report_id=f"batch_error_{hash(item.get('query', ''))}",
                        timestamp=time.time(),
                        query=item.get("query", "")[:200],
                        response="",
                        context="",
                        has_hallucination=False,
                        flags=["detection_error"],
                    )

        tasks = [_check_one(item) for item in items]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        reports = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                reports.append(HallucinationReport(
                    report_id=f"batch_err_{i}",
                    timestamp=time.time(),
                    query=items[i].get("query", "")[:200],
                    response="",
                    context="",
                    flags=["batch_error"],
                ))
            else:
                reports.append(r)

        return reports

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return dict(self._stats)

    async def flush(self):
        """刷新所有缓存和状态（graceful shutdown）"""
        self._cache.clear()
        logger.info("[SafetyCritic] 缓存已清空")

    # ──────── 工具方法 ────────

    @staticmethod
    def _make_report_id(query: str, response: str, timestamp: float) -> str:
        """生成唯一报告 ID"""
        raw = f"{query[:100]}|{response[:100]}|{timestamp}"
        return "hrep_" + hashlib.md5(raw.encode()).hexdigest()[:16]

    @staticmethod
    def _safe_json_parse(text: str) -> Dict[str, Any]:
        """安全解析 LLM 返回的 JSON，处理常见格式问题"""
        text = text.strip()

        # 去除 markdown 代码块
        if text.startswith("```"):
            lines = text.split("\n")
            if len(lines) > 2:
                text = "\n".join(lines[1:-1])
            elif lines[0].startswith("```json"):
                text = lines[0][7:].strip()

        # 提取 JSON 对象
        s = text.find("{")
        e = text.rfind("}")
        if s >= 0 and e > s:
            try:
                return json.loads(text[s:e + 1])
            except json.JSONDecodeError:
                pass

        # 直接解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        return {}


# ============ 全局实例 ============

_safety_critic: Optional[SafetyCritic] = None


def get_safety_critic() -> SafetyCritic:
    """获取全局 SafetyCritic 单例"""
    global _safety_critic
    if _safety_critic is None:
        _safety_critic = SafetyCritic()
    return _safety_critic


# ============ 便捷函数 ============

async def detect_hallucination(
    query: str,
    response: str,
    context: str = "",
    sources: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    便捷函数：单次幻觉检测。

    返回可直接序列化的 dict。

    Usage:
        from src.services.safety_critic import detect_hallucination
        result = await detect_hallucination(query, response, context)
    """
    critic = get_safety_critic()
    report = await critic.detect_hallucination(
        query=query,
        response=response,
        context=context,
        sources=sources,
    )
    return asdict(report)


async def quick_hallucination_check(
    query: str,
    response: str,
    context: str = "",
) -> Dict[str, Any]:
    """
    便捷函数：快速启发式幻觉检查（不调用 LLM）。
    """
    critic = get_safety_critic()
    return await critic.quick_check(query, response, context)