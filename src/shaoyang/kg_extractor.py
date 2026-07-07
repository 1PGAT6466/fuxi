"""
kg_extractor.py — Phase 5.3: 知识图谱 LLM 抽取 + 实体消歧 + 增量更新
"""
import json, logging, time
from typing import Dict, List

logger = logging.getLogger(__name__)

ENTITY_PROMPT = """从以下工业文档中抽取实体。只输出 JSON 数组。
实体类型：device / material / component / standard / supplier / parameter / process / tool

文档：{file_name}
内容：{text}

输出：[{{"name":"实体名","type":"类型","description":"一句话描述","aliases":["别名"]}}]"""

RELATION_PROMPT = """从以下工业文档中抽取实体间关系。只输出 JSON 数组。
实体列表：{entities}
文档内容：{text}

关系类型：uses(使用), contains(包含), manufactured_by(制造), supplied_by(供应), 
          measures(测量), controls(控制), part_of(组成部分), alternative(替代)

输出：[{{"source":"实体A","target":"实体B","relation":"关系类型","description":"一句话"}}]"""


async def extract_entities_llm(text: str, file_name: str) -> List[Dict]:
    """LLM 抽取实体"""
    from src.services.llm import call_llm
    prompt = ENTITY_PROMPT.format(file_name=file_name, text=text[:3000])
    result = await call_llm(prompt, max_tokens=2000)
    if result:
        try:
            result = result.strip()
            if result.startswith("```"):
                result = result.split("\n", 1)[1].rsplit("```", 1)[0]
            return json.loads(result)
        except json.JSONDecodeError as e:
            logger.warning("json.JSONDecodeError 失败: %s", e, exc_info=True)
    return []


async def extract_relations_llm(text: str, entities: List[Dict]) -> List[Dict]:
    """LLM 抽取关系"""
    from src.services.llm import call_llm
    entity_names = [e["name"] for e in entities[:15]]
    prompt = RELATION_PROMPT.format(entities=json.dumps(entity_names, ensure_ascii=False), text=text[:3000])
    result = await call_llm(prompt, max_tokens=1500)
    if result:
        try:
            result = result.strip()
            if result.startswith("```"):
                result = result.split("\n", 1)[1].rsplit("```", 1)[0]
            return json.loads(result)
        except json.JSONDecodeError as e:
            logger.warning("json.JSONDecodeError 失败: %s", e, exc_info=True)
    return []


class EntityResolver:
    """实体消歧"""
    
    def __init__(self):
        self._alias_map: Dict[str, str] = {}
        self._entities: Dict[str, dict] = {}
    
    def resolve(self, name: str, entity_type: str = "") -> str:
        """实体消歧：返回统一名称"""
        name_lower = name.lower().strip()
        # 1. 别名映射
        if name_lower in self._alias_map:
            return self._alias_map[name_lower]
        # 2. 精确匹配
        if name in self._entities:
            return name
        # 3. 编辑距离匹配（含包含关系）
        for existing in list(self._entities.keys()):
            if name in existing or existing in name:
                self._alias_map[name_lower] = existing
                return existing
        # 4. 新实体
        self._entities[name] = {"type": entity_type}
        self._alias_map[name_lower] = name
        return name
    
    def get_entity(self, name: str) -> dict:
        name = self.resolve(name)
        return self._entities.get(name, {})
    
    def get_stats(self) -> dict:
        return {"entities": len(self._entities), "aliases": len(self._alias_map)}


_resolver = None

def get_entity_resolver() -> EntityResolver:
    global _resolver
    if _resolver is None:
        _resolver = EntityResolver()
    return _resolver
