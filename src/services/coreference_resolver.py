"""
coreference_resolver.py — 指代消解服务
========================================
伏羲平台 P2 增强：多轮对话中的指代消解

功能：
  1. 代词替换：识别 它、他、她、这个、那个、其、此 等指代词
  2. 省略补全：补全上下文省略的主语/宾语
  3. 上下文感知：基于对话历史推断指代对象

架构：
  - 规则层：基于模式匹配的快速消解（< 1ms）
  - 上下文层：从历史中提取最近提及的实体
  - LLM层（可选）：当规则无法消解时，回退到 LLM

使用方式：
  from src.services.coreference_resolver import CoreferenceResolver
  resolver = CoreferenceResolver()
  resolved = await resolver.resolve("它多少钱？", history)

集成点：
  - src/shaoyin/brain.py: ShaoyinBrain.think() 第一步调用
  - src/api/chat.py: _chat_v1 / _chat_v2 预处理

设计约束：
  - 不修改现有框架代码
  - 异步编程模式
  - 与现有架构一致
"""

import re
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ============================================================================
# 规则配置
# ============================================================================

# 中文代词 → 候选指代类型
PRONOUN_PATTERNS = {
    # 第三人称代词
    "它": {"priority": 1, "entity_type": "thing", "description": "指物/概念"},
    "他": {"priority": 1, "entity_type": "person", "description": "指男性"},
    "她": {"priority": 1, "entity_type": "person", "description": "指女性"},
    "其": {"priority": 2, "entity_type": "any", "description": "指上文提到的对象（文言）"},
    # 指示代词
    "这个": {"priority": 1, "entity_type": "thing", "description": "近指"},
    "那个": {"priority": 1, "entity_type": "thing", "description": "远指"},
    "此": {"priority": 2, "entity_type": "any", "description": "指上文提到的对象"},
    "该": {"priority": 2, "entity_type": "any", "description": "指上文提到的对象"},
    "这些": {"priority": 1, "entity_type": "thing", "description": "复数近指"},
    "那些": {"priority": 1, "entity_type": "thing", "description": "复数远指"},
    # 地点/抽象代词
    "这里": {"priority": 2, "entity_type": "place", "description": "地点"},
    "那里": {"priority": 2, "entity_type": "place", "description": "地点"},
    # 时间代词
    "当时": {"priority": 2, "entity_type": "time", "description": "时间指代"},
    # 省略主语特征词
    "呢": {"priority": 3, "entity_type": "ellipsis", "description": "省略标记"},
    "怎么": {"priority": 3, "entity_type": "ellipsis", "description": "省略主语高频词"},
    "多少": {"priority": 3, "entity_type": "ellipsis", "description": "省略主语高频词"},
    "为什么": {"priority": 3, "entity_type": "ellipsis", "description": "省略主语高频词"},
}

# 需要消解的追问模式（短句 + 无明确主语）
FOLLOWUP_PATTERNS = [
    r"^(多少钱|多贵|价格多少|价格如何|收费)?[？?]?$",
    r"^(怎么|如何|怎样)(做|用|处理|解决|办|操作|实现|配置|安装)?[？?]?$",
    r"^(为什么|为啥|为何)[？?]?$",
    r"^(还有|另外|其他)(的|方面|呢|吗)?[？?]?$",
    r"^(能|可以)(再)?(详细|具体|深入)?(说明|解释|讲|介绍|说)?(一下|一点|一些|下)?[？?]?$",
    r"^(举个例子|举例|比如)[？?]?$",
    r"^(然后|之后|接下来|接着)[？?]?$",
    r"^(是什么|什么是)[？?]?$",
    r"^(特点|优缺点|优势|劣势|好处|坏处|区别)(是|有)?(什么|哪些)?[？?]?$",
    r"^(具体|详细)[说说明]?(一下|下)?[？?]?$",
    r"^(上述|前面|上面|之前|刚才)(提到的|说的)?[，。]?.*$",
    # 短追问格式（只含名词/参数 + 疑问）
    r"^[\u4e00-\u9fffA-Za-z0-9\s]{1,10}(多少|怎样|如何|怎么|吗|呢)[？?]?$",
]


class CoreferenceResolver:
    """指代消解器

    核心方法：
      - resolve(query, history) → str: 消解指代，返回独立查询
      - resolve_async(query, history, llm_fn=None) → str: 异步版本（支持 LLM 回退）

    消解策略（三级级联）：
      1. 快速路径：无指代词时直接返回
      2. 规则消解：基于模式匹配和上下文实体提取
      3. LLM 消解（可选）：规则无法处理时回退到 LLM
    """

    # 控制开关
    ENABLE_LLM_FALLBACK = False  # 默认关闭 LLM 回退，降低延迟
    MAX_HISTORY_TURNS = 5        # 最多回溯的对话轮数
    MAX_CONTEXT_LENGTH = 80      # 提取的上下文最大长度

    def __init__(self, enable_llm: bool = False):
        """初始化指代消解器

        Args:
            enable_llm: 是否启用 LLM 回退（会增加延迟，但处理更复杂场景）
        """
        self.ENABLE_LLM_FALLBACK = enable_llm
        self._stats = {"rule_hits": 0, "llm_hits": 0, "no_op": 0, "cache_hits": 0}
        self._context_cache: Dict[str, str] = {}  # session_id → last entity

    # ========================================================================
    # 公共 API
    # ========================================================================

    async def resolve(self, query: str, history: Optional[List[Dict]] = None,
                      session_id: Optional[str] = None,
                      llm_fn=None) -> str:
        """消解指代：将多轮对话中的指代性查询改写为独立查询

        Args:
            query: 用户当前查询
            history: 对话历史 [{"role": "user/assistant", "content": "..."}]
            session_id: 可选的会话ID，用于缓存
            llm_fn: 可选的 LLM 调用函数 async fn(messages, **kwargs) → str

        Returns:
            消解后的独立查询字符串

        Examples:
            >>> h = [{"role": "user", "content": "PLC-200 是什么？"},
            ...      {"role": "assistant", "content": "PLC-200 是一款控制器。"}]
            >>> await resolver.resolve("它多少钱？", h)
            "PLC-200 多少钱？"
        """
        # 1. 快速路径：无历史或查询无需消解
        if not history or len(history) == 0:
            self._stats["no_op"] += 1
            return query

        if not self._needs_resolution(query):
            self._stats["no_op"] += 1
            return query

        # 2. 缓存命中检查
        if session_id and self._context_cache.get(session_id):
            logger.debug(f"[CoreferenceResolver] cache hit for {session_id}")

        # 3. 规则消解
        resolved = self._rule_resolve(query, history)
        if resolved and resolved != query:
            self._stats["rule_hits"] += 1
            logger.info(f"[CoreferenceResolver] rule resolved: "
                        f"'{query[:30]}...' → '{resolved[:50]}...'")
            return resolved

        # 4. LLM 回退（如果启用）
        if self.ENABLE_LLM_FALLBACK:
            llm_resolved = await self._llm_resolve(query, history, llm_fn)
            if llm_resolved and llm_resolved != query:
                self._stats["llm_hits"] += 1
                logger.info(f"[CoreferenceResolver] llm resolved: "
                            f"'{query[:30]}...' → '{llm_resolved[:50]}...'")
                return llm_resolved

        self._stats["no_op"] += 1
        return query

    # ========================================================================
    # 判断是否需要消解
    # ========================================================================

    def _needs_resolution(self, query: str) -> bool:
        """快速判断查询是否包含需要消解的指代"""
        # 检查显式代词
        for pronoun in ["它", "他", "她", "这个", "那个", "其", "此", "该",
                         "这些", "那些", "这里", "那里", "当时", "上述"]:
            if pronoun in query:
                return True

        # 检查省略模式：短句 + 疑问词
        q = query.strip()

        # 短追问（< 15 字）
        if len(q) <= 15:
            for pattern in FOLLOWUP_PATTERNS:
                if re.match(pattern, q):
                    return True

        # 特殊模式："那 X 呢/吗？"（X 可以是任意字符）
        if re.match(r'^那.{1,20}[呢吗][？?]?$', q):
            return True

        # 特殊模式："能(再)?...一下/一点"
        if re.match(r'^(能|可以)(再)?.{1,20}(一下|一点|下|些|吗)[？?]?$', q):
            return True

        # 短追问（≤ 20 字且包含 "呢" 或 "吗"）
        if len(q) <= 20 and ('呢' in q or '吗' in q):
            return True

        # 极短追问（≤ 6 字，仅含中文字符 + 标点）→ 可能是省略主语的追问
        clean = re.sub(r'[？?。，！\s]', '', q)
        if len(clean) <= 6 and re.match(r'^[\u4e00-\u9fffA-Za-z0-9]+$', clean):
            return True

        return False

    # ========================================================================
    # 规则消解引擎
    # ========================================================================

    def _rule_resolve(self, query: str, history: List[Dict]) -> str:
        """基于规则的指代消解

        策略：
          1. 从历史中提取最近被提及的实体
          2. 将代词替换为具体实体
          3. 对于省略句，补全主语
        """
        # 提取上下文实体
        entities = self._extract_entities_from_history(history)

        resolved = query

        # 第一步：替换显式代词
        resolved = self._replace_pronouns(resolved, entities)

        # 第二步：处理省略（追问短句）→ 补全主语
        resolved = self._fill_ellipsis(resolved, entities, history)

        return resolved

    def _replace_pronouns(self, query: str, entities: Dict[str, str]) -> str:
        """用上下文实体替换代词"""
        result = query

        # 只处理真正的指代词（entity_type 不是 ellipsis 的）
        for pronoun, info in PRONOUN_PATTERNS.items():
            if info.get("entity_type") == "ellipsis":
                continue  # 跳过省略标记词，它们不是真正的代词
            if pronoun in result:
                # 查找对应的候选实体
                candidate = self._find_candidate(pronoun, entities)
                if candidate:
                    # 处理代词在句首的情况
                    if result.startswith(pronoun):
                        result = candidate + result[len(pronoun):]
                    else:
                        result = result.replace(pronoun, candidate)

        return result

    def _fill_ellipsis(self, query: str, entities: Dict[str, str],
                       history: List[Dict]) -> str:
        """补全省略的主语/宾语

        识别追问模式并补全上下文：
          - "多少钱？" → "PLC-200 多少钱？"
          - "为什么？" → "PLC-200 为什么..."
          - "举个例子" → "关于 PLC-200 举个例子"
        """
        query_stripped = query.strip().rstrip("？?。.")

        # 图案1：纯数字/价格追问
        if re.match(r'^(多少|几|怎么)(钱|价格|收费)[？?]?$', query_stripped):
            entity = entities.get("thing") or entities.get("any")
            if entity:
                return f"{entity} 多少钱？"

        # 图案2：纯方式追问
        if re.match(r'^(怎么|如何|怎样)(做|用|办|处理|操作|搞|实现)[？?]?$', query_stripped):
            entity = entities.get("thing") or entities.get("any")
            if entity:
                return f"如何 {entity}？"

        # 图案3：纯原因追问
        if re.match(r'^(为什么|为啥|为何|什么原因)[？?]?$', query_stripped):
            entity = entities.get("thing") or entities.get("any")
            if entity:
                return f"{entity} 为什么？"

        # 图案4：请求详细说明
        if re.match(r'^(能|可以)(再)?(详细|具体|深入)?(说|讲|解释|介绍|说明)?(一下|一点|下|些)?[？?]?$', query_stripped):
            entity = entities.get("thing") or entities.get("any")
            if entity:
                return f"请详细说明 {entity}"

        # 图案5：请求举例
        if re.match(r'^(举个|给个|来个)(例子|示例|栗子)[？?]?$', query_stripped) or \
           re.match(r'^(举例|比如)(说明)?[？?]?$', query_stripped):
            entity = entities.get("thing") or entities.get("any")
            if entity:
                return f"请举例说明 {entity}"

        # 图案6：追问后续
        if re.match(r'^(然后|之后|接下来|接着|继续)[？?]?$', query_stripped):
            entity = entities.get("thing") or entities.get("any")
            if entity:
                return f"{entity} 然后呢？"

        # 图案7：追问特点/优缺点
        if re.match(r'^(特点|优缺点|优势|劣势|好处|坏处|区别)(是什么|有哪些|是什么)?[？?]?$', query_stripped):
            entity = entities.get("thing") or entities.get("any")
            if entity:
                return f"{entity} 的特点是什么？"

        # 图案8："那 X 呢/吗？" 模式
        match_na = re.match(r'^那([\u4e00-\u9fffA-Za-z0-9\s]{1,20})[呢吗][？?]?$', query_stripped)
        if match_na:
            tail = match_na.group(1).strip()
            entity = entities.get("thing") or entities.get("any")
            if entity and tail:
                return f"{entity} {tail}呢？"
            elif entity:
                return f"{entity}呢？"

        # 图案9：句首已有代词但未完全替换，且整句较短 → 补全
        if len(query) <= 15 and not any(kw in query for kw in
                                         ['什么是', '如何', '请问', '为什么',
                                          '怎么', '哪些', '介绍', '解释',
                                          '说明', '定义']):
            entity = entities.get("thing") or entities.get("any")
            if entity and entity not in query:
                return f"{entity} {query}"

        return query

    def _find_candidate(self, pronoun: str,
                        entities: Dict[str, str]) -> Optional[str]:
        """为代词找到最合适的候选实体"""
        pronoun_info = PRONOUN_PATTERNS.get(pronoun, {})
        entity_type = pronoun_info.get("entity_type", "any")

        # 精确类型匹配
        if entity_type in entities:
            return entities[entity_type]

        # 通用回退
        return entities.get("any") or entities.get("thing")

    # ========================================================================
    # 上下文实体提取
    # ========================================================================

    def _extract_entities_from_history(self, history: List[Dict]) -> Dict[str, str]:
        """从对话历史中提取最近的实体引用

        返回实体类型 → 实体名称的映射：
          {"thing": "PLC-200", "person": "张三", "any": "PLC-200"}
        """
        entities = {}
        asst_entities = {}  # 助手消息中的实体（次优先级）

        # 从最近的到最早的分析（优先最近提及的）
        recent_history = history[-(self.MAX_HISTORY_TURNS * 2):]

        for msg in reversed(recent_history):
            content = msg.get("content", "")
            if not content:
                continue

            if msg.get("role") == "user":
                extracted = self._extract_key_entities(content)
                for etype, evalue in extracted.items():
                    if etype not in entities:
                        entities[etype] = evalue
            elif msg.get("role") == "assistant":
                extracted = self._extract_key_entities(content)
                for etype, evalue in extracted.items():
                    if etype not in asst_entities:
                        asst_entities[etype] = evalue

        # 如果用户实体质量不佳（模糊短语），使用助手实体覆盖
        if entities.get("thing"):
            user_entity = entities["thing"]
            asst_entity = asst_entities.get("thing", "")

            # 检查用户实体是否太模糊
            is_vague = (
                not re.search(r'[A-Za-z0-9]', user_entity) and
                not any(suffix in user_entity
                       for suffix in ['公司', '平台', '系统', '软件', '型号', '品牌', '产品'])
            )

            # 检查助手实体是否更具体（包含产品型号特征）
            asst_is_better = (
                asst_entity and
                re.search(r'[A-Za-z0-9]', asst_entity) and
                not any(suffix in user_entity
                       for suffix in ['公司', '平台', '系统', '软件', '型号', '品牌', '产品'])
            )

            if is_vague and asst_is_better:
                entities["thing"] = asst_entity
            elif is_vague and asst_entity and len(user_entity) <= 6:
                entities["thing"] = asst_entity

        # 如果没有从用户消息中找到，再从助手消息中找
        if not entities.get("thing") and not entities.get("any"):
            entities.update(asst_entities)

        # 确保有 any 作为通用回退
        if entities and "any" not in entities:
            entities["any"] = entities.get("thing") or entities.get("person") or \
                next(iter(entities.values()), None)

        return entities

    # 不应被当作实体的常见追问词/代词语块
    _ENTITY_BLACKLIST = {
        '它的', '他的', '她的', '它的主要参数', '它的性能', '它的价格',
        '它的', '这个', '那个', '这些', '那些', '上述', '前面',
        '什么是', '怎么', '如何', '为什么', '哪些', '多少钱',
        '有什么', '是什么', '什么样',
        '请问', '你好', '谢谢', '不客气',
    }

    def _extract_key_entities(self, text: str) -> Dict[str, str]:
        """从文本中提取关键实体

        策略（不需要 NLP 模型，纯规则）：
          - 专有名词：大写字母+数字组合（如 PLC-200、ABS-V0）
          - 中文专有名词：被引号包裹的文本
          - 产品型号：字母+数字组合
          - 首句主语：第一句话的主语通常是最重要的实体

        Returns:
            {"thing": "PLC-200"} 或 {"person": "张三"}
        """
        entities = {}

        def _is_valid_entity(candidate: str) -> bool:
            """过滤掉已知的追问词和代词语块"""
            c = candidate.strip()
            if len(c) < 2:
                return False
            if c in self._ENTITY_BLACKLIST:
                return False
            if any(c.startswith(b) for b in self._ENTITY_BLACKLIST if len(b) >= 3):
                return False
            # 排除纯疑问结构
            if re.match(r'^[它的这那什么怎么多少哪些]+', c):
                return False
            return True

        # 规则1：引号中的内容 → 高置信度实体
        quoted = re.findall(r'[「「『""]([^」」』""]{1,30})[」」』""]', text)
        if quoted and _is_valid_entity(quoted[0]):
            entities["thing"] = quoted[0]

        # 规则2：产品型号模式（大写字母+连字符+数字）
        # 优先匹配明确的型号格式：PLC-200, ABS-V0, ACD-2000, UL94 V-0
        # 排除纯数值（如 800MPa）——但保留带字母前缀的型号（如 M3, R100）
        # 匹配至少1个大写字母 + 可选连字符 + 数字的模式
        model_pattern = re.findall(
            r'\b([A-Z]{1,10}[-—–]?[A-Z]?\d{1,6}(?:[-—–\s]?[A-Z0-9]{1,6})*)\b',
            text
        )
        if model_pattern and "thing" not in entities:
            entities["thing"] = model_pattern[0]

        # 规则3：中文专有名词模式（XX公司、XX平台、XX系统）
        cn_patterns = re.findall(
            r'([\u4e00-\u9fff]{2,8}(?:公司|平台|系统|软件|产品|技术|型号|品牌))',
            text
        )
        if cn_patterns and "thing" not in entities and _is_valid_entity(cn_patterns[0]):
            entities["thing"] = cn_patterns[0]

        # 规则4：人名模式（如果包含他/她）
        person_pattern = re.findall(
            r'([\u4e00-\u9fff]{2,4}(?:先生|女士|老师|经理|工程师|博士|教授))',
            text
        )
        if person_pattern and "person" not in entities:
            entities["person"] = person_pattern[0]

        # 规则5：首句主语（简单启发式）— 仅在前面规则都没匹配时使用
        if "thing" not in entities:
            # 提取 "X是什么"、"X是一种"、"X的" 中的 X
            # 先去掉开头的代词
            cleaned = re.sub(r'^[这那它他她其此该上述前面刚才]+', '', text)
            subject_match = re.match(
                r'^[，。；、！？\s]*([\u4e00-\u9fffA-Za-z0-9\s\-—–]{2,20})'
                r'(?:是|的|有|可以|需要|怎么|什么|哪|为)',
                cleaned
            )
            if subject_match:
                subject = subject_match.group(1).strip()
                if _is_valid_entity(subject):
                    entities["thing"] = subject

        # 规则6：从助手回复中提取主题实体（如 "X 是一款..."、"X 达到..."）
        # 匹配 "X 是..."、"X 达到..."、"X 支持..." 等模式
        # 仅在前面规则都没匹配到时启用
        if "thing" not in entities:
            # 匹配模式：{产品型号/中文名词} 是/达到/支持/采用/具有...
            # 使用 findall + 第一个非代词匹配，确保优先提取主题而非宾语中的型号
            topic_matches = re.findall(
                r'(?:^|[，。；、！？\s])'
                r'([\u4e00-\u9fffA-Za-z0-9\-—–]{2,20})'
                r'(?:是|达到|支持|采用|具有|拥有|提供|推荐|作为|内置|使用|是一款|是一种)',
                text
            )
            for topic in topic_matches:
                topic = topic.strip()
                if _is_valid_entity(topic) and not re.match(r'^[它他她这那什么怎么多少]+', topic):
                    entities["thing"] = topic
                    break

        return entities

    # ========================================================================
    # LLM 回退消解（可选）
    # ========================================================================

    async def _llm_resolve(self, query: str, history: List[Dict],
                           llm_fn=None) -> Optional[str]:
        """使用 LLM 进行指代消解（延迟较高，但准确）"""
        if llm_fn is None:
            try:
                from src.services.llm import call_llm
                llm_fn = call_llm
            except ImportError:
                logger.debug("[CoreferenceResolver] LLM not available, skip")
                return None

        recent = history[-(self.MAX_HISTORY_TURNS * 2):]
        history_text = ""
        for msg in recent:
            role = "用户" if msg.get("role") == "user" else "AI"
            content = msg.get("content", "")[:200]
            history_text += f"{role}: {content}\n"

        prompt = (
            "你是一个查询改写助手。根据对话历史，将用户的最新问题改写成一个独立、完整的查询。\n\n"
            "规则：\n"
            "1. 替换所有代词（\"它\"、\"这个\"、\"那个\"、\"他们\"）为具体指代对象\n"
            "2. 补充缺失的上下文（如\"多少钱\"→\"PLC型号X的价格是多少\"）\n"
            "3. 保持原意不变，不要添加额外信息\n"
            "4. 如果查询已经是独立的（无需改写），直接返回原查询\n"
            "5. ONLY output the rewritten query, no explanation\n\n"
            f"对话历史：\n{history_text}\n"
            f"用户最新问题：{query}\n\n"
            f"改写后的独立查询："
        )

        try:
            resolved = await llm_fn(
                [{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0.1,
            )
            resolved = resolved.strip().strip('"').strip("'")
            if resolved and resolved != query:
                return resolved
        except Exception as e:
            logger.warning(f"[CoreferenceResolver] LLM resolve failed: {e}")

        return None

    # ========================================================================
    # 统计与诊断
    # ========================================================================

    def get_stats(self) -> Dict:
        """获取消解统计"""
        total = sum(self._stats.values())
        return {
            **self._stats,
            "total_queries": total,
            "rule_rate": self._stats["rule_hits"] / max(total, 1),
            "llm_rate": self._stats["llm_hits"] / max(total, 1),
        }

    def reset_stats(self):
        """重置统计"""
        self._stats = {"rule_hits": 0, "llm_hits": 0, "no_op": 0, "cache_hits": 0}
        self._context_cache.clear()


# ============================================================================
# 工厂函数（与现有架构的 resolve_query 兼容）
# ============================================================================

# 全局默认实例
_default_resolver: Optional[CoreferenceResolver] = None


def get_resolver(enable_llm: bool = False) -> CoreferenceResolver:
    """获取默认的指代消解器实例

    注意：每次调用都可能创建新实例（如果 enable_llm 参数变化）。
    仅当参数一致时返回缓存实例。
    """
    global _default_resolver
    if _default_resolver is None or _default_resolver.ENABLE_LLM_FALLBACK != enable_llm:
        _default_resolver = CoreferenceResolver(enable_llm=enable_llm)
    return _default_resolver


async def resolve_coreference(query: str, history: List[Dict],
                              llm_fn=None) -> str:
    """便捷函数：消解指代

    用法：
      from src.services.coreference_resolver import resolve_coreference
      resolved = await resolve_coreference(query, history)
    """
    resolver = get_resolver()
    return await resolver.resolve(query, history, llm_fn=llm_fn)
