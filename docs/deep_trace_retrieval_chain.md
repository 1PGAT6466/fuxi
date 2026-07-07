# 伏羲 v1.50 检索 & Rerank 全链路深度追踪报告

> 生成时间：2026-07-06  
> 仓库：`E:\easyclaw\伏羲-v1.44\repo`  
> 追踪原则：逐层追踪 import 链和实际调用点，不跳跃，验证"这个函数真的被调用了"

---

## 总体架构概览

```
                    ┌──────────────────────────────┐
                    │     /api/search  (search.py) │
                    │     /api/chat    (chat.py)   │
                    └──────────┬───────────────────┘
                               │
              ┌────────────────┼──────────────────┐
              ▼                ▼                   │
    hybrid_search()    ShaoyinBrain.think()        │
    (retrieval.py)     (brain.py)                  │
         │                  │                      │
         │    ┌─────────────┼─────────────────┐    │
         │    ▼             ▼                  ▼    │
         │  intent     _retrieve()          compose│
         │  classify   → hybrid_search()    + LLM  │
         │    │             │                      │
         ▼    │    ┌────────┘                      │
    TaiyangRefine.refine()                         │
    ┌──────────────────────────────────────────┐   │
    │ L0  Cache (cache.py)           ⚠️ 未接入  │   │
    │ L1  Query Expansion           (query_exp) │   │
    │ L2  Multi-recall (BM25+Vector)           │   │
    │ L2.5 Multi-hop   (feature flag)          │   │
    │ L2.6 Graph Query (try/except)            │   │
    │ L3  RRF Fusion   (fusion.py)             │   │
    │ L4  Rerank       (rerank.py) 4-level     │   │
    │ L5  Context Expand (postprocess)         │   │
    │ L6  Merge Multi-hop results              │   │
    └──────────────────────────────────────────┘   │
```

---

## 1. API 入口 → 检索函数调用链

### 1.1 `/api/search` (src/api/search.py)

```python
# 第 11 行 — 直接调用
from src.taiyang.retrieval import hybrid_search
results = await hybrid_search(q, top_k=top_k)
```

**调用链**：
```
GET /api/search?q=xxx&top_k=15
  → search()                          [src/api/search.py:11]
    → hybrid_search()                  [src/taiyang/retrieval.py:331]
      → get_retrieval()                [retrieval.py:327]
        → TaiyangRetrieval.refine()    [retrieval.py:43]
```

**验证结果**：✅ 调用链完整，`hybrid_search` 是全局便捷函数，内部获取 `TaiyangRetrieval` 单例后调用 `refine()`。

### 1.2 `/api/chat` (src/api/chat.py)

```python
# 第 20-22 行
from src.shaoyin.brain import ShaoyinBrain
from src.hypothalamus.meridian import Meridian
meridian = Meridian()
brain = ShaoyinBrain(meridian)
result = await brain.think(body.query, body.history)
```

**调用链**：
```
POST /api/chat {query, history}
  → ShaoyinBrain.think()              [src/shaoyin/brain.py:59]
    ├─ Step 1: _classify_intent()     → Instinct.classify_intent()
    ├─ Step 2: _select_strategy()     → 返回 "fast"/"deep"/"table"
    ├─ Step 3: _retrieve()            → hybrid_search()     [brain.py:152]
    ├─ Step 4: Self-RAG reflect       → SmartSelfRAG        [brain.py:79-92]
    ├─ Step 5: CRAG correct           → CRAGCorrector       [brain.py:95-105]
    ├─ Step 6: _compose()             → call_deepseek()     [brain.py:158-174]
    ├─ Step 7: _validate()            → 简单评分            [brain.py:189-196]
    └─ Step 8: _retry()               → call_deepseek()     [brain.py:198-210]
```

**验证结果**：✅ `/api/chat` 通过 `ShaoyinBrain.think()` → `_retrieve()` 间接调用 `hybrid_search()`。完整流程 8 个步骤，全部有实际调用。

---

## 2. `hybrid_search()` / `TaiyangRetrieval.refine()` — L0-L6 逐层分析

文件：`src/taiyang/retrieval.py`

### 总体管线（`refine()` 方法，第 43 行起）

```
refine(query, strategy="auto", top_k=15, trace_id=None)
  │
  ├─ [L1] _expand_query(query)          → 同义词+型号变体扩展
  ├─ [L2] asyncio.gather(
  │         _bm25_recall(expanded_q)    → SQLite BM25
  │         _vector_recall(expanded_q)  → ChromaDB 向量检索
  │       )
  ├─ [L2.5] multi_hop_search(query)     → ⚠️ 受 Feature Flag 控制
  ├─ [L2.6] GraphRouter.get_entity_context() → 知识图谱查询
  ├─ [L3] _fuse(bm25, vector)           → rrf_fusion()
  ├─ [L4] _rerank(query, fused)         → rerank_with_deepseek()
  ├─ [L5] _expand_context(reranked)     → expand_context()
  └─ [L6] merge_search_results()        → 合并多跳结果
```

---

### L0: 缓存层介入？

**文件**：`src/taiyang/cache.py`

**核心函数**：
| 函数 | 功能 |
|------|------|
| `get_cache(query)` | L1 精确匹配 → L2 语义余弦相似度 (≥0.92) |
| `set_cache(query, results)` | 写入缓存，同时更新 L1 + L2 |
| `get_cache_stats()` | 返回 hit/miss 统计 |

**实际调用验证**：
```
❌ refine() 方法中没有调用 get_cache()！
❌ brain.py 的 _retrieve() 也没有调用 get_cache()！
⚠️ 缓存仅被 services/__init__.py 导出，但从未在检索管线中实际使用。
⚠️ retrieval.py 仅在第 121 行引用了 src/infra/cache_stats（记录 miss 统计），而非缓存查询。
```

**结论**：**语义缓存（L0）在 v1.50 检索管线中实际上被架空，未接入管线。** 这是一个待集成的功能模块。

---

### L1: 查询扩展 — `_expand_query()`

**调用位置**：`retrieval.py:63` — 实际调用 ✅

```python
expanded_q = self._expand_query(query)
```

**实现**：`src/taiyang/query_expansion.py::expand_query()`

**具体步骤**：
1. **同义词扩展**：从 `synonyms.yaml` 加载同义词映射，对 query 中匹配到的术语，附加最多 3 个同义词
2. **型号变体扩展**：预定义的型号映射表（PA66→PA66-GF30, POM→POM-C/Delrin, ABS→ABS+PC 等）
3. **去重**：最后全部 join 成一个空格分隔的扩展 query 字符串

**外部依赖**：
- `src/services/synonym_loader::load_synonyms()` — 本地 YAML 文件加载
- `jieba` — 本地分词（可选）

**降级路径**：如果加载同义词失败，`_SYNONYM_MAP` 为空，直接返回原始 query

---

### L2: 双路并行召回 — `_bm25_recall()` + `_vector_recall()`

**调用位置**：`retrieval.py:67-68` — 通过 `asyncio.gather` 并行执行 ✅

#### L2a: BM25 召回 (`_bm25_recall()`)

```python
# retrieval.py:143-150
async def _bm25_recall(self, query, top_k):
    from src.db.memory_store import get_store
    store = get_store()
    results = store.keyword_search(query, top_k)
    return [{"text": ..., "score": ..., "_source": "bm25"} ...]
```

**外部服务**：
- `src/db/memory_store::get_store()` → SQLite 数据库 `chunks.db`
- 方法：`store.keyword_search()` — SQLite FTS5 全文检索
- **URL**：本地文件（`data/chunks.db`）
- **是否必需**：是（如果失败返回空列表 `[]`）

#### L2b: 向量召回 (`_vector_recall()`)

```python
# retrieval.py:152-179
async def _vector_recall(self, query, top_k):
    from src.db.vector_store import embed_texts, get_vector_store
    q_emb = await embed_texts([query])         # → embedder_server
    vs = get_vector_store()                     # → ChromaDB
    result = vs.query(q_emb[0], n_results=top_k)
    # 过滤相似度 > 0.15
    return [{"score": sim*10, "_source": "vector", "_similarity": sim} ...]
```

**外部服务**：
| 服务 | URL / 地址 | 模型 | 必需 |
|------|-----------|------|------|
| embedder_server | `EMBEDDER_URL` = `http://localhost:8081` | 本地模型 | 是 |
| ChromaDB | 本地文件 `data/chroma_db/` | — | 是（若无数据 count=0 返回空） |

**降级路径**：如果 embed_texts 失败或 ChromaDB 不可用，返回 `[]`，管线继续使用仅 BM25 的结果。

---

### L2.5: 多跳检索 — `multi_hop_search()`

**调用位置**：`retrieval.py:71-78` — ✅ 实际调用

```python
from src.taiyin.flags import is_enabled
if is_enabled("taiyang_multi_hop"):      # ⚠️ Feature Flag!
    from src.taiyang.multi_hop import multi_hop_search
    multi_hop_results = await multi_hop_search(query, top_k=top_k)
```

**关键发现**：
- **多跳检索默认不启用！** 它受 `taiyang_multi_hop` feature flag 控制
- 如果 flag 未开启，整个 L2.5 跳过，不会有任何调用
- Flag 由 `src/taiyin/flags.py` 管理

**多跳检索内部流程**（当启用时）：
1. **实体提取**（三级策略）：正则+jieba → 不足2个实体时 LLM 提取
2. **单实体**：事件关联 → 碎片向量检索
3. **多实体**：实体→事件→碎片 两跳检索
4. **打分**：`seed_score()` = 0.85×向量相似度 + 0.15×实体命中 + 0.05×双通道

**外部服务**：
| 服务 | 调用点 | URL | 模型 | 必需 |
|------|--------|-----|------|------|
| LLM 实体提取 | `_llm_extract_entities()` | MiMo/DeepSeek (via `call_ai`) | `mimo-v2.5` (默认) | 否（仅实体<2时触发） |
| SQLite | `_get_chunks_by_entity()`, `get_events_by_entity()` | 本地 `chunks.db` | — | 是 |
| hybrid_search | `_fallback_vector_search()` | 本地 | — | 否（降级时用） |

---

### L2.6: 知识图谱查询

**调用位置**：`retrieval.py:81-90` — ✅ 实际调用（但结果**未加入融合**）

```python
try:
    from src.services.graph_traversal import find_paths
    graph_paths = find_paths(query)
    if graph_paths:
        from src.taiyang.graph import GraphRouter
        router = GraphRouter()
        entity_context = router.get_entity_context(query)
        # 仅记录日志，结果未保存到任何变量中！
except Exception:
    logger.debug(...)
```

**关键发现**：
- 图谱查询被执行了，但结果**仅用于日志输出**
- 返回的 `graph_paths` 和 `entity_context` 没有传递给 `_fuse()` 或合并到最终结果
- 这意味着 L2.6 的图谱查询在 v1.50 中是**"查了但没用"**的状态

---

### L3: RRF 融合 — `_fuse()`

**调用位置**：`retrieval.py:93` — ✅ 实际调用

```python
fused = self._fuse(bm25_results, vector_results)
```

**实现**：`src/taiyang/fusion.py::rrf_fusion()`

**算法**：Reciprocal Rank Fusion (RRF)
```python
RRF_score = Σ 1.0 / (k + rank_i + 1)   # k=60
```

**关键发现 — 未调用的功能**：

`src/taiyang/fusion.py` 中还定义了以下函数，但在 `v1.50` 的 `src/taiyang/retrieval.py` 中**均未被调用**：

| 函数 | 状态 | 说明 |
|------|------|------|
| `weighted_fusion_adjust()` | ❌ 未调用 (v1.50) | 动态 alpha 加权调整，仅旧版 `src/services/retrieval.py:249` 调用 |
| `exact_match_boost()` | ❌ 未调用 (v1.50) | 型号精确匹配加权 |
| `dynamic_category_weight()` | ❌ 未调用 (v1.50) | 动态分类权重 |
| `personalized_boost()` | ❌ 未调用 (v1.50) | 个性化术语加权 |

**结论**：v1.50 的 `_fuse()` 只做了**纯 RRF 融合**。加权融合、精确匹配增强、动态分类权重、个性化加权这四个高级功能仅在旧版 `src/services/retrieval.py` 中（仍被 `agents_old/` 和 `hypothalamus/` 等遗留模块引用），新版 `taiyang/retrieval.py` 已经不用了。

---

### L4: 精排 — `_rerank()`

**调用位置**：`retrieval.py:96-98` — ✅ 实际调用

```python
reranked = await self._rerank(query, fused)
```

**实现**：
```python
# retrieval.py:100-107
async def _rerank(self, query, results):
    from src.taiyang.rerank import rerank_with_deepseek
    reranked = await rerank_with_deepseek(query, results, top_k=len(results))
    if reranked:
        return reranked
    return results  # 降级：返回原文
```

**⚠️ 关键发现**：`TaiyangRetrieval._rerank()` 只调用了 `rerank_with_deepseek`，而**没有调用统一的 `rerank()` 入口函数**！这意味着实际上只走了 DeepSeek 一条路。

#### 被跳过的统一入口 `rerank()`（rerank.py:176-195）

```python
async def rerank(query, candidates, top_k=30):
    # L1: SiliconFlow 专用 Rerank（首选，快+准+便宜）
    results = await rerank_with_siliconflow(query, candidates, top_k)
    if results: return results
    # L2: DeepSeek LLM 打分（云端兜底）
    results = await rerank_with_deepseek(query, candidates, top_k)
    if results: return results
    # L3: 本地 embedder_server Bi-Encoder（内网能用）
    results = await rerank_with_embedder(query, candidates, top_k)
    if results: return results
    # L4: 本地 TF-IDF 终极兜底（零依赖）
    return rerank_local(query, candidates, top_k)
```

---

### Rerank 四级降级链完整分析

尽管 `_rerank()` 只调用了 `rerank_with_deepseek`，完整的四级降级链其实存在于 `rerank.py` 的 `rerank()` 函数中（供外部直接调用时使用）：

#### 实际调用的路径（`retrieval.py::_rerank()`）：

```
rerank_with_deepseek()
  ├─ URL:  DEEPSEEK_BASE_URL/v1/chat/completions
  │        (默认: https://api.deepseek.com/v1/chat/completions)
  ├─ Model: "deepseek-chat"
  ├─ 方法:  LLM 批量打分（30 个文档一组，JSON 输出 0-10 分）
  ├─ 超时:  30 秒
  └─ 降级:  返回 []，管线使用原始 fused 结果
```

#### 完整降级链（`rerank()` 函数，未被 `_rerank()` 使用）：

| 级别 | 函数 | URL | 模型 | 必需 | 实际被 _rerank() 调用? |
|------|------|-----|------|------|----------------------|
| L1 | `rerank_with_siliconflow` | `SILICONFLOW_BASE_URL/rerank` (https://api.siliconflow.cn/v1/rerank) | `BAAI/bge-reranker-v2-m3` | 否 | ❌ |
| L2 | `rerank_with_deepseek` | `DEEPSEEK_BASE_URL/v1/chat/completions` (https://api.deepseek.com) | `deepseek-chat` | 否 | ✅ |
| L3 | `rerank_with_embedder` | `EMBEDDER_URL/rerank` (http://localhost:8081/rerank) | 本地 embedder | 否 | ❌ |
| L4 | `rerank_local` | 无（纯本地计算） | jieba + TF-IDF | 否 | ❌ |

**修正后的实际降级链（`_rerank()` 实际走的）**：
```
DeepSeek rerank 成功 → 返回精排结果
DeepSeek rerank 失败 → 返回原始 fused 结果（无排序变化）
```

---

### L5: 上下文扩展 — `_expand_context()`

**调用位置**：`retrieval.py:101` — ✅ 实际调用

```python
expanded = self._expand_context(reranked)
```

**实现**：`src/taiyang/results_postprocess.py::expand_context()`

**功能**：
- 对文本长度 < 500 的结果，从 SQLite 获取前一个和后一个相邻 chunk
- 拼接成：`[prev_chunk 后 200 字] + [当前文本] + [next_chunk 前 200 字]`
- 已满 500 字的直接跳过

**外部依赖**：SQLite `chunks.db`（本地，非必需，失败时返回原结果）

---

### L6: 合并多跳结果 — `merge_search_results()`

**调用位置**：`retrieval.py:104-106` — ✅ 仅在 multi_hop_results 非空时调用

```python
if multi_hop_results:
    from src.taiyang.results_postprocess import merge_search_results
    expanded = merge_search_results(expanded, [], multi_hop_results)
```

由于 L2.5 多跳检索默认不启用（feature flag），**L6 在默认配置下不会执行**。

---

## 3. CRAG 纠错链路 — 哪里真的用了？

### Taiyang 层的 CRAG (`src/taiyang/crag.py`)

**核心函数**：
| 函数 | 调用者 | 状态 |
|------|--------|------|
| `retrieve_with_correction()` | **无调用者** | ❌ 未被使用 |
| `rewrite_and_retry()` | **无调用者** | ❌ 未被使用 |
| `evaluate_retrieval()` | 仅被 `retrieve_with_correction` 内部调用 | ❌ 间接未使用 |

**结论**：`src/taiyang/crag.py` 的 CRAG 主循环（检索→校验→改写→重试）**在检索管线中完全未被调用**。

### L5 CRAG (`src/taiyang/l5_crag.py`)

- `L5CRAGExecutor` 类实现带查询改写的 CRAG 纠正
- 仅被 `src/taiyang/degradation_chain.py` 的 `_execute_l5()` 调用
- 但 `DegradationChain` 本身也**未被检索管线调用**（仅被 `services/__init__.py` 导出）
- **结论**：❌ 未被实际使用

### 少阴层的 CRAG (`src/shaoyin/crag_corrector.py`)

**调用位置**：`brain.py:95-105` — ✅ 被实际调用（条件触发）

```python
# brain.py:95-105
if not reflection_pass:
    crag = self._get_crag()
    if crag:
        new_results = await crag.correct_and_retry(query, results)
```

**触发条件**：Self-RAG 反思返回 `action != "pass"`
- 结果为空 → `action="crag_rewrite"`
- 关键词重叠低 → `action="crag_rewrite"`
- LLM 反思失败 → `action="crag_rewrite"`

**CRAGCorrector.correct_and_retry() 流程**：
1. `evaluator.evaluate(query, results)` → 返回 GOOD / NEED_REWRITE / OFF_TOPIC
2. GOOD → 直接返回原结果
3. OFF_TOPIC → 返回空列表 `[]`
4. NEED_REWRITE → `_rewrite_query()` 简单去掉停用词 → 调用 `hybrid_search()` 重新检索

**降级路径**：如果重写后的 `hybrid_search()` 也返回空，返回 `[]`

---

## 4. 多跳检索 — 是否真的被检索链路调用？

| 调用点 | 位置 | 是否实际调用 |
|--------|------|-------------|
| `retrieval.py:76` | `refine()` 中 L2.5 | ✅ 但受 `taiyang_multi_hop` flag 控制 |
| `degradation_chain.py:152` | `_execute_l3()` 中 | ❌ chain 本身未被使用 |

**结论**：多跳检索**仅在 feature flag 启用时**才会被检索管线调用。默认不启用。

---

## 5. RRF 融合和加权融合 — 实际调用关系

```
retrieval.py::_fuse()
  │
  ├─ rrf_fusion(bm25_results, vector_results)          ← ✅ 实际调用
  │    算法：Reciprocal Rank Fusion, k=60
  │
  ├─ weighted_fusion_adjust()                           ← ❌ 未调用 (v1.50 检索)
  │    仅被旧版 src/services/retrieval.py 调用
  │
  ├─ exact_match_boost()                                ← ❌ 未调用
  ├─ dynamic_category_weight()                          ← ❌ 未调用
  └─ personalized_boost()                               ← ❌ 未调用
```

**结论**：v1.50 的 `taiyang/retrieval.py` 只做纯 RRF 融合。加权融合等高级功能已从新版管线中移除，但旧版管线（`src/services/retrieval.py`）仍在 `agents_old/` 和 `hypothalamus/` 中使用。

---

## 6. 缓存层 — 在哪个阶段介入？

**结论**：❌ **缓存层未接入检索管线**

`src/taiyang/cache.py` 实现了两层缓存：
- **L1 精确缓存**：query 字符串哈希 → 结果，LRU 200 条，1 小时过期
- **L2 语义缓存**：query embedding 余弦相似度 ≥ 0.92 → 复用结果

但 `refine()` 方法（`retrieval.py:43-123`）从头到尾没有调用 `get_cache()` 或 `set_cache()`。

检索管线末尾仅调用了 `src/infra/cache_stats::get_cache_stats().record_miss(duration)`（第 119 行），这只是一个统计记录器，不是缓存逻辑。

---

## 7. 降级链路总结

### 7.1 `DegradationChain`（五层降级链）

文件：`src/taiyang/degradation_chain.py`

| 层级 | 名称 | 内容 | 使用状态 |
|------|------|------|---------|
| L1 | FAST | Simple RAG (hybrid_search) | ❌ 未被检索管线调用 |
| L2 | STANDARD | Self-RAG 反思 | ❌ 未被检索管线调用 |
| L3 | DEEP | GraphRAG + 多跳 | ❌ 未被检索管线调用 |
| L4 | AGENT | 调用少阴 Brain | ❌ 未被检索管线调用 |
| L5 | CRAG | 纠正检索 | ❌ 未被检索管线调用 |

**结论**：`DegradationChain` 的 5 级降级链是一个**设计蓝图但未集成**的模块。实际检索管线**不使用**这个降级链，而是直接在 `retrieval.py` 内部做简化的 try/except 降级。

---

### 7.2 实际降级路径（检索管线内）

```
查询进入
  ├─ BM25 失败 → 返回 []（不阻止管线，仅无 BM25 结果）
  ├─ 向量检索失败 → 返回 []（不阻止管线，仅无向量结果）
  ├─ 融合同义词失败 → 返回原 query
  ├─ RRF 融合失败 → 返回 bm25_results + vector_results（简单拼接）
  ├─ DeepSeek Rerank 失败 → 返回原始 fused 结果
  ├─ 上下文扩展失败 → 返回原结果
  └─ 所有数据为空 → 返回 []（不抛异常）
```

---

## 8. 完整外部服务调用汇总

| 阶段 | 服务 | URL | 模型 | 是否必需 | 降级 |
|------|------|-----|------|---------|------|
| L0 | 语义缓存 | 本地计算 | — | ❌ 未接入 | — |
| L1 | 同义词加载 | 本地 YAML | — | 否 | 返回原 query |
| L2 | BM25 检索 | 本地 SQLite `chunks.db` | — | 是 | 返回 [] |
| L2 | 向量嵌入 | `http://localhost:8081` | 本地 embedder | 是 | 返回 [] |
| L2 | 向量检索 | 本地 ChromaDB | — | 是 | 返回 [] |
| L2.5 | 多跳 LLM 提取 | MiMo API | `mimo-v2.5` | 否 | 跳过 LLM |
| L2.5 | 多跳 SQL 事件查询 | 本地 SQLite | — | 否 | — |
| L2.6 | 知识图谱 | 本地 SQLite `worldtree.db` | — | 否 | 跳过 |
| L3 | RRF 融合 | 本地计算 | — | 是 | 简单拼接 |
| L4 | DeepSeek Rerank | `https://api.deepseek.com/v1/chat/completions` | `deepseek-chat` | 否 | 返回 fused |
| L4 (备选) | SiliconFlow Rerank | `https://api.siliconflow.cn/v1/rerank` | `BAAI/bge-reranker-v2-m3` | 否 | ❌ 未使用 |
| L4 (备选) | Embedder Rerank | `http://localhost:8081/rerank` | 本地 embedder | 否 | ❌ 未使用 |
| L4 (备选) | 本地 TF-IDF | 本地 jieba | — | 否 | ❌ 未使用 |
| L5 | 上下文扩展 | 本地 SQLite | — | 否 | 返回原结果 |
| L6 | 多跳合并 | 本地计算 | — | 否 | 仅在 flag 启用时 |
| Brain | LLM 合成/反思 | `https://token-plan-cn.xiaomimimo.com/v1/chat/completions` | `mimo-v2.5-pro` → `deepseek-v4-pro` | 是 | 模板拼接 |
| Brain | CRAG 重试查询 | 同上 | 同上 | 否 | 返回空 |

---

## 9. 关键发现与建议

### 🔴 发现：架空/死代码
1. **语义缓存**（`cache.py`）—— 完整实现但未接入管线
2. **CRAG 主循环**（`taiyang/crag.py::retrieve_with_correction`）—— 无人调用
3. **L5 CRAG 执行器**（`l5_crag.py`）—— 仅被未使用的 `DegradationChain` 调用
4. **Rerank 统一入口 `rerank()`**（4 级降级）—— 被 `services/__init__.py` 导出但 `_rerank()` 不调用
5. **加权融合四件套** — `weighted_fusion_adjust/exact_match_boost/dynamic_category_weight/personalized_boost` — v1.50 未使用
6. **`DegradationChain`** 五级降级链 — 完整设计但未集成

### 🟡 发现：输出浪费
7. **图谱查询结果** 被执行但丢弃，仅用于打印日志
8. **`rerank()` 函数的 L1 SiliconFlow** 是更快更便宜的方案但被跳过

### 🟢 建议
1. **接入缓存**：在 `refine()` 开头加 `get_cache()`，结尾加 `set_cache()`
2. **整合 Rerank**：让 `_rerank()` 调用 `rerank()` 统一入口而不是直接 `rerank_with_deepseek`
3. **移除或整合** `DegradationChain`：要么接入管线，要么标记为废弃
4. **恢复加权融合**：在 L3 后添加 `exact_match_boost()` 可改善精确型号查询
5. **用上图谱结果**：将图谱实体信息融入 `_fuse()` 或作为额外结果添加
