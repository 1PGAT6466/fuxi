#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
auto_graph.py — 自组网知识图谱构建器

伏羲 v1.50 Phase B: Self-Wiring Knowledge Graph
对标 GBrain 的 Self-Wiring KG — 写入时自动提取实体+类型化边，零 LLM 调用。

设计原则：
  1. 零 LLM 调用 — 全部基于正则 + 规则，GPU/API 成本为零
  2. 确定性 — 相同输入 → 相同输出，可复现、可审计
  3. 高性能 — 正则引擎是 O(n)，单文档处理 < 10ms
  4. 可扩展 — ENTITY_PATTERNS 和 EDGE_RULES 均可热加载/追加

核心类：
  AutoGraphBuilder  — 文档入库时自动建图

使用示例::

    from src.bagua.auto_graph import AutoGraphBuilder

    builder = AutoGraphBuilder()
    text = "张三在阿里巴巴工作，负责淘宝项目。他于2020年参加了云栖大会。"
    entities = builder.extract_entities(text)
    edges = builder.build_from_text(text, doc_id="doc-001")

参考：
  GBrain: garrytan/gbrain — Self-Wiring KG, P@5 49.1% / R@5 97.9%
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("bagua.auto_graph")

# ============================================================================
# 实体提取模式 — 正则规则（零 LLM）
# ============================================================================

ENTITY_PATTERNS: Dict[str, str] = {
    # 英文人名：类似 "John Smith" 或 "John M. Smith"
    "person": r"\b(?:[A-Z][a-z]+(?:\s+(?:[A-Z]\.?\s+)?[A-Z][a-z]+)+)\b",
    
    # 公司/组织名：英文 + 中文
    "company": r"\b(?:[A-Z][a-zA-Z]*(?:\s+[A-Z][a-zA-Z]*)*\s*(?:Inc\.?|Corp\.?|LLC|Ltd\.?|Corporation|Limited)"
              r"|[\u4e00-\u9fff]{2,}(?:公司|集团|科技|有限|股份|实业|控股|技术|企业|工厂|研究所))",
    
    # 日期：YYYY-MM-DD / YYYY/MM/DD / YYYY.MM.DD
    # 注：不用 \b 因为中文上下文中 \b 不匹配
    "date": r"\d{4}[-/.]\d{1,2}[-/.]\d{1,2}",
    
    # 金额/价格
    # 支持：$12,500 / 500万元 / $1,234.56 USD / 采购金额500万元
    # 必须包含货币标志：$、万、亿、元 或 ISO 货币代码
    "money": r"\$\d{1,3}(?:,\d{3})*(?:\.\d+)?(?:\s*(?:dollars?|USD|CNY|JPY|EUR|RMB))?"
             r"|\d+(?:,\d{3})*(?:\.\d+)?\s*(?:万|亿|元|块)",
    
    # 产品编号：大写字母+数字+连字符的组合，如 HG-KN43BJ-S100
    "product": r"\b[A-Z]{2,}[-]?[A-Z0-9]+(?:-[A-Z0-9]+)*\b",
    
    # 电话号码
    "phone": r"\b(?:1[3-9]\d{9}|\d{3,4}-\d{7,8}|\+\d{1,3}\s?\d{3,4}\s?\d{4,8})\b",
    
    # 邮箱
    "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
    
    # 技术/设备型号：字母数字混合标识
    "device": r"\b[A-Z]{2,6}[-]?\d{2,4}[A-Z]?\b",
    
    # URL
    "url": r"\bhttps?://[^\s<>\"|\\^`{}\[\]]+\b",
    
    # 中文人名（简单版：2-4个汉字 + 常见后缀）
    # 注：会有误匹配（如 "项目于"），但日期/金额/产品等优先级更高
    "chinese_name": r"[\u4e00-\u9fff]{2,4}(?:先生|女士|经理|总监|主任|设计师|老师|博士|硕士|CEO|CTO|CFO)?",
    
    # 材料/物料编号
    # 注：不用 \b 因为中文上下文中 \b 不匹配
    "material": r"(?:PA\d{2}|\b(?:PC|ABS|PP|PE|PVC|POM|PMMA|PBT|PET|TPE|TPU)\b"
                r"|不锈钢|铝合金|钛合金|碳纤维"
                r"|[A-Z]{2,5}[-]?\d{2,4}[-]?[A-Z0-9]*)",
    
    # 品牌名（常见工业品牌）
    "brand": r"\b(?:MISUMI|SMC|FESTO|Bosch|Siemens|ABB|Omron|Keyence|Panasonic|三菱|松下|施耐德|西门子)"
            r"|(?:[\u4e00-\u9fff]{2,}(?:品牌|牌))",
}

# ============================================================================
# 边关系规则 — 基于模式的规则引擎（零 LLM）
# ============================================================================

EDGE_RULES: List[Tuple[str, str, float]] = [
    # (正则模式, 边类型, 置信度)
    
    # 雇佣关系 — "在X工作/任职/上班"
    (r"(\w+|[\u4e00-\u9fff]{2,4})\s*(?:在|于|at)\s*(\w+|[\u4e00-\u9fff]{2,}(?:公司|集团|科技))"
     r"\s*(?:工作|任职|上班|就职|服务)",
     "works_at", 0.90),
    
    # 投资关系
    (r"(\w+|[\u4e00-\u9fff]{2,}(?:公司|集团|科技)?)\s*(?:投资|参投|invested?\s*(?:in)?|入股|注资)\s*"
     r"(\w+|[\u4e00-\u9fff]{2,}(?:公司|集团|科技|项目)?)",
     "invested_in", 0.85),
    
    # 出席会议/活动
    (r"(\w+|[\u4e00-\u9fff]{2,4})\s*(?:参加|出席|参与|attended)\s*"
     r"(\w.+?|[\u4e00-\u9fff]{2,}.+?)(?:\s*(?:会议|大会|峰会|论坛|meeting|conference|summit|forum))",
     "attended", 0.80),
    
    # 创建/成立
    (r"(\w+|[\u4e00-\u9fff]{2,4})\s*(?:创建|创立|成立|创办|建立|founded|created|established|launched)\s*"
     r"(\w+|[\u4e00-\u9fff]{2,}(?:公司|集团|项目|团队|组织|部门)?)",
     "founded", 0.85),
    
    # 领导/负责
    (r"(\w+|[\u4e00-\u9fff]{2,4})\s*(?:负责|担任|主管|管理|领导|leads?|manages?|heads?|directs?)\s*"
     r"(\w+|[\u4e00-\u9fff]{2,}(?:部门|团队|项目|小组|委员会|事业部|中心)?)",
     "leads", 0.70),
    
    # 采购/购买
    (r"(\w+|[\u4e00-\u9fff]{2,}(?:部门|公司|工厂|项目)?)\s*(?:采购|购买|订购|buy|purchase|order)\s*"
     r"(\w+|[\u4e00-\u9fff]{2,}(?:设备|产品|物料|零件|部件|材料)?)",
     "purchased", 0.75),
    
    # 供应商关系
    (r"(\w+|[\u4e00-\u9fff]{2,})\s*(?:是|is)\s*(\w+|[\u4e00-\u9fff]{2,})"
     r"\s*(?:的)\s*(?:供应商|厂商|供货商|制造商|生产商|supplier|manufacturer|vendor)",
     "supplier_of", 0.80),
    
    # 客户关系
    (r"(\w+|[\u4e00-\u9fff]{2,})\s*(?:是|is)\s*(\w+|[\u4e00-\u9fff]{2,})"
     r"\s*(?:的)\s*(?:客户|采购方|买家|customer|client|buyer)",
     "customer_of", 0.80),
    
    # 包含关系 — "A 包含/包括/由...组成 B"
    (r"(\w+|[\u4e00-\u9fff]{2,}(?:系统|平台|产品|设备|项目|方案)?)\s*(?:包含|包括|由|consists?\s*(?:of)?|comprises?|includes?)\s*"
     r"(\w+|[\u4e00-\u9fff]{2,}(?:模块|组件|部件|零件|物料|功能)?)",
     "contains", 0.75),
    
    # 合作/协作
    (r"(\w+|[\u4e00-\u9fff]{2,}(?:公司|集团|部门|团队)?)\s*(?:与|和|同|合作|协作|collaborates?\s*(?:with)?|partners?\s*(?:with)?)\s*"
     r"(\w+|[\u4e00-\u9fff]{2,}(?:公司|集团|部门|团队)?)",
     "collaborates_with", 0.75),
    
    # 位于/地点关系
    (r"(\w+|[\u4e00-\u9fff]{2,}(?:公司|集团|总部|工厂|办公处)?)\s*(?:位于|坐落|在|总部设在|located?\s*(?:in|at)?|based?\s*(?:in)?)\s*"
     r"(\w+|[\u4e00-\u9fff]{2,})",
     "located_in", 0.70),
]


# ============================================================================
# AutoGraphBuilder 核心类
# ============================================================================

class AutoGraphBuilder:
    """自组网知识图谱构建器
    
    坤卦后处理：文档入库时自动建图。
    纯规则驱动，零 LLM 调用，全部基于正则 + 规则引擎。
    
    Attributes:
        entity_patterns:    实体提取正则模式字典 {type: pattern}
        edge_rules:         边关系规则列表 [(pattern, type, confidence)]
        compiled_entities:  预编译的实体模式
        compiled_edges:     预编译的边规则
    """
    
    def __init__(self, custom_patterns: Optional[Dict[str, str]] = None,
                 custom_rules: Optional[List[Tuple[str, str, float]]] = None):
        """初始化构建器
        
        Args:
            custom_patterns:  自定义实体提取模式（会与默认合并）
            custom_rules:     自定义边规则（会追加到默认规则之后）
        """
        # 合并实体模式
        self.entity_patterns: Dict[str, str] = dict(ENTITY_PATTERNS)
        if custom_patterns:
            self.entity_patterns.update(custom_patterns)
        
        # 编译实体正则（预编译提升性能）
        self._compiled_entities: Dict[str, re.Pattern] = {}
        for etype, pattern in self.entity_patterns.items():
            try:
                self._compiled_entities[etype] = re.compile(pattern, re.IGNORECASE)
            except re.error as e:
                logger.warning("实体模式编译失败 [%s]: %s — %s", etype, pattern[:60], e)
        
        # 合并边规则（自定义规则在前，优先级更高）
        self.edge_rules: List[Tuple[str, str, float]] = list(custom_rules or []) + list(EDGE_RULES)
        
        # 编译边规则正则
        self._compiled_edges: List[Tuple[re.Pattern, str, float]] = []
        for pattern, etype, confidence in self.edge_rules:
            try:
                self._compiled_edges.append((re.compile(pattern, re.IGNORECASE), etype, confidence))
            except re.error as e:
                logger.warning("边规则编译失败 [%s]: %s — %s", etype, pattern[:60], e)
        
        # 统计
        self._built_count: int = 0
        self._total_entities: int = 0
        self._total_edges: int = 0
    
    # ========================================================================
    # 核心 API
    # ========================================================================
    
    def build_from_text(self, text: str, doc_id: str = "") -> List[Dict[str, Any]]:
        """从文本构建知识图谱边列表
        
        完整流程：
          1. 提取实体
          2. 基于规则匹配边关系
          3. 去重 + 按置信度排序
          4. 返回边列表
        
        Args:
            text:   文档文本内容
            doc_id: 文档唯一标识
        
        Returns:
            边列表，每项格式:
            {
                "source": str,        # 源实体名
                "target": str,        # 目标实体名
                "type": str,          # 边类型 (works_at, supplied_by, ...)
                "confidence": float,  # 置信度 (0-1)
                "doc_id": str,        # 来源文档 ID
                "evidence": str,      # 匹配到的原文片段
            }
        """
        if not text or not text.strip():
            return []
        
        # 步骤 1: 提取实体
        entities = self.extract_entities(text)
        
        # 步骤 2: 基于规则匹配边
        edges = self._extract_edges(text, entities, doc_id)
        
        # 步骤 3: 去重 — 相同 source/target/type 只保留 confidence 最高的
        deduped = self._deduplicate_edges(edges)
        
        # 步骤 4: 按置信度降序排序
        deduped.sort(key=lambda e: e["confidence"], reverse=True)
        
        # 更新统计
        self._built_count += 1
        self._total_entities += len(entities)
        self._total_edges += len(deduped)
        
        logger.debug(
            "AutoGraph: 文档 %s 提取 %d 实体, %d 条边 (去重后 %d)",
            doc_id, len(entities), len(edges), len(deduped),
        )
        
        return deduped
    
    def extract_entities(self, text: str) -> List[Dict[str, Any]]:
        """从文本中提取所有实体
        
        对所有已注册的实体模式逐一匹配，返回去重后的实体列表。
        后处理规则：
          - 中文人名：过滤掉过短（1字）或过长（>4字，去掉后缀后）
          - 日期/金额/URL：不在产品编号类中重复提取
          - 同一名称被多个类型匹配时，按优先级保留（product > company > person > chinese_name）
        
        Args:
            text: 待提取的文本
        
        Returns:
            实体列表，每项格式:
            {
                "name": str,         # 实体名称
                "type": str,         # 实体类型 (person, company, date, money, product, ...)
                "positions": list,   # [(start, end), ...] — 在原文中的位置
                "count": int,        # 出现次数
            }
        """
        if not text:
            return []
        
        # 阶段 1: 所有模式匹配
        raw_matches: Dict[str, Dict[str, List[Tuple[int, int]]]] = {}
        
        for etype, pattern in self._compiled_entities.items():
            raw_matches[etype] = {}
            for match in pattern.finditer(text):
                name = match.group().strip()
                # 跳过纯数字/太短
                if len(name) < 2:
                    continue
                # 跳过纯标点
                if not any(c.isalnum() or '\u4e00' <= c <= '\u9fff' or '\u3040' <= c <= '\u30ff' for c in name):
                    continue
                
                start, end = match.span()
                if name not in raw_matches[etype]:
                    raw_matches[etype][name] = []
                raw_matches[etype][name].append((start, end))
        
        # 阶段 2: 后处理 + 合并
        entities: List[Dict[str, Any]] = []
        seen_names: Dict[str, str] = {}  # name → type (用于优先级去重)
        
        # 优先级排序：更具体的类型优先
        type_priority = [
            "date", "money", "email", "phone", "url",       # 明确的格式
            "product", "material", "device", "brand",        # 产品/物料类
            "company",                                       # 公司/组织
            "chinese_name", "person",                        # 人名
        ]
        # 确保所有编译的类型都在优先级中
        for etype in self._compiled_entities:
            if etype not in type_priority:
                type_priority.append(etype)
        
        for etype in type_priority:
            if etype not in raw_matches:
                continue
            
            for name, positions in raw_matches[etype].items():
                # 后处理：过滤无效的中文人名
                if etype == "chinese_name":
                    # 去掉常见后缀后检查
                    name_stripped = re.sub(r'(先生|女士|经理|总监|主任|工程师|设计师|老师|博士|硕士|总裁|CEO|CTO|CFO)$', '', name)
                    if len(name_stripped) < 2 or len(name_stripped) > 4:
                        continue
                    # 不是纯中文字符的人名跳过
                    if not re.match(r'^[\u4e00-\u9fff]{2,4}$', name_stripped):
                        continue
                
                # 后处理：过滤过短/过长的英文人名
                if etype == "person":
                    name_stripped = name.strip()
                    if len(name_stripped) < 5:  # "A B" 至少 3+space+1
                        continue
                
                # 后处理：company 名不能太短
                if etype == "company":
                    if len(name) < 3:
                        continue
                
                # 去重：如果名称已被更高优先级类型匹配，跳过
                if name in seen_names:
                    existing_type = seen_names[name]
                    # 当前类型优先级低于已存在的，跳过
                    existing_priority = type_priority.index(existing_type) if existing_type in type_priority else 999
                    current_priority = type_priority.index(etype) if etype in type_priority else 999
                    if current_priority > existing_priority:
                        continue
                
                seen_names[name] = etype
                entities.append({
                    "name": name,
                    "type": etype,
                    "positions": positions,
                    "count": len(positions),
                })
        
        return entities
    
    # ========================================================================
    # 内部方法
    # ========================================================================
    
    def _extract_edges(self, text: str, entities: List[Dict[str, Any]],
                       doc_id: str) -> List[Dict[str, Any]]:
        """基于规则匹配边关系
        
        策略：
          1. 对文本全文匹配每个 EDGE_RULES 正则
          2. 从匹配的 group(1) 和 group(2) 中提取源/目标实体
          3. 模糊匹配到 actually extracted 的实体
          4. 如果实体出现在匹配文本中，则建立边
        
        Args:
            text:     文档文本
            entities: 已提取的实体
            doc_id:   文档 ID
        
        Returns:
            边列表
        """
        edges: List[Dict[str, Any]] = []
        
        if not entities or not text:
            return edges
        
        # 构建实体名集合用于快速查找
        entity_names: set = {e["name"] for e in entities}
        
        # 对每个边规则匹配全文
        for pattern, etype, confidence in self._compiled_edges:
            for match in pattern.finditer(text):
                try:
                    source_raw = match.group(1).strip()
                    target_raw = match.group(2).strip()
                except IndexError:
                    continue
                
                if not source_raw or not target_raw:
                    continue
                
                # 模糊匹配：查找实体中是否包含 source_raw 或 target_raw
                source_entity = self._find_best_entity(source_raw, entity_names)
                target_entity = self._find_best_entity(target_raw, entity_names)
                
                if source_entity and target_entity and source_entity != target_entity:
                    evidence = match.group(0).strip()[:200]
                    edges.append({
                        "source": source_entity,
                        "target": target_entity,
                        "type": etype,
                        "confidence": confidence,
                        "doc_id": doc_id,
                        "evidence": evidence,
                    })
        
        return edges
    
    @staticmethod
    def _find_best_entity(raw_name: str, entity_names: set) -> Optional[str]:
        """在已知实体集中模糊匹配最佳实体
        
        匹配策略：
          1. 精确匹配 → 直接返回
          2. raw_name 是某个实体名的子串 → 返回该实体
          3. raw_name 包含某个实体名 → 返回该实体
          4. 都不匹配 → None
        
        Args:
            raw_name:      从边规则中提取的原始名称
            entity_names:  已提取的实体名集合
        
        Returns:
            匹配到的实体名，或 None
        """
        if raw_name in entity_names:
            return raw_name
        
        # 从最长实体名开始尝试
        sorted_entities = sorted(entity_names, key=len, reverse=True)
        
        for entity_name in sorted_entities:
            # raw_name 是实体名的子串
            if raw_name in entity_name:
                return entity_name
            # 实体名是 raw_name 的子串
            if entity_name in raw_name:
                return entity_name
        
        return None
    
    @staticmethod
    def _deduplicate_edges(edges: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """边去重：相同 (source, target, type) 保留置信度最高的
        
        Args:
            edges: 原始边列表
        
        Returns:
            去重后的边列表
        """
        best: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
        
        for edge in edges:
            key = (edge["source"], edge["target"], edge["type"])
            if key not in best or edge["confidence"] > best[key]["confidence"]:
                best[key] = edge
        
        return list(best.values())
    
    # ========================================================================
    # 综合构建 — 返回实体 + 边（供坤卦集成使用）
    # ========================================================================
    
    def build_full_graph(self, text: str, doc_id: str = "") -> Dict[str, Any]:
        """构建完整图形：实体 + 边
        
        这是 build_from_text 的扩展版，同时返回实体和边。
        适用于需要直接写入 store_graph() 的场景。
        
        Args:
            text:   文档文本
            doc_id: 文档标识
        
        Returns:
            {
                "doc_id": str,
                "entities": [...],  # 实体列表
                "edges": [...],     # 边列表
                "stats": {
                    "entity_count": int,
                    "edge_count": int,
                    "built_at": str,
                }
            }
        """
        entities = self.extract_entities(text)
        edges = self.build_from_text(text, doc_id)
        
        # 转换为 store_graph 需要的格式
        graph_entities = [
            {
                "name": e["name"],
                "type": e["type"],
                "description": f"从文档 {doc_id} 中提取的 {e['type']}",
                "count": e["count"],
            }
            for e in entities
        ]
        
        graph_relations = [
            {
                "source": edge["source"],
                "target": edge["target"],
                "relation": edge["type"],
                "description": edge.get("evidence", ""),
                "confidence": edge["confidence"],
            }
            for edge in edges
        ]
        
        return {
            "doc_id": doc_id,
            "entities": graph_entities,
            "edges": graph_relations,
            "stats": {
                "entity_count": len(graph_entities),
                "edge_count": len(graph_relations),
                "built_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            },
        }
    
    # ========================================================================
    # 扩展：追加自定义规则（热加载）
    # ========================================================================
    
    def add_entity_pattern(self, name: str, pattern: str) -> bool:
        """动态添加实体提取模式
        
        Args:
            name:    实体类型名
            pattern: 正则表达式
        
        Returns:
            是否成功
        """
        try:
            compiled = re.compile(pattern, re.IGNORECASE)
            self._compiled_entities[name] = compiled
            self.entity_patterns[name] = pattern
            logger.info("AutoGraph: 添加实体模式 [%s] — %s", name, pattern[:60])
            return True
        except re.error as e:
            logger.error("AutoGraph: 实体模式编译失败 [%s] — %s", name, e)
            return False
    
    def add_edge_rule(self, pattern: str, edge_type: str, confidence: float) -> bool:
        """动态添加边关系规则
        
        Args:
            pattern:    正则模式（必须包含两个捕获组）
            edge_type:  边类型名
            confidence: 置信度 (0-1)
        
        Returns:
            是否成功
        """
        try:
            compiled = re.compile(pattern, re.IGNORECASE)
            self._compiled_edges.append((compiled, edge_type, float(confidence)))
            self.edge_rules.append((pattern, edge_type, float(confidence)))
            logger.info("AutoGraph: 添加边规则 [%s] (conf=%.2f) — %s", edge_type, confidence, pattern[:60])
            return True
        except re.error as e:
            logger.error("AutoGraph: 边规则编译失败 [%s] — %s", edge_type, e)
            return False
    
    # ========================================================================
    # 统计
    # ========================================================================
    
    def get_stats(self) -> Dict[str, Any]:
        """获取构建器统计信息
        
        Returns:
            {
                "total_builds": int,         # 总构建次数
                "total_entities": int,       # 累计提取实体数
                "total_edges": int,          # 累计提取边数
                "entity_patterns": int,      # 实体模式数
                "edge_rules": int,           # 边规则数
                "llm_calls": 0,              # 零 LLM 保证
            }
        """
        return {
            "total_builds": self._built_count,
            "total_entities": self._total_entities,
            "total_edges": self._total_edges,
            "entity_patterns": len(self._compiled_entities),
            "edge_rules": len(self._compiled_edges),
            "llm_calls": 0,  # 零 LLM 保证
        }


# ============================================================================
# 全局单例
# ============================================================================

_global_builder: Optional[AutoGraphBuilder] = None


def get_auto_graph_builder() -> AutoGraphBuilder:
    """获取全局 AutoGraphBuilder 单例
    
    Returns:
        AutoGraphBuilder 实例
    """
    global _global_builder
    if _global_builder is None:
        _global_builder = AutoGraphBuilder()
    return _global_builder


# ============================================================================
# 模块导出
# ============================================================================

__all__ = [
    "AutoGraphBuilder",
    "ENTITY_PATTERNS",
    "EDGE_RULES",
    "get_auto_graph_builder",
]
