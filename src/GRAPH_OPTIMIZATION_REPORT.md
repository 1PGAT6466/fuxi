# 伏羲知识图谱深度优化 — 变更报告

## 变更概览

本次优化涉及 4 个文件，涵盖 5 个优化维度：
1. 知识图谱数据模型 ✓
2. 实体抽取增强 ✓
3. 关系抽取增强 ✓
4. 图谱查询优化 ✓
5. 前端 API 对接 ✓

---

## 文件变更清单

### 1. `E:\fuxi-system\app\src\bagua\auto_graph.py`

**变更类型：** 新增类 + 增强配置

**变更内容：**

#### 新增 ENHANCED_ENTITY_PATTERNS 常量
- `chinese_person` — 增强版中文人名识别（支持职务后缀、动词前缀）
- `chinese_org` — 增强版中文组织机构名（支持更多后缀类型）
- `chinese_location` — 增强版中文地名（支持省市区县镇村等）
- `tech_term` — 工业/制造技术术语（注塑、冲压、CNC 等）
- `product_model` — 产品型号（支持中英文混合，如 M3x10、φ10H7）

#### 新增 LLM 配置常量
- `_LLM_ENTITY_PROMPT` — LLM 实体抽取提示词模板
- `_LLM_RELATION_PROMPT` — LLM 关系抽取提示词模板

#### 新增 EnhancedAutoGraphBuilder 类
继承自 AutoGraphBuilder，增加以下能力：

**实体抽取增强：**
- `extract_entities_llm()` — LLM 实体抽取（可选）
- `extract_entities_fallback()` — 规则抽取降级方案
- `extract_entities()` — 重写，优先 LLM，降级到规则

**关系抽取增强：**
- `extract_relations_llm()` — LLM 关系抽取
- `extract_relations_cooccurrence()` — 共现关系抽取（降级方案）
- 支持按句子级共现统计，置信度基于频率计算

**边权重计算：**
- `_calculate_edge_weights()` — 综合权重 = 置信度 × 关系类型权重 × 实体可信度
- 关系类型权重映射（works_at=0.9, located_in=0.85 等）

**实体去重合并：**
- `_normalize_entity_name()` — 名称归一化（去职务后缀、去空格）
- `_merge_entity_lists()` — 合并 LLM 和规则抽取结果

**核心方法重写：**
- `build_from_text()` — 三层策略：LLM + 规则 + 共现
- `build_full_graph()` — 增强版完整图构建
- `get_stats()` — 增加 LLM 调用数和共现边数统计

#### 更新 get_auto_graph_builder() 函数
- 新增 `use_enhanced` 参数（默认 True）
- 自动检测 LLM 可用性，选择合适的构建器

#### 更新 __all__ 导出
- 新增 `EnhancedAutoGraphBuilder`
- 新增 `ENHANCED_ENTITY_PATTERNS`

---

### 2. `E:\fuxi-system\app\src\api\graph.py`

**变更类型：** 新增 API 端点

**新增端点：**

#### `GET /api/graph/overview`
图谱概览 — 返回节点数、边数、类型分布等核心指标
```json
{
    "nodes_count": 100,
    "edges_count": 250,
    "entity_type_distribution": {"person": 30, "company": 20, ...},
    "edge_type_distribution": {"works_at": 50, "located_in": 30, ...},
    "communities_count": 5,
    "isolated_nodes": 10,
    "avg_degree": 5.0,
    "density": 0.025
}
```

#### `GET /api/graph/search`
节点搜索 — 按名称模糊匹配图谱节点
- 参数：`q`（搜索关键词）、`limit`（返回上限，默认 20）
- 返回匹配的节点列表

#### `GET /api/graph/node/{node_id}`
节点详情 — 获取指定节点的完整信息
- 支持 ID 或名称查询
- 返回节点属性和关联边数

#### `GET /api/graph/node/{node_id}/neighbors`
邻居节点 — 获取指定节点的所有关联节点
- 参数：`limit`（返回上限）、`relation`（按关系类型过滤）
- 返回邻居列表，包含方向（incoming/outgoing）和置信度

#### `GET /api/graph/statistics`
图谱统计信息 — `/api/graph/stats` 的别名，返回更详细的统计
- 包含 avg_degree 和 density

---

### 3. `E:\fuxi-system\app\src\taiyang\graph_traversal.py`

**变更类型：** 新增查询缓存

**变更内容：**

#### 新增缓存变量
- `_graph_cache` — 缓存的图数据
- `_graph_cache_time` — 缓存时间戳
- `_CACHE_TTL` — 缓存有效期（300 秒）

#### 重写 load_graph() 函数
- 使用全局缓存避免重复读取 JSON 文件
- TTL 300 秒自动失效
- 文件读取失败时返回旧缓存

#### 新增 invalidate_graph_cache() 函数
- 手动使图谱缓存失效
- 在图谱数据更新后调用

---

### 4. `E:\fuxi-system\app\src\taiyang\graph_router.py`

**变更类型：** 改进函数 + 移除重复代码

**变更内容：**

#### 改进 fuzzy_match_entity() 函数
增强版模糊匹配策略（优先级递减）：
1. 精确匹配 → 1.0
2. 节点名是查询的子串 → 0.9
3. 查询是节点名的子串 → 0.8
4. 词级重叠（英文适用）→ 0.6 × 重叠比例
5. 字符级相似度（中文支持）→ 0.5 × 公共字符比例

#### 移除重复 wiki-link 代码块
- 原代码有两个几乎相同的 wiki-link 查询块
- 第二个块会覆盖第一个块的结果
- 已移除重复的第二个块

---

## 兼容性说明

1. **向后兼容：** 所有原有 API 端点保持不变
2. **新增功能：** 新增的 API 端点和增强类都是可选的
3. **降级策略：** EnhancedAutoGraphBuilder 在 LLM 不可用时自动降级到规则引擎
4. **缓存策略：** 查询缓存使用 TTL 机制，不影响数据一致性

---

## 使用示例

### 使用 EnhancedAutoGraphBuilder
```python
from src.bagua.auto_graph import EnhancedAutoGraphBuilder

builder = EnhancedAutoGraphBuilder()
text = "张三在阿里巴巴工作，负责淘宝项目。他于2020年参加了云栖大会。"

# 提取实体（自动选择 LLM 或规则）
entities = builder.extract_entities(text)

# 构建图谱（LLM + 规则 + 共现三层策略）
graph = builder.build_full_graph(text, doc_id="doc-001")

# 获取统计信息
stats = builder.get_stats()
print(f"LLM 调用次数: {stats['llm_calls']}")
print(f"共现边数: {stats['cooccurrence_edges']}")
```

### 调用新 API 端点
```bash
# 图谱概览
curl http://localhost:8080/api/graph/overview

# 节点搜索
curl "http://localhost:8080/api/graph/search?q=张三&limit=10"

# 节点详情
curl http://localhost:8080/api/graph/node/张三

# 邻居节点
curl "http://localhost:8080/api/graph/node/张三/neighbors?limit=20&relation=works_at"

# 图谱统计
curl http://localhost:8080/api/graph/statistics
```

---

## 后续建议

1. **性能监控：** 观察 EnhancedAutoGraphBuilder 的 LLM 调用频率和耗时
2. **缓存调优：** 根据实际使用情况调整 `_CACHE_TTL` 参数
3. **规则扩展：** 根据业务需求添加更多实体抽取规则和边规则
4. **前端对接：** 使用新增的 API 端点实现图谱可视化界面
