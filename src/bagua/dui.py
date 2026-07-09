#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dui.py — 兑卦 ☱ · 伏羲 v2.1

兑为泽，主对话与交互。
对应能力：对话管理、意图识别、多轮上下文、输出对齐。

Phase 2 实现：
  - 响应格式化：将各卦输出包装为前端友好的响应
  - 多轮对话缓存：维护短期对话历史
  - 输出对齐：确保回答与用户提问的格式一致
  - 对话摘要：从多轮对话提取摘要
"""


import hashlib
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from src.bagua.base_gua import (
    GuaBase,
    DegradationRule,
    FallbackAction,
)
from src.bagua.gap_analyzer import (
    GapAnalyzer,
    is_gap_analysis_enabled,
)

logger = logging.getLogger("bagua.dui")


# ============================================================================
# MerkleAuditChain — 卦象审计链
# ============================================================================


class MerkleAuditChain:
    """Merkle 树审计链 — 每卦执行后可验证的审计追踪

    每卦执行后，将 (卦名, 输入hash, 输出hash, timestamp) 作为 leaf 节点
    添加到 Merkle 树中。根 hash 存储在兑卦中，可供外部验证。

    数据结构：
        leaf = sha256(卦名 + 输入hash + 输出hash + timestamp)
        root = merkle_root([leaf1, leaf2, ..., leafN])

    用法：
        chain = MerkleAuditChain()
        chain.add_leaf("乾", "input_hash_abc", "output_hash_def")
        chain.add_leaf("离", "input_hash_xyz", "output_hash_uvw")
        root_hash = chain.get_root()
        proof = chain.get_proof(0)  # 第0个叶子节点的 Merkle proof
        is_valid = chain.verify(root_hash, proof, "乾", "input_hash_abc", "output_hash_def")

    Attributes:
        leaves:     [(卦名, 输入hash, 输出hash, timestamp), ...]
        _leaf_nodes: 已计算的叶子节点 hash 列表
        _tree_levels: Merkle 树各层 hash 列表
    """

    def __init__(self) -> None:
        self.leaves: List[Tuple[str, str, str, float]] = []
        self._leaf_nodes: List[str] = []
        self._dirty: bool = True
        self._root_hash: Optional[str] = None

    # ========================================================================
    # 公共 API
    # ========================================================================

    def add_leaf(
        self,
        gua_name: str,
        input_hash: str,
        output_hash: str,
        timestamp: Optional[float] = None,
    ) -> str:
        """添加一个卦执行记录作为叶子节点

        Args:
            gua_name:    卦名（如 "乾", "离", "艮"）
            input_hash:  输入数据的 SHA256 hash
            output_hash: 输出数据的 SHA256 hash
            timestamp:   时间戳（默认使用当前时间）

        Returns:
            叶子节点的 hash 值
        """
        if timestamp is None:
            timestamp = time.time()

        leaf_data = f"{gua_name}|{input_hash}|{output_hash}|{timestamp}"
        leaf_hash = hashlib.sha256(leaf_data.encode("utf-8")).hexdigest()

        self.leaves.append((gua_name, input_hash, output_hash, timestamp))
        self._leaf_nodes.append(leaf_hash)
        self._dirty = True

        logger.debug(
            "🔗 [Merkle] 添加叶子: gua=%s leaf=%s...",
            gua_name, leaf_hash[:16],
        )
        return leaf_hash

    def get_root(self) -> str:
        """获取 Merkle 树的根 hash

        Returns:
            64 字符的 hex 字符串，如果树为空则返回空字符串的 hash
        """
        if self._dirty:
            self._root_hash = self._compute_root()
            self._dirty = False
        return self._root_hash or ""

    def get_proof(self, leaf_index: int) -> List[Dict[str, str]]:
        """获取指定叶子节点的 Merkle proof

        Merkle proof 包含从叶子到根的路径上所有兄弟节点 hash，
        外部可用此 proof 验证叶子节点是否在树中。

        Args:
            leaf_index: 叶子节点索引（0-based）

        Returns:
            [{"position": "left"|"right", "hash": str}, ...]
            空列表如果树为空或索引越界
        """
        if leaf_index < 0 or leaf_index >= len(self._leaf_nodes):
            return []

        # 确保根已计算
        if self._dirty:
            self._root_hash = self._compute_root()
            self._dirty = False

        leaves = list(self._leaf_nodes)
        proofs: List[Dict[str, str]] = []
        index = leaf_index
        level = leaves

        while len(level) > 1:
            pair_index = index ^ 1  # XOR: 0↔1, 2↔3, ...
            if pair_index < len(level):
                position = "left" if index % 2 == 1 else "right"
                proofs.append({"position": position, "hash": level[pair_index]})

            # 计算上一层
            next_level: List[str] = []
            for i in range(0, len(level), 2):
                if i + 1 < len(level):
                    combined = level[i] + level[i + 1]
                    next_level.append(
                        hashlib.sha256(combined.encode("utf-8")).hexdigest()
                    )
                else:
                    # 奇数节点，复制自己
                    next_level.append(level[i])

            level = next_level
            index //= 2

        return proofs

    def verify(
        self,
        root_hash: str,
        gua_name: str,
        input_hash: str,
        output_hash: str,
        timestamp: float,
    ) -> bool:
        """验证某个卦执行记录是否在审计链中

        重新计算叶子 hash 并与存储的 leaves 比较。
        适用于外部审计验证场景。

        Args:
            root_hash:   期望的根 hash
            gua_name:    卦名
            input_hash:  输入 hash
            output_hash: 输出 hash
            timestamp:   时间戳

        Returns:
            True 如果该记录存在于链中且根 hash 匹配
        """
        leaf_data = f"{gua_name}|{input_hash}|{output_hash}|{timestamp}"
        expected_leaf = hashlib.sha256(leaf_data.encode("utf-8")).hexdigest()

        return expected_leaf in self._leaf_nodes and self.get_root() == root_hash

    def to_dict(self) -> Dict[str, Any]:
        """导出审计链为可序列化字典

        Returns:
            {
                "root_hash": str,
                "leaf_count": int,
                "leaves": [{"gua": str, "input_hash": str, "output_hash": str, "timestamp": float}, ...],
                "created_at": float,
            }
        """
        return {
            "root_hash": self.get_root(),
            "leaf_count": len(self.leaves),
            "leaves": [
                {
                    "gua": gua,
                    "input_hash": ih,
                    "output_hash": oh,
                    "timestamp": ts,
                }
                for gua, ih, oh, ts in self.leaves
            ],
            "created_at": time.time(),
        }

    def clear(self) -> None:
        """清空审计链"""
        self.leaves.clear()
        self._leaf_nodes.clear()
        self._dirty = True
        self._root_hash = None

    # ========================================================================
    # 内部方法
    # ========================================================================

    def _compute_root(self) -> str:
        """计算 Merkle 树的根 hash

        用标准的自底向上方法构建 Merkle 树：
          叶子层 → 两两配对 hash → ... → 单根

        Returns:
            根 hash（64 hex chars）
        """
        if not self._leaf_nodes:
            return hashlib.sha256(b"").hexdigest()

        level = list(self._leaf_nodes)

        while len(level) > 1:
            next_level: List[str] = []
            for i in range(0, len(level), 2):
                if i + 1 < len(level):
                    combined = level[i] + level[i + 1]
                    next_level.append(
                        hashlib.sha256(combined.encode("utf-8")).hexdigest()
                    )
                else:
                    # 奇数节点：复制自己配对
                    combined = level[i] + level[i]
                    next_level.append(
                        hashlib.sha256(combined.encode("utf-8")).hexdigest()
                    )
            level = next_level

        return level[0]

    @staticmethod
    def hash_text(text: str) -> str:
        """对文本内容做 SHA256 hash

        便捷方法，将任意文本转为 64 字符 hex hash。
        用于卦的输入/输出 hash 计算。

        Args:
            text: 文本内容

        Returns:
            64 字符 hex hash
        """
        return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ============================================================================
# DuiGua — 兑卦
# ============================================================================


class DuiGua(GuaBase):
    """兑卦 — 对话与交互

    兑卦代表沟通与交换，负责：
      - 响应格式化（将内部输出转化为用户可读文本）
      - 多轮对话上下文管理
      - 输出对齐与样式控制

    Usage::

        dui = DuiGua()
        dui.start()

        # 格式化搜索结果为对话格式
        result = dui.execute({
            "action": "format_answer",
            "query": "Python 怎么学？",
            "answer": "建议从官方教程开始...",
            "sources": ["官方文档", "教程网站"],
            "confidence": 0.85,
        })

        # 管理对话历史
        dui.execute({
            "action": "add_to_history",
            "session_id": "s1",
            "role": "user",
            "content": "你好",
        })

        dui.stop()
    """

    GUA_NAME: str = "dui"
    GUA_EMOJI: str = "☱"
    GUA_DESCRIPTION: str = "对话与交互 — 对话管理、意图识别、多轮上下文"

    # 每 session 最大对话条数
    MAX_HISTORY_SIZE: int = 100

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

        # 对话历史缓存 {session_id: [{"role": str, "content": str, "time": float}, ...]}
        self._histories: Dict[str, List[Dict[str, Any]]] = {}

        # Merkle 审计链 — 记录每卦执行的审计追踪
        self._audit_chain: MerkleAuditChain = MerkleAuditChain()

        # 注册外部依赖
        self.register_dependency("llm", failure_threshold=3)
        self.register_dependency("output_formatter", failure_threshold=5)

    # ========================================================================
    # GuaBase 抽象方法实现
    # ========================================================================

    def _setup_degradation_rules(self) -> None:
        """注册兑卦降级规则

        1. LLM 不可用时使用模板格式化（priority=10）
        2. 历史缓存超限时自动精简（priority=5）
        """
        llm_cb = self._circuits.get("llm")

        # 规则 10: LLM 不可用 → 模板格式化
        self.add_rule(DegradationRule(
            name="llm_unavailable",
            condition_fn=lambda: (
                llm_cb is not None and not llm_cb.is_healthy
            ),
            fallback=FallbackAction(
                name="template_format_fallback",
                handler=self._fallback_template_format,
                description="LLM 不可用时使用模板格式化",
            ),
            priority=10,
        ))

        # 规则 5: 历史缓存超限
        self.add_rule(DegradationRule(
            name="history_overflow",
            condition_fn=lambda: self._check_history_overflow(),
            fallback=FallbackAction(
                name="trim_history",
                handler=self._fallback_trim_history,
                description="历史缓存超限时自动精简",
            ),
            priority=5,
        ))

    async def _execute_core(self, params: Dict[str, Any]) -> Any:
        """核心执行 — 按 action 字段分发

        Supported actions:
            - "format_answer":    格式化最终答案输出
            - "add_to_history":   添加一条对话到历史
            - "get_history":      获取对话历史
            - "clear_history":    清空对话历史
            - "summarize_history": 生成对话摘要
            - "fmt_error":        格式化错误消息
            - "audit_record":     记录卦执行到审计链
            - "audit_root":       获取审计链根 hash
            - "audit_verify":     验证审计链中的记录
            - "audit_export":     导出审计链数据

        Args:
            params: {
                "action": str,
                ... (各 action 特有参数)
            }

        Returns:
            各 action 的返回值

        Raises:
            ValueError: 未知 action
        """
        action = params.get("action", "format_answer")

        # ---- 审计链 actions ----
        if action == "audit_record":
            return self._audit_record(
                gua_name=params.get("gua_name", "unknown"),
                input_data=params.get("input_data", ""),
                output_data=params.get("output_data", ""),
            )

        if action == "audit_root":
            return self._audit_get_root()

        if action == "audit_verify":
            return self._audit_verify(
                gua_name=params.get("gua_name", ""),
                input_data=params.get("input_data", ""),
                output_data=params.get("output_data", ""),
                timestamp=params.get("timestamp", 0),
            )

        if action == "audit_export":
            return self._audit_chain.to_dict()

        if action == "format_answer":
            return self._format_answer(
                query=params.get("query", ""),
                answer=params.get("answer", ""),
                sources=params.get("sources", []),
                confidence=params.get("confidence", 0.0),
                mode=params.get("mode", ""),
            )

        if action == "add_to_history":
            return self._add_to_history(
                session_id=params.get("session_id", "default"),
                role=params.get("role", "user"),
                content=params.get("content", ""),
            )

        if action == "get_history":
            return self._get_history(
                session_id=params.get("session_id", "default"),
                n=params.get("n", 10),
            )

        if action == "clear_history":
            return self._clear_history(
                session_id=params.get("session_id", "default"),
            )

        if action == "summarize_history":
            return self._summarize_history(
                session_id=params.get("session_id", "default"),
            )

        if action == "fmt_error":
            return self._fmt_error(
                error_message=params.get("error_message", "未知错误"),
                error_code=params.get("error_code", ""),
            )

        # ---- 新增 SSE actions ----
        if action == "sse_stream":
            return await self._stream_response(params)

        if action == "compress_history":
            return self._compress_history(
                session_id=params.get("session_id", "default"),
                max_tokens=params.get("max_tokens", 500),
            )

        raise ValueError(
            f"[{self.GUA_NAME}] 未知 action: {action}。"
            f"支持: format_answer, add_to_history, get_history, "
            f"clear_history, summarize_history, compress_history, fmt_error, "
            f"audit_record, audit_root, audit_verify, audit_export, "
            f"sse_stream"
        )

    # ========================================================================
    # 核心能力 — 响应格式化
    # ========================================================================

    def _format_answer(
        self,
        query: str,
        answer: str,
        sources: Optional[List[str]] = None,
        confidence: float = 0.0,
        mode: str = "",
        enable_gap_analysis: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """格式化最终答案为对话友好的格式

        将内部输出包装为结构化的用户可见格式。
        包含：
          - 主要答案文本
          - 可折叠的引用来源
          - 置信度指示器
          - 格式元数据
          - Gap Analysis 知识盲区标注（v1.50 Phase A）

        Args:
            query:      用户原始提问
            answer:     系统生成的答案
            sources:    信息来源列表
            confidence: 答案置信度
            mode:       执行模式
            enable_gap_analysis: 是否启用 Gap Analysis
                                （None=使用全局 Feature Flag）

        Returns:
            {
                "text": str,              # 格式化后的完整文本
                "answer": str,            # 原始答案
                "sources": [str, ...],    # 来源列表
                "confidence": float,      # 置信度
                "mode": str,              # 执行模式
                "has_sources": bool,      # 是否有来源引用
                "timestamp": float,       # 时间戳
                "gap_analysis": {...},    # Gap Analysis 结果（v1.50）
            }
        """
        sources = sources or []

        # ================================================================
        # v1.50 Phase A: Gap Analysis — 知识盲区标注
        # ================================================================
        gap_result = None
        _do_gap = enable_gap_analysis if enable_gap_analysis is not None else is_gap_analysis_enabled()

        if _do_gap and answer and sources:
            try:
                gap_analyzer = GapAnalyzer()
                gap_result = gap_analyzer.analyze(answer=answer, sources=sources)
                # 如果存在 gaps，将 gap_text 追加到 answer
                if gap_result.has_gaps and gap_result.gap_text:
                    answer = answer.rstrip() + "\n\n" + gap_result.gap_text
            except Exception:  # TODO: Narrow exception type
                logger.warning(
                    "☱ [兑] Gap Analysis 执行失败，跳过", exc_info=True
                )

        # 置信度标签
        if confidence >= 0.85:
            conf_label = "高"
        elif confidence >= 0.6:
            conf_label = "中"
        else:
            conf_label = "低"

        # 构建格式化文本
        lines = [answer]

        # 添加来源引用
        if sources:
            lines.append("")
            lines.append("📚 **参考来源:**")
            for i, src in enumerate(sources, 1):
                lines.append(f"  [{i}] {src}")

        # 置信度（低置信度时显示提示）
        if confidence > 0 and confidence < 0.6:
            lines.append("")
            lines.append(f"⚠️ 置信度: {conf_label} ({confidence:.0%})，建议核实信息。")
        elif confidence > 0:
            lines.append("")
            lines.append(f"✓ 置信度: {conf_label} ({confidence:.0%})")

        # 模式标签
        if mode:
            lines.append("")
            lines.append(f"🔧 模式: {mode}")

        formatted_text = "\n".join(lines)

        return {
            "text": formatted_text,
            "answer": answer,
            "sources": sources,
            "confidence": round(confidence, 4),
            "mode": mode,
            "has_sources": len(sources) > 0,
            "timestamp": time.time(),
            "gap_analysis": {
                "enabled": _do_gap,
                "has_gaps": gap_result.has_gaps if gap_result else False,
                "gap_count": len(gap_result.gaps) if gap_result else 0,
                "coverage_rate": gap_result.coverage_rate if gap_result else 1.0,
                "gap_text": gap_result.gap_text if gap_result else "",
            },
        }

    # ========================================================================
    # 核心能力 — 对话历史管理
    # ========================================================================

    def _add_to_history(
        self,
        session_id: str = "default",
        role: str = "user",
        content: str = "",
    ) -> Dict[str, Any]:
        """添加一条对话记录到历史

        Args:
            session_id: 会话标识
            role:       角色（"user" / "assistant" / "system"）
            content:    对话内容

        Returns:
            {"ok": bool, "size": int}
        """
        if not content:
            return {"ok": False, "size": 0, "error": "空内容"}

        if session_id not in self._histories:
            self._histories[session_id] = []

        entry = {
            "role": role,
            "content": content,
            "time": time.time(),
        }
        self._histories[session_id].append(entry)

        # 上限检查
        if len(self._histories[session_id]) > self.MAX_HISTORY_SIZE:
            self._histories[session_id] = self._histories[session_id][-self.MAX_HISTORY_SIZE:]

        return {"ok": True, "size": len(self._histories[session_id])}

    def _get_history(
        self,
        session_id: str = "default",
        n: int = 10,
    ) -> Dict[str, Any]:
        """获取对话历史

        Args:
            session_id: 会话标识
            n:          返回条数

        Returns:
            {"history": [...], "total": int}
        """
        history = self._histories.get(session_id, [])
        return {
            "history": list(history[-n:]),
            "total": len(history),
        }

    def _clear_history(self, session_id: str = "default") -> Dict[str, Any]:
        """清空指定会话的对话历史

        Args:
            session_id: 会话标识

        Returns:
            {"ok": bool}
        """
        if session_id in self._histories:
            size = len(self._histories[session_id])
            del self._histories[session_id]
            logger.info("☱ [兑] Session %s 历史已清空 (%d 条)", session_id, size)
        return {"ok": True}

    def _summarize_history(self, session_id: str = "default") -> Dict[str, Any]:
        """生成对话历史摘要

        Args:
            session_id: 会话标识

        Returns:
            {
                "summary": str,
                "total_messages": int,
                "total_chars": int,
                "duration_sec": float,
                "topics": [str, ...],
            }
        """
        history = self._histories.get(session_id, [])

        if not history:
            return {
                "summary": "暂无对话历史",
                "total_messages": 0,
                "total_chars": 0,
                "duration_sec": 0.0,
                "topics": [],
            }

        # 统计信息
        total_messages = len(history)
        total_chars = sum(len(h.get("content", "")) for h in history)

        # 时间段
        first_time = history[0].get("time", 0)
        last_time = history[-1].get("time", 0)
        duration_sec = last_time - first_time

        # 简单话题检测：提取用户消息中的关键词
        user_messages = [h.get("content", "") for h in history if h.get("role") == "user"]
        topics = _extract_topics(user_messages)

        # 生成摘要
        duration_min = duration_sec / 60
        if duration_min < 1:
            time_desc = f"{duration_sec:.0f} 秒"
        else:
            time_desc = f"{duration_min:.1f} 分钟"

        summary = (
            f"共 {total_messages} 条消息，{total_chars} 字符，"
            f"持续 {time_desc}。"
            f"涉及话题: {', '.join(topics) if topics else '未识别'}。"
        )

        return {
            "summary": summary,
            "total_messages": total_messages,
            "total_chars": total_chars,
            "duration_sec": round(duration_sec, 1),
            "topics": topics,
        }

    def _compress_history(
        self,
        session_id: str = "default",
        max_tokens: int = 500,
    ) -> Dict[str, Any]:
        """长对话记忆浓缩 — 将历史压缩为摘要

        当对话历史过长时，保留最近 N 轮完整对话 + 之前的压缩摘要。
        估算逻辑：中文字符 ≈ 1 token，英文 ≈ 0.75 token/char。

        Args:
            session_id: 会话标识
            max_tokens: 压缩后保留的最大 token 数

        Returns:
            {
                "compressed": str,        # 压缩后的完整文本（摘要 + 最近对话）
                "summary": str,           # 早期对话的摘要
                "recent_messages": [...], # 保留的最近完整消息
                "original_total": int,    # 原始消息总数
                "compressed_total": int,  # 压缩后保留消息数
                "estimated_tokens": int,  # 压缩后估算 token 数
            }
        """
        history = self._histories.get(session_id, [])

        if not history:
            return {
                "compressed": "",
                "summary": "暂无对话历史",
                "recent_messages": [],
                "original_total": 0,
                "compressed_total": 0,
                "estimated_tokens": 0,
            }

        original_total = len(history)

        # 估算每消息 token 数
        def _estimate_tokens(msg: Dict[str, Any]) -> int:
            text = msg.get("content", "")
            # 中文 1 char ≈ 1 token, 英文 1 char ≈ 0.25 token（保守估计）
            import re as _re
            cn_chars = len(_re.findall(r'[\u4e00-\u9fff]', text))
            en_chars = len(text) - cn_chars
            return cn_chars + int(en_chars * 0.25)

        # 从末尾向开头累加 token 直到超过 max_tokens
        recent_messages: List[Dict[str, Any]] = []
        token_count = 0
        cutoff_index = original_total

        for i in range(original_total - 1, -1, -1):
            msg_tokens = _estimate_tokens(history[i])
            if token_count + msg_tokens > max_tokens:
                cutoff_index = i + 1
                break
            recent_messages.insert(0, history[i])
            token_count += msg_tokens

        # 生成早期对话的压缩摘要
        summary = ""
        if cutoff_index > 0:
            early_msgs = history[:cutoff_index]
            user_msgs = [m.get("content", "") for m in early_msgs if m.get("role") == "user"]
            assistant_msgs = [m.get("content", "") for m in early_msgs if m.get("role") == "assistant"]

            topics = _extract_topics(user_msgs)
            topic_str = "、".join(topics) if topics else "各种话题"

            summary = (
                f"[对话摘要: {len(early_msgs)} 条历史消息, "
                f"涉及 {topic_str}]"
            )

        compressed = summary
        if compressed and recent_messages:
            compressed += "\n\n--- 最近对话 ---"

        logger.info(
            "☱ [兑] 对话浓缩: session=%s %d→%d 条 (est. %d tokens)",
            session_id, original_total, len(recent_messages), token_count,
        )

        return {
            "compressed": compressed,
            "summary": summary,
            "recent_messages": recent_messages,
            "original_total": original_total,
            "compressed_total": len(recent_messages),
            "estimated_tokens": token_count,
        }

    # ========================================================================
    # 核心能力 — 错误格式化
    # ========================================================================

    def _fmt_error(
        self,
        error_message: str = "未知错误",
        error_code: str = "",
    ) -> Dict[str, Any]:
        """格式化错误消息为用户友好的文本

        Args:
            error_message: 错误消息
            error_code:    错误代码

        Returns:
            {"user_message": str, "error_code": str, "severity": str}
        """
        # 根据错误类型分级
        severity = _classify_error_severity(error_message, error_code)

        # 用户友好消息
        user_message = _to_user_friendly(error_message)

        return {
            "user_message": user_message,
            "error_code": error_code,
            "severity": severity,
            "raw": error_message,
            "timestamp": time.time(),
        }

    # ========================================================================
    # 核心能力 — SSE 流式输出
    # ========================================================================

    async def _stream_response(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """SSE 流式输出 — 将文本分块推送

        将 answer 内容按句子或字符边界拆分，逐块生成 SSE 事件。
        调用方（如乾卦的 PRESENT 意图）可读取 chunks 列表并按块流式推送。

        Args:
            params: {
                "answer": str,      # 完整答案文本
                "chunk_size": int,  # 每块字符数（默认 50）
                "delay_ms": int,    # 块间延迟模拟（默认 50ms）
            }

        Returns:
            {
                "total_chunks": int,
                "chunks": [str, ...],
                "sse_events": [str, ...],  # SSE 格式化的事件
                "total_chars": int,
            }
        """
        answer = params.get("answer", "")
        chunk_size = min(params.get("chunk_size", 50), 200)
        delay_ms = min(params.get("delay_ms", 0), 500)

        if not answer:
            return {"total_chunks": 0, "chunks": [], "sse_events": [], "total_chars": 0}

        import re as _re
        # 按句子边界分割（中英文句号、问号、感叹号、换行）
        sentences = _re.split(r'(?<=[。！？.!?\n])', answer)
        # 过滤空段并合并短句
        chunks: List[str] = []
        buf = ""
        for s in sentences:
            s = s.strip()
            if not s:
                continue
            if len(buf) + len(s) < chunk_size:
                buf += s
            else:
                if buf:
                    chunks.append(buf)
                buf = s
        if buf:
            chunks.append(buf)

        # 生成 SSE 事件
        sse_events: List[str] = []
        for i, chunk in enumerate(chunks):
            event = f"data: {chunk}\n\n"
            if i == len(chunks) - 1:
                event += "data: [DONE]\n\n"
            sse_events.append(event)

        # 如果指定了延迟，模拟逐块发送
        if delay_ms > 0:
            await asyncio.sleep(delay_ms / 1000.0)

        logger.debug(
            "☱ [兑] SSE 流式: %d chunks, %d chars",
            len(chunks), len(answer),
        )

        return {
            "total_chunks": len(chunks),
            "chunks": chunks,
            "sse_events": sse_events,
            "total_chars": len(answer),
        }

    # ========================================================================
    # 审计链辅助方法
    # ========================================================================

    def _audit_record(
        self,
        gua_name: str,
        input_data: str,
        output_data: str,
    ) -> Dict[str, Any]:
        """记录一次卦执行到 Merkle 审计链

        Args:
            gua_name:   卦名
            input_data: 输入数据（文本或 JSON 字符串）
            output_data: 输出数据（文本或 JSON 字符串）

        Returns:
            {"leaf_hash": str, "total_leaves": int}
        """
        input_hash = MerkleAuditChain.hash_text(input_data)
        output_hash = MerkleAuditChain.hash_text(output_data)
        leaf_hash = self._audit_chain.add_leaf(
            gua_name, input_hash, output_hash,
        )
        logger.debug(
            "☱ [兑] 审计记录: gua=%s leaf=%s... total=%d",
            gua_name, leaf_hash[:16], len(self._audit_chain.leaves),
        )
        return {
            "leaf_hash": leaf_hash,
            "total_leaves": len(self._audit_chain.leaves),
        }

    def _audit_get_root(self) -> Dict[str, Any]:
        """获取审计链的根 hash

        Returns:
            {"root_hash": str, "leaf_count": int}
        """
        return {
            "root_hash": self._audit_chain.get_root(),
            "leaf_count": len(self._audit_chain.leaves),
        }

    def _audit_verify(
        self,
        gua_name: str,
        input_data: str,
        output_data: str,
        timestamp: float,
    ) -> Dict[str, Any]:
        """验证审计链中的一条记录

        Args:
            gua_name:   卦名
            input_data: 输入数据
            output_data: 输出数据
            timestamp:  记录时间戳

        Returns:
            {"valid": bool, "root_hash": str}
        """
        input_hash = MerkleAuditChain.hash_text(input_data)
        output_hash = MerkleAuditChain.hash_text(output_data)
        root_hash = self._audit_chain.get_root()
        valid = self._audit_chain.verify(
            root_hash, gua_name, input_hash, output_hash, timestamp,
        )
        return {"valid": valid, "root_hash": root_hash}

    # ========================================================================
    # 降级处理
    # ========================================================================

    def _check_history_overflow(self) -> bool:
        """检查对话历史是否超限

        Returns:
            True 如果任意 session 超过 90% 上限
        """
        for history in self._histories.values():
            if len(history) >= int(self.MAX_HISTORY_SIZE * 0.9):
                return True
        return False

    def _fallback_template_format(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """LLM 不可用 → 模板格式化降级"""
        return self._format_answer(
            query=params.get("query", ""),
            answer=params.get("answer", "抱歉，当前以简化模式运行。"),
            sources=params.get("sources", []),
            confidence=params.get("confidence", 0.5),
            mode=params.get("mode", "degraded"),
        )

    def _fallback_trim_history(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """历史超限 → 自动精简"""
        for session_id, history in self._histories.items():
            if len(history) > int(self.MAX_HISTORY_SIZE * 0.8):
                keep = int(self.MAX_HISTORY_SIZE * 0.8)
                self._histories[session_id] = history[-keep:]
                logger.warning(
                    "☱ [兑] Session %s 历史精简完成，保留 %d 条",
                    session_id, keep,
                )
        return self._execute_core(params)


# ============================================================================
# 辅助函数
# ============================================================================


def _extract_topics(user_messages: List[str], max_topics: int = 5) -> List[str]:
    """从用户消息中提取简单话题关键词

    Args:
        user_messages: 用户消息列表
        max_topics:    最多返回的话题数

    Returns:
        话题关键词列表
    """
    import re
    # 高信息量关键词模式（中文话题词）
    topic_patterns = [
        r'(问题|错误|性能|优化|部署|配置|API|接口|数据库|缓存|安全|权限|认证|测试)',
        r'(python|java|go|rust|docker|kubernetes|linux|aws|git)',
    ]

    topic_scores: Dict[str, int] = {}
    for msg in user_messages:
        for pattern in topic_patterns:
            matches = re.findall(pattern, msg, re.IGNORECASE)
            for m in matches:
                topic_scores[m] = topic_scores.get(m, 0) + 1

    # 按频率排序
    sorted_topics = sorted(topic_scores.items(), key=lambda x: x[1], reverse=True)
    return [t for t, _ in sorted_topics[:max_topics]]


def _classify_error_severity(error_message: str, error_code: str = "") -> str:
    """根据错误消息分级

    Args:
        error_message: 错误消息
        error_code:    错误代码

    Returns:
        "critical" | "warning" | "info"
    """
    critical_keywords = ["fatal", "crash", "灾难", "不可恢复", "数据丢失"]
    for kw in critical_keywords:
        if kw.lower() in error_message.lower():
            return "critical"
    return "warning"


def _to_user_friendly(error_message: str) -> str:
    """将技术错误消息转换为用户友好文本

    Args:
        error_message: 原始技术错误消息

    Returns:
        用户友好的消息
    """
    msg_lower = error_message.lower()

    if "connection" in msg_lower or "timeout" in msg_lower or "超时" in error_message:
        return "服务暂时繁忙，请稍后重试。"
    if "permission" in msg_lower or "权限" in error_message:
        return "抱歉，您没有执行该操作的权限。"
    if "not found" in msg_lower or "未找到" in error_message:
        return "未找到您需要的信息，请尝试其他搜索词。"
    if "rate limit" in msg_lower:
        return "请求过于频繁，请稍后重试。"
    if "llm" in msg_lower or "模型" in error_message:
        return "智能服务暂时不可用，系统将以简化模式运行。"

    # 默认消息
    return "抱歉，处理您的请求时遇到问题，请稍后重试。"


__all__ = ["DuiGua", "MerkleAuditChain"]
