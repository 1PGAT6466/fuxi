# 伏羲系统数据层审计报告

> 审计日期: 2026-07-09  
> 审计人员: 数据库调优师  
> 审计范围: 工作目录 `E:\easyclaw\伏羲-v1.44\repo\`  
> **原则: 不改代码，只摸底**

---

## 一、总体结论

| 组件 | 状态 | 数据类型 |
|------|------|----------|
| ChromaDB 向量数据库 | ✅ 运行中 | **Mock 种子数据 + 1 条真实文档数据** |
| SQLite (chunks.db) | ✅ 运行中 | **种子数据 + 1 份测试文档** |
| SQLite (worldtree.db) | ✅ 运行中 | **1 份测试 wiki 文档** |
| PostgreSQL | ❌ **不存在** | — |
| 用户数据 (users.json) | ✅ 存在 | **测试用户（8 个 fake 帐号）** |
| 审计日志 (audit.db) | ✅ 存在 | **真实运行日志（44 条）** |
| 评测数据 | ⚠️ 空 | **无实际评测数据** |
| Dream Cycle | ⚠️ Mock | **报告数据为固定假数据** |

**核心结论**: 伏羲系统当前处于 **测试环境状态**，所有数据均为种子/测试数据，没有任何生产业务数据。

---

## 二、ChromaDB（向量数据库）— 详细结果

### 2.1 数据库路径

- **配置路径**: `data/chromadb`（环境变量 `KB_CHROMA_DIR`）
- **实际路径**: `E:\easyclaw\伏羲-v1.44\repo\data\chromadb\`
- **路径状态**: ✅ 正确，与配置一致

### 2.2 集合详情

| 集合名称 | Collection ID | 向量维度 | 当前向量数 | 状态 |
|----------|---------------|----------|-----------|------|
| `kb_chunks` | `509ac747-...` | **128** 维 | **6 条** | ✅ |
| `kb_tables` | `e3ffe3d2-...` | 无 | **0 条** | ⚠️ 空集合 |

### 2.3 kb_chunks 中的 6 条向量——全是种子数据

| # | 内容摘要 | 来源 | 真实？ |
|---|---------|------|--------|
| 1 | "伏羲是一个企业知识认知中枢…" | `scripts/seed_vectors.py` | ❌ 种子 |
| 2 | "ChromaDB 是一个开源的向量数据库…" | `scripts/seed_vectors.py` | ❌ 种子 |
| 3 | "PostgreSQL 的 pgvector 扩展…" | `scripts/seed_vectors.py` | ❌ 种子 |
| 4 | "文档分块是 RAG 管线的关键步骤…" | `scripts/seed_vectors.py` | ❌ 种子 |
| 5 | "HNSW 是一种高效的近似最近邻搜索算法…" | `scripts/seed_vectors.py` | ❌ 种子 |
| 6 | "坤卦 ☷ 负责伏羲系统的记忆存储…" | `scripts/seed_vectors.py` | ❌ 种子 |

**关键发现**: 向量维度为 **128 维**（文件注释称 1024 维，实际用 128），使用 `random.uniform(-1, 1)` 生成+L2 归一化的**随机伪向量**，并非真实嵌入。没有真实的 BAAI/bge-large-zh-v1.5 嵌入数据。

### 2.4 第二个 ChromaDB 实例 (`data/chroma/`)

- 路径: `data/chroma/chroma.sqlite3` (188 KB)
- 也有 2 个 collection（与 `data/chromadb/` 相同结构）
- embeddings 数量: **0** — 旧实例，未被使用
- 结论: **废弃副本**

### 2.5 第三个 ChromaDB 实例 (`src/data/chroma_wiki/`)

- 路径: `src/data/chroma_wiki/chroma.sqlite3`
- 1 个 collection，0 embeddings
- 结论: **另一个废弃副本**

### 2.6 是否有真实知识文档数据？

**没有**。当前 ChromaDB 中所有 6 条向量全部来自 `scripts/seed_vectors.py` 脚本中的硬编码种子文本。这些向量的嵌入值是随机生成的（无外部 embedder 服务调用）。

---

## 三、SQLite 关系数据库 — 详细结果

### 3.1 chunks.db（主文档 chunk 存储）

| 表 | 行数 | 说明 |
|----|------|------|
| `chunks` | **7 行** | 7 条 chunk 记录 |

7 条 chunk 的内容分析:

| ID | 文件 | 来源 | 真实？ |
|----|------|------|--------|
| 1 | `malware.exe` | 上传的测试文件（4 字节） | ❌ 测试 |
| 2-7 | `test_knowledge.md` | 同一份文档的 6 个 chunk | ⚠️ 半真实 |

**关键发现**:
- `test_knowledge.md` 的 6 条 chunk 内容完全相同（#1-#6），表明分块逻辑可能有问题
- 文件来自: `C:\Users\FENGSH~1\AppData\Local\Temp\easyclaw\runtime\fuxi_smoke_nyt024sx\test_knowledge.md`（烟雾测试临时文件）
- `malware.exe` 是一个 4 字节的假文件

### 3.2 worldtree.db（知识图谱/Wiki 存储）

| 表 | 行数 | 说明 |
|----|------|------|
| `wiki_pages` | **2 行** | 2 页 wiki 文档 |
| `wiki_cross_links` | 0 行 | 无交叉链接 |

wiki_pages 内容:
- 第 1 页: `wiki_52708f8cc011a45625d6655d15c4e0b4` — "伏羲智能知识库系统"（来自烟雾测试）
- 第 2 页: `wiki_52708f8cc011a456` — 同一文档的去重副本（category 不同）
- 两者的 `source` 均指向: `C:\Users\FENGSH~1\AppData\Local\Temp\easyclaw\runtime\fuxi_smoke_nyt024sx\test_knowledge.md`

**worldtree.db 没有 entities/entity_relations/terms 表** — 这些表在代码中有定义，但在数据库实际不存在。`db.py` 中对这些表的查询会失败。

### 3.3 memory.db

| 表 | 行数 | 说明 |
|----|------|------|
| `entities` | 0 | 空 |
| `events` | 0 | 空 |
| `event_entities` | 0 | 空 |

**结论**: 完全空库，未被使用。events/entities 的实际定义在 `chunks.db` 中（MemoryStore 创建在同一个 chunks.db 内）。

### 3.4 audit.db（审计日志）

- `audit_log` 表: **44 条记录** ✅ **真实**
- 这是唯一可以确认的**真实运行数据**，记录了 API 调用和用户操作
- 包含 timestamp、user、action、path、ip_address 等字段

---

## 四、PostgreSQL — 确认结果

### ❌ 完全不存在

- `.env.example` 中有 `REDIS_URL` 但没有 `DATABASE_URL` 或 PostgreSQL 相关配置
- `.env` 配置中没有任何 PostgreSQL 连接信息
- 系统中所有"数据库"操作全部走 SQLite
- 代码中的 `src/core/db.py` 使用 `sqlite3.connect()`
- 连接池代码 (`src/infra/connection_pool.py`) 存在但为本地连接池，不是 PostgreSQL 连接池
- docker-compose.yml 中无 PostgreSQL 服务

**伏羲 v1.50 是一个 SQLite-only 架构，不含 PostgreSQL。**

---

## 五、文件存储 — 详细结果

### 5.1 data/ 目录结构总览

```
data/
├── ab_tests/          ← 空目录
├── backups/           ← 空目录
├── chroma/            ← 废弃的 ChromaDB 副本
├── chromadb/          ← 当前 ChromaDB（6 条种子向量）
├── config_history/    ← 空目录
├── dream_reports/     ← 2 份假 Dream 报告
├── evaluation/
│   └── reports/       ← 空目录
├── growth/
│   ├── shaoyin_quality.jsonl  ← 28 条品质记录（真实调用）
│   └── taiyin_quality.jsonl   ← 8 条品质记录（真实调用）
├── kb-images/
│   └── thumbs/        ← 空目录
├── knowledge_lifecycle/ ← 空目录
├── logs/              ← 空目录
├── memory/            ← 空目录
├── online_eval/       ← 空目录
├── services/
│   └── dxf-viewer/    ← 空目录
├── traces/
│   ├── 8c3c3f49a0d6.log  ← 3 条 trace 日志（真实调用）
│   ├── 96b06f42ecd3.log
│   └── 99355385f4d7.log
├── uploads/
│   └── malware.exe    ← 4 字节测试文件
├── wiki/              ← 空目录
├── audit.db           ← 审计日志（44 条真实）
├── chunks.db          ← 7 条 chunk
├── feature_flags.json ← 功能开关配置
├── knowledge_graph.json ← 知识图谱（7 节点，7 边，来自测试文档）
├── memory.db          ← 空库
├── users.json         ← 8 个测试用户
└── worldtree.db       ← 2 条 wiki 页面
```

### 5.2 知识库源文件位置

- **上传文件**: `data/uploads/`（只有 1 个 `malware.exe`，4 字节测试文件）
- **知识库图片**: `data/kb-images/`（空，thumbs 也为空）
- **Wiki 源数据**: 存储在 `data/worldtree.db` 中的 `wiki_pages` 表
- **注意**: 没有 `data/knowledge/` 或 `data/documents/` 目录来存储原始文档文件

### 5.3 growth 数据

`shaoyin_quality.jsonl` 和 `taiyin_quality.jsonl` 包含 **28+8 条真实 API 调用品质记录**，包括:
- 搜索查询 (query: "test", "hello", "测试问题")
- trace_id
- 置信度分数 (confidence_avg: 0.3-0.5)
- 重试率 (retry_rate: 0.0-1.0)
- 延迟 (duration_ms: 2842-25413)
- 时间戳 (2026-07 的多次调用)

**这些是真实的系统运行记录 ✅**

---

## 六、关键子系统审计

### 6.1 健康检查 API (`/api/health`)

**数据来源分析**:

| 检查项 | 数据来源 | 真实/模拟 |
|--------|---------|----------|
| `check_database()` | `SELECT 1` 检查 SQLite 连接 | ✅ 真实 |
| `check_vector_store()` | `get_vector_store()` 是否为 None | ✅ 真实检查 |
| `check_llm()` | 仅检查是否能 `import call_llm` | ⚠️ 浅检查，不实际调用 LLM |
| `check_bagua_overall()` | 从 `_gua_registry` 获取实例状态 | ✅ 真实（如果八卦已注册） |
| `check_connection_pool()` | 检查本地连接池 | ✅ 真实 |
| `check_llm_api_reachable()` | HTTP GET `{MIMO_BASE_URL}/models` | ✅ 真实（如果配置了 API key） |
| `check_intent_bus()` | 检查 IntentBus 实例状态 | ✅ 真实 |

**结论**: 健康检查 API 返回的数据 **大部分来自真实检查**，但都是进程内状态（进程级可用性，不是数据库级数据量）。没有检查数据行数、磁盘用量等业务指标。

### 6.2 八卦子系统数据来源

```python
# health_check.py 中 check_bagua_overall()
def _get_gua_instances():
    if _gua_registry:
        return dict(_gua_registry)  # ← 从运行时注册表
    # fallback: 从 bagua 模块导入检查 health_summary
```

**数据流向**: `IntentBus` 注册表（运行时内存）→ `GuaBase.health_summary()` → 返回健康状况

- 八卦的健康状态完全来自**运行时内存中的对象**
- `health_summary()` 检查的是断路器等进程内状态
- **不查询任何数据库**

**结论**: 八卦子系统的健康数据 **来自真实的运行时状态**（断路器、依赖可用性），但不是持久化的历史数据。如果系统刚启动且八卦尚未注册，会显示 "unregistered" 或 "unknown"。

### 6.3 评测数据

- `data/evaluation/reports/`: **空目录** — 没有任何评测报告
- `eval_automation.py` 代码完整，定义了 smoke test 和 daily eval 流程
- `/api/evaluation/overview` 返回 `{"search_stats": {}, "rag_eval": {}, "test_cases_count": 0}`
- `/api/evaluation/results` 返回空列表 — **从未执行过真实评测**
- `ground_truth.json` 存在于 `src/eval/` 但评估从未运行过

**结论**: 评测数据 **全部为空**，前端看到的 0/0/0 状态是真实的空状态。评测框架代码已就绪，但从未执行过。

### 6.4 Dream Cycle（夜间循环）数据

- `data/dream_reports/` 包含 2 份报告（2026-07-08 03:58 和 03:59）
- 报告显示固定的假数据:
  - 消化: 新文档=15, 嵌入=13, 总计=1542
  - 实体: 342 个实体, 87 条边
  - 空白查询: "Q4 report"、"security audit"
- **数据来源**: `DreamCycle.run()` 查询 `chunks.db` 但返回的数据量不匹配（声称 1542 文档但 chunks.db 只有 7 条）
- `dream_data_*.json` 显示 `report_path` 指向 `E:/easyclaw/伏羲-v1.44/repo/src/evolution/../../data/dream_reports/...`

**关键发现**: Dream 报告中的数据**与 chunks.db 实际数据量严重不符**，报告声称有 1542 个文档，342 个实体，但实际 chunks.db 只有 7 条 chunk，entities 表为空。这些疑似是 **mock/占位数据** 或来自已删除的数据。

### 6.5 Wiki 数据来源

- Wiki API (`/api/wiki/*`) 调用 `WikiEngine.list_pages()` → `src/taiyang/wiki.py`
- 数据源: `worldtree.db` 的 `wiki_pages` 表
- 当前数据: **2 条 wiki 页面**，全部来自测试文档 `test_knowledge.md`
- 知识点之间的关系: `knowledge_graph.json` 中有 7 个节点、7 条边，但**全部来自同一份测试文档**

**结论**: Wiki 数据 **源于真实数据库查询**（从 worldtree.db），但数据库中的内容**全部是测试数据**。没有真实的团队文档或业务知识。

---

## 七、用户数据

`data/users.json` 包含 **8 个测试帐号**:

| 用户名 | 角色 | 创建时间 (Unix) | 说明 |
|-------|------|----------------|------|
| admin | admin | 1782719335 | 管理员，密码已 hash |
| testuser | user | 1783253590 | 测试用户 |
| testuser2 | user | 1783254311 | 测试用户 |
| testuser_69121 | user | 1783299934 | 自动生成的测试用户 |
| testuser_62052 | user | 1783299956 | 自动生成的测试用户 |
| curltest99 | user | 1783303100 | curl 测试用户 |
| testuser_41868 | user | 1783329714 | 自动生成的测试用户 |
| testuser_27235 | user | 1783329928 | 自动生成的测试用户 |

**密码**: 所有密码经过 bcrypt hash（`$2b$12$...`），符合安全规范（v1.50 无硬编码默认值）。

**结论**: 全部是测试/开发帐号，**无真实企业用户**。

---

## 八、审计日志

`data/audit.db` 中的 `audit_log` 表有 **44 条真实审计记录**。

- 格式: id, timestamp, user, action, path, method, status_code, ip_address, user_agent, details
- 这是唯一确认的**真实运行数据**，记录了开发测试期间的 API 调用

---

## 九、总结矩阵

| 数据维度 | 实际值 | 代码声称/预期 | 差距 | 真实性 |
|---------|--------|--------------|------|--------|
| ChromaDB 向量数 | 6 | dev→数百，prod→数千+ | **巨大** | ❌ 全种子 |
| chunks.db 文档数 | 1 份（7 chunks） | 数百份 | **巨大** | ⚠️ 测试文档 |
| wiki 页面 | 2 | 数十页 | 差距 | ⚠️ 测试文档 |
| 知识图谱节点 | 7 | 数百节点 | 差距 | ⚠️ 来自测试文档 |
| Dream 报告声称数 | 1542 文档 / 342 实体 | — | **严重不匹配** | ❌ 假数据 |
| 评测数据 | 0 | 数十轮评测 | — | ❌ 从未执行 |
| 用户数 | 8（全测试） | 适用于团队 | — | ❌ 无真实用户 |
| 审计日志 | 44 条 | — | — | ✅ 真实 |
| 上传文件 | 1（malware.exe） | 多份文档 | **巨大** | ❌ 测试文件 |
| Growth 指标 | 36 条记录 | — | — | ✅ 真实 API 调用记录 |
| Trace 日志 | 3 条 | — | — | ✅ 真实 |

**最终结论**: 伏羲系统 **所有业务数据均为种子/测试数据**，系统框架完整（数据库 schema、API 路由、健康检查全部就绪），Chat 接口和搜索链路经过测试验证（growth 指标和 trace 日志证实），但缺少真实的知识文档、用户和生产运行数据。Dream Cycle 报告中存在与实际数据库不符的假数据（1542 文档 vs 实际 7 chunks），需要排查。
