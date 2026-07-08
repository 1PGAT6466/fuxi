#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
synthesizer.py — CrossEntitySynthesizer 跨实体合成器

伏羲 v1.50 Phase D: Synthesis 跨实体合成
对标 GBrain 的 Synthesis 合成层：跨文档/人员/公司/交易的整合回答。

设计原则：
  1. 不止返回"相关 chunk 列表" — 跨多个实体/文档/时间线整合信息
  2. 按实体分组聚合 — 同一实体的信息聚合到一段
  3. 按时间线排序 — 如果有日期信息，按时间顺序排列
  4. 关系图谱片段 — 输出实体之间的关系边
  5. 来源引用透明 — 每条信息标注来源文档

核心类：
  CrossEntitySynthesizer  — 跨实体合成回答

使用示例::

    from src.bagua.synthesizer import CrossEntitySynthesizer

    synthesizer = CrossEntitySynthesizer()
    result = synthesizer.synthesize(
        query="张三和李四在阿里巴巴的合作情况",
        retrieved_chunks=[
            {"doc_id": "doc-001", "content": "张三在阿里巴巴负责淘宝项目...", 
             "source": "员工档案.md", "date": "2020-03-15"},
            {"doc_id": "doc-002", "content": "李四于2019年加入阿里巴巴...",
             "source": "入职记录.md", "date": "2019-07-01"},
            ...
        ],
        graph_entities=[
            {"name": "张三", "type": "person"},
            {"name": "李四", "type": "person"},
            {"name": "阿里巴巴", "type": "company"},
            {"name": "淘宝项目", "type": "product"},
        ],
        graph_edges=[
            {"source": "张三", "target": "阿里巴巴", "type": "works_at", "confidence": 0.90},
            {"source": "李四", "target": "阿里巴巴", "type": "works_at", "confidence": 0.85},
            {"source": "张三", "target": "淘宝项目", "type": "leads", "confidence": 0.70},
        ],
    )
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("bagua.synthesizer")


# ============================================================================
# 数据结构
# ============================================================================

@dataclass
class SynthesisResult:
    """合成结果
    
    Attributes:
        query:            原始查询
        synthesized_text:  合成回答文本（Markdown 格式）
        entity_groups:     按实体分组的信息
        relations:         实体关系图片段
        sources:           来源引用列表
        entity_count:      涉及的实体数量
        chunk_count:       使用的 chunk 数量
        mode:              合成模式（cross_entity / fallback_rag）
    """
    query: str = ""
    synthesized_text: str = ""
    entity_groups: List[Dict[str, Any]] = field(default_factory=list)
    relations: List[Dict[str, Any]] = field(default_factory=list)
    sources: List[Dict[str, Any]] = field(default_factory=list)
    entity_count: int = 0
    chunk_count: int = 0
    mode: str = "cross_entity"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "synthesized_text": self.synthesized_text,
            "entity_groups": self.entity_groups,
            "relations": self.relations,
            "sources": self.sources,
            "entity_count": self.entity_count,
            "chunk_count": self.chunk_count,
            "mode": self.mode,
        }


# ============================================================================
# CrossEntitySynthesizer 核心类
# ============================================================================

class CrossEntitySynthesizer:
    """跨实体合成回答
    
    离卦增强：不止返回"相关 chunk 列表"，而是跨多个
    实体/文档/时间线整合信息，生成连贯的合成回答。
    
    对标 GBrain：Synthesis 合成层 + 来源引用。
    
    Attributes:
        entity_patterns:  实体提取正则模式（内置 + 自定义）
        max_chunks:       最大处理 chunk 数
        max_entities:     最大跟踪实体数
        date_pattern:     日期识别正则
    """
    
    # 中文实体提取模式（用于从 chunk 中提取实体名）
    ENTITY_PATTERNS: Dict[str, str] = {
        "person": r"(?:([\u4e00-\u9fff]{2,4})(?:先生|女士|经理|总监|主任|设计师|老师|博士|硕士|CEO|CTO|CFO)?)",
        "company": r"(?:([\u4e00-\u9fff]{2,})(?:公司|集团|科技|有限|股份|实业|控股|技术|企业|工厂|研究所|银行|保险|证券))",
        "product": r"(?:([\u4e00-\u9fff]{2,})(?:项目|平台|系统|产品|方案|服务|应用|软件))",
    }
    
    # 日期提取模式
    DATE_PATTERN: str = r"(\d{4}[-/.]?\d{1,2}[-/.]?\d{1,2})"
    
    def __init__(self, custom_entity_patterns: Optional[Dict[str, str]] = None,
                 max_chunks: int = 20, max_entities: int = 10):
        """初始化合成器
        
        Args:
            custom_entity_patterns:  自定义实体提取模式
            max_chunks:               最大处理 chunk 数
            max_entities:             最大跟踪实体数
        """
        # 合并实体模式
        self.entity_patterns = dict(self.ENTITY_PATTERNS)
        if custom_entity_patterns:
            self.entity_patterns.update(custom_entity_patterns)
        
        # 编译正则
        self._compiled_patterns: Dict[str, re.Pattern] = {}
        for etype, pattern in self.entity_patterns.items():
            try:
                self._compiled_patterns[etype] = re.compile(pattern)
            except re.error as e:
                logger.warning("实体模式编译失败 [%s]: %s — %s", etype, pattern[:60], e)
        
        self._date_re = re.compile(self.DATE_PATTERN)
        
        self.max_chunks = max_chunks
        self.max_entities = max_entities
        
        # 统计
        self._synthesis_count: int = 0
    
    # ========================================================================
    # 核心 API
    # ========================================================================
    
    def synthesize(
        self,
        query: str,
        retrieved_chunks: List[Dict[str, Any]],
        graph_entities: Optional[List[Dict[str, Any]]] = None,
        graph_edges: Optional[List[Dict[str, Any]]] = None,
        entity_names: Optional[List[str]] = None,
    ) -> SynthesisResult:
        """跨实体合成查询
        
        完整流程：
          1. 从 chunk 中提取实体名称
          2. 匹配 graph_entities 获取已知实体
          3. 按实体分组 chunk 信息
          4. 按时间线排序
          5. 整合关系边
          6. 生成格式化文本
        
        Args:
            query:              用户查询
            retrieved_chunks:    RAG 检索的 top-K chunk 列表。
                                每项至少含 {"content": str}，
                                推荐含 {"source": str, "date": str, "doc_id": str}
            graph_entities:      知识图谱实体列表。
                                每项至少含 {"name": str, "type": str}
            graph_edges:         知识图谱边列表。
                                每项至少含 {"source": str, "target": str, "type": str}
            entity_names:        可选，指定要合成的实体列表。
                                不指定则自动从 chunk 和 graph_entities 中提取
        
        Returns:
            SynthesisResult: 合成结果
        """
        if not query:
            return SynthesisResult(query=query, mode="fallback_rag")
        
        if not retrieved_chunks:
            return SynthesisResult(
                query=query,
                synthesized_text=f"## 未找到相关信息\n\n知识库中暂无与「{query}」相关的文档。",
                mode="fallback_rag",
            )
        
        graph_entities = graph_entities or []
        graph_edges = graph_edges or []
        
        # 步骤 1: 提取实体名称
        if entity_names:
            target_entities = list(entity_names)
        else:
            target_entities = self._extract_entity_names(
                query=query,
                chunks=retrieved_chunks,
                graph_entities=graph_entities,
            )
        
        # 如果无实体可提取 → 回退到普通 RAG 模式
        if not target_entities:
            return self._fallback_rag(query, retrieved_chunks)
        
        # 步骤 2: 按实体分组 chunk 信息
        entity_groups = self._group_chunks_by_entity(
            chunks=retrieved_chunks,
            entities=target_entities,
        )
        
        # 步骤 3: 匹配相关边
        relations = self._match_relations(
            entities=target_entities,
            graph_edges=graph_edges,
        )
        
        # 步骤 4: 收集来源
        sources = self._collect_sources(retrieved_chunks)
        
        # 步骤 5: 生成合成文本
        synthesized_text = self._format_synthesis(
            query=query,
            entity_groups=entity_groups,
            relations=relations,
            sources=sources,
        )
        
        # 更新统计
        self._synthesis_count += 1
        
        return SynthesisResult(
            query=query,
            synthesized_text=synthesized_text,
            entity_groups=entity_groups,
            relations=relations,
            sources=sources,
            entity_count=len(target_entities),
            chunk_count=len(retrieved_chunks),
            mode="cross_entity",
        )
    
    # ========================================================================
    # 实体提取
    # ========================================================================
    
    def _extract_entity_names(
        self,
        query: str,
        chunks: List[Dict[str, Any]],
        graph_entities: List[Dict[str, Any]],
    ) -> List[str]:
        """从 query、chunks 和 graph_entities 中提取目标实体名
        
        策略：
          1. 从 graph_entities 中取所有已知实体名作为候选池
          2. 在 query 和 chunks 中搜索这些实体名的出现
          3. 同时用正则从 chunks 中提取可能的实体名
          4. 按出现频率排序，取 top-N
        
        Args:
            query:           用户查询
            chunks:          检索到的 chunk
            graph_entities:  知识图谱实体
        
        Returns:
            实体名列表（按相关性排序）
        """
        # 构建已知实体名集合（来自知识图谱）
        known_names: set = {e.get("name", "") for e in graph_entities if e.get("name")}
        
        # 用已知实体名在 query + chunks 中搜索
        entity_hits: Dict[str, int] = {}
        
        # 在 query 中匹配
        query_lower = query.lower()
        for name in known_names:
            if name.lower() in query_lower:
                entity_hits[name] = entity_hits.get(name, 0) + 2  # query 匹配权重加倍
        
        # 在 chunks 中匹配
        for chunk in chunks[:self.max_chunks]:
            content = chunk.get("content", "")
            content_lower = content.lower()
            for name in known_names:
                if name.lower() in content_lower:
                    entity_hits[name] = entity_hits.get(name, 0) + 1
        
        # 用正则提取候选实体名
        for chunk in chunks[:self.max_chunks]:
            content = chunk.get("content", "")
            for etype, pattern in self._compiled_patterns.items():
                for match in pattern.finditer(content):
                    name = match.group(1).strip() if match.lastindex else match.group().strip()
                    if name and len(name) >= 2:
                        entity_hits[name] = entity_hits.get(name, 0) + 1
        
        # 按命中次数排序
        sorted_entities = sorted(entity_hits.items(), key=lambda x: x[1], reverse=True)
        
        # 取 top-N
        top_entities = [name for name, _ in sorted_entities[:self.max_entities]]
        
        if not top_entities:
            logger.debug("未找到任何实体，回退到 RAG 模式")
        else:
            logger.debug(
                "提取到 %d 个目标实体：%s",
                len(top_entities),
                ", ".join(top_entities[:5]),
            )
        
        return top_entities
    
    # ========================================================================
    # 实体分组
    # ========================================================================
    
    def _group_chunks_by_entity(
        self,
        chunks: List[Dict[str, Any]],
        entities: List[str],
    ) -> List[Dict[str, Any]]:
        """按实体分组 chunk 信息
        
        对每个目标实体：
          - 收集所有提及该实体的 chunk 片段
          - 提取日期信息
          - 按时间排序
        
        Args:
            chunks:    检索到的 chunk
            entities:  目标实体名列表
        
        Returns:
            分组列表，每项格式:
            {
                "entity": str,           # 实体名
                "items": [               # 该实体的相关片段
                    {
                        "text": str,      # 原文片段
                        "source": str,    # 来源文档
                        "date": str,      # 日期（如有）
                        "doc_id": str,    # 文档 ID
                    },
                    ...
                ],
                "mention_count": int,     # 提及次数
            }
        """
        groups: List[Dict[str, Any]] = []
        
        for entity in entities:
            items: List[Dict[str, Any]] = []
            entity_lower = entity.lower()
            
            for chunk in chunks[:self.max_chunks]:
                content = chunk.get("content", "")
                
                # 检查 chunk 中是否提及该实体
                if entity_lower not in content.lower():
                    continue
                
                # 提取相关片段（实体周围 500 字符）
                snippet = self._extract_snippet(content, entity, window=500)
                
                # 提取日期
                date = chunk.get("date", "")
                if not date:
                    date_match = self._date_re.search(content)
                    if date_match:
                        date = date_match.group(1)
                
                items.append({
                    "text": snippet,
                    "source": chunk.get("source", chunk.get("doc_id", "未知文档")),
                    "date": date,
                    "doc_id": chunk.get("doc_id", ""),
                })
            
            # 按日期排序
            items.sort(key=lambda x: x.get("date", "0000-00-00") or "0000-00-00")
            
            if items:
                groups.append({
                    "entity": entity,
                    "items": items,
                    "mention_count": len(items),
                })
        
        # 实体间按提及次数排序
        groups.sort(key=lambda g: g["mention_count"], reverse=True)
        
        return groups
    
    def _extract_snippet(self, text: str, keyword: str, window: int = 500) -> str:
        """从文本中提取关键词周围片段
        
        Args:
            text:     原始文本
            keyword:  关键词
            window:   窗口大小（字符数）
        
        Returns:
            截取的片段
        """
        idx = text.lower().find(keyword.lower())
        if idx < 0:
            # 关键词不在文本中，取开头
            return text[:window] + ("..." if len(text) > window else "")
        
        start = max(0, idx - window // 2)
        end = min(len(text), start + window)
        
        snippet = text[start:end].strip()
        prefix = "..." if start > 0 else ""
        suffix = "..." if end < len(text) else ""
        
        return prefix + snippet + suffix
    
    # ========================================================================
    # 关系匹配
    # ========================================================================
    
    def _match_relations(
        self,
        entities: List[str],
        graph_edges: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """匹配实体间的关系边
        
        从 graph_edges 中筛选 source 或 target 在 target_entities 中的边。
        
        Args:
            entities:     目标实体名列表
            graph_edges:  知识图谱边列表
        
        Returns:
            相关边列表，每项格式:
            {
                "source": str,
                "target": str,
                "type": str,
                "confidence": float,
                "evidence": str,
            }
        """
        entity_set = set(entities)
        matched: List[Dict[str, Any]] = []
        seen: set = set()
        
        for edge in graph_edges:
            source = edge.get("source", "")
            target = edge.get("target", "")
            
            # 源或目标在目标实体中
            if source in entity_set or target in entity_set:
                key = (source, target, edge.get("type", ""))
                if key not in seen:
                    seen.add(key)
                    matched.append({
                        "source": source,
                        "target": target,
                        "type": edge.get("type", edge.get("relation", "related_to")),
                        "confidence": edge.get("confidence", 0.5),
                        "evidence": edge.get("evidence", edge.get("description", "")),
                    })
        
        # 按置信度排序
        matched.sort(key=lambda e: e.get("confidence", 0), reverse=True)
        
        return matched
    
    # ========================================================================
    # 来源收集
    # ========================================================================
    
    def _collect_sources(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """收集并去重来源引用
        
        Args:
            chunks: 检索到的 chunk
        
        Returns:
            去重后的来源列表
        """
        seen: set = set()
        sources: List[Dict[str, Any]] = []
        
        for chunk in chunks[:self.max_chunks]:
            source = chunk.get("source", chunk.get("doc_id", ""))
            if source and source not in seen:
                seen.add(source)
                sources.append({
                    "source": source,
                    "date": chunk.get("date", ""),
                    "doc_id": chunk.get("doc_id", ""),
                })
        
        return sources
    
    # ========================================================================
    # 格式化输出
    # ========================================================================
    
    def _format_synthesis(
        self,
        query: str,
        entity_groups: List[Dict[str, Any]],
        relations: List[Dict[str, Any]],
        sources: List[Dict[str, Any]],
    ) -> str:
        """格式化合成回答（Markdown）
        
        输出格式：
        
        ## 关于 [实体A]
        · [chunk1 中的相关信息]
        · [chunk2 中的相关信息]
        > 来源：[文档名] (时间)
        
        ## 关于 [实体B]
        ...
        
        ## 关联关系
        · [实体A] → [关系类型] → [实体B]
        
        Args:
            query:          原始查询
            entity_groups:  按实体分组的信息
            relations:      实体关系
            sources:        来源引用
        
        Returns:
            Markdown 格式的合成文本
        """
        lines: List[str] = []
        
        # 标题
        lines.append(f"## 跨实体合成回答")
        lines.append(f"")
        lines.append(f"> 查询：{query}")
        lines.append(f"")
        
        # 各实体信息
        for group in entity_groups:
            entity = group["entity"]
            items = group["items"]
            
            lines.append(f"### 关于 {entity}")
            lines.append("")
            
            for item in items:
                # 使用 · 作为列表项
                text = item["text"][:500]  # 截断过长文本
                lines.append(f"· {text}")
            
            lines.append("")
            
            # 来源
            item_sources = set()
            for item in items:
                source = item["source"]
                date = item.get("date", "")
                if source and source not in item_sources:
                    item_sources.add(source)
                    date_str = f" ({date})" if date else ""
                    lines.append(f"> 来源：{source}{date_str}")
            
            lines.append("")
        
        # 关联关系
        if relations:
            lines.append(f"### 关联关系")
            lines.append("")
            for rel in relations:
                source = rel["source"]
                target = rel["target"]
                rel_type = rel["type"]
                confidence = rel.get("confidence", 0.5)
                conf_str = f" (置信度: {confidence:.0%})" if confidence < 1.0 else ""
                lines.append(f"· **{source}** → {rel_type} → **{target}**{conf_str}")
            
            lines.append("")
        
        # 来源汇总
        if sources:
            lines.append(f"### 来源汇总")
            lines.append("")
            for i, src in enumerate(sources, 1):
                date_str = f" ({src['date']})" if src.get("date") else ""
                lines.append(f"{i}. {src['source']}{date_str}")
            
            lines.append("")
        
        # 元数据
        lines.append(f"---")
        lines.append(
            f"*合成统计：{len(entity_groups)} 个实体 | "
            f"{sum(g['mention_count'] for g in entity_groups)} 条信息 | "
            f"{len(relations)} 个关系 | "
            f"{len(sources)} 个来源*"
        )
        
        return "\n".join(lines)
    
    # ========================================================================
    # 回退模式
    # ========================================================================
    
    def _fallback_rag(
        self, query: str, chunks: List[Dict[str, Any]]
    ) -> SynthesisResult:
        """空实体时的回退：普通 RAG 模式
        
        当无法从检索结果中提取到实体时，回退到简单的 chunk 列表展示。
        
        Args:
            query:  查询
            chunks: 检索 chunk
        
        Returns:
            SynthesisResult (mode="fallback_rag")
        """
        lines = [
            f"## 检索结果",
            f"",
            f"> 查询：{query}",
            f"",
            f"*未检测到明确的实体，以下为知识库中的相关内容：*",
            f"",
        ]
        
        sources_set: set = set()
        for i, chunk in enumerate(chunks[:10], 1):
            content = chunk.get("content", "")
            source = chunk.get("source", chunk.get("doc_id", "未知"))
            date = chunk.get("date", "")
            
            preview = content[:300] + ("..." if len(content) > 300 else "")
            lines.append(f"{i}. {preview}")
            date_str = f" ({date})" if date else ""
            lines.append(f"   > 来源：{source}{date_str}")
            lines.append("")
            
            sources_set.add(source)
        
        sources = [{"source": s} for s in sources_set]
        
        return SynthesisResult(
            query=query,
            synthesized_text="\n".join(lines),
            entity_groups=[],
            relations=[],
            sources=sources,
            entity_count=0,
            chunk_count=len(chunks),
            mode="fallback_rag",
        )
    
    # ========================================================================
    # 便捷方法
    # ========================================================================
    
    def synthesize_from_rag_result(
        self,
        query: str,
        rag_result: Dict[str, Any],
        graph_data: Optional[Dict[str, Any]] = None,
    ) -> SynthesisResult:
        """从 RAG 检索结果直接合成
        
        便捷方法：将 RAG 返回的 dict 直接传入。
        
        Args:
            query:       用户查询
            rag_result:  RAG 检索结果 {"results": [...], "total": int}
            graph_data:  知识图谱数据 {"entities": [...], "edges": [...]}
        
        Returns:
            SynthesisResult
        """
        chunks = rag_result.get("results", [])
        if not chunks:
            chunks = rag_result.get("data", [])
        
        graph_data = graph_data or {}
        graph_entities = graph_data.get("entities", [])
        graph_edges = graph_data.get("edges", [])
        
        return self.synthesize(
            query=query,
            retrieved_chunks=chunks,
            graph_entities=graph_entities,
            graph_edges=graph_edges,
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_synthesis": self._synthesis_count,
            "max_chunks": self.max_chunks,
            "max_entities": self.max_entities,
            "entity_patterns": len(self._compiled_patterns),
        }


# ============================================================================
# 全局单例
# ============================================================================

_global_synthesizer: Optional[CrossEntitySynthesizer] = None


def get_synthesizer() -> CrossEntitySynthesizer:
    """获取全局 CrossEntitySynthesizer 单例"""
    global _global_synthesizer
    if _global_synthesizer is None:
        _global_synthesizer = CrossEntitySynthesizer()
    return _global_synthesizer


# ============================================================================
# 模块导出
# ============================================================================

__all__ = [
    "CrossEntitySynthesizer",
    "SynthesisResult",
    "get_synthesizer",
]
