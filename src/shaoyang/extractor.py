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
    """SAG式事件/实体提取器"""

    def __init__(self):
        self._extract_count = 0
        self._success_count = 0

    async def extract(self, chunk_text: str, chunk_meta: Dict = None) -> ExtractionResult:
        """从文本中提取事件和实体"""
        if not chunk_text or len(chunk_text) < 50:
            return ExtractionResult()

        try:
            # 构建六段式Prompt
            prompt = self._build_prompt(chunk_text, chunk_meta)

            # 调用LLM
            response = await self._call_llm(prompt)

            # 解析结果
            result = self._parse_response(response)

            self._extract_count += 1
            if result.events or result.entities:
                self._success_count += 1

            return result

        except Exception as e:
            logger.warning(f"[SAG] 提取失败: {e}")
            return ExtractionResult()

    def _build_prompt(self, text: str, meta: Dict = None) -> str:
        """构建六段式Prompt"""
        file_name = meta.get("file_name", "") if meta else ""
        category = meta.get("category", "") if meta else ""
        chunk_index = meta.get("chunk_index", 0) if meta else 0
        total_chunks = meta.get("total_chunks", 1) if meta else 1

        # 动态读取实体类型
        entity_types = self._get_entity_types()

        prompt = f"""## Role
你是专业的内容提取器，核心任务是从原始文档中提取**事项**和**实体**两类结构化信息。

## Background
当前文件：{file_name}
文件分类：{category}
当前片段：第 {chunk_index + 1}/{total_chunks} 段

## Task
1. **过滤** — 识别有效内容，过滤噪音信息（广告/页脚/导航直接丢弃）
2. **事项提取**
   - 按语义分层：大事件 → 子事件 → 细节（最多2层）
   - 每个事项：标题、摘要、完整内容、引用的片段索引
   - **代词消歧**：把"他"替换为具体人名，把"该公司"替换为具体公司名
3. **实体提取**
   - 主语+谓语+宾语的核心实体
   - 并列实体拆开："张三和李四" → 张三 + 李四
   - 类型：{entity_types}
   - 每个实体：名称、类型、在事项中的作用描述

## Input
{text[:3000]}

## Output
```json
{{
  "events": [
    {{
      "title": "事项标题",
      "summary": "一句话摘要",
      "content": "完整内容",
      "keywords": ["关键词1", "关键词2"],
      "priority": "HIGH/MEDIUM/LOW",
      "entities": ["实体1", "实体2"],
      "references": [1],
      "children": []
    }}
  ],
  "entities": [
    {{
      "name": "实体名称",
      "type": "person/organization/product/...",
      "description": "在事项中的作用"
    }}
  ]
}}
```

## Rules
- 每个片段至少提取1个事项，禁止空结果
- 子事项必须从父事项继承具体名称（禁止代词）
- 每个最细事项至少提取1个实体
- 实体类型必须从预定义列表选择
- 相同实体的不同表达都要提取（全称+缩写+别称）
- 整理而非创作，不添加、不臆测"""

        return prompt

    def _get_entity_types(self) -> str:
        """获取实体类型列表"""
        try:
            from src.db.ontology import ENTITY_TYPES
            types = [f"{t}: {info.get('label', t)}" for t, info in ENTITY_TYPES.items()]
            return "/".join(types[:10])  # 限制长度
        except Exception:
            return "person/organization/product/location/time/subject/metric/material/device"

    async def _call_llm(self, prompt: str) -> str:
        """调用LLM"""
        try:
            from src.services.llm import call_deepseek
            return await call_deepseek(prompt)
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
