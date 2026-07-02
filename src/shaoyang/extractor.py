"""
extractor.py — 少阳·SAG式事件/实体提取器
六段式Prompt + Pydantic约束 + 代词消歧 + 层级事件
"""
import json
import logging
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger("shaoyang.extractor")


@dataclass
class ExtractionResult:
    """提取结果"""
    events: List[Dict] = field(default_factory=list)
    entities: List[Dict] = field(default_factory=list)


class SAGExtractor:
    """SAG式事件/实体提取器 — 六段式Prompt + Pydantic约束"""

    # 六段式 Prompt 模板
    PROMPT_TEMPLATE = """
    ## 第一段：角色定义
    你是一个专业的知识抽取助手，擅长从文本中提取事件和实体。

    ## 第二段：任务说明
    请从以下文本中提取：
    1. 事件（Event）：一个完整的语义单元，包含时间、地点、人物、动作
    2. 实体（Entity）：人名、地名、组织、概念、产品、技术

    ## 第三段：输出格式
    请严格按照以下 JSON 格式输出：
    {
      "events": [{
        "title": "事件标题",
        "summary": "事件摘要",
        "time": "时间（如有）",
        "location": "地点（如有）",
        "participants": ["参与者"],
        "action": "核心动作",
        "result": "结果（如有）",
        "children": []
      }],
      "entities": [{
        "name": "实体名称",
        "type": "类型",
        "description": "描述",
        "attributes": {}
      }]
    }

    ## 第四段：约束条件
    - 事件必须是一个完整的语义单元
    - 实体必须是具体、可识别的
    - 代词必须消歧为具体实体
    - 层级事件需要标注父子关系
    - 每个片段至少提取1个事项，禁止空结果
    - 子事项必须从父事项继承具体名称（禁止代词）
    - 每个最细事项至少提取3个实体
    - 实体类型必须从预定义列表选择
    - 相同实体的不同表达都要提取（全称+缩写+别称）

    ## 第五段：示例
    输入：张三在2024年1月1日在北京参加了AI大会。
    输出：{
      "events": [{"title": "张三参加AI大会", "summary": "张三于2024年1月1日在北京参加了AI大会", "time": "2024-01-01", "location": "北京", "participants": ["张三"], "action": "参加", "result": null, "children": []}],
      "entities": [{"name": "张三", "type": "人名", "description": "参加AI大会的人", "attributes": {}}, {"name": "北京", "type": "地名", "description": "AI大会举办地", "attributes": {}}, {"name": "AI大会", "type": "概念", "description": "人工智能会议", "attributes": {}}]
    }

    ## 第六段：待处理文本
    {text}
    """

    def __init__(self):
        self._extract_count = 0
        self._success_count = 0

    async def extract(self, chunk_text: str, chunk_meta: Dict = None) -> ExtractionResult:
        """从文本中提取事件和实体"""
        if not chunk_text or len(chunk_text) < 50:
            return ExtractionResult()

        try:
            # 1. 构建 Prompt（注入实体类型）
            entity_types = self._build_entity_types_text()
            prompt = self.PROMPT_TEMPLATE.format(text=chunk_text[:3000])

            # 2. 调用 LLM
            response = await self._call_llm(prompt)

            # 3. 解析结果
            result = self._parse_response(response)

            # 4. 代词消歧
            result = self._resolve_pronouns(result)

            # 5. 层级事件标注
            result = self._annotate_hierarchy(result)

            # 6. 实体去重归一化
            result = self._deduplicate_entities(result)

            self._extract_count += 1
            if result.events or result.entities:
                self._success_count += 1

            return result

        except Exception as e:
            logger.warning(f"[SAG] 提取失败: {e}")
            return ExtractionResult()

    def _build_entity_types_text(self) -> str:
        """从 ontology.py 动态读取实体类型"""
        try:
            from src.db.ontology import ENTITY_TYPES
            types = []
            for t, info in ENTITY_TYPES.items():
                label = info.get("label", t)
                desc = info.get("description", "")
                types.append(f"- {t}: {label}（{desc}）" if desc else f"- {t}: {label}")
            return "\n".join(types)
        except Exception:
            return "- person: 人名\n- organization: 组织\n- product: 产品\n- location: 地点\n- time: 时间\n- subject: 主题\n- metric: 指标\n- material: 材料\n- device: 设备"

    def _resolve_pronouns(self, result: ExtractionResult) -> ExtractionResult:
        """代词消歧：子事件继承父事件实体名"""
        for event in result.events:
            children = event.get("children", [])
            if children:
                parent_entities = set(event.get("participants", []) + event.get("entities", []))
                for child in children:
                    # 替换代词
                    for pronoun in ["他", "她", "它", "该公司", "该组织"]:
                        content = child.get("content", "") or child.get("summary", "")
                        if pronoun in content:
                            if parent_entities:
                                new_content = content.replace(pronoun, list(parent_entities)[0])
                                if "content" in child:
                                    child["content"] = new_content
                                if "summary" in child:
                                    child["summary"] = new_content
        return result

    def _annotate_hierarchy(self, result: ExtractionResult) -> ExtractionResult:
        """层级事件标注：大事件→子事件→细节"""
        for event in result.events:
            # 标记层级
            if "children" in event and event["children"]:
                event["level"] = 1
                for child in event["children"]:
                    child["level"] = 2
                    if "children" in child:
                        for grandchild in child["children"]:
                            grandchild["level"] = 3
            else:
                event["level"] = 1
        return result

    def _deduplicate_entities(self, result: ExtractionResult) -> ExtractionResult:
        """实体去重归一化"""
        seen = {}
        deduplicated = []

        for entity in result.entities:
            name = entity.get("name", "").strip()
            if not name:
                continue

            # 标准化名称
            key = name.lower()
            if key in seen:
                # 合并描述
                existing = seen[key]
                existing_desc = existing.get("description", "")
                new_desc = entity.get("description", "")
                if new_desc and new_desc not in existing_desc:
                    existing["description"] = existing_desc + "；" + new_desc
            else:
                seen[key] = entity
                deduplicated.append(entity)

        result.entities = deduplicated
        return result

    async def _call_llm(self, prompt: str) -> str:
        """调用LLM"""
        try:
            from src.infra.llm import call_ai
            return await call_ai(prompt)
        except Exception as e:
            logger.warning(f"[SAG] LLM调用失败: {e}")
            return ""

    def _parse_response(self, response: str) -> ExtractionResult:
        """解析LLM响应"""
        if not response:
            return ExtractionResult()

        try:
            # 清理响应
            clean = response.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
            if clean.endswith("```"):
                clean = clean[:-3]
            clean = clean.strip()

            data = json.loads(clean)

            events = data.get("events", [])
            entities = data.get("entities", [])

            return ExtractionResult(events=events, entities=entities)

        except json.JSONDecodeError:
            logger.warning("[SAG] JSON解析失败")
            return ExtractionResult()

    def get_stats(self) -> Dict:
        """获取提取统计"""
        return {
            "extract_count": self._extract_count,
            "success_count": self._success_count,
            "success_rate": self._success_count / max(self._extract_count, 1),
        }
