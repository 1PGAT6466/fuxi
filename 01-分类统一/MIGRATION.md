# 分类统一迁移指南

## 步骤

### 1. 放置文件
将 `category_registry.py` 放入 `src/` 目录。

### 2. 修改 `src/services/graph_router.py`

**删除**以下定义（约 50 行）：
```python
# 删除 CATEGORY_ALIAS 字典
CATEGORY_ALIAS = { ... }

# 删除 INTENT_KEYWORDS 字典
INTENT_KEYWORDS = { ... }

# 删除 ENTITY_TYPE_TO_CATEGORY 字典
ENTITY_TYPE_TO_CATEGORY = { ... }

# 删除 ENTITY_SYNONYMS 字典
ENTITY_SYNONYMS = { ... }
```

**替换为**：
```python
from src.category_registry import (
    CATEGORIES, normalize_category, match_category, match_categories_multi,
    get_entity_type_category, SYNONYM_MAP, get_keywords
)
```

**修改 `route_to_categories` 函数**：
```python
def route_to_categories(query: str) -> List[str]:
    """图谱路由：识别查询中的实体 → 映射到分类"""
    entities = _match_entities_in_query(query)
    if not entities:
        return []
    
    cats = {}
    for e in entities:
        cat = get_entity_type_category(e.get("type", ""))
        if cat:
            cats[cat] = cats.get(cat, 0) + e.get("mentions", 1)
    
    sorted_cats = sorted(cats.items(), key=lambda x: x[1], reverse=True)
    return [c for c, _ in sorted_cats]
```

**修改 `expand_query_with_synonyms` 函数**：
```python
def expand_query_with_synonyms(query: str) -> str:
    """同义词扩展（使用统一同义词表）"""
    expanded = query
    for term, synonyms in SYNONYM_MAP.items():
        if term in query.lower():
            expanded += " " + " ".join(synonyms)
    return expanded
```

### 3. 修改 `src/services/fusion.py`

**删除** `CAT_KW` 字典（约 30 行），替换为：
```python
from src.category_registry import CATEGORIES

# 动态生成 CAT_KW（从统一注册表）
CAT_KW = {}
for cat_name, cat_info in CATEGORIES.items():
    if cat_info.get("domain") in ("network", "mechanical", "electrical", "quality", "process"):
        CAT_KW[cat_name] = cat_info["keywords"][:10]  # 取前 10 个关键词
```

**删除** `_SYNONYM_MAP` 字典，替换为：
```python
from src.category_registry import SYNONYM_MAP as _SYNONYM_MAP
```

### 4. 修改 `src/api/chat.py`

**删除** `DOMAIN_KEYWORDS` 字典，替换为：
```python
from src.category_registry import match_category, get_domain, get_domain_prompt, CATEGORIES
```

**修改 `_get_domain_override` 函数**：
```python
def _get_domain_override(query: str, route_name: str) -> str:
    if route_name != "default":
        return get_domain_prompt(get_domain(route_name))
    
    matched_cat = match_category(query)
    if matched_cat:
        return get_domain_prompt(matched_cat)
    return ""
```

### 5. 数据迁移（可选，对已有数据）

运行迁移脚本更新数据库中的旧分类名：
```bash
cd /home/feng-shaoxuan/kb-server
python scripts/migrate_categories.py
```

### 6. 验证

```bash
# 测试分类匹配
python -c "
from src.category_registry import match_category, normalize_category
print(match_category('VLAN 80 怎么配置'))  # 应输出: IT网络
print(match_category('模具导柱材料'))      # 应输出: 模具设计
print(normalize_category('网络建设'))       # 应输出: IT网络
print(normalize_category('品质管理'))       # 应输出: 品质测量
"
```
