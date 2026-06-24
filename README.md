# 伏羲 v4.3 修复代码包

> 生成时间：2026-06-24
> 基于 GitHub 源码审查：https://github.com/1PGAT6466/fuxi

---

## 目录结构

```
26624/
├── 01-分类统一/           ← 最重要，其他修复依赖这个
│   ├── category_registry.py    # 统一分类注册表（新文件）
│   └── MIGRATION.md            # 迁移指南
│
├── 02-缓存修复/
│   └── cache.py                # 修复 module NameError + numpy 加速
│
├── 03-向量补全/
│   ├── rebuild_vectors.py      # 全量重建向量索引脚本
│   └── vector_store_patch.py   # 统一信号量 + embed 重试
│
├── 04-Wiki重构/
│   └── wiki_v2.py              # Wiki 统一存储方案
│
├── 05-图谱增强/
│   ├── graph_enhanced.py       # 图谱缓存 + 清洗 + 检索注入
│   └── clean_graph.py          # 图谱清洗脚本
│
├── 06-检索优化/
│   ├── retrieval_patch.py      # 检索流程优化（快速路径+图谱注入）
│   └── llm_stream_patch.py     # 流式响应 chunk 超时修复
│
├── 07-反馈修复/
│   └── feedback_fix.py         # 反馈闭环修复（不再静默失败）
│
├── 08-监控增强/
│   └── health_check.py         # 各组件独立探活
│
└── 09-脚本工具/
    └── migrate_categories.py   # 分类数据迁移脚本
```

---

## 修复优先级

### 🔴 第一批（立即执行）

| 序号 | 修复项 | 文件 | 预计耗时 |
|------|--------|------|----------|
| 1 | 统一分类注册表 | `01-分类统一/` | 2-3 小时 |
| 2 | 分类数据迁移 | `09-脚本工具/migrate_categories.py` | 30 分钟 |
| 3 | 缓存 NameError 修复 | `02-缓存修复/cache.py` | 10 分钟 |
| 4 | 向量索引补全 | `03-向量补全/rebuild_vectors.py` | 1-2 小时 |

### 🟡 第二批（1-2 周内）

| 序号 | 修复项 | 文件 | 预计耗时 |
|------|--------|------|----------|
| 5 | Wiki 统一存储 | `04-Wiki重构/wiki_v2.py` | 1-2 天 |
| 6 | 图谱清洗 | `05-图谱增强/clean_graph.py` | 1 小时 |
| 7 | 反馈闭环修复 | `07-反馈修复/feedback_fix.py` | 半天 |
| 8 | 流式响应超时 | `06-检索优化/llm_stream_patch.py` | 1 小时 |
| 9 | 信号量统一 | `03-向量补全/vector_store_patch.py` | 30 分钟 |

### 🟢 第三批（1-2 月内）

| 序号 | 修复项 | 文件 | 预计耗时 |
|------|--------|------|----------|
| 10 | 检索流程优化 | `06-检索优化/retrieval_patch.py` | 1-2 天 |
| 11 | 图谱增强（LLM 抽取） | `05-图谱增强/graph_enhanced.py` | 1 周 |
| 12 | 健康检查增强 | `08-监控增强/health_check.py` | 半天 |

---

## 快速开始

### 1. 统一分类（最关键）

```bash
# 1. 复制 category_registry.py 到 src/
cp 01-分类统一/category_registry.py /home/feng-shaoxuan/kb-server/src/

# 2. 按 MIGRATION.md 修改 graph_router.py, fusion.py, chat.py

# 3. 运行数据迁移
python 09-脚本工具/migrate_categories.py --dry-run  # 先预览
python 09-脚本工具/migrate_categories.py            # 确认后执行
```

### 2. 修复缓存

```bash
# 替换 cache.py
cp 02-缓存修复/cache.py /home/feng-shaoxuan/kb-server/src/services/
```

### 3. 补全向量

```bash
# 运行重建脚本
python 03-向量补全/rebuild_vectors.py --dry-run  # 先预览
python 03-向量补全/rebuild_vectors.py            # 确认后执行
```

### 4. 清洗图谱

```bash
python 05-图谱增强/clean_graph.py --dry-run  # 先预览
python 05-图谱增强/clean_graph.py            # 确认后执行
```

---

## 验证清单

修复后逐项验证：

- [ ] `match_category("VLAN 80 配置")` 返回 "IT网络"
- [ ] `match_category("模具导柱")` 返回 "模具设计"
- [ ] `normalize_category("网络建设")` 返回 "IT网络"
- [ ] 搜索 "GP-20-150" 能命中标准件文档
- [ ] 搜索 "VLAN 80" 能命中网络文档
- [ ] 图谱查询 "LSW1" 显示设备及关联实体
- [ ] 点击 👍 后日志显示 "learned: True"
- [ ] `/api/health` 返回各组件状态
- [ ] 流式响应在 API 挂起 30s 后自动中断
- [ ] 缓存 hit rate 逐步提升

---

## 注意事项

1. **所有操作先 `--dry-run` 预览**，确认无误再执行
2. **备份数据**：迁移前备份 `data/` 目录
3. **重启服务**：修改代码后需要重启 kb-server
4. **逐步上线**：不要一次性替换所有文件，先改分类，验证通过再改下一个

---

## 需要手动修改的文件

以下文件需要你手动编辑（不能直接替换）：

1. `src/services/graph_router.py` — 删除旧分类定义，import category_registry
2. `src/services/fusion.py` — 删除 CAT_KW，import category_registry
3. `src/api/chat.py` — 删除 DOMAIN_KEYWORDS，import category_registry
4. `src/services/retrieval.py` — 应用 retrieval_patch.py 中的优化

每个文件的具体修改方法见 `01-分类统一/MIGRATION.md`。
