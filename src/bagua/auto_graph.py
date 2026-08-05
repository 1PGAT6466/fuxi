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


import logging
import re
import time
import json
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("bagua.auto_graph")

# ============================================================================
# 增强版中文 NER 模式 — 补充 ENTITY_PATTERNS
# 用于 EnhancedAutoGraphBuilder 的规则抽取降级方案
# ============================================================================

ENHANCED_ENTITY_PATTERNS: Dict[str, str] = {
    # 中文人名（增强版）— 支持姓名后跟职务/角色，或前面有"由""请"等动词
    "chinese_person": (
        r'(?:由|请|让|派|通知|联系)\s*([\u4e00-\u9fff]{2,4})'
        r'|([\u4e00-\u9fff]{2,4})(?:总工程师|工程师|研究员|教授|博士|总经理|副总|'
        r'部长|科长|处长|主管|经理|总监|主任|书记|主席|院长|校长|所长)'
    ),
    # 中文组织机构名（增强版）— 支持更多组织类型后缀
    "chinese_org": (
        r'[\u4e00-\u9fff]{2,}(?:大学|学院|研究院|研究所|实验室|中心|学会|协会|'
        r'委员会|基金会|联盟|组织|部门|厅|局|处|科|办|站|院|所|厂|矿|场|店|'
        r'银行|证券|保险|基金|投资)'
    ),
    # 中文地名（增强版）— 支持省市区县镇村及地理实体
    "chinese_location": (
        r'[\u4e00-\u9fff]{2,}(?:省|市|区|县|镇|村|乡|街道|路|大道|街|巷|号|'
        r'工业区|开发区|高新区|新区|园区|基地)'
    ),
    # 技术术语 — 常见工业/制造技术关键词
    "tech_term": (
        r'(?:注塑|冲压|压铸|锻造|焊接|切割|打磨|抛光|电镀|喷涂|热处理|'
        r'退火|淬火|回火|渗碳|氮化|阳极氧化|钝化|磷化|电泳|粉末冶金|'
        r'CNC|数控|加工中心|车床|铣床|磨床|钻床|线切割|放电加工|EDM|'
        r'三坐标|CMM|投影仪|卡尺|千分尺|粗糙度|硬度|拉伸|压缩|弯曲|'
        r'疲劳|蠕变|冲击|韧性|强度|刚度|硬度|耐磨|耐腐蚀|绝缘|导热)'
    ),
    # 产品型号 — 支持中英文混合型号，如 "HG-KN43BJ" "M3x10" "φ10H7"
    "product_model": (
        r'\b[A-Z]{1,6}[-]?\d{2,6}[A-Z]?(?:[-/][A-Z0-9]+)*\b'
        r'|[Mm]\d+[xX×]\d+(?:\.\d+)?'
        r'|[φΦ]\d+(?:\.\d+)?[A-Z]?\d*'
    ),
}

# LLM 实体抽取/关系抽取配置
_LLM_API_KEY = None  # 延迟加载，避免循环导入
_LLM_BASE_URL = None
_LLM_MODEL = None
_LLM_TIMEOUT = 30  # 秒
_LLM_ENTITY_PROMPT = """请从以下文本中提取所有实体，返回 JSON 格式：
{"entities": [{"name": "实体名", "type": "person/org/location/product/tech_term/other", "confidence": 0.9}]}

文本：
{text}

仅返回 JSON，不要解释。"""

_LLM_RELATION_PROMPT = """请从以下文本中提取实体间关系，返回 JSON 格式：
{"relations": [{"source": "实体A", "target": "实体B", "relation": "关系类型", "confidence": 0.9}]}

关系类型包括：works_at, located_in, contains, uses, produces, supplies, collaborates_with, related_to

文本：
{text}

仅返回 JSON，不要解释。"""

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

        # 内存邻接缓存（优化遍历性能）
        self._adjacency_cache: Optional[Dict[str, List[Tuple[str, str, float]]]] = None
        self._adjacency_dirty: bool = True
    
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
    # 增量更新支持
    # ========================================================================

    def update_incremental(
        self,
        text: str,
        doc_id: str,
        existing_graph: Dict[str, Any],
    ) -> Dict[str, Any]:
        """增量更新知识图谱

        仅处理新增/变更的文档内容，合并到已有图谱中。
        与 build_full_graph 的区别：
          - build_full_graph: 从零构建
          - update_incremental: 合并到已有图谱，去重、保留高置信度边

        Args:
            text:           新文档文本
            doc_id:         文档 ID
            existing_graph: 已有图谱数据
                            {"entities": [...], "edges": [...]}
                            或 {"nodes": {...}, "edges": [...]}

        Returns:
            {
                "doc_id": str,
                "entities": [...],       # 合并后的全部实体
                "edges": [...],          # 合并后的全部边
                "new_entities": int,     # 本次新增实体数
                "new_edges": int,        # 本次新增边数
                "updated_edges": int,    # 本次更新（置信度提升）的边数
                "stats": {...},
            }
        """
        # 提取新文档的实体和边
        new_entities = self.extract_entities(text)
        new_edges = self.build_from_text(text, doc_id)

        # 解析已有图谱
        existing_entities = existing_graph.get("entities", [])
        existing_edges = existing_graph.get("edges", [])
        # 兼容 nodes 格式
        if not existing_entities and "nodes" in existing_graph:
            nodes = existing_graph["nodes"]
            if isinstance(nodes, dict):
                existing_entities = [
                    {"name": name, **(info if isinstance(info, dict) else {})}
                    for name, info in nodes.items()
                ]

        # 合并实体（按 name 去重）
        entity_map: Dict[str, Dict[str, Any]] = {}
        for e in existing_entities:
            name = e.get("name", "")
            if name:
                entity_map[name] = e

        new_entity_count = 0
        for e in new_entities:
            name = e["name"]
            if name not in entity_map:
                entity_map[name] = {
                    "name": name,
                    "type": e["type"],
                    "description": f"从文档 {doc_id} 中提取的 {e['type']}",
                    "count": e["count"],
                }
                new_entity_count += 1
            else:
                # 更新计数
                prev_count = entity_map[name].get("count", 0)
                entity_map[name]["count"] = prev_count + e["count"]

        # 合并边（按 source+target+type 去重，保留高置信度）
        edge_key_map: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
        for edge in existing_edges:
            src = edge.get("source", edge.get("from", ""))
            tgt = edge.get("target", edge.get("to", ""))
            rel = edge.get("relation", edge.get("type", "related_to"))
            key = (src, tgt, rel)
            edge_key_map[key] = {
                "source": src,
                "target": tgt,
                "type": rel,
                "confidence": float(edge.get("confidence", edge.get("weight", 1.0))),
                "doc_id": edge.get("doc_id", ""),
                "evidence": edge.get("description", edge.get("evidence", "")),
            }

        new_edge_count = 0
        updated_edge_count = 0
        for edge in new_edges:
            key = (edge["source"], edge["target"], edge["type"])
            if key not in edge_key_map:
                edge_key_map[key] = {
                    "source": edge["source"],
                    "target": edge["target"],
                    "type": edge["type"],
                    "confidence": edge["confidence"],
                    "doc_id": doc_id,
                    "evidence": edge.get("evidence", ""),
                }
                new_edge_count += 1
            else:
                existing_conf = edge_key_map[key]["confidence"]
                if edge["confidence"] > existing_conf:
                    edge_key_map[key]["confidence"] = edge["confidence"]
                    edge_key_map[key]["evidence"] = edge.get("evidence", "")
                    updated_edge_count += 1

        # 转换为输出格式
        merged_entities = list(entity_map.values())
        merged_edges = list(edge_key_map.values())

        # 标记邻接缓存需要更新
        self._adjacency_dirty = True

        # 更新统计
        self._built_count += 1
        self._total_entities += new_entity_count
        self._total_edges += new_edge_count

        logger.info(
            "AutoGraph: 增量更新 %s — 新增 %d 实体 / %d 边，更新 %d 边",
            doc_id, new_entity_count, new_edge_count, updated_edge_count,
        )

        return {
            "doc_id": doc_id,
            "entities": merged_entities,
            "edges": merged_edges,
            "new_entities": new_entity_count,
            "new_edges": new_edge_count,
            "updated_edges": updated_edge_count,
            "stats": {
                "entity_count": len(merged_entities),
                "edge_count": len(merged_edges),
                "built_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            },
        }

    # ========================================================================
    # 邻接缓存（优化遍历性能）
    # ========================================================================

    def build_adjacency_cache(self, edges: List[Dict[str, Any]]) -> None:
        """构建内存邻接缓存，加速图遍历

        Args:
            edges: 边列表（source/target/type/confidence 格式）
        """
        adj: Dict[str, List[Tuple[str, str, float]]] = {}
        for edge in edges:
            src = edge.get("source", edge.get("from", ""))
            tgt = edge.get("target", edge.get("to", ""))
            rel = edge.get("type", edge.get("relation", "related_to"))
            conf = float(edge.get("confidence", edge.get("weight", 1.0)))
            if src and tgt:
                adj.setdefault(src, []).append((tgt, rel, conf))
                adj.setdefault(tgt, []).append((src, rel, conf))
        self._adjacency_cache = adj
        self._adjacency_dirty = False
        logger.debug("AutoGraph: 邻接缓存已构建，%d 个节点", len(adj))

    def get_neighbors(
        self,
        entity: str,
        relation_filter: Optional[str] = None,
        min_confidence: float = 0.0,
    ) -> List[Tuple[str, str, float]]:
        """获取实体的邻居节点（使用邻接缓存加速）

        Args:
            entity:          实体名称
            relation_filter: 只返回指定关系类型的邻居
            min_confidence:  最低置信度阈值

        Returns:
            [(neighbor, relation, confidence), ...]
        """
        if self._adjacency_cache is None or self._adjacency_dirty:
            # 需要先构建缓存（从外部传入 edges 或返回空）
            return []

        neighbors = self._adjacency_cache.get(entity, [])
        result = []
        for neighbor, rel, conf in neighbors:
            if relation_filter and rel != relation_filter:
                continue
            if conf < min_confidence:
                continue
            result.append((neighbor, rel, conf))

        # 按置信度降序排序
        result.sort(key=lambda x: x[2], reverse=True)
        return result

    def find_paths_cached(
        self,
        start: str,
        end: str,
        max_hops: int = 3,
    ) -> List[List[Tuple[str, str, float]]]:
        """使用邻接缓存查找两实体间路径

        Args:
            start:    起始实体
            end:      目标实体
            max_hops: 最大跳数

        Returns:
            路径列表，每条路径为 [(entity, relation, confidence), ...]
        """
        if self._adjacency_cache is None or self._adjacency_dirty:
            return []

        from collections import deque

        visited = {start}
        queue: deque = deque([(start, [], 0)])
        found_paths = []

        while queue:
            current, path, depth = queue.popleft()
            if depth >= max_hops:
                continue

            for neighbor, rel, conf in self._adjacency_cache.get(current, []):
                if neighbor in visited:
                    continue

                new_path = path + [(neighbor, rel, conf)]
                if neighbor == end:
                    found_paths.append(new_path)
                    if len(found_paths) >= 10:
                        return found_paths
                else:
                    visited.add(neighbor)
                    queue.append((neighbor, new_path, depth + 1))

        return found_paths

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
# EnhancedAutoGraphBuilder — 增强版知识图谱构建器
# ============================================================================

class EnhancedAutoGraphBuilder(AutoGraphBuilder):
    """增强版知识图谱构建器
    
    在 AutoGraphBuilder 基础上增加：
      1. LLM 实体/关系抽取（可选，API 不可用时自动降级到规则引擎）
      2. 共现关系提取（作为关系抽取的降级方案）
      3. 增强中文实体识别（更多模式、后缀过滤）
      4. 边权重综合计算（置信度 × 共现频率 × 关系类型权重）
      5. 实体去重与合并（名称归一化 + 相似实体合并）
    
    使用示例::
    
        from src.bagua.auto_graph import EnhancedAutoGraphBuilder
        
        builder = EnhancedAutoGraphBuilder()
        text = "张三在阿里巴巴工作，负责淘宝项目。他于2020年参加了云栖大会。"
        entities = builder.extract_entities(text)
        edges = builder.build_from_text(text, doc_id="doc-001")
    """
    
    def __init__(self, custom_patterns=None, custom_rules=None):
        """初始化增强版构建器
        
        Args:
            custom_patterns: 自定义实体提取模式
            custom_rules:    自定义边规则
        """
        super().__init__(custom_patterns, custom_rules)
        
        # 加载增强版中文 NER 模式
        for name, pattern in ENHANCED_ENTITY_PATTERNS.items():
            if name not in self._compiled_entities:
                try:
                    self._compiled_entities[name] = re.compile(pattern, re.IGNORECASE)
                    self.entity_patterns[name] = pattern
                except re.error as e:
                    logger.warning("增强模式编译失败 [%s]: %s", name, e)
        
        # LLM 配置（延迟加载）
        self._llm_available = None  # None = 未检测, True/False = 已检测
        
        # 共现窗口大小（句子级）
        self._cooccurrence_window = 200  # 字符
        self._min_cooccurrence = 2  # 最小共现次数
        
        # 关系类型权重映射
        self._relation_weights = {
            "works_at": 0.90,
            "located_in": 0.85,
            "contains": 0.80,
            "uses": 0.85,
            "produces": 0.85,
            "supplies": 0.80,
            "collaborates_with": 0.75,
            "related_to": 0.50,
            "co_occurrence": 0.40,
        }
        
        # 统计
        self._llm_calls = 0
        self._cooccurrence_edges = 0
    
    # ========================================================================
    # LLM 实体抽取
    # ========================================================================
    
    def extract_entities_llm(self, text) -> Any:
        """使用 LLM 抽取实体（可选增强）
        
        调用 MiMo API 进行实体抽取。如果 API 不可用，返回空列表。
        
        Args:
            text: 待抽取的文本
            
        Returns:
            实体列表，格式同 extract_entities
        """
        if not self._ensure_llm_available():
            return []
        
        # 限制文本长度
        truncated = text[:3000]
        
        prompt = _LLM_ENTITY_PROMPT.format(text=truncated)
        response = self._call_llm(prompt)
        
        if not response:
            return []
        
        # 解析 JSON 响应
        try:
            json_str = response
            # 如果响应包含 markdown 代码块，提取其中的 JSON
            if "```" in json_str:
                match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', json_str, re.DOTALL)
                if match:
                    json_str = match.group(1).strip()
            
            data = json.loads(json_str)
            entities = []
            seen = set()
            
            for item in data.get("entities", []):
                name = item.get("name", "").strip()
                etype = item.get("type", "other")
                confidence = float(item.get("confidence", 0.8))
                
                if not name or len(name) < 2:
                    continue
                if name in seen:
                    continue
                seen.add(name)
                
                entities.append({
                    "name": name,
                    "type": etype,
                    "confidence": confidence,
                    "positions": [],
                    "count": 1,
                    "source": "llm",
                })
            
            self._llm_calls += 1
            return entities
            
        except Exception as e:
            logger.warning("LLM 实体抽取结果解析失败: %s", e)
            return []
    
    def extract_entities_fallback(self, text) -> Any:
        """规则抽取降级方案 — 当 LLM 不可用时使用
        
        Args:
            text: 待抽取的文本
            
        Returns:
            实体列表
        """
        # 使用父类的正则抽取
        return super().extract_entities(text)
    
    def extract_entities(self, text) -> Any:
        """增强版实体抽取 — 优先 LLM，降级到规则
        
        Args:
            text: 待抽取的文本
            
        Returns:
            实体列表（合并 LLM 和规则抽取结果，去重）
        """
        if not text:
            return []
        
        # 1. 规则抽取（始终执行，作为基线）
        rule_entities = self.extract_entities_fallback(text)
        
        # 2. LLM 抽取（可选）
        llm_entities = self.extract_entities_llm(text)
        
        if not llm_entities:
            return rule_entities
        
        # 3. 合并去重
        merged = self._merge_entity_lists(llm_entities, rule_entities)
        
        # 4. 按置信度排序
        merged.sort(key=lambda e: e.get("confidence", 0.5), reverse=True)
        
        return merged
    
    # ========================================================================
    # LLM 关系抽取
    # ========================================================================
    
    def extract_relations_llm(self, text) -> Any:
        """使用 LLM 抽取关系
        
        Args:
            text: 待抽取的文本
            
        Returns:
            关系列表，格式同 _extract_edges 输出
        """
        if not self._ensure_llm_available():
            return []
        
        truncated = text[:3000]
        
        prompt = _LLM_RELATION_PROMPT.format(text=truncated)
        response = self._call_llm(prompt)
        
        if not response:
            return []
        
        try:
            json_str = response
            if "```" in json_str:
                match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', json_str, re.DOTALL)
                if match:
                    json_str = match.group(1).strip()
            
            data = json.loads(json_str)
            relations = []
            
            for item in data.get("relations", []):
                source = item.get("source", "").strip()
                target = item.get("target", "").strip()
                relation = item.get("relation", "related_to")
                confidence = float(item.get("confidence", 0.7))
                
                if not source or not target:
                    continue
                if source == target:
                    continue
                
                relations.append({
                    "source": source,
                    "target": target,
                    "type": relation,
                    "confidence": confidence,
                    "doc_id": "",
                    "evidence": "LLM 抽取",
                    "source_method": "llm",
                })
            
            self._llm_calls += 1
            return relations
            
        except Exception as e:
            logger.warning("LLM 关系抽取结果解析失败: %s", e)
            return []
    
    def extract_relations_cooccurrence(self, text, entities, window_size=None) -> Any:
        """共现关系抽取 — 作为关系抽取的降级方案
        
        基于实体在同一句子/窗口中共现的频率来推断关系。
        共现频率越高，关系置信度越高。
        
        Args:
            text:        原文文本
            entities:    已提取的实体列表
            window_size: 共现窗口大小（字符数），默认使用 self._cooccurrence_window
            
        Returns:
            关系列表
        """
        if not entities or not text:
            return []
        
        window = window_size or self._cooccurrence_window
        entity_names = [e["name"] for e in entities if e.get("name")]
        
        if len(entity_names) < 2:
            return []
        
        # 按句子分割
        sentences = re.split(r'[。！？\n;；]', text)
        
        # 统计共现
        cooccurrence_counts = {}
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence or len(sentence) < 4:
                continue
            
            # 找到这个句子中出现的实体
            present = []
            for name in entity_names:
                if name in sentence:
                    present.append(name)
            
            # 如果有多个实体共现，两两建立关系
            if len(present) >= 2:
                for i in range(len(present)):
                    for j in range(i + 1, len(present)):
                        key = tuple(sorted([present[i], present[j]]))
                        cooccurrence_counts[key] = cooccurrence_counts.get(key, 0) + 1
        
        # 转换为关系列表
        relations = []
        max_count = max(cooccurrence_counts.values()) if cooccurrence_counts else 1
        
        for (e1, e2), count in cooccurrence_counts.items():
            if count < self._min_cooccurrence:
                continue
            
            # 置信度 = 基础值 + 频率贡献
            confidence = 0.4 + 0.4 * (count / max_count)
            confidence = min(confidence, 0.85)
            
            relations.append({
                "source": e1,
                "target": e2,
                "type": "co_occurrence",
                "confidence": round(confidence, 2),
                "doc_id": "",
                "evidence": f"共现 {count} 次",
                "source_method": "cooccurrence",
            })
        
        self._cooccurrence_edges += len(relations)
        return relations
    
    # ========================================================================
    # 重写核心方法
    # ========================================================================
    
    def build_from_text(self, text, doc_id="") -> Any:
        """增强版图谱构建 — LLM + 规则 + 共现三层策略
        
        Args:
            text:   文档文本
            doc_id: 文档 ID
            
        Returns:
            边列表
        """
        if not text or not text.strip():
            return []
        
        # 1. 提取实体
        entities = self.extract_entities(text)
        
        # 2. LLM 关系抽取（可选）
        llm_relations = self.extract_relations_llm(text)
        
        # 3. 规则关系抽取（降级方案）
        rule_relations = self._extract_edges(text, entities, doc_id)
        
        # 4. 共现关系抽取（降级方案）
        cooccurrence_relations = self.extract_relations_cooccurrence(text, entities)
        
        # 5. 合并所有关系
        all_relations = llm_relations + rule_relations + cooccurrence_relations
        
        # 6. 边权重计算
        weighted = self._calculate_edge_weights(all_relations, entities)
        
        # 7. 去重
        deduped = self._deduplicate_edges(weighted)
        
        # 8. 排序
        deduped.sort(key=lambda e: e["confidence"], reverse=True)
        
        # 更新统计
        self._built_count += 1
        self._total_entities += len(entities)
        self._total_edges += len(deduped)
        
        return deduped
    
    def build_full_graph(self, text, doc_id="") -> Any:
        """增强版完整图构建
        
        Args:
            text:   文档文本
            doc_id: 文档 ID
            
        Returns:
            {"doc_id", "entities", "edges", "stats"}
        """
        entities = self.extract_entities(text)
        edges = self.build_from_text(text, doc_id)
        
        graph_entities = [
            {
                "name": e["name"],
                "type": e["type"],
                "description": f"从文档 {doc_id} 中提取的 {e['type']}",
                "count": e.get("count", 1),
                "confidence": e.get("confidence", 0.5),
                "source": e.get("source", "rule"),
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
                "weight": edge.get("weight", edge["confidence"]),
                "source_method": edge.get("source_method", "rule"),
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
                "llm_calls": self._llm_calls,
                "cooccurrence_edges": self._cooccurrence_edges,
                "built_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            },
        }
    
    def get_stats(self) -> Any:
        """获取增强版构建器统计信息"""
        base = super().get_stats()
        base["llm_calls"] = self._llm_calls
        base["cooccurrence_edges"] = self._cooccurrence_edges
        base["builder_type"] = "enhanced"
        return base
    
    # ========================================================================
    # 内部辅助方法
    # ========================================================================
    
    def _ensure_llm_available(self) -> Any:
        """检测 LLM API 是否可用（缓存结果）"""
        if self._llm_available is not None:
            return self._llm_available
        
        try:
            from src.config import MIMO_API_KEY
            if not MIMO_API_KEY:
                self._llm_available = False
                return False
            self._llm_available = True
            return True
        except ImportError:
            self._llm_available = False
            return False
    
    def _call_llm(self, prompt) -> Any:
        """调用 LLM API"""
        try:
            from src.config import MIMO_API_KEY, MIMO_BASE_URL, MIMO_MODEL, AI_TIMEOUT_SECONDS
            import httpx
            
            url = f"{MIMO_BASE_URL.rstrip('/')}/chat/completions"
            headers = {
                "Authorization": f"Bearer {MIMO_API_KEY}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": MIMO_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 2000,
            }
            
            with httpx.Client(timeout=AI_TIMEOUT_SECONDS) as client:
                resp = client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.debug("LLM 调用失败（将降级到规则引擎）: %s", e)
            self._llm_available = False
            return None
    
    def _merge_entity_lists(self, primary, secondary) -> Any:
        """合并两个实体列表，primary 优先
        
        Args:
            primary:   主要实体列表（如 LLM 结果）
            secondary: 次要实体列表（如规则结果）
            
        Returns:
            合并后的去重实体列表
        """
        merged = {}
        
        # 先加入主要列表
        for e in primary:
            name = self._normalize_entity_name(e["name"])
            if name not in merged:
                merged[name] = e.copy()
                merged[name]["name"] = name
        
        # 再加入次要列表（不覆盖已有）
        for e in secondary:
            name = self._normalize_entity_name(e["name"])
            if name not in merged:
                merged[name] = e.copy()
                merged[name]["name"] = name
            else:
                # 如果已存在，增加 count
                merged[name]["count"] = merged[name].get("count", 1) + e.get("count", 1)
        
        return list(merged.values())
    
    def _normalize_entity_name(self, name) -> Any:
        """实体名称归一化
        
        处理：去前后缀、去多余空格、统一标点
        """
        if not name:
            return name
        # 去除职务后缀
        suffixes = ["先生", "女士", "经理", "总监", "主任", "工程师", 
                    "设计师", "老师", "博士", "硕士", "总裁", "CEO", 
                    "CTO", "CFO", "副总", "部长", "科长", "处长", 
                    "主管", "书记", "主席", "院长", "校长", "所长"]
        result = name.strip()
        for suffix in suffixes:
            if result.endswith(suffix) and len(result) > len(suffix):
                result = result[:-len(suffix)]
                break
        # 去多余空格
        result = re.sub(r'\s+', '', result)
        return result if result else name.strip()
    
    def _calculate_edge_weights(self, edges, entities) -> Any:
        """计算边权重
        
        权重 = 置信度 × 关系类型权重 × 实体共现频率贡献
        
        Args:
            edges:    原始边列表
            entities: 已提取的实体列表
            
        Returns:
            带权重的边列表
        """
        entity_names = {e["name"] for e in entities}
        
        weighted = []
        for edge in edges:
            conf = edge.get("confidence", 0.5)
            rel_type = edge.get("type", "related_to")
            rel_weight = self._relation_weights.get(rel_type, 0.5)
            
            # 源实体是否在已提取实体中（提升可信度）
            src_in = 1.0 if edge.get("source") in entity_names else 0.7
            tgt_in = 1.0 if edge.get("target") in entity_names else 0.7
            
            # 综合权重
            weight = conf * rel_weight * ((src_in + tgt_in) / 2)
            
            edge_copy = edge.copy()
            edge_copy["weight"] = round(min(weight, 1.0), 3)
            weighted.append(edge_copy)
        
        return weighted
    
    def _deduplicate_edges(self, edges) -> Any:
        """增强版边去重 — 相同 (source, target, type) 保留置信度最高的"""
        best = {}
        
        for edge in edges:
            src = self._normalize_entity_name(edge.get("source", ""))
            tgt = self._normalize_entity_name(edge.get("target", ""))
            rel = edge.get("type", "related_to")
            key = (src, tgt, rel)
            
            if key not in best or edge.get("confidence", 0) > best[key].get("confidence", 0):
                edge_copy = edge.copy()
                edge_copy["source"] = src
                edge_copy["target"] = tgt
                best[key] = edge_copy
        
        return list(best.values())


# ============================================================================
# 全局单例
# ============================================================================

_global_builder: Optional[AutoGraphBuilder] = None


def get_auto_graph_builder(use_enhanced: bool = True) -> AutoGraphBuilder:
    """获取全局 AutoGraphBuilder 单例
    
    Args:
        use_enhanced: 是否使用增强版（默认 True，自动检测 LLM 可用性）
    
    Returns:
        AutoGraphBuilder 或 EnhancedAutoGraphBuilder 实例
    """
    global _global_builder
    if _global_builder is None:
        if use_enhanced:
            _global_builder = EnhancedAutoGraphBuilder()
        else:
            _global_builder = AutoGraphBuilder()
    return _global_builder


# ============================================================================
# 模块导出
# ============================================================================

__all__ = [
    "AutoGraphBuilder",
    "EnhancedAutoGraphBuilder",
    "ENTITY_PATTERNS",
    "ENHANCED_ENTITY_PATTERNS",
    "EDGE_RULES",
    "get_auto_graph_builder",
]